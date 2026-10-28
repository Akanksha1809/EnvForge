from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application


class ApplicationError(Exception):
    pass


async def get_application(db: AsyncSession, application_id: str) -> Application | None:
    return await db.get(Application, application_id)


async def get_application_by_slug(db: AsyncSession, slug: str) -> Application | None:
    result = await db.execute(select(Application).where(Application.slug == slug))
    return result.scalar_one_or_none()


async def get_application_by_github_repo(
    db: AsyncSession, repo_full_name: str
) -> Application | None:
    result = await db.execute(
        select(Application).where(
            Application.github_repo == repo_full_name, Application.is_active.is_(True)
        )
    )
    return result.scalar_one_or_none()


async def create_application(db: AsyncSession, **fields: Any) -> Application:
    if await get_application_by_slug(db, fields["slug"]) is not None:
        raise ApplicationError(f"An application with slug '{fields['slug']}' already exists")

    application = Application(**fields)
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


async def update_application(
    db: AsyncSession, application: Application, updates: dict[str, Any]
) -> Application:
    for field, value in updates.items():
        if value is not None:
            setattr(application, field, value)
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


async def delete_application(db: AsyncSession, application: Application) -> None:
    await db.delete(application)
    await db.commit()
