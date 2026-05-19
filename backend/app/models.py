from sqlalchemy import JSON, Column, DateTime, Float, Integer, String
from sqlalchemy.sql import func

from .database import Base


class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(Integer, primary_key=True, index=True)
    event_time = Column(DateTime(timezone=True), nullable=False)
    node_id = Column(String(128), nullable=False, index=True)
    vibration_hz = Column(Float, nullable=False)
    temperature_c = Column(Float, nullable=False)
    link_quality_qos = Column(Float, nullable=False)
    ground_truth = Column(Integer, nullable=True)
    ai_prediction = Column(Integer, nullable=False, index=True)
    anomaly_score = Column(Float, nullable=True)
    decision = Column(String(32), nullable=False, index=True)
    severity = Column(String(32), nullable=False, index=True)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    event_time = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(128), nullable=False, index=True)
    severity = Column(String(32), nullable=False, index=True)
    actor = Column(String(128), nullable=False)
    description = Column(String(512), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
