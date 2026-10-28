import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_login_me_flow(client: AsyncClient) -> None:
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "portal@example.com",
            "full_name": "Portal User",
            "password": "supersecret123",
        },
    )
    assert register_resp.status_code == 201
    body = register_resp.json()
    assert body["email"] == "portal@example.com"
    assert body["platform_role"] == "platform_admin"  # first user bootstraps as admin

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "portal@example.com", "password": "supersecret123"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    me_resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "portal@example.com"


@pytest.mark.asyncio
async def test_me_without_token_is_unauthorized(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password_is_unauthorized(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "p2@example.com", "full_name": "P2", "password": "supersecret123"},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "p2@example.com", "password": "wrong-password"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_flow(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "p3@example.com", "full_name": "P3", "password": "supersecret123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "p3@example.com", "password": "supersecret123"}
    )
    refresh_token = login_resp.json()["refresh_token"]
    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
