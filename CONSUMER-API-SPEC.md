# Consumer API Spec — saves, follows, in-app approvals

The mobile app's consumer mode (member role) has UI built for saving cases, following
clinics, and reviewing/approving a provider's post of the patient's own before & after.
These interactions currently have no backend. This document specifies the endpoints to
build. The reader is expected to follow existing repo conventions throughout:

- Routers live in `backend/app/api/routes/`, registered in `app/api/router.py`,
  responses wrapped with `success_response`, serializers in `app/services/serializers.py`.
- Auth via `get_current_user`. **Members have `practice_id = NULL`** — never use
  `get_current_practice` in these routes.
- Schema changes ship as an Alembic migration (next revision after current head,
  `alembic/versions/`), using `batch_alter_table`-safe operations so SQLite works.
- Every endpoint gets pytest coverage in `backend/tests/` (happy path + auth/404 cases),
  following the style of `test_auth.py`.

## 1. New tables (one migration)

```
saved_cases
  id           String(36) PK (uuid4, like other tables)
  user_id      FK users.id, index
  session_id   FK sessions.id, index
  created_at / updated_at (TimestampMixin)
  UNIQUE (user_id, session_id)

followed_practices
  id           String(36) PK
  user_id      FK users.id, index
  practice_id  FK practices.id, index
  created_at / updated_at
  UNIQUE (user_id, practice_id)
```

Add matching SQLAlchemy models in `app/models/domain.py` (+ exports in
`app/models/__init__.py`). Cascade cleanup: extend `demo_seed.delete_synthetic_records`
to delete saves/follows rows referencing deleted users/sessions/practices.

## 2. Saves

All require auth (any role; members are the expected caller).

- `POST /api/me/saves/{session_id}` — save a case.
  - 404 if the session doesn't exist, isn't `published`, or is archived.
  - Idempotent: if already saved return 200 with the existing record; else 201.
  - Response: `{ "session_id": ..., "saved_at": iso }`
- `DELETE /api/me/saves/{session_id}` — unsave. 200 `{ "removed": true|false }`.
- `GET /api/me/saves?limit=&offset=` — newest first. Response:
  `{ "sessions": [serialize_public_session_card + "saved_at"], "total": n }`.
  Exclude sessions that have since been unpublished/archived.

## 3. Follows

Same shape as saves, for practices:

- `POST /api/me/follows/{practice_id}` — 404 if practice doesn't exist; idempotent.
- `DELETE /api/me/follows/{practice_id}`
- `GET /api/me/follows` — `{ "practices": [serialize_public_practice + "followed_at"
  + "published_session_count"], "total": n }`.

## 4. In-app approvals (the consent loop, mockup C4)

Today a patient approves via the emailed web link (`/api/patient/{token}/consent`).
Members need the same records queryable and actionable in-app, matched by email.
**Keep the web-link flow working unchanged** — extract shared logic rather than fork it.

- `GET /api/me/approvals` — auth required. Followups where
  `lower(followup.patient_email) == lower(current_user.email)` and status is actionable
  (sent/opened — same statuses the token flow accepts). For each:
  ```
  {
    "id": followup.id,
    "requested_at": iso,
    "practice": { "id", "name", "location" },
    "session": {
      "id", "treatment", "category",
      "before_image_url", "after_image_url"   // web keys via the public URL helper
    },
    "discount_offer": { "full": $, "partial": $, "full_blur": $ }  // practice defaults
  }
  ```
  Note: these sessions are NOT published yet — this endpoint intentionally shows the
  patient their own pending case. Never serve another user's followups.
- `POST /api/me/approvals/{followup_id}/respond` — body:
  ```
  { "decision": "full" | "full_blur" | "partial" | "decline",
    "signature_svg": "<svg...>"  // required unless decision == "decline"
  }
  ```
  Must produce **exactly the same state transitions** as `submit_patient_consent` in
  `app/api/routes/patient.py` (consent tier, obscure mode, status via
  `next_status_after_consent`, credit issuance, auto-publish handling, followup
  completion). Refactor the core of that route into a shared service function
  (e.g. `app/services/consent.py`) called by both the token route and this one.
  403 if the followup's email doesn't match the caller; 409 if already completed.

## 5. Search — no new endpoint

`GET /api/gallery/sessions` already supports `query`, `category`, `location`,
`practice_slug`, pagination, and returns `available_categories`. The app will wire its
search box to this. Nothing to build; do not duplicate it.

## Acceptance

- `pytest` green, including new tests: save/unsave/list (member), follow/unfollow/list,
  approvals list only returns the caller's followups, respond mirrors the token flow's
  state transitions (assert session status + consent tier + credit created), respond is
  rejected for wrong user / already-completed followups.
- `alembic upgrade head` works on a fresh DB and on the live one.
- Web-link patient flow unchanged (existing patient tests still pass).
- Manual check with the seeded data: create a followup from the Veriba Atelier provider
  account for patient email `member@veriba.app`, then `GET /api/me/approvals` as that
  member shows it, and responding `full_blur` completes the loop.

---

## 6. Activity feed (added July 4) — `GET /api/me/activity`

Powers the Inbox "Earlier" section. **No new tables** — derive events from existing
data for the authenticated user (matched by `lower(patient_email)` on followups and
credits, same as approvals/results):

```
{ "items": [
    { "id": "<kind>-<row id>",            # stable
      "kind": "approval_completed" | "case_published" | "credit_earned" | "credit_expiring",
      "text": "<human sentence>",
      "timestamp": iso,                    # sort key, newest first
      "session_id": str | null }
  ], "total": n }
```

Sources (limit 50 after merge-sort desc by timestamp):
- **approval_completed** — completed followups: "You approved {practice}'s request to
  publish your {treatment}." ts = session.consent_at (fallback followup.updated_at).
- **case_published** — published sessions linked via the member's followups:
  "{practice} published your {treatment} before & after." ts = published_at.
  Include session_id so the app can link to /case/{id}.
- **credit_earned** — credits with matching patient_email: "You earned a ${amount}
  reward at {practice}." ts = earned_at.
- **credit_expiring** — active credits expiring within 21 days: "Your ${amount}
  reward at {practice} expires soon." ts = expires_at (these may sort into the
  future — cap displayed ts at now, or just let the client render them first).

Tests: member with a completed followup + credit sees the derived items; another
user's rows never leak; empty case returns `{"items": [], "total": 0}`.
