"""GitHub webhook signature verification and event processing.

The signature check and idempotency (dedupe by `X-GitHub-Delivery`) are
the real integration logic — GitHub's own retry behavior (it redelivers
on timeout or a 5xx response) means a webhook handler that isn't
idempotent will eventually create duplicate environments in production.
"""

import hashlib
import hmac
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import EventTrigger
from app.models.webhook_delivery import WebhookDelivery
from app.schemas.webhook import PullRequestEvent
from app.services import applications as applications_service
from app.services import environments as environments_service
from app.services import github_client

logger = get_logger("envforge.webhooks")

_SUPPORTED_PR_ACTIONS = {"opened", "reopened", "synchronize", "closed"}


class WebhookError(Exception):
    pass


def verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """Validates the `X-Hub-Signature-256` header GitHub sends: hex HMAC-
    SHA256 of the raw request body, keyed by the configured webhook
    secret. Uses `hmac.compare_digest` to avoid a timing side-channel."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    settings = get_settings()
    expected = hmac.new(
        settings.github_webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


async def already_processed(db: AsyncSession, delivery_id: str) -> bool:
    return await db.get(WebhookDelivery, delivery_id) is not None


async def _record_delivery(
    db: AsyncSession,
    *,
    delivery_id: str,
    event_type: str,
    action: str | None,
    repository_full_name: str | None,
    environment_id: str | None,
    result: dict[str, Any],
) -> None:
    db.add(
        WebhookDelivery(
            delivery_id=delivery_id,
            event_type=event_type,
            action=action,
            repository_full_name=repository_full_name,
            environment_id=environment_id,
            result=result,
        )
    )
    await db.commit()


async def process_webhook(
    db: AsyncSession, *, event_type: str, delivery_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Entry point the API router calls after signature verification and
    the duplicate-delivery check."""
    if event_type == "ping":
        result = {"status": "pong"}
        await _record_delivery(
            db,
            delivery_id=delivery_id,
            event_type=event_type,
            action=None,
            repository_full_name=(payload.get("repository") or {}).get("full_name"),
            environment_id=None,
            result=result,
        )
        return result

    if event_type != "pull_request":
        result = {"status": "ignored", "reason": f"unsupported event type '{event_type}'"}
        await _record_delivery(
            db,
            delivery_id=delivery_id,
            event_type=event_type,
            action=payload.get("action"),
            repository_full_name=(payload.get("repository") or {}).get("full_name"),
            environment_id=None,
            result=result,
        )
        return result

    return await process_pull_request_event(db, delivery_id=delivery_id, payload=payload)


async def process_pull_request_event(
    db: AsyncSession, *, delivery_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        event = PullRequestEvent.model_validate(payload)
    except ValidationError as exc:
        result: dict[str, Any] = {
            "status": "ignored",
            "reason": f"malformed pull_request payload: {exc}",
        }
        await _record_delivery(
            db,
            delivery_id=delivery_id,
            event_type="pull_request",
            action=payload.get("action"),
            repository_full_name=(payload.get("repository") or {}).get("full_name"),
            environment_id=None,
            result=result,
        )
        return result

    repo_full_name = event.repository.full_name
    application = await applications_service.get_application_by_github_repo(db, repo_full_name)

    if application is None:
        result = {"status": "ignored", "reason": f"no application registered for {repo_full_name}"}
        await _record_delivery(
            db,
            delivery_id=delivery_id,
            event_type="pull_request",
            action=event.action,
            repository_full_name=repo_full_name,
            environment_id=None,
            result=result,
        )
        return result

    if event.action not in _SUPPORTED_PR_ACTIONS:
        result = {"status": "ignored", "reason": f"unhandled action '{event.action}'"}
        await _record_delivery(
            db,
            delivery_id=delivery_id,
            event_type="pull_request",
            action=event.action,
            repository_full_name=repo_full_name,
            environment_id=None,
            result=result,
        )
        return result

    existing = await environments_service.get_active_environment_for_pr(
        db, application_id=application.id, pr_number=event.number
    )

    environment = None
    status: str

    if event.action in ("opened", "reopened"):
        if existing is not None:
            # Redelivered/duplicate "opened" (or a sync we never saw) —
            # never create a second environment for the same PR.
            environment = await environments_service.redeploy_for_new_commit(
                db,
                existing,
                commit_sha=event.pull_request.head.sha,
                trigger=EventTrigger.WEBHOOK,
            )
            status = "redeployed_existing"
        else:
            environment = await environments_service.create_environment(
                db,
                application=application,
                requested_by_user_id=None,
                pr_number=event.number,
                pr_branch=event.pull_request.head.ref,
                pr_commit_sha=event.pull_request.head.sha,
                trigger=EventTrigger.WEBHOOK,
            )
            status = "environment_created"
            await github_client.post_commit_status(
                repo_full_name,
                event.pull_request.head.sha,
                state="pending",
                description="EnvForge is provisioning a preview environment",
            )

    elif event.action == "synchronize":
        if existing is not None:
            environment = await environments_service.redeploy_for_new_commit(
                db,
                existing,
                commit_sha=event.pull_request.head.sha,
                trigger=EventTrigger.WEBHOOK,
            )
            status = "redeployed_existing"
        else:
            # Self-healing: we never saw "opened" for this PR (e.g. the
            # webhook was registered after it was already open) — treat
            # the first "synchronize" we do see as the creation trigger.
            environment = await environments_service.create_environment(
                db,
                application=application,
                requested_by_user_id=None,
                pr_number=event.number,
                pr_branch=event.pull_request.head.ref,
                pr_commit_sha=event.pull_request.head.sha,
                trigger=EventTrigger.WEBHOOK,
            )
            status = "environment_created"

    else:  # "closed" (merged or not — either way, tear the preview down)
        if existing is not None:
            environment = await environments_service.request_deletion(
                db, existing, actor_user_id=None, trigger=EventTrigger.WEBHOOK
            )
            status = "environment_deletion_requested"
        else:
            status = "no_environment_to_delete"

    result = {
        "status": status,
        "environment_id": environment.id if environment else None,
    }
    await _record_delivery(
        db,
        delivery_id=delivery_id,
        event_type="pull_request",
        action=event.action,
        repository_full_name=repo_full_name,
        environment_id=environment.id if environment else None,
        result=result,
    )
    return result
