from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.pagination import paginate
from app.db.session import get_db
from app.models.enums import EventTrigger
from app.models.environment import Environment, EnvironmentEvent
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.environment import (
    EnvironmentCreateRequest,
    EnvironmentEventOut,
    EnvironmentExtendRequest,
    EnvironmentLogLineOut,
    EnvironmentOut,
)
from app.services import applications as applications_service
from app.services import environments as environments_service
from app.services import rbac
from app.services.audit import record as audit_record

router = APIRouter()


@router.post("", response_model=EnvironmentOut, status_code=status.HTTP_202_ACCEPTED)
async def create_environment(
    payload: EnvironmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Environment:
    rbac.require_permission(current_user, rbac.Permission.ENVIRONMENT_CREATE)

    application = await applications_service.get_application(db, payload.application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    await rbac.require_team_membership(db, user=current_user, team_id=application.team_id)

    try:
        environment = await environments_service.create_environment(
            db,
            application=application,
            requested_by_user_id=current_user.id,
            name=payload.name,
            pr_number=payload.pr_number,
            pr_branch=payload.pr_branch,
            pr_commit_sha=payload.pr_commit_sha,
            config_overrides=payload.config_overrides,
        )
    except environments_service.QuotaExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except environments_service.EnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await audit_record(
        db,
        action="environment.create",
        resource_type="environment",
        resource_id=environment.id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )
    return environment


@router.get("", response_model=Page[EnvironmentOut])
async def list_environments(
    application_id: str | None = Query(default=None),
    state: str | None = Query(default=None),
    pr_number: int | None = Query(default=None),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[EnvironmentOut]:
    stmt = select(Environment)
    if application_id:
        stmt = stmt.where(Environment.application_id == application_id)
    if state:
        stmt = stmt.where(Environment.state == state)
    if pr_number is not None:
        stmt = stmt.where(Environment.pr_number == pr_number)

    return await paginate(
        db,
        stmt,
        params,
        EnvironmentOut,
        sortable_columns={"created_at": Environment.created_at, "name": Environment.name},
    )


async def _get_environment_or_404(db: AsyncSession, environment_id: str) -> Environment:
    environment = await environments_service.get_environment(db, environment_id)
    if environment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found")
    return environment


@router.get("/{environment_id}", response_model=EnvironmentOut)
async def get_environment(
    environment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Environment:
    return await _get_environment_or_404(db, environment_id)


@router.delete("/{environment_id}", response_model=EnvironmentOut)
async def delete_environment(
    environment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Environment:
    environment = await _get_environment_or_404(db, environment_id)
    application = await applications_service.get_application(db, environment.application_id)
    rbac.require_permission(current_user, rbac.Permission.ENVIRONMENT_DELETE)
    if application is not None:
        await rbac.require_team_membership(db, user=current_user, team_id=application.team_id)

    try:
        environment = await environments_service.request_deletion(
            db, environment, actor_user_id=current_user.id, trigger=EventTrigger.USER
        )
    except environments_service.EnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await audit_record(
        db,
        action="environment.delete",
        resource_type="environment",
        resource_id=environment_id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )
    return environment


@router.post("/{environment_id}/extend", response_model=EnvironmentOut)
async def extend_environment(
    environment_id: str,
    payload: EnvironmentExtendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Environment:
    environment = await _get_environment_or_404(db, environment_id)
    rbac.require_permission(current_user, rbac.Permission.ENVIRONMENT_EXTEND)

    try:
        environment = await environments_service.extend_environment(
            db,
            environment,
            additional_hours=payload.additional_hours,
            actor_user_id=current_user.id,
        )
    except environments_service.EnvironmentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await audit_record(
        db,
        action="environment.extend",
        resource_type="environment",
        resource_id=environment_id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
        metadata={"additional_hours": payload.additional_hours},
    )
    return environment


@router.post(
    "/{environment_id}/refresh", response_model=EnvironmentOut, status_code=status.HTTP_202_ACCEPTED
)
async def refresh_environment(
    environment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Environment:
    """Re-queues provisioning for an existing environment (e.g. a new commit
    was pushed to its PR). The actual redeploy pipeline lands in Phase 3/4 —
    today this records the request as an audited no-op so the API contract
    is stable for the frontend and GitHub integration to build against."""
    environment = await _get_environment_or_404(db, environment_id)
    rbac.require_permission(current_user, rbac.Permission.ENVIRONMENT_CREATE)

    db.add(
        EnvironmentEvent(
            environment_id=environment.id,
            previous_state=environment.state,
            new_state=environment.state,
            trigger=EventTrigger.USER.value,
            actor_user_id=current_user.id,
            metadata_json={"note": "refresh requested; redeploy pipeline lands in Phase 3/4"},
        )
    )
    await db.commit()
    await db.refresh(environment)
    return environment


@router.get("/{environment_id}/events", response_model=list[EnvironmentEventOut])
async def get_environment_events(
    environment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnvironmentEvent]:
    await _get_environment_or_404(db, environment_id)
    result = await db.execute(
        select(EnvironmentEvent)
        .where(EnvironmentEvent.environment_id == environment_id)
        .order_by(EnvironmentEvent.created_at)
    )
    return list(result.scalars().all())


@router.get("/{environment_id}/logs", response_model=list[EnvironmentLogLineOut])
async def get_environment_logs(
    environment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnvironmentLogLineOut]:
    """Real container log streaming depends on the Kubernetes provisioning
    pipeline (Phase 3), so until then this derives log-shaped lines from the
    lifecycle event history rather than returning fabricated application
    log output."""
    await _get_environment_or_404(db, environment_id)
    result = await db.execute(
        select(EnvironmentEvent)
        .where(EnvironmentEvent.environment_id == environment_id)
        .order_by(EnvironmentEvent.created_at)
    )
    events = result.scalars().all()
    return [
        EnvironmentLogLineOut(
            timestamp=event.created_at,
            level="ERROR" if event.error_message else "INFO",
            message=event.error_message
            or (
                f"state transition: {event.previous_state} -> {event.new_state} "
                f"(trigger={event.trigger})"
            ),
            source="lifecycle",
        )
        for event in events
    ]
