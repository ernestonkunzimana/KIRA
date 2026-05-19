import os
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import AuditEvent, DetectionEvent
from .schemas import (
    AuditEventRequest,
    DetectionEventResponse,
    DetectionIngestRequest,
    MetricsSummaryResponse,
)

app = FastAPI(title="KIRA Enterprise API", version="1.0.0")

origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


class ConnectionManager:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self._clients.discard(websocket)

    async def broadcast(self, message: dict[str, Any]):
        stale: list[WebSocket] = []
        for client in self._clients:
            try:
                await client.send_json(message)
            except Exception:
                stale.append(client)
        for ws in stale:
            self.disconnect(ws)


ws_manager = ConnectionManager()


def _severity_from_prediction(prediction: int) -> str:
    return "CRITICAL" if prediction == -1 else "INFO"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "kira-backend"}


@app.post("/api/v1/events/detection", response_model=DetectionEventResponse)
async def ingest_detection(
    payload: DetectionIngestRequest,
    db: Session = Depends(get_db),
) -> DetectionEvent:
    severity = _severity_from_prediction(payload.ai_prediction)
    event = DetectionEvent(
        event_time=payload.timestamp,
        node_id=payload.node_id,
        vibration_hz=payload.metrics.vibration_hz,
        temperature_c=payload.metrics.temperature_c,
        link_quality_qos=payload.metrics.link_quality_qos,
        ground_truth=payload.ground_truth,
        ai_prediction=payload.ai_prediction,
        anomaly_score=payload.anomaly_score,
        decision=payload.decision,
        severity=severity,
        raw_payload=payload.raw_payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    await ws_manager.broadcast(
        {
            "type": "detection_event",
            "payload": {
                "id": event.id,
                "event_time": event.event_time.isoformat(),
                "node_id": event.node_id,
                "anomaly_score": event.anomaly_score,
                "decision": event.decision,
                "severity": event.severity,
            },
        }
    )
    return event


@app.post("/api/v1/events/audit")
async def ingest_audit(payload: AuditEventRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    event = AuditEvent(
        event_time=payload.timestamp,
        event_type=payload.event_type,
        severity=payload.severity,
        actor=payload.actor,
        description=payload.description,
        details=payload.details,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    await ws_manager.broadcast(
        {
            "type": "audit_event",
            "payload": {
                "id": event.id,
                "event_type": event.event_type,
                "severity": event.severity,
                "actor": event.actor,
                "description": event.description,
                "event_time": event.event_time.isoformat(),
            },
        }
    )
    return {"id": event.id, "status": "stored"}


@app.get("/api/v1/alerts", response_model=list[DetectionEventResponse])
def get_alerts(limit: int = 50, db: Session = Depends(get_db)) -> list[DetectionEvent]:
    return (
        db.query(DetectionEvent)
        .order_by(desc(DetectionEvent.event_time))
        .limit(max(1, min(limit, 500)))
        .all()
    )


@app.get("/api/v1/metrics/summary", response_model=MetricsSummaryResponse)
def get_summary(db: Session = Depends(get_db)) -> MetricsSummaryResponse:
    total_events = db.query(func.count(DetectionEvent.id)).scalar() or 0
    anomalies = (
        db.query(func.count(DetectionEvent.id))
        .filter(DetectionEvent.ai_prediction == -1)
        .scalar()
        or 0
    )
    healthy = total_events - anomalies
    anomaly_rate = (anomalies / total_events) if total_events else 0.0
    return MetricsSummaryResponse(
        total_events=total_events,
        anomalies=anomalies,
        healthy=healthy,
        anomaly_rate=round(anomaly_rate, 4),
    )


@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await ws_manager.connect(websocket)
    await websocket.send_json(
        {
            "type": "system",
            "payload": {
                "message": "Connected to KIRA real-time stream",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
