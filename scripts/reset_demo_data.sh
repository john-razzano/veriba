#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T fastapi python -m app.scripts.reset_demo_data "$@"
