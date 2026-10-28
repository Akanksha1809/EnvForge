import hashlib
import hmac
import json
import uuid

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.conftest import register_and_login


def _sign(body: bytes) -> str:
    secret = get_settings().github_webhook_secret
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _send_webhook(
    client: AsyncClient, *, event_type: str, payload: dict, delivery_id: str | None = None
) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": event_type,
        "X-GitHub-Delivery": delivery_id or str(uuid.uuid4()),
        "X-Hub-Signature-256": _sign(body),
        "Content-Type": "application/json",
    }
    resp = await client.post("/api/v1/webhooks/github", content=body, headers=headers)
    return resp.status_code, resp.json()


def _pr_payload(
    action: str, *, repo: str, pr_number: int, sha: str, branch: str = "feature/x"
) -> dict:
    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "number": pr_number,
            "head": {"ref": branch, "sha": sha},
            "html_url": f"https://github.com/{repo}/pull/{pr_number}",
        },
        "repository": {"full_name": repo},
    }


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected(client: AsyncClient) -> None:
    body = b'{"action": "opened"}'
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": str(uuid.uuid4()),
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ping_event_is_acknowledged(client: AsyncClient) -> None:
    status_code, body = await _send_webhook(
        client, event_type="ping", payload={"zen": "Keep it logically awesome."}
    )
    assert status_code == 200
    assert body["status"] == "pong"


@pytest.mark.asyncio
async def test_webhook_for_unregistered_repo_is_ignored(client: AsyncClient) -> None:
    status_code, body = await _send_webhook(
        client,
        event_type="pull_request",
        payload=_pr_payload("opened", repo="nobody/unregistered", pr_number=1, sha="abc123"),
    )
    assert status_code == 200
    assert body["status"] == "ignored"


@pytest.mark.asyncio
async def test_full_pr_open_sync_close_lifecycle(client: AsyncClient) -> None:
    headers = await register_and_login(client, "webhook-admin@envforge.dev")

    team_resp = await client.post(
        "/api/v1/teams", json={"name": "Webhook Team", "slug": "webhook-team"}, headers=headers
    )
    team_id = team_resp.json()["id"]

    app_resp = await client.post(
        "/api/v1/applications",
        json={
            "name": "Webhook App",
            "slug": "webhook-app",
            "team_id": team_id,
            "github_repo": "acme/webhook-app",
        },
        headers=headers,
    )
    application_id = app_resp.json()["id"]

    # opened -> creates exactly one environment for this PR.
    status_code, body = await _send_webhook(
        client,
        event_type="pull_request",
        payload=_pr_payload("opened", repo="acme/webhook-app", pr_number=7, sha="sha-one"),
    )
    assert status_code == 200
    assert body["status"] == "environment_created"
    environment_id = body["environment_id"]

    envs_resp = await client.get(
        "/api/v1/environments",
        params={"application_id": application_id, "pr_number": 7},
        headers=headers,
    )
    assert envs_resp.json()["total"] == 1

    # A redelivered "opened" (same semantics as a retry) must not create a
    # second environment for the same PR.
    status_code, body = await _send_webhook(
        client,
        event_type="pull_request",
        payload=_pr_payload("opened", repo="acme/webhook-app", pr_number=7, sha="sha-one"),
    )
    assert body["status"] == "redeployed_existing"
    assert body["environment_id"] == environment_id

    envs_resp = await client.get(
        "/api/v1/environments",
        params={"application_id": application_id, "pr_number": 7},
        headers=headers,
    )
    assert envs_resp.json()["total"] == 1

    # synchronize -> updates the same environment's tracked commit SHA.
    status_code, body = await _send_webhook(
        client,
        event_type="pull_request",
        payload=_pr_payload("synchronize", repo="acme/webhook-app", pr_number=7, sha="sha-two"),
    )
    assert body["status"] == "redeployed_existing"
    assert body["environment_id"] == environment_id

    env_resp = await client.get(f"/api/v1/environments/{environment_id}", headers=headers)
    assert env_resp.json()["pr_commit_sha"] == "sha-two"

    # The exact same delivery redelivered must be a safe no-op.
    delivery_id = str(uuid.uuid4())
    first = await _send_webhook(
        client,
        event_type="pull_request",
        payload=_pr_payload("synchronize", repo="acme/webhook-app", pr_number=7, sha="sha-three"),
        delivery_id=delivery_id,
    )
    second = await _send_webhook(
        client,
        event_type="pull_request",
        payload=_pr_payload("synchronize", repo="acme/webhook-app", pr_number=7, sha="sha-three"),
        delivery_id=delivery_id,
    )
    assert first[1]["status"] == "redeployed_existing"
    assert second[1]["status"] == "duplicate_delivery_ignored"

    # closed -> the environment is torn down (never provisioned here, so
    # deletion completes synchronously straight to "deleted").
    status_code, body = await _send_webhook(
        client,
        event_type="pull_request",
        payload=_pr_payload("closed", repo="acme/webhook-app", pr_number=7, sha="sha-three"),
    )
    assert body["status"] == "environment_deletion_requested"

    env_resp = await client.get(f"/api/v1/environments/{environment_id}", headers=headers)
    assert env_resp.json()["state"] == "deleted"

    # Closing again with no active environment left is a clean no-op.
    status_code, body = await _send_webhook(
        client,
        event_type="pull_request",
        payload=_pr_payload("closed", repo="acme/webhook-app", pr_number=7, sha="sha-three"),
    )
    assert body["status"] == "no_environment_to_delete"
