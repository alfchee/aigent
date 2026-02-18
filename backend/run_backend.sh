#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Activar venv si existe y no está activo o es incorrecto
if [ -d "venv" ]; then
    if [ -z "$VIRTUAL_ENV" ] || [ "$VIRTUAL_ENV" != "$(pwd)/venv" ]; then
        echo "Activating venv..."
        source venv/bin/activate
    fi
fi

# Usar python -m uvicorn para asegurar consistencia
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8231 --reload-exclude "workspace_data" --reload-exclude "navi_memory_db" --reload-exclude "logs" --reload-dir "app"
