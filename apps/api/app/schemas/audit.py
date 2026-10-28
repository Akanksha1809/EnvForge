from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: str | None
    actor_label: str
    action: str
    resource_type: str
    resource_id: str | None
    metadata_json: dict[str, Any]
    ip_address: str | None
    created_at: datetime
