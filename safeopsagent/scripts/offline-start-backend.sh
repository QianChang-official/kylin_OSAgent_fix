#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"
export LLM_PROVIDER="${LLM_PROVIDER:-mock}"
export CONSOLE_AUTH_ENABLED="${CONSOLE_AUTH_ENABLED:-0}"
export PYTHONPATH="${PROJECT_ROOT}"

echo "Starting SafeOpsAgent backend in offline mock mode..."
echo "Project root: ${PROJECT_ROOT}"
echo "LLM_PROVIDER=${LLM_PROVIDER}"
echo "Console authentication is disabled only for this loopback development launcher."
echo "URL: http://127.0.0.1:8000"

exec python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
