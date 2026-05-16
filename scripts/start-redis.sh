#!/usr/bin/env bash
# Start Redis for local development. Uses a safe relaxed seccomp only for local dev.
set -euo pipefail
if docker ps --filter name=kira-redis --format '{{.Names}}' | grep -q kira-redis; then
  echo "kira-redis already running"
else
  echo "Starting kira-redis..."
  docker rm -f kira-redis 2>/dev/null || true
  docker run --name kira-redis -p 6379:6379 --security-opt seccomp=unconfined -d redis:7.2-alpine
  echo "kira-redis started"
fi
