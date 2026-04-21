from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import datetime

class SignalResult(BaseModel):
    plugin_name: str
    score: float  # 0.0 to 100.0
    confidence: float # 0.0 to 1.0
    reasoning: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ScoringResult(BaseModel):
    trust_score: float
    risk_category: str
    enforcement_action: str

class ReportResponse(BaseModel):
    id: str
    media_reference_id: str
    file_hash: str
    composite_score: Optional[float]
    risk_category: Optional[str]
    enforcement_action: Optional[str]
    signal_telemetry: Optional[Dict[str, Any]]
    previous_hash: str
    current_hash: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class MediaUploadResponse(BaseModel):
    media_id: str
    file_hash: str
    status: str
    message: str
