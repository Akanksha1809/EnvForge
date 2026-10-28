from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TemplateType


class TemplateCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    template_type: TemplateType = TemplateType.CUSTOM
    required_services: list[str] = Field(default_factory=list)
    infrastructure_requirements: dict[str, Any] = Field(default_factory=dict)
    resource_limits: dict[str, Any] = Field(default_factory=dict)
    env_vars: dict[str, str] = Field(default_factory=dict)
    deployment_strategy: str = Field(default="rolling", max_length=64)
    health_checks: dict[str, Any] = Field(default_factory=dict)
    dependency_requirements: list[str] = Field(default_factory=list)
    cleanup_rules: dict[str, Any] = Field(default_factory=dict)


class TemplateNewVersionRequest(TemplateCreateRequest):
    """Same shape as creation — posting a new version re-specifies the full
    template body rather than patching, so each version is a complete,
    independently-auditable snapshot."""


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    version: int
    is_latest: bool
    name: str
    description: str | None
    template_type: TemplateType
    required_services: list[str]
    infrastructure_requirements: dict[str, Any]
    resource_limits: dict[str, Any]
    env_vars: dict[str, str]
    deployment_strategy: str
    health_checks: dict[str, Any]
    dependency_requirements: list[str]
    cleanup_rules: dict[str, Any]
    created_at: datetime
