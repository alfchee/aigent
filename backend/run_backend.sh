#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8231 --reload-exclude "workspace_data" --reload-exclude "navi_memory_db" --reload-exclude "logs" --reload-dir "app"
