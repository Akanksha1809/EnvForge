from pydantic import BaseModel

from app.schemas.job import JobOut


class ApplicationEnvironmentCount(BaseModel):
    name: str
    slug: str
    active_count: int


class TeamEnvironmentCount(BaseModel):
    name: str
    slug: str
    active_count: int


class DashboardSummaryOut(BaseModel):
    total_environments: int
    active_environments: int
    provisioning_environments: int
    failed_environments: int
    expiring_environments: int
    environments_by_application: list[ApplicationEnvironmentCount]
    environments_by_team: list[TeamEnvironmentCount]
    provisioning_success_rate: float | None
    average_provisioning_duration_seconds: float | None
    recent_jobs: list[JobOut]
