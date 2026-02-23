#!/bin/bash
set -e

cd "$(dirname "$0")/frontend"

echo "==> VERA Frontend starten"
echo "    API: http://192.168.0.144:31367"
echo "    App: http://192.168.0.144:31368"

exec npm run dev -- --port 31368 --hostname 0.0.0.0
