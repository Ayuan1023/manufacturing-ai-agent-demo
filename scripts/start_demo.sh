#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.11)"
else
  PYTHON_BIN="$(command -v python3)"
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "frontend dependencies are missing; run npm install in frontend/ first"
  exit 1
fi

echo "Preparing deterministic demo data..."
"$PYTHON_BIN" -m backend.simulator.generate_data >/dev/null

echo "Starting backend at http://localhost:8000"
"$PYTHON_BIN" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cleanup() {
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting frontend at http://localhost:5173"
cd "$ROOT_DIR/frontend"
npm run dev -- --host 127.0.0.1
