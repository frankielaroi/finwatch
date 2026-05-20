from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: str
    entity_id: str
    transaction_id: Optional[str]
    alert_type: str
    typology: str
    severity: str
    risk_score: float
    priority: int
    status: str
    title: str
    description: str
    evidence: List[dict]
    recommended_action: Optional[str]
    generated_by: Optional[str] = None
    assigned_to: Optional[str]
    sar_required: bool
    sar_filed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AlertAssign(BaseModel):
    assigned_to: str


class AlertResolve(BaseModel):
    resolution: str
    resolution_notes: Optional[str] = None
    sar_required: Optional[bool] = None
