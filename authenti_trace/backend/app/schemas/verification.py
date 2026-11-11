from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Literal, Optional
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
    reason: str = ""  # why the system abstained or applied a cap; empty for a normal verdict
    evidence: float = 0.0  # total confidence-weighted evidence behind the score
    calibrated: bool = False  # True when the score is a measured probability, not a raw heuristic score

class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seq: int
    hash_version: int
    versions: Optional[Dict[str, Any]] = None
    media_reference_id: str
    file_hash: str
    composite_score: Optional[float]
    risk_category: Optional[str]
    enforcement_action: Optional[str]
    signal_telemetry: Optional[Dict[str, Any]]
    previous_hash: str
    current_hash: str
    created_at: datetime.datetime


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    job_id: str = Field(validation_alias="id")
    status: str
    attempts: int
    report_id: Optional[str] = None
    error: Optional[str] = None


class ReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=500)
    reviewer: str = Field(default="anonymous", max_length=80)  # replaced by the API key identity when auth is on


class PendingReview(BaseModel):
    id: str
    seq: int
    media_reference_id: str
    composite_score: Optional[float]
    risk_category: Optional[str]
    enforcement_action: Optional[str]
    reason: str = ""
    created_at: datetime.datetime
