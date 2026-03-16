#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"

if [[ -f "$BACKEND_DIR/.env" ]]; then
  set -a
  source "$BACKEND_DIR/.env"
  set +a
fi

export NAVIBOT_ENV="${NAVIBOT_ENV:-development}"
export LOG_LEVEL="${LOG_LEVEL:-DEBUG}"
export PYTHONPATH="${PYTHONPATH:-$BACKEND_DIR}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

mkdir -p "$BACKEND_DIR/workspace/db"

cd "$BACKEND_DIR"

if [[ -x "$VENV_PYTHON" ]]; then
  exec "$VENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
fi

exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
