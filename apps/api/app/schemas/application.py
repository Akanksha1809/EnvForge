from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = Field(default=None, max_length=2048)
    github_repo: str | None = Field(default=None, max_length=512)
    default_branch: str = Field(default="main", max_length=255)
    team_id: str
    environment_template_id: str | None = None
    environment_template_version: int | None = None
    deployment_config: dict[str, Any] = Field(default_factory=dict)
    infrastructure_requirements: dict[str, Any] = Field(default_factory=dict)
    resource_requirements: dict[str, Any] = Field(default_factory=dict)
    health_check_config: dict[str, Any] = Field(default_factory=dict)
    env_vars: dict[str, str] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    environment_ttl_hours: int = Field(default=48, ge=1, le=24 * 30)
    max_active_environments: int | None = Field(default=None, ge=1, le=1000)


class ApplicationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2048)
    github_repo: str | None = Field(default=None, max_length=512)
    default_branch: str | None = Field(default=None, max_length=255)
    environment_template_id: str | None = None
    environment_template_version: int | None = None
    deployment_config: dict[str, Any] | None = None
    infrastructure_requirements: dict[str, Any] | None = None
    resource_requirements: dict[str, Any] | None = None
    health_check_config: dict[str, Any] | None = None
    env_vars: dict[str, str] | None = None
    dependencies: list[str] | None = None
    environment_ttl_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    max_active_environments: int | None = Field(default=None, ge=1, le=1000)
    is_active: bool | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None
    github_repo: str | None
    default_branch: str
    team_id: str
    environment_template_id: str | None
    environment_template_version: int | None
    deployment_config: dict[str, Any]
    infrastructure_requirements: dict[str, Any]
    resource_requirements: dict[str, Any]
    health_check_config: dict[str, Any]
    env_vars: dict[str, str]
    dependencies: list[str]
    environment_ttl_hours: int
    max_active_environments: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
