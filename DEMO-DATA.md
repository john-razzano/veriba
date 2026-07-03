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
- `owner+atelier@veriba-demo.studio` (Veriba Atelier — real photography, see below)

## What Gets Seeded

- 4 demo medspas
- published gallery-ready sessions plus internal pending sessions for dashboard workflow testing
- reward credits in active, redeemed, and voided states
- imagery written through the same storage layer as the app: generated illustrative
  placeholders for the three concept spas, real photography for Veriba Atelier

## Veriba Atelier (Real Photography)

`Veriba Atelier` (slug `veriba-atelier`) is the flagship demo practice used to seed the
consumer discovery feed with **18 real, watermark-free before/after pairs** (lip filler,
liquid rhinoplasty, PDO threads, BBL/Moxi laser, microneedling, under-eye). The source
files live in `backend/app/scripts/seed_assets/` — split from clinic composites, with
labels/watermarks cropped out; two `*_mid.jpg` progression extras are included for a
future multi-photo case UI but are not seeded.

- Sessions reference assets via `before_asset` / `after_asset` on `DemoSessionSpec`
  in `backend/app/scripts/demo_seed.py`; anything without assets falls back to
  generated placeholder art.
- Log in as `owner+atelier@veriba-demo.studio` (shared demo password) in the web or
  mobile app to manage or unpublish individual Atelier cases through normal provider flows.
- The mobile app's consumer Explore/Search/Saved screens read these cases from
  `GET /api/gallery/sessions`; image URLs are built from `PUBLIC_STORAGE_BASE_URL`,
  which must be publicly reachable (e.g. `https://<tunnel-domain>/storage/veriba`).
- To remove: `./scripts/reset_demo_data.sh` deletes Atelier along with the other demo
  spas — sessions, owner account, tokens, and stored media (storage prefix purge).
  There is currently no per-practice removal; add a slug filter to the reset script
  if Atelier ever needs to outlive the concept spas.

## Why The Gallery Was Empty

The public site is already connected to the live FastAPI backend and database. It only shows published sessions with uploaded imagery. If no medspa has created and published cases yet, the gallery will render with empty states until real or demo data exists.
