# Demo Data

Use these commands from the project root while Docker is running:

```bash
./scripts/reset_demo_data.sh
./scripts/seed_demo_gallery.sh
```

`reset_demo_data.sh` removes only synthetic records:
- smoke-test accounts created with `@example.com`
- seeded demo medspas and their sessions, credits, refresh tokens, and media objects

`seed_demo_gallery.sh` repopulates the app with polished illustrative placeholder data and resets old synthetic records first so it stays idempotent.

## Demo Accounts

All seeded medspa accounts use the same password:

```text
veriba-demo-2026
```

Seeded owners:

- `owner+aster@veriba-demo.studio`
- `owner+meridian@veriba-demo.studio`
- `owner+solstice@veriba-demo.studio`

## What Gets Seeded

- 3 demo medspas
- 6 published gallery-ready sessions
- 3 internal pending sessions for dashboard workflow testing
- reward credits in active, redeemed, and voided states
- generated illustrative before/after imagery written through the same storage layer as the app

## Why The Gallery Was Empty

The public site is already connected to the live FastAPI backend and database. It only shows published sessions with uploaded imagery. If no medspa has created and published cases yet, the gallery will render with empty states until real or demo data exists.
