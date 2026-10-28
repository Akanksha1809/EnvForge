from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.environment_template import EnvironmentTemplate


class TemplateError(Exception):
    pass


async def get_template(db: AsyncSession, template_id: str) -> EnvironmentTemplate | None:
    return await db.get(EnvironmentTemplate, template_id)


async def get_latest_version(db: AsyncSession, slug: str) -> EnvironmentTemplate | None:
    result = await db.execute(
        select(EnvironmentTemplate).where(
            EnvironmentTemplate.slug == slug, EnvironmentTemplate.is_latest.is_(True)
        )
    )
    return result.scalar_one_or_none()


async def get_version(db: AsyncSession, slug: str, version: int) -> EnvironmentTemplate | None:
    result = await db.execute(
        select(EnvironmentTemplate).where(
            EnvironmentTemplate.slug == slug, EnvironmentTemplate.version == version
        )
    )
    return result.scalar_one_or_none()


async def create_template(db: AsyncSession, **fields: Any) -> EnvironmentTemplate:
    """Creates version 1 of a new template family. Use `create_new_version`
    to add a version to an existing slug."""
    if await get_latest_version(db, fields["slug"]) is not None:
        raise TemplateError(f"Template '{fields['slug']}' already exists — post a new version")

    template = EnvironmentTemplate(version=1, is_latest=True, **fields)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def create_new_version(db: AsyncSession, slug: str, **fields: Any) -> EnvironmentTemplate:
    current_latest = await get_latest_version(db, slug)
    if current_latest is None:
        raise TemplateError(f"No existing template with slug '{slug}' — create it first")

    current_latest.is_latest = False
    db.add(current_latest)

    new_version = EnvironmentTemplate(
        slug=slug, version=current_latest.version + 1, is_latest=True, **fields
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    return new_version


async def list_template_versions(db: AsyncSession, slug: str) -> list[EnvironmentTemplate]:
    result = await db.execute(
        select(EnvironmentTemplate)
        .where(EnvironmentTemplate.slug == slug)
        .order_by(EnvironmentTemplate.version.desc())
    )
    return list(result.scalars().all())
