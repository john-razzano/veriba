#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T fastapi python -m app.scripts.seed_demo_gallery --reset-first "$@"
