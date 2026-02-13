#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "🛑 Stopping backend server..."
pkill -f "uvicorn.*app.main:app" || true

echo "🧹 Cleaning up memory database..."
rm -rf navi_memory_db/chroma.sqlite3 navi_memory_db/chroma.sqlite3-journal navi_memory_db/chroma.log || true

echo "🧹 Cleaning up workspace data..."
rm -rf workspace_data/tg_10018049 || true

echo "✅ Cleanup complete. You can now restart the backend with:"
echo "   ./run_backend.sh"
