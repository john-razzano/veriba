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

---

# §6 Member-linked followups (added July 6) — QR identity + push at send-time

Two changes: followups can be bound to a member account directly (QR scan in
the clinic) instead of relying on email string-matching, and the member push
moves from followup *creation* to followup *send* so it respects the
provider's delay. Email always still sends (once Resend exists).

## Schema (migration 0007)

- `followups.patient_user_id` — String(36) FK users.id, nullable, index.

## Member resolution (one rule, used everywhere)

`patient_user_id` wins when set; otherwise case-insensitive `patient_email`
match against member-role users. Apply this single rule in:
- the push sender's member lookup,
- `GET /api/me/approvals` and `GET /api/me/results` (currently email-only —
  a QR-bound followup with a different email on file must still reach the
  member's app).

## Endpoints

- `POST /api/sessions/{id}/followup` accepts optional `patient_user_id`.
  Validate it's an existing member-role user; 422 otherwise.
- Followup serializer (incl. the create/list responses) gains
  `member_match: {id, name, initials} | null`, resolved via the rule above —
  works for pure email matches too. The app uses it to show
  "✓ Veriba member — they'll get a notification".
- `GET /api/members/lookup` (practice auth) — `?user_id=` or `?email=`
  (exact match only, no search) → `{member: {id, name, initials} | null}`.
  Return only name/initials — never the account email.

## Push at send-time (fix)

- Move the member push out of followup creation. Fire it wherever the
  followup email actually sends: the `send_at` scheduling path (including
  `sendImmediately`), resend, and reminders 1/2.
- Copy by session state at send time:
  - `pending_after` → title = practice name, body
    "Time to add your after photo — tap to upload.",
    data `{followup_id, kind: "after_upload"}`
  - `pending_consent` / ready → existing "shared your results for review"
    body, data `{followup_id, kind: "approval"}`

## Tests

- user_id match beats email match; QR-bound followup with mismatched email
  still appears in that member's /api/me/approvals + /results.
- lookup endpoint: practice-auth only, exact match, no email leakage.
- Push fires at send time not create time; reminder sends push again;
  respects send_at delay. Full suite green; report migration number + count.

---

# §7 QR-linked followups: email becomes optional (added July 8)

The provider-side wizard now leads with "scan the patient's Veriba code"
(QR → `patient_user_id`) and only falls back to a typed email when scanning
isn't possible (patient has no app, forgot phone, etc). Right now
`patient_email` is required even when `patient_user_id` is present, which
forces a redundant field. Relax it.

## Change

`POST /api/sessions/{id}/followup`:
- `patient_email` becomes optional in the request body.
- Validation: require **either** `patient_email` **or** `patient_user_id`.
  422 if both are absent.
- When `patient_user_id` is given and `patient_email` is omitted, resolve the
  linked user and use **their own account email** as `followups.patient_email`
  internally (for the DB record / any future email-based flows). Do not
  return that email to the practice in the serializer — providers already
  only see `member_match: {id, name, initials}`, keep it that way.
- When `patient_user_id` is absent, behavior is unchanged: `patient_email`
  required, this is the no-app fallback path (emailed upload link).

## Tests

- Create with `patient_user_id` only, no email → 201, followup's stored
  `patient_email` is the linked user's account email, response doesn't leak it.
- Create with neither `patient_email` nor `patient_user_id` → 422.
- Existing email-only path unaffected.

Report: test count, any deviations.

---

# §8 In-app after-photo upload for members (added July 8)

Today a member reviewing a `pending_after` case (no after photo yet) lands on
the same `/approval/{id}` consent screen as a complete case — but nothing
gates the consent options on the after photo existing, so a member could sign
off on publishing a photo pair that doesn't exist yet. The web-only fallback
(`POST /patient/upload/{token}/photo`, token-based, no login) already has all
the processing logic; we need an **authenticated** equivalent so a logged-in
member can add the photo in-app instead of only via the emailed web link.

## Endpoint

`POST /api/me/approvals/{followup_id}/photo` (member auth, multipart
`file`):

- Resolve the followup the same way `respond` does: 404 unless it belongs to
  the current member (`patient_user_id == me.id` OR
  `patient_user_id IS NULL AND lower(patient_email) == lower(me.email)`).
- 409 if `followup.status` is `expired`/`cancelled`/`completed`, or if the
  session already has an `after_image_key` (photo already added — re-upload
  isn't this endpoint's job).
- Otherwise, run the **exact same processing** as
  `upload_patient_photo` in `app/api/routes/patient.py`: compress, hash,
  blurhash, set `after_image_key`/`after_original_image_key`/dimensions/
  `after_capture_hash`/`after_captured_at`, `after_provenance = "Uploaded by
  patient in-app"` (distinct string from the web-link path, for the
  provenance audit trail), `session.status = pending_consent`. Do **not**
  touch `followup.status` or create a credit here — unlike the web flow,
  consent is a separate explicit step the member takes right after via the
  existing `respond` endpoint, so leave the followup `sent`/`opened` as-is.
- Response: the same shape as `serialize_public_case_study`/approval item's
  `session` sub-object (`before_image_url`, `after_image_url`, blurhashes)
  so the app can update its local state without a full re-fetch.

## Tests

- Happy path: upload → 200, session status becomes `pending_consent`,
  `after_image_key` set, response includes `after_image_url`.
- 409 when session already has an after photo.
- 404 for a followup that isn't the caller's (email or user_id mismatch).
- 404/409 for expired/cancelled/completed followup status.
- Existing `/patient/upload/{token}/photo` (web link) path unaffected.

Report: test count, any deviations.

---

# §9 Member-facing rewards list (added July 12)

The app's Inbox activity feed already surfaces "You earned a $150 reward at
{practice}" and "expires soon" events (`GET /api/me/activity`, kinds
`credit_earned`/`credit_expiring`), but tapping either currently 404s in the
app — the frontend was routing to the public case page, and a credit's
session isn't always publicly published (e.g. blurred/partial consent tiers
still earn a reward without going public). Members need an actual place to
see their rewards, and the activity events need enough data to deep-link
there instead of into the public feed.

## New endpoint

`GET /api/me/credits` (member auth, no query params for now):

- Same ownership filter `list_activity` already uses for credits:
  `func.lower(Credit.patient_email) == current_user.email.lower()` (this
  already correctly covers QR-linked members too, since §7 backfills
  `followup.patient_email`/`credit.patient_email` with the linked account's
  own email even when no email was typed).
- Newest first (`earned_at desc`).
- Per item, reuse `serialize_credit` and add on top: `practice: {id, name,
  location}` and `session: {id, treatment, after_image_url}` (thumbnail so
  the list isn't just text) — `after_image_url` via the existing
  `_image_url` helper, falling back to `before_image_url` if
  `after_image_key` isn't set (can be null, that's fine).
- Response: `{"credits": [...], "total": n}`.

## Activity event change

In `list_activity`, add `"credit_id": credit.id` to both the `credit_earned`
and `credit_expiring` event dicts (alongside the existing `session_id`) so
the app can deep-link to the specific reward rather than guessing from
session_id.

## Tests

- Member with 2 credits at different practices → both returned, newest
  first, correct practice/session nesting.
- Member with zero credits → `{"credits": [], "total": 0}`, 200 not 404.
- Credit belonging to a different member's email is excluded.
- QR-linked credit (no typed email on the followup) still appears — confirms
  the §7 email-backfill makes the plain email-match filter sufficient.
- `list_activity` response now includes `credit_id` on `credit_earned` and
  `credit_expiring` events; existing fields unchanged.

Report: test count, any deviations.
