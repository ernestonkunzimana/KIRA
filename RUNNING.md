Local run instructions (fast dev mode)

This repository provides scripts to quickly start the KIRA backend, Streamlit frontend, and a local Redis instance for development.

Quick start (fast, lightweight - does NOT install heavy ML libs):

1) Start Redis (local docker)

```bash
cd /home/ernest/Desktop/KIRA
./scripts/start-redis.sh
```

2) Activate the project venv (create if needed)

```bash
cd /home/ernest/Desktop/KIRA
python3 -m venv .venv
source .venv/bin/activate
pip install -r kigali_watchman/backend/requirements-dev.txt
```

3) Start backend (development)

```bash
# From project root
./scripts/start-backend.sh
# Backend will be available on http://127.0.0.1:5001
```

4) Start frontend (Streamlit)

```bash
# From project root
./scripts/start-frontend.sh
# Frontend will be available on http://localhost:8501
```

Quick smoke tests

- Health:
  curl http://127.0.0.1:5001/api/v1/health

- Get a token:
  curl -X POST -H "Content-Type: application/json" -d '{"client_id":"dashboard","client_secret":"kira-dashboard-2024"}' http://127.0.0.1:5001/auth/token

- Predict (use token):
  curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" -d '{"tower_id":"Test-Tower","district":"Gasabo","sensor_data":{}}' http://127.0.0.1:5001/api/v1/predict/iot

Notes

- The `requirements-dev.txt` installs a lightweight set of dependencies suitable for local development. To enable full ML models you will need to install the full `kigali_watchman/backend/requirements.txt` which includes `tensorflow`, `xgboost`, and may require Python 3.11/3.12 or building from Docker.

- For production, follow the recommended path: build Docker images, use Gunicorn, Nginx reverse proxy, TLS, and a managed Redis instance. See the repo's `docker-compose.yml` and use the `backend/Dockerfile` and `frontend/Dockerfile` as a starting point.

- Live mode and client-side caching are implemented in the Streamlit app to reduce round-trips and improve mobile performance.
