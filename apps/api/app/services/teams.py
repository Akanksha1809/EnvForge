from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TeamRole
from app.models.team import Team, TeamMembership


class TeamError(Exception):
    pass


async def get_team(db: AsyncSession, team_id: str) -> Team | None:
    return await db.get(Team, team_id)


async def get_team_by_slug(db: AsyncSession, slug: str) -> Team | None:
    result = await db.execute(select(Team).where(Team.slug == slug))
    return result.scalar_one_or_none()


async def create_team(
    db: AsyncSession,
    *,
    name: str,
    slug: str,
    description: str | None,
    max_active_environments: int,
    creator_user_id: str,
) -> Team:
    if await get_team_by_slug(db, slug) is not None:
        raise TeamError(f"A team with slug '{slug}' already exists")

    team = Team(
        name=name,
        slug=slug,
        description=description,
        max_active_environments=max_active_environments,
    )
    db.add(team)
    await db.flush()

    # The creator is automatically a team admin so they can immediately
    # manage membership and register applications under it.
    db.add(TeamMembership(user_id=creator_user_id, team_id=team.id, role=TeamRole.ADMIN.value))
    await db.commit()
    await db.refresh(team)
    return team


async def add_member(
    db: AsyncSession, *, team_id: str, user_id: str, role: TeamRole
) -> TeamMembership:
    existing = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id, TeamMembership.user_id == user_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise TeamError("User is already a member of this team")

    membership = TeamMembership(team_id=team_id, user_id=user_id, role=role.value)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def remove_member(db: AsyncSession, *, team_id: str, user_id: str) -> None:
    result = await db.execute(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id, TeamMembership.user_id == user_id
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise TeamError("User is not a member of this team")
    await db.delete(membership)
    await db.commit()
