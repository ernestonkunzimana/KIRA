from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MetricsPayload(BaseModel):
    vibration_hz: float
    temperature_c: float
    link_quality_qos: float


class DetectionIngestRequest(BaseModel):
    timestamp: datetime
    node_id: str = Field(min_length=1, max_length=128)
    metrics: MetricsPayload
    ground_truth: int | None = None
    ai_prediction: int
    anomaly_score: float | None = None
    decision: str
    raw_payload: dict[str, Any] | None = None


class AuditEventRequest(BaseModel):
    timestamp: datetime
    event_type: str
    severity: str
    actor: str
    description: str
    details: dict[str, Any] | None = None


class DetectionEventResponse(BaseModel):
    id: int
    event_time: datetime
    node_id: str
    vibration_hz: float
    temperature_c: float
    link_quality_qos: float
    ai_prediction: int
    anomaly_score: float | None
    decision: str
    severity: str

    class Config:
        from_attributes = True


class MetricsSummaryResponse(BaseModel):
    total_events: int
    anomalies: int
    healthy: int
    anomaly_rate: float
