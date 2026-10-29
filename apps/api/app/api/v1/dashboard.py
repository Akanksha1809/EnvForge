from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.cost import CostSummaryOut
from app.schemas.dashboard import DashboardSummaryOut
from app.schemas.recommendation import RecommendationOut
from app.services import cost_engine
from app.services import dashboard as dashboard_service
from app.services import recommendations as recommendations_service

router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryOut)
async def get_dashboard_summary(
    expiring_within_hours: int = Query(default=24, ge=1, le=24 * 30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardSummaryOut:
    data = await dashboard_service.get_summary(db, expiring_within_hours=expiring_within_hours)
    return DashboardSummaryOut.model_validate(data)


@router.get("/cost-summary", response_model=CostSummaryOut)
async def get_cost_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CostSummaryOut:
    data = await cost_engine.estimate_cost_summary(db)
    return CostSummaryOut.model_validate(data)


@router.get("/recommendations", response_model=list[RecommendationOut])
async def get_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return await recommendations_service.get_recommendations(db)
