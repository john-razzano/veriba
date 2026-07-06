# Growth Spec (Phase 3) — consults, multi-photo, hours, push, analytics

Written July 5, 2026 for the backend agent. Frontend wiring happens in
parallel against this contract; keep the `success_response` envelope and
serializer conventions used everywhere else. Five independent workstreams —
land them as separate commits in this order (frontend needs 1 and 2 first).

Auth notes: "member" = `role == "member"` (see `app/api/routes/me.py` guards);
"practice user" = the existing practice-scoped dependency used by
`sessions.py`/`practices.py`.

---

## 1. Consult requests (member → practice inbox)

A member asks a clinic for a consult from a case or clinic page. **Not chat**:
one message, provider reads it and responds off-platform, then marks it
handled. Deliberately no threads/read-receipts — that's a later phase.

### Schema (migration 0006, together with §2–4 columns if you prefer one migration)

`consult_requests` table:

| column | type | notes |
| --- | --- | --- |
| id | String(36) uuid pk | |
| practice_id | FK practices.id, index | |
| user_id | FK users.id, index | requesting member |
| session_id | FK sessions.id, nullable | the case they came from, if any |
| message | Text, nullable | member's note |
| contact_email | String(255) | prefill from user.email, member can edit |
| contact_phone | String(50), nullable | |
| status | String(20), default `new` | `new` / `handled` |
| handled_at | DateTime(tz), nullable | |
| + TimestampMixin | | |

### Endpoints

- `POST /api/me/consults` (member) — body `{practice_id, session_id?, message?, contact_email, contact_phone?}`.
  Validate practice exists. 429-style guard: reject if the member already has
  a `new` request for the same practice (`409 conflict`, message "You already
  have an open request with this clinic."). Returns the serialized request.
- `GET /api/me/consults` (member) — their own requests, newest first (so the
  app can show "requested" state on the clinic page).
- `GET /api/consults?status=new|handled|all` (practice user) — practice's
  inbox, newest first, `{consults: [...], total}`. Include member name +
  initials, contact fields, session treatment + after-image thumb (reuse
  `serialize_public_session_card` fields for the session part or inline
  `{id, treatment, after_image_url}`).
- `POST /api/consults/{id}/handled` (practice user, own practice only) — sets
  status + handled_at. Idempotent.

Serializer: `{id, practice: {id, name, widget_slug}, member: {name, initials}, session: {...}|null, message, contact_email, contact_phone, status, created_at, handled_at}`.
For the member-facing list, omit nothing (it's their own data).

### Activity

Add a `consult_request` event kind to `GET /api/me/activity` derivation
(member sees "You requested a consult with {practice}").

---

## 2. Multi-photo cases (`photos[]`)

Only two triptychs exist in `seed_assets/` (`woodbury-lip-fillers_mid.jpg`,
`woodbury-lip-volume_mid.jpg`) — that's fine, the contract matters more than
volume.

### Schema

`session_photos` table:

| column | type | notes |
| --- | --- | --- |
| id | String(36) uuid pk | |
| session_id | FK sessions.id, index | |
| image_key | String(500) | |
| blurhash | String(64), nullable | compute like migration 0005 backfill |
| label | String(100), nullable | e.g. "2 weeks", "Side profile" |
| sort_order | Integer, default 0 | |
| + TimestampMixin | | |

These are **extra after-side angles/stages**; before/after keys on `sessions`
stay canonical and hash-locked. Privacy: photos ride the session's consent —
they are only ever serialized where `after_image_url` is (published public
payloads + the owning practice's session detail). No separate consent state.

### Endpoints / serializers

- `serialize_public_case_study` grows `photos: [{id, url, blurhash, label}]`
  ordered by sort_order (empty list when none — not null).
- Practice-side `serialize_session_detail` grows the same.
- `POST /api/sessions/{id}/photos` (practice user) — multipart upload like the
  avatar endpoint; optional `label`. `DELETE /api/sessions/{id}/photos/{photo_id}`.
  (No app UI for these yet, but the seed and future wizard need them.)

### Seed

`demo_seed.py`: attach the two `_mid.jpg` files as `session_photos` on their
matching Veriba Atelier sessions with label "In progress". Upload to MinIO
alongside the existing assets; compute blurhash.

---

## 3. Practice hours (display-only)

- Migration: `practices.hours` — JSON, nullable. Shape the app will send:
  `{"mon": "9:00–17:00", "tue": "9:00–17:00", ..., "sun": null}` (null = closed).
  Store as given; no server-side parsing beyond "is a dict of day→string|null".
- `PATCH /api/practices/me` accepts `hours`.
- `serialize_public_practice` + practice self-serializer include `hours`.
- Seed Veriba Atelier with Mon–Fri 9:00–17:00, Sat 10:00–14:00, Sun closed.
- Map is frontend-only (opens Apple/Google Maps with the location string) —
  nothing needed server-side; `lat`/`lng` columns stay dormant.

---

## 4. Push notification plumbing (Expo)

Goal: tokens stored and the sender written, but **delivery stays dark** until
John configures the APNs key in EAS — do not block anything on it.

### Schema

`push_tokens` table: `id, user_id FK index, token String(255) unique,
platform String(10) ("ios"/"android"), + TimestampMixin`.

### Endpoints

- `POST /api/me/push-token` (any authed user) — `{token, platform}`. Upsert on
  token; re-point user_id if the token moved accounts (device changed login).
- `DELETE /api/me/push-token` — body `{token}`; called on logout.

### Sender

`app/services/push.py`: `send_push(user_ids, title, body, data)` — POST to
`https://exp.host/--/api/v2/push/send` (batch, chunk 100). httpx is fine; call
via the existing Celery worker so requests don't block. Deactivate (delete)
tokens that come back `DeviceNotRegistered`.

Hook it where followups notify members: on followup creation/resend, if the
`patient_email` matches a member user with push tokens, send
"{practice} shared your results for review" with `data: {followup_id}` in the
same place `_send_followup_email` is called. Log-and-continue on any failure.

### Tests

Mock the Expo endpoint; test token upsert/move/delete, chunking, and the
DeviceNotRegistered cleanup. No live sends.

---

## 5. Analytics counts (cheap, derived)

The app's provider surfaces will show per-case saves alongside the existing
`page_views`, and follower count on the dashboard.

- `serialize_session_detail` (practice-side) grows `saves_count`
  (count of `saved_cases` per session; single grouped query, no N+1).
- Practice-side session **list** payload grows the same (grouped subquery like
  `_practice_count_subquery`).
- `GET /api/practices/me` response grows `followers_count`
  (count of `followed_practices`).
- No new tables, no timeseries — deliberately just counts this phase.

---

## Acceptance

- `alembic upgrade head` from 0005 is clean on prod data; downgrades work.
- Member can create a consult request; duplicate-`new` returns 409; provider
  lists + marks handled; member activity shows the event.
- Public case study for the two Woodbury triptych sessions returns one photo
  in `photos[]` with a blurhash; all other cases return `[]`.
- `PATCH /api/practices/me` round-trips `hours`; public practice payload
  includes it; Atelier seeded with hours.
- Push token upsert/delete works; sender unit-tested against a mocked Expo
  endpoint; followup creation attempts a push for member patients and never
  fails the request if push errors.
- Session list/detail include `saves_count`; `/api/practices/me` includes
  `followers_count`; test with a member who saved a case.
- Full suite green; report new test count + any deviations from this spec.
