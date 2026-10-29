from pydantic import BaseModel


class EnvironmentCostOut(BaseModel):
    environment_id: str
    basis: str  # "estimated" | "simulated" — never "actual", see cost_engine.py
    hours_active: float
    cpu_cores: float
    memory_gb: float
    estimated_cost_usd: float
    is_still_active: bool


class CostBucket(BaseModel):
    name: str
    slug: str
    estimated_cost_usd: float


class CostSummaryOut(BaseModel):
    basis: str
    total_estimated_cost_usd: float
    by_team: list[CostBucket]
    by_application: list[CostBucket]
