import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


async def _setup_app(client: AsyncClient, headers: dict) -> tuple[str, str]:
    team_resp = await client.post(
        "/api/v1/teams", json={"name": "Cost Team", "slug": "cost-team"}, headers=headers
    )
    team_id = team_resp.json()["id"]
    app_resp = await client.post(
        "/api/v1/applications",
        json={"name": "Cost App", "slug": "cost-app", "team_id": team_id},
        headers=headers,
    )
    return team_id, app_resp.json()["id"]


@pytest.mark.asyncio
async def test_environment_cost_endpoint_returns_simulated_basis(client: AsyncClient) -> None:
    headers = await register_and_login(client, "cost-user@envforge.dev")
    _, application_id = await _setup_app(client, headers)

    env_resp = await client.post(
        "/api/v1/environments", json={"application_id": application_id}, headers=headers
    )
    environment_id = env_resp.json()["id"]

    cost_resp = await client.get(f"/api/v1/environments/{environment_id}/cost", headers=headers)
    assert cost_resp.status_code == 200
    body = cost_resp.json()
    assert body["basis"] == "simulated"
    assert body["is_still_active"] is True
    assert body["estimated_cost_usd"] >= 0


@pytest.mark.asyncio
async def test_cost_summary_endpoint_aggregates_real_environments(client: AsyncClient) -> None:
    headers = await register_and_login(client, "cost-summary-user@envforge.dev")
    _, application_id = await _setup_app(client, headers)

    await client.post(
        "/api/v1/environments", json={"application_id": application_id}, headers=headers
    )

    resp = await client.get("/api/v1/dashboard/cost-summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["basis"] in ("estimated", "simulated")
    assert any(bucket["slug"] == "cost-team" for bucket in body["by_team"])
    assert any(bucket["slug"] == "cost-app" for bucket in body["by_application"])


@pytest.mark.asyncio
async def test_clone_environment_creates_new_non_pr_environment(client: AsyncClient) -> None:
    headers = await register_and_login(client, "clone-user@envforge.dev")
    _, application_id = await _setup_app(client, headers)

    original_resp = await client.post(
        "/api/v1/environments",
        json={"application_id": application_id, "pr_number": 99, "pr_branch": "feature/x"},
        headers=headers,
    )
    original_id = original_resp.json()["id"]

    clone_resp = await client.post(f"/api/v1/environments/{original_id}/clone", headers=headers)
    assert clone_resp.status_code == 202, clone_resp.text
    clone = clone_resp.json()

    assert clone["id"] != original_id
    assert clone["application_id"] == application_id
    assert clone["pr_number"] is None  # a clone is always manual, never PR-linked
    assert "clone" in clone["name"]

    # Original PR-linked environment is untouched.
    original_after = (
        await client.get(f"/api/v1/environments/{original_id}", headers=headers)
    ).json()
    assert original_after["pr_number"] == 99


@pytest.mark.asyncio
async def test_clone_respects_team_quota(client: AsyncClient) -> None:
    headers = await register_and_login(client, "clone-quota-user@envforge.dev")
    team_resp = await client.post(
        "/api/v1/teams",
        json={"name": "Clone Quota Team", "slug": "clone-quota-team", "max_active_environments": 1},
        headers=headers,
    )
    team_id = team_resp.json()["id"]
    app_resp = await client.post(
        "/api/v1/applications",
        json={"name": "Quota App", "slug": "quota-app-clone", "team_id": team_id},
        headers=headers,
    )
    application_id = app_resp.json()["id"]

    original_resp = await client.post(
        "/api/v1/environments", json={"application_id": application_id}, headers=headers
    )
    original_id = original_resp.json()["id"]

    # Team is already at quota (1/1 active) — cloning would exceed it.
    clone_resp = await client.post(f"/api/v1/environments/{original_id}/clone", headers=headers)
    assert clone_resp.status_code == 429
