"""The full platform journey in one test: register, build out a team's
application with a versioned template, create an environment, actually
drive it through the provisioning pipeline to READY (with only the
Terraform/kubectl calls mocked — everything else is the real pipeline),
then exercise cost, recommendations, extension, cloning, teardown, and
the audit trail against the result.

Every other test file in this project is scoped to one subsystem
(templates, webhooks, RBAC, cost...); this one is the only place that
walks the same environment through all of them in the order a real user
or CI pipeline would, so a regression that only shows up when subsystems
are combined (e.g. a READY environment's cost/clone/audit behavior) has
somewhere to surface.
"""

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import provisioning
from app.workers.tasks import provisioning as provisioning_tasks
from tests.conftest import register_and_login


def _fake_task_db_session_factory(db_session: AsyncSession):
    """Tests never run a real Celery worker, so a created Job sits at
    PENDING/QUEUED forever unless something actually executes the task
    body. This reuses the same technique as
    tests/unit/test_provisioning_task_failures.py: patch task_db_session
    to reuse the test's own session, and mock only the Terraform/kubectl
    calls — the state machine, job bookkeeping, and HTTP layer above it
    are all real.
    """

    @asynccontextmanager
    async def _factory():
        yield db_session

    return _factory


@pytest.mark.asyncio
async def test_full_platform_flow_register_to_teardown(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # 1. Register — first user in a fresh DB becomes platform_admin, so
    # every permission-gated step below exercises the real RBAC path.
    headers = await register_and_login(client, "e2e-admin@envforge.dev")

    # 2. Create a team.
    team_resp = await client.post(
        "/api/v1/teams",
        json={"name": "E2E Team", "slug": "e2e-team", "max_active_environments": 5},
        headers=headers,
    )
    assert team_resp.status_code == 201, team_resp.text
    team_id = team_resp.json()["id"]

    # 3. Create a versioned environment template.
    template_resp = await client.post(
        "/api/v1/templates",
        json={
            "slug": "e2e-backend",
            "name": "E2E Backend",
            "template_type": "basic_backend",
            "required_services": ["postgres"],
        },
        headers=headers,
    )
    assert template_resp.status_code == 201, template_resp.text
    template = template_resp.json()

    # 4. Register an application pinned to that template.
    app_resp = await client.post(
        "/api/v1/applications",
        json={
            "name": "E2E App",
            "slug": "e2e-app",
            "team_id": team_id,
            "environment_template_id": template["id"],
            "environment_template_version": template["version"],
        },
        headers=headers,
    )
    assert app_resp.status_code == 201, app_resp.text
    application = app_resp.json()

    # 5. Create an environment for it.
    env_resp = await client.post(
        "/api/v1/environments",
        json={"application_id": application["id"]},
        headers=headers,
    )
    assert env_resp.status_code == 202, env_resp.text
    environment = env_resp.json()
    assert environment["state"] == "queued"

    jobs_resp = await client.get(
        "/api/v1/jobs", params={"environment_id": environment["id"]}, headers=headers
    )
    job_id = jobs_resp.json()["items"][0]["id"]

    # 6. Actually drive the provisioning pipeline to READY — the part no
    # other integration test does, since none of them run a worker.
    with (
        patch.object(
            provisioning_tasks, "task_db_session", _fake_task_db_session_factory(db_session)
        ),
        patch.object(
            provisioning,
            "apply_environment",
            return_value={
                "namespace_name": "envforge-e2e-app-abc123",
                "preview_url": "http://e2e-app.127.0.0.1.nip.io:18080",
            },
        ),
        patch.object(provisioning, "wait_for_health", return_value=True),
    ):
        await provisioning_tasks._provision_environment(job_id)

    env_resp = await client.get(f"/api/v1/environments/{environment['id']}", headers=headers)
    environment = env_resp.json()
    assert environment["state"] == "ready"
    assert environment["preview_url"] == "http://e2e-app.127.0.0.1.nip.io:18080"

    # 7. Cost estimate for the now-live environment.
    cost_resp = await client.get(f"/api/v1/environments/{environment['id']}/cost", headers=headers)
    assert cost_resp.status_code == 200
    assert cost_resp.json()["is_still_active"] is True

    # 8. Dashboard summary reflects the one active environment.
    summary_resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert summary_resp.json()["active_environments"] >= 1

    # 9. Cost summary aggregates it by team and application.
    cost_summary_resp = await client.get("/api/v1/dashboard/cost-summary", headers=headers)
    assert any(b["slug"] == "e2e-team" for b in cost_summary_resp.json()["by_team"])

    # 10. Recommendations run without error against the now-populated
    # platform state (content isn't asserted — it's query-driven and
    # covered in depth by tests/unit/test_recommendations.py).
    recs_resp = await client.get("/api/v1/dashboard/recommendations", headers=headers)
    assert recs_resp.status_code == 200
    assert isinstance(recs_resp.json(), list)

    # 11. Extend, then clone — the clone starts its own, separate
    # provisioning job rather than inheriting the original's state.
    extend_resp = await client.post(
        f"/api/v1/environments/{environment['id']}/extend",
        json={"additional_hours": 6},
        headers=headers,
    )
    assert extend_resp.status_code == 200

    clone_resp = await client.post(
        f"/api/v1/environments/{environment['id']}/clone", headers=headers
    )
    assert clone_resp.status_code == 202, clone_resp.text
    clone = clone_resp.json()
    assert clone["id"] != environment["id"]
    assert clone["pr_number"] is None

    # 12. Tear down the original environment and confirm the full action
    # history — every step above that goes through the audited API
    # layer — shows up in the audit log.
    delete_resp = await client.delete(f"/api/v1/environments/{environment['id']}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["state"] in ("deleted", "deleting")

    audit_resp = await client.get(
        "/api/v1/audit-logs", params={"resource_id": environment["id"]}, headers=headers
    )
    assert audit_resp.status_code == 200
    actions = {entry["action"] for entry in audit_resp.json()["items"]}
    assert {"environment.create", "environment.extend", "environment.delete"} <= actions
