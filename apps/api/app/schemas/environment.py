from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EnvironmentState, EventTrigger


class EnvironmentCreateRequest(BaseModel):
    application_id: str
    name: str | None = Field(default=None, max_length=255)
    pr_number: int | None = None
    pr_branch: str | None = Field(default=None, max_length=255)
    pr_commit_sha: str | None = Field(default=None, max_length=64)
    config_overrides: dict[str, Any] = Field(default_factory=dict)


class EnvironmentExtendRequest(BaseModel):
    additional_hours: int = Field(default=24, ge=1, le=24 * 14)


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    requested_by_user_id: str | None
    template_id: str | None
    template_version: int | None
    name: str
    state: EnvironmentState
    pr_number: int | None
    pr_branch: str | None
    pr_commit_sha: str | None
    namespace: str | None
    preview_url: str | None
    last_error: str | None
    ttl_expires_at: datetime | None
    destroyed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EnvironmentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    environment_id: str
    previous_state: EnvironmentState
    new_state: EnvironmentState
    trigger: EventTrigger
    actor_user_id: str | None
    job_id: str | None
    error_message: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class EnvironmentLogLineOut(BaseModel):
    timestamp: datetime
    level: str
    message: str
    source: str
