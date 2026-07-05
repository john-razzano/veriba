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

---

# Phase 2 (added July 5) — featured case, services, blurhash

Same conventions as Phase 1. One migration (0005) covers everything below.

## 1. Schema (migration 0005)

```
practices.featured_session_id  String(36) FK sessions.id, nullable
practices.services             JSON, nullable        # list[str], provider-curated
sessions.before_blurhash       String(64), nullable
sessions.after_blurhash        String(64), nullable
```

(Hide/reorder of the public grid is deliberately OUT of scope — unpublish already
covers removal; revisit only if providers ask.)

## 2. Featured case

- `PATCH /api/practices/me` accepts `featured_session_id: str | null`.
  Validate: session exists, belongs to the practice, and is `published` (400
  otherwise); null clears the pin.
- `GET /api/gallery/practices/{slug}`: the `featured_session` used in
  `serialize_public_practice` becomes the pinned session when set (fall back to
  latest published, as today). Also include `featured_session_id` on the
  provider-facing practice payload so the app can render the pin state.
- If the featured session is later unpublished/archived, treat as unset (don't 500).

## 3. Services (persist what the app currently keeps client-side)

- `PATCH /api/practices/me` accepts `services: list[str] | null` — max 30 items,
  each 1..60 chars, strip + dedupe case-insensitively, preserve order.
- Include `services` in provider-facing AND public practice serializers (the app's
  clinic page will render a services strip).

## 4. Blurhash placeholders

- Add the pure-python `blurhash` package to pyproject dependencies.
- In the session image upload path (and the practice avatar upload), after
  `compress_for_web`, compute a blurhash from a small thumbnail (e.g. resize the
  web image to ≤32px on the long edge first — encoding full-size images is slow);
  components 4x3. Store on the session (`before_blurhash` / `after_blurhash`) or
  practice (`avatar_blurhash` — add to the migration too, String(64) nullable).
- Serialize: `before_blurhash`/`after_blurhash` on public session payloads
  (card + case study); `avatar_blurhash` on practice payloads.
- **Backfill**: `python -m app.scripts.backfill_blurhashes` — iterate sessions with
  image keys but null hashes, fetch web image from storage, compute, save; print a
  summary. Run it once on the live DB after deploy.
- Seeded demo data should get hashes via the backfill (or compute at seed time).

## Acceptance

- Tests: featured pin happy path + wrong-practice/unpublished rejection + cleared on
  unpublish; services validation (count/length/dedupe); blurhash present after a
  fresh upload; serializers expose all new fields; existing suites green.
- `alembic upgrade head` clean on live DB; backfill run on live data — report how
  many sessions/avatars were backfilled.
- Curl check: PATCH services + featured for veriba-atelier, then
  `GET /api/gallery/practices/veriba-atelier` shows `services`, pinned
  `featured_session`, and sessions with `before_blurhash`/`after_blurhash`.
