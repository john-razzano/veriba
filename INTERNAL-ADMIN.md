# Internal Admin Portal

The internal Veriba admin portal is intentionally hidden from the public site.

## Route

```text
http://localhost/veriba-admin/
```

## Seed A Dev Internal Admin

The Docker `fastapi` container provisions this dev internal admin account on startup.
Run the script below if you want to re-seed it or reset the password back to the documented default.

```bash
./scripts/seed_internal_admin.sh
```

Dev internal admin credentials:

```text
email: admin@veriba-internal.studio
password: veriba-internal-2026
```

## What It Can Do

- view portfolio-wide medspa counts and publishing metrics
- onboard a new medspa and owner account
- search all onboarded medspas
- inspect recent sessions and credits for any medspa
- update practice settings and owner contact details across the portfolio

## Smoke Test

```bash
./scripts/internal_admin_smoke_test.sh
```
