import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_team_application_environment_full_flow(client: AsyncClient) -> None:
    # First registered user is platform_admin, so every permission check below
    # (team create, app register, template manage, env create/extend/delete)
    # exercises the real RBAC path rather than being skipped.
    headers = await register_and_login(client, "admin@envforge.dev")

    team_resp = await client.post(
        "/api/v1/teams",
        json={"name": "Platform Team", "slug": "platform-team", "max_active_environments": 5},
        headers=headers,
    )
    assert team_resp.status_code == 201, team_resp.text
    team_id = team_resp.json()["id"]

    template_resp = await client.post(
        "/api/v1/templates",
        json={
            "slug": "basic-backend",
            "name": "Basic Backend",
            "template_type": "basic_backend",
            "required_services": ["postgres", "redis"],
            "resource_limits": {"cpu": "500m", "memory": "512Mi"},
        },
        headers=headers,
    )
    assert template_resp.status_code == 201, template_resp.text
    template = template_resp.json()
    assert template["version"] == 1
    assert template["is_latest"] is True

    v2_resp = await client.post(
        "/api/v1/templates/basic-backend/versions",
        json={
            "slug": "basic-backend",
            "name": "Basic Backend",
            "template_type": "basic_backend",
            "required_services": ["postgres", "redis", "rabbitmq"],
        },
        headers=headers,
    )
    assert v2_resp.status_code == 201, v2_resp.text
    assert v2_resp.json()["version"] == 2

    versions_resp = await client.get("/api/v1/templates/basic-backend/versions", headers=headers)
    assert [v["version"] for v in versions_resp.json()] == [2, 1]

    app_resp = await client.post(
        "/api/v1/applications",
        json={
            "name": "Payments API",
            "slug": "payments-api",
            "team_id": team_id,
            "github_repo": "acme/payments-api",
            "environment_template_id": template["id"],
            "environment_template_version": 1,
            "environment_ttl_hours": 24,
        },
        headers=headers,
    )
    assert app_resp.status_code == 201, app_resp.text
    application = app_resp.json()
    assert application["slug"] == "payments-api"

    env_resp = await client.post(
        "/api/v1/environments",
        json={"application_id": application["id"], "pr_number": 42, "pr_branch": "feature/x"},
        headers=headers,
    )
    assert env_resp.status_code == 202, env_resp.text
    environment = env_resp.json()
    assert environment["state"] == "queued"
    assert environment["name"] == "payments-api-pr-42"

    events_resp = await client.get(
        f"/api/v1/environments/{environment['id']}/events", headers=headers
    )
    assert events_resp.status_code == 200
    transitions = [(e["previous_state"], e["new_state"]) for e in events_resp.json()]
    assert transitions == [
        ("requested", "requested"),
        ("requested", "validating"),
        ("validating", "queued"),
    ]

    jobs_resp = await client.get(
        "/api/v1/jobs", params={"environment_id": environment["id"]}, headers=headers
    )
    assert jobs_resp.status_code == 200
    jobs = jobs_resp.json()["items"]
    assert len(jobs) == 1
    assert jobs[0]["job_type"] == "provision"
    assert jobs[0]["status"] == "pending"

    extend_resp = await client.post(
        f"/api/v1/environments/{environment['id']}/extend",
        json={"additional_hours": 12},
        headers=headers,
    )
    assert extend_resp.status_code == 200

    logs_resp = await client.get(f"/api/v1/environments/{environment['id']}/logs", headers=headers)
    assert logs_resp.status_code == 200
    assert len(logs_resp.json()) >= 3

    delete_resp = await client.delete(f"/api/v1/environments/{environment['id']}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["state"] == "deleted"


@pytest.mark.asyncio
async def test_environment_creation_blocked_by_team_quota(client: AsyncClient) -> None:
    headers = await register_and_login(client, "quota@envforge.dev")

    team_resp = await client.post(
        "/api/v1/teams",
        json={"name": "Tiny Team", "slug": "tiny-team", "max_active_environments": 1},
        headers=headers,
    )
    team_id = team_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        json={"name": "Tiny App", "slug": "tiny-app", "team_id": team_id},
        headers=headers,
    )
    application_id = app_resp.json()["id"]

    first = await client.post(
        "/api/v1/environments", json={"application_id": application_id}, headers=headers
    )
    assert first.status_code == 202

    second = await client.post(
        "/api/v1/environments", json={"application_id": application_id}, headers=headers
    )
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_viewer_cannot_create_application(client: AsyncClient) -> None:
    admin_headers = await register_and_login(client, "owner@envforge.dev")
    viewer_headers = await register_and_login(client, "viewer@envforge.dev")

    team_resp = await client.post(
        "/api/v1/teams",
        json={"name": "Viewer Team", "slug": "viewer-team"},
        headers=admin_headers,
    )
    team_id = team_resp.json()["id"]

    # Second registered user defaults to `developer`, not `viewer` — directly
    # downgrade via the DB-backed service isn't exposed over the API yet
    # (role management lands with team admin tooling), so this asserts the
    # weaker guarantee: a non-member of the team is rejected even though
    # they hold the `developer` platform role and the APPLICATION_REGISTER
    # permission globally.
    resp = await client.post(
        "/api/v1/applications",
        json={"name": "Blocked App", "slug": "blocked-app", "team_id": team_id},
        headers=viewer_headers,
    )
    assert resp.status_code == 403
