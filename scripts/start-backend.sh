#!/usr/bin/env bash
# Start backend in development mode using project venv.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/kigali_watchman/backend"
if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
else
  echo "Warning: .venv not found. Activate your venv manually."
fi
export PORT=${PORT:-5001}
export FLASK_ENV=${FLASK_ENV:-development}
python3 main.py
