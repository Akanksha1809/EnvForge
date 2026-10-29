from pydantic import BaseModel


class RecommendationOut(BaseModel):
    severity: str  # "info" | "warning" | "critical"
    category: str
    message: str
    resource_type: str
    resource_id: str | None
