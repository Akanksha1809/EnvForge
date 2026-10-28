from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.pagination import paginate
from app.db.session import get_db
from app.models.environment_template import EnvironmentTemplate
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.template import TemplateCreateRequest, TemplateNewVersionRequest, TemplateOut
from app.services import rbac
from app.services import templates as templates_service
from app.services.audit import record as audit_record

router = APIRouter()


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: TemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvironmentTemplate:
    rbac.require_permission(current_user, rbac.Permission.TEMPLATE_MANAGE)
    try:
        template = await templates_service.create_template(
            db, **{**payload.model_dump(), "template_type": payload.template_type.value}
        )
    except templates_service.TemplateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_record(
        db,
        action="template.create",
        resource_type="template",
        resource_id=template.id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )
    return template


@router.get("", response_model=Page[TemplateOut])
async def list_templates(
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[TemplateOut]:
    stmt = select(EnvironmentTemplate).where(EnvironmentTemplate.is_latest.is_(True))
    return await paginate(
        db,
        stmt,
        params,
        TemplateOut,
        sortable_columns={
            "created_at": EnvironmentTemplate.created_at,
            "name": EnvironmentTemplate.name,
        },
    )


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvironmentTemplate:
    template = await templates_service.get_template(db, template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.post("/{slug}/versions", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template_version(
    slug: str,
    payload: TemplateNewVersionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnvironmentTemplate:
    rbac.require_permission(current_user, rbac.Permission.TEMPLATE_MANAGE)
    fields = payload.model_dump(exclude={"slug"})
    fields["template_type"] = payload.template_type.value
    try:
        new_version = await templates_service.create_new_version(db, slug, **fields)
    except templates_service.TemplateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_record(
        db,
        action="template.new_version",
        resource_type="template",
        resource_id=new_version.id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
        metadata={"slug": slug, "version": new_version.version},
    )
    return new_version


@router.get("/{slug}/versions", response_model=list[TemplateOut])
async def list_template_versions(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EnvironmentTemplate]:
    return await templates_service.list_template_versions(db, slug)
