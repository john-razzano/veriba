# Veriba Platform

FastAPI backend plus a public editorial gallery frontend implementing the API plan in [VERIBA-API-PLAN.md](VERIBA-API-PLAN.md).

## Quick Start

1. Copy `.env.example` to `.env` and adjust secrets.
2. Start services with `docker compose up --build`.
3. Visit `http://localhost/` for the public gallery frontend.
4. Visit `http://localhost/medspa/` for the medspa admin studio.
5. Visit `http://localhost/medspa/cases/`, `http://localhost/medspa/credits/`, and `http://localhost/medspa/settings/` for focused medspa workflows.
6. Visit `http://localhost:8000/docs` for the API docs.

## Smoke Tests

- `./scripts/gallery_smoke_test.sh` verifies the public gallery pages and cross-medspa public API.
- `./scripts/deep_smoke_test.sh` verifies the provider workflow, widget endpoints, and publish flow.
- `./scripts/medspa_admin_smoke_test.sh` verifies the medspa admin shell and the auth-backed dashboard APIs.

## Demo Data

- `./scripts/reset_demo_data.sh` removes seeded demo data and smoke-test records.
- `./scripts/seed_demo_gallery.sh` repopulates the app with illustrative placeholder medspas, sessions, credits, and media.
- [DEMO-DATA.md](DEMO-DATA.md) lists the seeded demo accounts and explains what gets created.

## Local Fallback

If Docker is unavailable, use:

1. `./scripts/bootstrap_local.sh`
2. `./scripts/run_local.sh`
3. `./scripts/smoke_test.sh`

## Project Layout

- `backend/app` contains the FastAPI application.
- `frontend` contains the public gallery site and medspa admin studio served by Caddy.
- `backend/tests` contains API tests for key flows.
- `docker-compose.yml` runs FastAPI, PostgreSQL, Redis, MinIO, Caddy, and Celery workers.
