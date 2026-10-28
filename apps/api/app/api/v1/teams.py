from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.pagination import paginate
from app.db.session import get_db
from app.models.team import Team, TeamMembership
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.team import (
    TeamCreateRequest,
    TeamMembershipAddRequest,
    TeamMembershipOut,
    TeamOut,
    TeamUpdateRequest,
)
from app.services import rbac
from app.services import teams as teams_service
from app.services.audit import record as audit_record

router = APIRouter()


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: TeamCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Team:
    rbac.require_permission(current_user, rbac.Permission.TEAM_MANAGE)
    try:
        team = await teams_service.create_team(
            db,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            max_active_environments=payload.max_active_environments,
            creator_user_id=current_user.id,
        )
    except teams_service.TeamError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_record(
        db,
        action="team.create",
        resource_type="team",
        resource_id=team.id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )
    return team


@router.get("", response_model=Page[TeamOut])
async def list_teams(
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[TeamOut]:
    stmt = select(Team)
    return await paginate(
        db,
        stmt,
        params,
        TeamOut,
        sortable_columns={"created_at": Team.created_at, "name": Team.name},
    )


@router.get("/{team_id}", response_model=TeamOut)
async def get_team(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Team:
    team = await teams_service.get_team(db, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


@router.patch("/{team_id}", response_model=TeamOut)
async def update_team(
    team_id: str,
    payload: TeamUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Team:
    team = await teams_service.get_team(db, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    await rbac.require_team_admin(db, user=current_user, team_id=team_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(team, field, value)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


@router.post(
    "/{team_id}/members", response_model=TeamMembershipOut, status_code=status.HTTP_201_CREATED
)
async def add_team_member(
    team_id: str,
    payload: TeamMembershipAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamMembership:
    team = await teams_service.get_team(db, team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    await rbac.require_team_admin(db, user=current_user, team_id=team_id)

    try:
        membership = await teams_service.add_member(
            db, team_id=team_id, user_id=payload.user_id, role=payload.role
        )
    except teams_service.TeamError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_record(
        db,
        action="team.member.add",
        resource_type="team",
        resource_id=team_id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
        metadata={"added_user_id": payload.user_id, "role": payload.role.value},
    )
    return membership


@router.get("/{team_id}/members", response_model=list[TeamMembershipOut])
async def list_team_members(
    team_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TeamMembership]:
    result = await db.execute(select(TeamMembership).where(TeamMembership.team_id == team_id))
    return list(result.scalars().all())


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await rbac.require_team_admin(db, user=current_user, team_id=team_id)
    try:
        await teams_service.remove_member(db, team_id=team_id, user_id=user_id)
    except teams_service.TeamError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    await audit_record(
        db,
        action="team.member.remove",
        resource_type="team",
        resource_id=team_id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
        metadata={"removed_user_id": user_id},
    )
