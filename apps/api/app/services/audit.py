"""Single write path for the audit trail — see app/models/audit_log.py.

Every service that performs a sensitive action should call `record()` rather
than inserting an AuditLog row directly, so the shape of an audit entry stays
consistent and callers can't accidentally omit required context.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    actor_user_id: str | None = None,
    actor_label: str = "system",
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    commit: bool = True,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
        ip_address=ip_address,
    )
    db.add(entry)
    if commit:
        await db.commit()
    else:
        await db.flush()
    return entry
