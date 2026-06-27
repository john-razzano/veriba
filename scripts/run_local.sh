#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source .venv/bin/activate
export PYTHONPATH="$ROOT_DIR/backend"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir backend

