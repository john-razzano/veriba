# Practice Profile Spec — provider-managed public page (Phase 1)

Providers need to manage the presentation of their public clinic page
(`GET /api/gallery/practices/{slug}`, consumed by the app's clinic screen and the web
gallery). Principle: **providers own presentation, Veriba owns truth** — verified
counts, custody state, and publish status remain derived and are NOT editable.

Follow existing repo conventions (routers in `app/api/routes/`, `success_response`,
Alembic migration for schema changes, storage via `get_storage()` +
`compress_for_web`, pytest coverage).

## 1. Schema (migration 0004)

Add to `practices`:

```
bio          Text, nullable            # plain text, max 600 chars (validate in schema)
avatar_key   String(500), nullable     # storage key for the clinic logo/avatar (web version)
booking_url  String(500), nullable     # https URL for "Book consult"
```

## 2. Endpoints

### PATCH `/api/practices/me`
Auth: `get_current_practice` (owner/staff). Partial update:

```
{ "name"?: str(1..255), "location"?: str(1..255), "website"?: str|null,
  "bio"?: str(0..600)|null, "booking_url"?: str|null }
```

- Validate `booking_url` and `website` as http(s) URLs (reuse/extend
  `normalize_website`); empty string → null.
- Log name/location changes (`logger.info`) — cheap audit trail for rebrand abuse.
- Response: the practice serialized as in `GET /api/practices/me` (or equivalent
  provider-facing shape already in use).

### POST `/api/practices/me/avatar`
Auth: owner/staff. Multipart `file` upload, same pipeline as session images
(`read_upload_bytes` → `compress_for_web`, reject > max size). Store at
`{practice_id}/profile/avatar.jpg` (web) — overwrite on re-upload. Response includes
the public `avatar_url`.

### DELETE `/api/practices/me/avatar` (optional, cheap)
Clears `avatar_key` and deletes the object.

## 3. Serializers

- `serialize_public_practice`: add `bio`, `avatar_url` (public URL from key),
  `booking_url`.
- The `practice` sub-object in `serialize_public_session_card` (feed/case cards):
  add `booking_url` and `avatar_url` so the app's case detail can offer booking
  without a second fetch.
- Provider-facing practice serialization: include the raw fields so the editor can
  round-trip.

## 4. Seed

Give **Veriba Atelier** a bio, booking_url, and avatar in `demo_seed.py` so the page
demos well, e.g. bio: "Editorial-grade aesthetics in Newport Beach. Every result on
this page is captured, consented, and hash-verified with Veriba." + booking_url
`https://atelier.veriba.studio/book`. Avatar: generate a simple monogram image at
seed time (reuse the placeholder-art helpers) or ship a small `seed_assets/atelier-avatar.jpg`.

## 5. Tests

- PATCH happy path (owner), 403 for members (no practice), validation failures
  (bio > 600, bad URL).
- Avatar upload → public URL resolves; re-upload overwrites; DELETE clears.
- Public gallery practice payload includes the three new fields.
- Existing tests stay green; `alembic upgrade head` clean on live DB.

## Acceptance

`curl` sequence as `owner+atelier@veriba-demo.studio`: PATCH bio + booking_url,
upload an avatar, then `GET /api/gallery/practices/veriba-atelier` shows all three
publicly. Report results + push to main.
