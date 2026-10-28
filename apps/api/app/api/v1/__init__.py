from fastapi import APIRouter

from app.api.v1.applications import router as applications_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.environments import router as environments_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.teams import router as teams_router
from app.api.v1.templates import router as templates_router
from app.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(teams_router, prefix="/teams", tags=["teams"])
api_router.include_router(applications_router, prefix="/applications", tags=["applications"])
api_router.include_router(templates_router, prefix="/templates", tags=["templates"])
api_router.include_router(environments_router, prefix="/environments", tags=["environments"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(audit_router, prefix="/audit-logs", tags=["audit"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
