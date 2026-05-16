#!/usr/bin/env bash
# Start the Streamlit frontend using project venv.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/kigali_watchman/frontend"
if [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
else
  echo "Warning: .venv not found. Activate your venv manually."
fi
export KIRA_API_URL=${KIRA_API_URL:-http://127.0.0.1:5001}
streamlit run app.py --server.port ${STREAMLIT_PORT:-8501}
