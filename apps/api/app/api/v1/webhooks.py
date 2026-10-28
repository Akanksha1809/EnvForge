"""GitHub webhook receiver. Deliberately has no auth dependency — GitHub
can't carry a bearer token — trust instead comes entirely from the HMAC
signature check against the shared webhook secret.
"""

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import webhooks as webhooks_service

router = APIRouter()


@router.post("/github", status_code=status.HTTP_200_OK)
async def github_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_github_event: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict:
    raw_body = await request.body()

    if not webhooks_service.verify_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    if not x_github_delivery:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-GitHub-Delivery header"
        )
    if not x_github_event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-GitHub-Event header"
        )

    if await webhooks_service.already_processed(db, x_github_delivery):
        return {"status": "duplicate_delivery_ignored", "delivery_id": x_github_delivery}

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON") from exc

    return await webhooks_service.process_webhook(
        db, event_type=x_github_event, delivery_id=x_github_delivery, payload=payload
    )
