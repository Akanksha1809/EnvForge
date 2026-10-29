"""Exercises the RBAC matrix through the real API (not just the service
function directly — see tests/unit/test_rbac_matrix.py for that), so a
router that forgets to call rbac.require_permission would actually be
caught here.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_team_member_can_register_application_for_their_team(client: AsyncClient) -> None:
    admin_headers = await register_and_login(client, "owner2@envforge.dev")
    member_headers = await register_and_login(client, "member2@envforge.dev")

    team_resp = await client.post(
        "/api/v1/teams", json={"name": "Member Team", "slug": "member-team"}, headers=admin_headers
    )
    team_id = team_resp.json()["id"]

    tokens_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "member2@envforge.dev", "password": "supersecret123"},
    )
    member_user_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens_resp.json()['access_token']}"},
    )
    member_user_id = member_user_resp.json()["id"]

    add_member_resp = await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": member_user_id, "role": "member"},
        headers=admin_headers,
    )
    assert add_member_resp.status_code == 201

    # The second registered user is a `developer` globally (has
    # APPLICATION_REGISTER) *and* now a team member — both conditions the
    # endpoint requires — so this should succeed.
    app_resp = await client.post(
        "/api/v1/applications",
        json={"name": "Member App", "slug": "member-app", "team_id": team_id},
        headers=member_headers,
    )
    assert app_resp.status_code == 201, app_resp.text


@pytest.mark.asyncio
async def test_non_team_member_with_global_permission_is_still_blocked(
    client: AsyncClient,
) -> None:
    admin_headers = await register_and_login(client, "owner3@envforge.dev")
    outsider_headers = await register_and_login(client, "outsider3@envforge.dev")

    team_resp = await client.post(
        "/api/v1/teams", json={"name": "Closed Team", "slug": "closed-team"}, headers=admin_headers
    )
    team_id = team_resp.json()["id"]

    # outsider3 is a `developer` globally — APPLICATION_REGISTER passes —
    # but was never added to this team, so the team-membership check
    # must still reject it.
    resp = await client.post(
        "/api/v1/applications",
        json={"name": "Blocked App", "slug": "blocked-app-2", "team_id": team_id},
        headers=outsider_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_regular_team_member_cannot_delete_application(client: AsyncClient) -> None:
    admin_headers = await register_and_login(client, "owner4@envforge.dev")
    member_headers = await register_and_login(client, "member4@envforge.dev")

    team_resp = await client.post(
        "/api/v1/teams", json={"name": "Delete Team", "slug": "delete-team"}, headers=admin_headers
    )
    team_id = team_resp.json()["id"]

    member_user_id = (await client.get("/api/v1/auth/me", headers=member_headers)).json()["id"]
    await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"user_id": member_user_id, "role": "member"},
        headers=admin_headers,
    )

    app_resp = await client.post(
        "/api/v1/applications",
        json={"name": "Delete App", "slug": "delete-app", "team_id": team_id},
        headers=admin_headers,
    )
    application_id = app_resp.json()["id"]

    # A plain `member` (not team `admin`) can register applications but
    # not delete them — require_team_admin in the delete endpoint must
    # reject this even though require_team_membership alone would pass.
    resp = await client.delete(f"/api/v1/applications/{application_id}", headers=member_headers)
    assert resp.status_code == 403

    # The team admin (the creator) can.
    resp = await client.delete(f"/api/v1/applications/{application_id}", headers=admin_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_only_platform_admin_can_manage_templates(client: AsyncClient) -> None:
    # First registered user only in this test's isolated DB -> platform_admin.
    admin_headers = await register_and_login(client, "template-admin@envforge.dev")
    developer_headers = await register_and_login(client, "template-dev@envforge.dev")

    # developer (no team_admin anywhere) lacks TEMPLATE_MANAGE globally.
    resp = await client.post(
        "/api/v1/templates",
        json={"slug": "dev-blocked", "name": "Blocked", "template_type": "custom"},
        headers=developer_headers,
    )
    assert resp.status_code == 403

    resp = await client.post(
        "/api/v1/templates",
        json={"slug": "admin-allowed", "name": "Allowed", "template_type": "custom"},
        headers=admin_headers,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_only_platform_admin_can_read_audit_logs(client: AsyncClient) -> None:
    admin_headers = await register_and_login(client, "audit-admin@envforge.dev")
    developer_headers = await register_and_login(client, "audit-dev@envforge.dev")

    resp = await client.get("/api/v1/audit-logs", headers=developer_headers)
    assert resp.status_code == 403

    resp = await client.get("/api/v1/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
