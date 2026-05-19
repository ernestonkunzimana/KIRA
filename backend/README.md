# KIRA Backend API

FastAPI service for enterprise integration:
- REST API for alerts, metrics, and audit feeds
- WebSocket stream for real-time dashboard updates
- PostgreSQL persistence for detections and audit events

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
