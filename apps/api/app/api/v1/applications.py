from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.pagination import paginate
from app.db.session import get_db
from app.models.application import Application
from app.models.user import User
from app.schemas.application import (
    ApplicationCreateRequest,
    ApplicationOut,
    ApplicationUpdateRequest,
)
from app.schemas.common import Page, PageParams
from app.services import applications as applications_service
from app.services import rbac
from app.services.audit import record as audit_record

router = APIRouter()


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    rbac.require_permission(current_user, rbac.Permission.APPLICATION_REGISTER)
    await rbac.require_team_membership(db, user=current_user, team_id=payload.team_id)

    try:
        application = await applications_service.create_application(db, **payload.model_dump())
    except applications_service.ApplicationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_record(
        db,
        action="application.create",
        resource_type="application",
        resource_id=application.id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )
    return application


@router.get("", response_model=Page[ApplicationOut])
async def list_applications(
    team_id: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[ApplicationOut]:
    stmt = select(Application)
    if team_id:
        stmt = stmt.where(Application.team_id == team_id)
    if is_active is not None:
        stmt = stmt.where(Application.is_active == is_active)

    return await paginate(
        db,
        stmt,
        params,
        ApplicationOut,
        sortable_columns={"created_at": Application.created_at, "name": Application.name},
    )


@router.get("/{application_id}", response_model=ApplicationOut)
async def get_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    application = await applications_service.get_application(db, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.patch("/{application_id}", response_model=ApplicationOut)
async def update_application(
    application_id: str,
    payload: ApplicationUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Application:
    application = await applications_service.get_application(db, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    rbac.require_permission(current_user, rbac.Permission.APPLICATION_MANAGE)
    await rbac.require_team_membership(db, user=current_user, team_id=application.team_id)

    updated = await applications_service.update_application(
        db, application, payload.model_dump(exclude_unset=True)
    )
    await audit_record(
        db,
        action="application.update",
        resource_type="application",
        resource_id=application_id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )
    return updated


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    application = await applications_service.get_application(db, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    rbac.require_permission(current_user, rbac.Permission.APPLICATION_MANAGE)
    await rbac.require_team_admin(db, user=current_user, team_id=application.team_id)

    await applications_service.delete_application(db, application)
    await audit_record(
        db,
        action="application.delete",
        resource_type="application",
        resource_id=application_id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )
