from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TeamRole


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = Field(default=None, max_length=1024)
    max_active_environments: int = Field(default=10, ge=1, le=1000)


class TeamUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    max_active_environments: int | None = Field(default=None, ge=1, le=1000)


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None
    max_active_environments: int
    created_at: datetime


class TeamMembershipAddRequest(BaseModel):
    user_id: str
    role: TeamRole = TeamRole.MEMBER


class TeamMembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    team_id: str
    role: TeamRole
    created_at: datetime
