#!/bin/bash
set -e

cd "$(dirname "$0")/backend"

echo "==> VERA Backend starten"
echo "    Datenbank: SQLite (vera.db)"

# venv aktivieren
source .venv/bin/activate

# Backend starten mit Auto-Reload
exec uvicorn app.main:app --host 0.0.0.0 --port 31367 --reload
