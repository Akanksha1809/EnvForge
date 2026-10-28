from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.pagination import paginate
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page, PageParams
from app.services import rbac

router = APIRouter()


@router.get("", response_model=Page[AuditLogOut])
async def list_audit_logs(
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[AuditLogOut]:
    rbac.require_permission(current_user, rbac.Permission.PLATFORM_ADMINISTER)

    stmt = select(AuditLog)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)

    return await paginate(
        db, stmt, params, AuditLogOut, sortable_columns={"created_at": AuditLog.created_at}
    )
