# Veribā Backend — API Endpoint Plan

## Architecture Overview

```
Internet
  │
  ▼
Cloudflare Edge (caches static assets — images, widget JS)
  │
  ▼
Cloudflare Tunnel
  │
  ▼
┌─────────────────────────────────────────────┐
│  Caddy (reverse proxy + auto HTTPS)         │
│  ├── /api/*    → fastapi:8000               │
│  ├── /storage/* → minio:9000 (presigned)    │
│  └── /admin    → minio:9001 (console)       │
└─────────────────────────────────────────────┘
  │           │            │
  ▼           ▼            ▼
FastAPI    PostgreSQL    MinIO
:8000      :5432         :9000/:9001
```

**Image delivery**: MinIO serves images with long-lived cache headers (`Cache-Control: public, max-age=31536000`). Cloudflare automatically caches these at edge nodes worldwide, so the widget gallery loads with CDN-like performance without a separate CDN service. First request hits MinIO; subsequent requests serve from Cloudflare's cache.

**Base URL**: `https://api.veriba.agence.studio` (or whatever domain you route through the tunnel)

**Auth**: JWT Bearer tokens for all protected endpoints. `Authorization: Bearer <token>`

**Response format**: All responses follow this structure:
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

---

## 1. Auth Endpoints

No auth required for these — they issue/manage tokens.

### `POST /api/auth/register`
Create a new user account.
```
Request:
{
  "email": "john@luxeaesthetics.com",
  "password": "...",
  "name": "John Doe",
  "practice_name": "Luxe Aesthetics",
  "practice_location": "Reno, NV",
  "practice_website": "luxeaesthetics.com"
}

Response:
{
  "user": { "id", "email", "name" },
  "practice": { "id", "name", "location", "widget_slug" },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```
**Notes**: Creates both a user and a practice in one call. The first user to register a practice becomes the owner. Generates a `widget_slug` from the practice name (e.g., "luxe-aesthetics").

### `POST /api/auth/login`
Authenticate and receive tokens.
```
Request:
{
  "email": "john@luxeaesthetics.com",
  "password": "..."
}

Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id", "email", "name", "practice_id" }
}
```
**Notes**: Access tokens expire in 30 minutes. Refresh tokens expire in 7 days.

### `POST /api/auth/refresh`
Exchange a refresh token for a new access token.
```
Request:
{
  "refresh_token": "eyJ..."
}

Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### `POST /api/auth/logout`
Invalidate the current refresh token.
```
Headers: Authorization: Bearer <access_token>

Response:
{
  "success": true
}
```

---

## 2. User / Profile Endpoints

All require auth. Users can only access their own data.

### `GET /api/users/me`
Get the current user's profile.
```
Response:
{
  "id": "uuid",
  "email": "john@luxeaesthetics.com",
  "name": "John Doe",
  "initials": "JD",
  "practice_id": "uuid",
  "created_at": "2026-03-16T..."
}
```

### `PATCH /api/users/me`
Update user profile fields.
```
Request:
{
  "name": "John D.",
  "email": "newemail@luxeaesthetics.com"
}
```

### `PATCH /api/users/me/password`
Change password.
```
Request:
{
  "current_password": "...",
  "new_password": "..."
}
```

---

## 3. Practice Endpoints

All require auth. Users can only access their own practice.

### `GET /api/practices/me`
Get the current user's practice details.
```
Response:
{
  "id": "uuid",
  "name": "Luxe Aesthetics",
  "location": "Reno, NV",
  "coordinates": { "lat": 39.5296, "lng": -119.8138 },
  "website": "luxeaesthetics.com",
  "widget_slug": "luxe-aesthetics",
  "default_discounts": {
    "full": 150,
    "partial": 75,
    "full_blur": 25
  },
  "owner_id": "uuid",
  "created_at": "...",
  "updated_at": "..."
}
```

### `PATCH /api/practices/me`
Update practice settings.
```
Request:
{
  "name": "Luxe Aesthetics & Wellness",
  "location": "Reno, NV",
  "website": "luxeaesthetics.com",
  "default_discounts": {
    "full": 200,
    "partial": 100,
    "full_blur": 50
  }
}
```

### `GET /api/practices/me/stats`
Dashboard statistics.
```
Response:
{
  "total_published": 127,
  "total_pending": 3,
  "total_declined": 2,
  "profile_views_total": 892,
  "profile_views_this_week": 64,
  "seo_impressions_total": 4200,
  "seo_impressions_this_week": 340
}
```

---

## 4. Session Endpoints

Core CRUD for photo sessions. All require auth, scoped to user's practice.

### `GET /api/sessions`
List all sessions for the practice.
```
Query params:
  ?status=published|pending_consent|pending_after|declined|draft
  ?category=Botox|Fillers|Skin|Hair|Body
  ?sort=created_at|updated_at|page_views
  ?order=asc|desc
  ?limit=20
  &offset=0

Response:
{
  "sessions": [
    {
      "id": "uuid",
      "patient_initials": "AM",
      "treatment": "Botox – Forehead",
      "category": "Botox",
      "status": "published",
      "obscure_mode": "none",
      "consent_tier": "full",
      "before_image_url": "https://...",
      "after_image_url": "https://...",
      "page_views": 24,
      "captured_at": "2026-03-16T14:14:00Z",
      "published_at": "2026-03-16T14:19:00Z",
      "created_at": "...",
      "updated_at": "..."
    },
    ...
  ],
  "total": 127,
  "limit": 20,
  "offset": 0
}
```

### `POST /api/sessions`
Create a new session (starts as "draft" or "pending_after").
```
Request:
{
  "patient_initials": "AM",
  "treatment": "Botox – Forehead",
  "category": "Botox",
  "status": "draft"
}

Response:
{
  "id": "uuid",
  "patient_initials": "AM",
  "treatment": "Botox – Forehead",
  "category": "Botox",
  "status": "draft",
  "before_image_url": null,
  "after_image_url": null,
  "seo": null,
  "chain_of_custody": [],
  "created_at": "..."
}
```
**Notes**: Session starts with no images. Images are uploaded separately via the image endpoints. Status can be "draft" (just created) or "pending_after" (has before image, waiting for after).

### `GET /api/sessions/:id`
Get full session detail including chain of custody.
```
Response:
{
  "id": "uuid",
  "patient_initials": "AM",
  "treatment": "Botox – Forehead",
  "category": "Botox",
  "status": "published",
  "obscure_mode": "none",

  "before_image_url": "https://...",
  "after_image_url": "https://...",

  "chain_of_custody": {
    "all_verified": true,
    "checkpoints": [
      {
        "step": "captured",
        "label": "Captured in-app",
        "detail": "Photo taken via Veribā camera",
        "timestamp": "2026-03-16T14:14:00Z",
        "hash": "a3f8c912...d7b1",
        "verified": true
      },
      {
        "step": "signed",
        "label": "Cryptographically signed",
        "detail": "SHA-256 hash recorded at capture",
        "timestamp": "2026-03-16T14:14:00Z",
        "hash": "a3f8c912...d7b1",
        "verified": true
      },
      {
        "step": "geotagged",
        "label": "Geo-tagged & timestamped",
        "detail": "Reno, NV (39.53°N, 119.81°W)",
        "timestamp": "2026-03-16T14:14:00Z",
        "hash": null,
        "verified": true
      },
      {
        "step": "consent",
        "label": "Consent recorded",
        "detail": "Full face · Patient signature on file",
        "timestamp": "2026-03-16T14:18:00Z",
        "hash": null,
        "verified": true
      },
      {
        "step": "published",
        "label": "Published to web",
        "detail": "Widget + Veribā Gallery + sitemap updated",
        "timestamp": "2026-03-16T14:19:00Z",
        "hash": "d7b1e483...f2a9",
        "verified": true
      }
    ]
  },

  "consent_tier": "full",
  "consent_signature_url": "https://...",
  "consent_at": "2026-03-16T14:18:00Z",
  "discount_applied": 150,

  "seo": {
    "title": "Botox – Forehead Before & After | Reno, NV",
    "alt_text": "Botox forehead horizontal lines treatment, 20 units, before and after at Luxe Aesthetics Reno NV, March 2026",
    "meta_description": "See verified botox forehead results at Luxe Aesthetics in Reno, NV. Horizontal line reduction with 20 units. Before photo at consultation, after captured 14 days post-treatment.",
    "filename": "botox-forehead-horizontal-lines-luxe-aesthetics-reno-nv-2026-03-001.jpg",
    "url_slug": "botox-forehead-horizontal-lines-reno-nv-2026-03-001"
  },

  "page_views": 24,
  "captured_at": "2026-03-16T14:14:00Z",
  "published_at": "2026-03-16T14:19:00Z",
  "created_at": "...",
  "updated_at": "..."
}
```

### `PATCH /api/sessions/:id`
Update session fields (treatment, obscure mode, patient initials, etc.)
```
Request:
{
  "treatment": "Botox – Forehead Lines",
  "obscure_mode": "eyes",
  "patient_initials": "A.M."
}

Response: updated session object
```
**Notes**: When treatment or obscure_mode changes on a published session, the SEO metadata is auto-regenerated and the publish hash is updated in the chain of custody.

### `DELETE /api/sessions/:id`
Delete a session (soft delete — marks as archived).

### `POST /api/sessions/:id/unpublish`
Unpublish a published session.
```
Response: session with status changed to "unpublished"
```

---

## 5. Image Endpoints

Handle photo upload, retrieval, and processing. All require auth.

### `POST /api/sessions/:id/images/before`
Upload the "before" photo.
```
Request: multipart/form-data
  - file: image file (JPEG/PNG)
  - capture_hash: "a3f8c912..." (SHA-256 computed on device)
  - capture_lat: 39.5296
  - capture_lng: -119.8138
  - captured_at: "2026-03-16T14:14:00Z"

Response:
{
  "image_url": "https://...",
  "capture_hash": "a3f8c912...",
  "capture_coordinates": { "lat": 39.5296, "lng": -119.8138 },
  "captured_at": "2026-03-16T14:14:00Z",
  "server_hash": "a3f8c912...",
  "hash_match": true,
  "chain_of_custody_updated": true
}
```
**Notes**: The server re-computes the SHA-256 hash and compares it to the client-provided hash. If they match, the chain of custody "captured" and "signed" checkpoints are marked verified. The image is stored in MinIO under `{practice_id}/sessions/{session_id}/before.jpg`. Session status auto-transitions to "pending_after" if no after image exists, or "pending_consent" if both images are present.

### `POST /api/sessions/:id/images/after`
Upload the "after" photo. Same request/response format as before.

**Notes**: Session status auto-transitions to "pending_consent" once both images are uploaded. If the session was in "pending_after" status, this completes the pair.

### `GET /api/sessions/:id/images/before`
Get the before image URL. The stored image already has obscuring applied (done on-device before upload).
```
Query params:
  ?size=thumb|medium|full

Response:
{
  "url": "https://...",
  "size": "medium",
  "width": 800,
  "height": 1000
}
```

### `POST /api/sessions/:id/images/before/presign`
Get a presigned upload URL for direct-to-MinIO upload (alternative to multipart).
```
Response:
{
  "upload_url": "https://minio.../presigned...",
  "expires_in": 3600,
  "fields": { ... }
}
```
**Notes**: For large images, presigned uploads are faster because the file goes directly to MinIO instead of through FastAPI. The app then calls a separate endpoint to confirm the upload and trigger hash verification.

---

## 6. Consent Endpoints

### `POST /api/sessions/:id/consent`
Record patient consent for a session.
```
Request:
{
  "consent_tier": "full",
  "obscure_mode": "none",
  "discount_applied": 150,
  "signature_svg": "M10 35 Q30 10 50 30 T90 25..."
}

Response:
{
  "consent_tier": "full",
  "obscure_mode": "none",
  "consent_at": "2026-03-16T14:18:00Z",
  "discount_applied": 150,
  "signature_url": "https://...",
  "chain_of_custody_updated": true,
  "session_status": "pending_consent" → changes to ready for publish
}
```
**Notes**: The signature SVG is rendered to a PNG and stored in MinIO. The consent checkpoint in chain of custody is marked verified. If consent_tier is "decline", session status changes to "declined".

### `POST /api/sessions/:id/consent/decline`
Shortcut to decline consent.
```
Response: session with status "declined", no signature stored
```

---

## 7. Publish Endpoints

### `POST /api/sessions/:id/publish`
Publish a session — generates SEO metadata and marks as live.
```
Request:
{
  "destinations": ["widget", "gallery"],
  "treatment_details": "20 units, horizontal forehead lines"
}

Response:
{
  "status": "published",
  "published_at": "2026-03-16T14:19:00Z",
  "publish_hash": "d7b1e483...",
  "seo": {
    "title": "Botox Forehead Horizontal Lines Before & After | Luxe Aesthetics, Reno NV",
    "alt_text": "Botox forehead horizontal lines, 20 units, before and after at Luxe Aesthetics Reno NV March 2026",
    "meta_description": "See verified botox forehead results...",
    "filename": "botox-forehead-horizontal-lines-luxe-aesthetics-reno-nv-2026-03-001.jpg",
    "url_slug": "botox-forehead-horizontal-lines-reno-nv-2026-03-001"
  },
  "destinations": ["widget", "gallery"],
  "chain_of_custody_updated": true
}
```
**Notes**: 
- SEO metadata is auto-generated. The filename and slug include: treatment, area, technique/detail, practice name, location, date, and a sequential number to ensure uniqueness.
- A publish hash is computed from: original capture hash + consent data + publish timestamp. This creates the final link in the chain of custody.
- `treatment_details` is an optional free-text field the provider can fill in to add specificity (units, product name, technique). This feeds into the SEO generation for more unique metadata.

### `GET /api/sessions/:id/seo`
Get the generated SEO metadata for a session (read-only).

### `POST /api/sessions/:id/seo/regenerate`
Force regeneration of SEO metadata (e.g., after editing the treatment).

---

## 8. Patient Follow-Up Endpoints

Provider-facing endpoints to schedule follow-up emails to patients. Requires auth.

### `POST /api/sessions/:id/followup`
Schedule a follow-up email to the patient requesting their "after" photo.
```
Request:
{
  "patient_email": "patient@email.com",
  "patient_first_name": "Amanda",
  "send_at": "2026-03-30T10:00:00Z",
  "message": "Hi Amanda, your Botox results should be fully visible now! Please use the link below to submit your after photo and claim your $150 reward."
}

Response:
{
  "id": "uuid",
  "session_id": "uuid",
  "patient_email": "patient@email.com",
  "patient_first_name": "Amanda",
  "send_at": "2026-03-30T10:00:00Z",
  "status": "scheduled",
  "upload_token": "tok_abc123...",
  "upload_url": "https://veriba.agence.studio/upload/tok_abc123...",
  "created_at": "..."
}
```
**Notes**: 
- If `send_at` is null or in the past, the email is sent immediately.
- The `upload_token` is a unique, cryptographically random token (URL-safe, 64 chars) tied to this specific session. It expires after 30 days.
- The `upload_url` is what gets embedded in the email. No login required — the token IS the auth.
- The email is sent via Resend (transactional email API). A background Celery worker picks up scheduled emails at the right time.
- The `message` field is optional — if omitted, a default template is used based on the treatment type.

### `GET /api/sessions/:id/followups`
List all follow-up emails for a session (history of sends, resends).
```
Response:
{
  "followups": [
    {
      "id": "uuid",
      "patient_email": "patient@email.com",
      "status": "sent",
      "sent_at": "2026-03-30T10:00:12Z",
      "opened_at": "2026-03-30T14:22:00Z",
      "upload_completed_at": null,
      "upload_token": "tok_abc123...",
      "expires_at": "2026-04-29T10:00:00Z"
    }
  ]
}
```

### `POST /api/sessions/:id/followup/:followup_id/resend`
Resend a follow-up email (generates a new token, invalidates the old one).

### `DELETE /api/sessions/:id/followup/:followup_id`
Cancel a scheduled (not yet sent) follow-up.

### Default Treatment Timelines

When the provider doesn't specify a `send_at`, the system auto-suggests a date based on treatment type:

| Treatment Category | Default Follow-Up Delay |
|---|---|
| Botox (all areas) | 14 days |
| Dermal Fillers (all areas) | 7 days |
| Chemical Peel | 10 days |
| Microneedling | 7 days |
| Laser Resurfacing | 14 days |
| Hair Restoration – PRP | 30 days |
| CoolSculpting | 60 days |
| Thread Lift | 21 days |
| Other | 14 days (default) |

---

## 9. Patient Upload Portal Endpoints

These are **unauthenticated** — accessed via the unique upload token in the email link. No login required.

### `GET /api/patient/upload/:token`
Validate the token and return session context for the upload page.
```
Response:
{
  "valid": true,
  "practice_name": "Luxe Aesthetics",
  "patient_first_name": "Amanda",
  "treatment": "Botox – Forehead",
  "before_image_url": "https://...",
  "captured_at": "2026-03-16T14:14:00Z",
  "reward_amount": 150,
  "reward_description": "$150 off your next visit",
  "consent_options": [
    { "tier": "full", "label": "Full face — no obscuring", "reward": "$150 off" },
    { "tier": "partial", "label": "Eyes blurred", "reward": "$75 off" },
    { "tier": "full_blur", "label": "Full face blur", "reward": "$25 off" },
    { "tier": "decline", "label": "I don't want my photos shared", "reward": "No reward" }
  ],
  "expires_at": "2026-04-29T10:00:00Z"
}

Error (expired/invalid):
{
  "valid": false,
  "error": "This link has expired. Please contact your provider for a new one."
}
```
**Notes**: The patient sees the "before" photo they took at the office, the treatment name, and the reward tiers. This reassures them the link is legitimate. The before image shown uses the practice's default obscuring unless consent was already given.

### `POST /api/patient/upload/:token/photo`
Patient uploads their "after" photo.
```
Request: multipart/form-data
  - file: image file (JPEG/PNG)

Response:
{
  "success": true,
  "message": "Photo uploaded successfully! Please select your sharing preference below to claim your reward."
}
```
**Notes**: The server computes a SHA-256 hash and records the upload timestamp. The after image chain-of-custody notes that it was "uploaded by patient via email link" (different provenance than in-app capture, which is noted in the chain of custody). Session status transitions to "pending_consent".

### `POST /api/patient/upload/:token/consent`
Patient selects their consent tier and claims the reward.
```
Request:
{
  "consent_tier": "full",
  "signature_data": "base64 encoded signature image or null"
}

Response:
{
  "success": true,
  "consent_tier": "full",
  "reward_earned": {
    "id": "uuid",
    "amount": 150,
    "description": "$150 off your next visit",
    "code": "VERIBA-AM-150-X8K2",
    "status": "active",
    "expires_at": "2026-09-16T00:00:00Z"
  },
  "message": "Thank you! Your reward code is VERIBA-AM-150-X8K2. Show this to your provider at your next visit."
}
```
**Notes**: 
- A credit is created in the rewards ledger, linked to this session.
- A unique reward code is generated (human-readable, practice-prefixed).
- The token is marked as "completed" and can no longer be used for uploads.
- If the patient already gave consent in-office, this step is skipped and the upload alone triggers the reward.
- The session auto-transitions based on practice settings: either to "pending_consent" (provider reviews before publishing) or auto-publishes if the practice has enabled auto-publish.

### `GET /api/patient/upload/:token/status`
Check the status of an upload (for the confirmation page).
```
Response:
{
  "photo_uploaded": true,
  "consent_given": true,
  "reward_earned": true,
  "reward_code": "VERIBA-AM-150-X8K2",
  "session_status": "published"
}
```

---

## 10. Credits / Rewards Ledger Endpoints

Full credits management system. Requires auth, scoped to practice.

### `GET /api/credits`
List all credits/rewards for the practice.
```
Query params:
  ?status=active|redeemed|expired|voided
  ?patient_initials=AM
  ?sort=created_at|expires_at|amount
  &limit=20
  &offset=0

Response:
{
  "credits": [
    {
      "id": "uuid",
      "session_id": "uuid",
      "patient_initials": "AM",
      "patient_email": "patient@email.com",
      "code": "VERIBA-AM-150-X8K2",
      "amount": 150,
      "description": "$150 off next visit",
      "consent_tier": "full",
      "status": "active",
      "earned_at": "2026-03-30T15:00:00Z",
      "expires_at": "2026-09-30T00:00:00Z",
      "redeemed_at": null,
      "redeemed_by": null
    },
    ...
  ],
  "total": 42,
  "total_active_value": 4250,
  "total_redeemed_value": 2100,
  "total_expired_value": 600
}
```

### `GET /api/credits/:id`
Get a single credit's detail.

### `POST /api/credits/:id/redeem`
Mark a credit as redeemed (when the patient uses it at their next visit).
```
Request:
{
  "redeemed_by": "John Razzano",
  "notes": "Applied to lip filler appointment 4/15"
}

Response:
{
  "id": "uuid",
  "status": "redeemed",
  "redeemed_at": "2026-04-15T10:30:00Z",
  "redeemed_by": "John Razzano",
  "notes": "Applied to lip filler appointment 4/15"
}
```

### `POST /api/credits/:id/void`
Void a credit (e.g., if photos were unsuitable).
```
Request:
{
  "reason": "After photo quality insufficient — requesting retake"
}

Response:
{
  "id": "uuid",
  "status": "voided",
  "void_reason": "After photo quality insufficient — requesting retake"
}
```

### `GET /api/credits/lookup/:code`
Look up a credit by its reward code (for quick redemption at checkout).
```
Response:
{
  "id": "uuid",
  "code": "VERIBA-AM-150-X8K2",
  "amount": 150,
  "status": "active",
  "patient_initials": "AM",
  "treatment": "Botox – Forehead",
  "expires_at": "2026-09-30T00:00:00Z"
}
```
**Notes**: This is what the front desk would use — patient says "I have a Veribā reward," staff enters the code, sees the amount and validity, and applies it.

### `GET /api/credits/stats`
Aggregate credit statistics for the practice dashboard.
```
Response:
{
  "total_issued": 42,
  "total_active": 18,
  "total_redeemed": 20,
  "total_expired": 3,
  "total_voided": 1,
  "active_value": 4250,
  "redeemed_value": 2100,
  "average_credit_amount": 112,
  "redemption_rate": 0.476,
  "credits_expiring_30d": 5,
  "credits_expiring_30d_value": 575
}
```

---

## 11. Widget / Public Endpoints

These are **unauthenticated** — they serve data to the embeddable JS widget and the Veribā Gallery. Rate-limited by practice slug.

### `GET /api/widget/:practice_slug/gallery`
Get all published sessions for a practice's widget.
```
Query params:
  ?category=Botox|Fillers|Skin|Hair|Body
  ?limit=20
  &offset=0

Response:
{
  "practice": {
    "name": "Luxe Aesthetics",
    "location": "Reno, NV"
  },
  "sessions": [
    {
      "id": "uuid",
      "treatment": "Botox – Forehead",
      "category": "Botox",
      "before_image_url": "https://...",
      "after_image_url": "https://...",
      "obscure_mode": "none",
      "seo": { "title", "alt_text", "filename" },
      "chain_of_custody": {
        "all_verified": true,
        "checkpoint_count": 5
      },
      "published_at": "2026-03-16T14:19:00Z"
    },
    ...
  ],
  "total": 127
}
```
**Notes**: Images are served as-is — obscuring was already applied on-device before upload. Chain of custody is summarized (not full detail) for the public view.

### `GET /api/widget/:practice_slug/session/:id`
Get a single session's public detail (for the lightbox view in the widget).

### `POST /api/widget/:practice_slug/session/:id/view`
Track a page view. Called by the widget JS when a user views a session detail.
```
Response: { "recorded": true }
```

---

## 12. Health / System Endpoints

### `GET /api/health`
Health check for monitoring.
```
Response:
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "connected",
  "storage": "connected",
  "uptime": "3d 14h 22m"
}
```

### `GET /api/health/db`
Database connectivity check.

### `GET /api/health/storage`
MinIO connectivity check.

---

## Database Schema (High-Level)

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| email | VARCHAR(255) | unique |
| password_hash | VARCHAR(255) | bcrypt |
| name | VARCHAR(255) | |
| initials | VARCHAR(5) | auto-derived |
| role | VARCHAR(20) | enum: owner, provider, staff |
| practice_id | UUID | FK → practices |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `practices`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | VARCHAR(255) | |
| location | VARCHAR(255) | |
| lat | DECIMAL(10,7) | |
| lng | DECIMAL(10,7) | |
| website | VARCHAR(255) | |
| widget_slug | VARCHAR(100) | unique, URL-safe |
| default_discount_full | INTEGER | cents |
| default_discount_partial | INTEGER | cents |
| default_discount_blur | INTEGER | cents |
| credit_expiration_days | INTEGER | default 180 (6 months), range 30–365 |
| auto_publish | BOOLEAN | default false |
| owner_id | UUID | FK → users |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `sessions`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| practice_id | UUID | FK → practices |
| patient_initials | VARCHAR(10) | |
| treatment | VARCHAR(255) | |
| category | VARCHAR(50) | enum: Botox, Fillers, Skin, Hair, Body, Other |
| status | VARCHAR(20) | enum: draft, pending_after, pending_consent, ready_to_publish, published, declined, unpublished |
| obscure_mode | VARCHAR(10) | enum: none, eyes, upper, full |
| treatment_details | TEXT | optional free-text (units, product, technique) |
| before_image_key | VARCHAR(500) | MinIO object key |
| after_image_key | VARCHAR(500) | MinIO object key |
| capture_hash | VARCHAR(64) | SHA-256 of before image |
| capture_lat | DECIMAL(10,7) | |
| capture_lng | DECIMAL(10,7) | |
| captured_at | TIMESTAMPTZ | |
| sign_hash | VARCHAR(64) | server-verified hash |
| signed_at | TIMESTAMPTZ | |
| after_capture_hash | VARCHAR(64) | SHA-256 of after image |
| after_captured_at | TIMESTAMPTZ | |
| consent_tier | VARCHAR(20) | enum: full, partial, full_blur, decline, null |
| consent_signature_key | VARCHAR(500) | MinIO key for signature PNG |
| consent_at | TIMESTAMPTZ | |
| discount_applied | INTEGER | cents |
| publish_hash | VARCHAR(64) | hash of (capture_hash + consent + timestamp) |
| published_at | TIMESTAMPTZ | |
| published_destinations | JSONB | ["widget", "gallery", "gbp"] |
| seo_title | VARCHAR(500) | |
| seo_alt_text | VARCHAR(500) | |
| seo_meta_description | TEXT | |
| seo_filename | VARCHAR(255) | unique |
| seo_url_slug | VARCHAR(255) | unique |
| page_views | INTEGER | default 0 |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `refresh_tokens`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| user_id | UUID | FK → users |
| token_hash | VARCHAR(64) | hashed refresh token |
| expires_at | TIMESTAMPTZ | |
| revoked | BOOLEAN | default false |
| created_at | TIMESTAMPTZ | |

### `followups`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| session_id | UUID | FK → sessions |
| practice_id | UUID | FK → practices |
| patient_email | VARCHAR(255) | |
| patient_first_name | VARCHAR(100) | |
| upload_token | VARCHAR(128) | unique, cryptographically random |
| token_expires_at | TIMESTAMPTZ | default: 30 days from creation |
| custom_message | TEXT | optional provider message |
| status | VARCHAR(20) | enum: scheduled, sent, opened, completed, expired, cancelled |
| send_at | TIMESTAMPTZ | when to send the email |
| sent_at | TIMESTAMPTZ | when actually sent |
| opened_at | TIMESTAMPTZ | email open tracking |
| upload_completed_at | TIMESTAMPTZ | when patient uploaded photo |
| reminder_1_sent_at | TIMESTAMPTZ | auto-sent 7 days after sent_at |
| reminder_2_sent_at | TIMESTAMPTZ | auto-sent 14 days after sent_at |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### `credits`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| practice_id | UUID | FK → practices |
| session_id | UUID | FK → sessions |
| followup_id | UUID | FK → followups, nullable |
| patient_initials | VARCHAR(10) | |
| patient_email | VARCHAR(255) | |
| code | VARCHAR(30) | unique, human-readable (VERIBA-XX-000-XXXX) |
| amount | INTEGER | in cents |
| description | VARCHAR(255) | e.g., "$150 off next visit" |
| consent_tier | VARCHAR(20) | tier that earned this credit |
| status | VARCHAR(20) | enum: active, redeemed, expired, voided |
| earned_at | TIMESTAMPTZ | |
| expires_at | TIMESTAMPTZ | default: 6 months from earned_at |
| redeemed_at | TIMESTAMPTZ | |
| redeemed_by | VARCHAR(255) | staff member who processed |
| redeem_notes | TEXT | |
| void_reason | TEXT | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

---

## Docker Compose Services

```yaml
services:
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes: ["./Caddyfile:/etc/caddy/Caddyfile", "caddy_data:/data"]
    depends_on: [fastapi, minio]

  fastapi:
    build: ./backend
    env_file: .env
    depends_on: [postgres, minio, redis]
    volumes: ["./backend:/app"]

  celery-worker:
    build: ./backend
    command: celery -A app.worker worker --loglevel=info
    env_file: .env
    depends_on: [postgres, minio, redis]

  celery-beat:
    build: ./backend
    command: celery -A app.worker beat --loglevel=info
    env_file: .env
    depends_on: [redis]

  postgres:
    image: postgres:16
    env_file: .env
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    volumes: ["redis_data:/data"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    env_file: .env
    volumes: ["minio_data:/data"]

  cloudflared:
    image: cloudflare/cloudflared
    command: tunnel run
    env_file: .env

volumes:
  postgres_data:
  minio_data:
  redis_data:
  caddy_data:
```

**New services**:
- **redis**: Task queue broker for Celery. Lightweight, Alpine-based, minimal resource usage.
- **celery-worker**: Processes background tasks (sending scheduled emails, expiring old tokens/credits).
- **celery-beat**: Periodic task scheduler — runs cron-like jobs (e.g., check for credits nearing expiration, send reminder emails at scheduled times, expire old upload tokens).

---

## SEO Filename / Metadata Uniqueness Strategy

Every published session gets a **unique** filename and URL slug generated from:

```
{treatment_slug}-{area_detail}-{practice_slug}-{location_slug}-{YYYY-MM}-{sequence}.jpg
```

**Examples:**
- `botox-forehead-horizontal-lines-luxe-aesthetics-reno-nv-2026-03-001.jpg`
- `botox-forehead-horizontal-lines-luxe-aesthetics-reno-nv-2026-03-002.jpg`
- `dermal-filler-lips-volume-luxe-aesthetics-reno-nv-2026-03-001.jpg`
- `chemical-peel-full-face-luxe-aesthetics-reno-nv-2026-02-003.jpg`

The `{sequence}` is a per-practice, per-treatment, per-month counter stored in the DB. This guarantees uniqueness even for the same treatment at the same practice.

Meta descriptions are generated with variation templates to avoid duplicate content:
- Template A: "See verified {treatment} results at {practice} in {location}. {details}. Before photo at consultation, after captured {timeframe} post-treatment."
- Template B: "Real {treatment} before and after from {practice}, {location}. {details}. Verified with Veribā chain-of-custody authentication."
- Template C: "{practice} in {location} shares verified {treatment} results. {details}. Every photo cryptographically signed and unaltered."

The system cycles through templates and incorporates `treatment_details` for uniqueness.

---

## Session Status Flow

```
[CREATE] → draft
              │
    upload before photo
              │
              ▼
        pending_after
         │          │
    (in office)   (patient email)
         │          │
   provider        patient clicks link
   captures        and uploads after
   after photo     photo remotely
         │          │
         └────┬─────┘
              │
              ▼
       pending_consent
         │          │
    consent given  consent declined
    (in-app or     │
     patient        │
     portal)        ▼
         │       declined
         │
         ├── credit/reward generated (if via patient email)
         │
   ┌── auto_publish ON? ──┐
   │ YES              NO  │
   ▼                  ▼   │
published      ready_to_publish
                     │
               manual publish
                     │
                     ▼
                  published ←→ unpublished
```

### Session Status Enum
- `draft` — created, no images yet
- `pending_after` — has before image, waiting for after
- `pending_consent` — both images uploaded, awaiting consent
- `ready_to_publish` — consent given, awaiting manual publish (auto_publish OFF)
- `published` — live on widget/gallery
- `unpublished` — manually taken down
- `declined` — patient declined digital use

### Patient Email Upload Path (detailed)
```
1. Provider creates session + captures "before" in-app
2. Provider schedules follow-up email via POST /api/sessions/:id/followup
3. Celery worker sends email at scheduled time (via Resend)
4. Patient receives email with unique upload link
5. Patient clicks link → sees before photo + treatment + reward tiers
6. Patient uploads after photo → session transitions to pending_consent
7. Patient selects consent tier → credit generated in ledger
8. Session transitions to ready_to_publish (or auto-publishes if practice toggle is ON)
9. Patient receives reward code on confirmation screen
10. Patient redeems code at next visit → staff marks as redeemed
11. If patient doesn't upload: auto-reminder at 7 days, second at 14 days, then stop
```

---

## Design Decisions (Finalized)

1. **Image obscuring**: Handled entirely on-device. The provider applies obscuring (eyes, upper face, full blur) in the app using real-time preview, and the final obscured image is what gets uploaded. The server never processes or stores the unobscured original — it receives, hashes, and stores the finished image as-is. This eliminates server-side image processing dependencies and is a privacy win (unblurred originals never leave the device).

2. **Rate limiting**: 100 req/min per practice slug for widget endpoints. 10 req/min per token for patient upload portal. Enforced via FastAPI middleware (slowapi).

3. **Image size limits**: 10MB max upload. Server auto-compresses to 2MB for web delivery (JPEG quality 80, max 2000px wide). Original preserved in MinIO for future use.

4. **Multi-user per practice**: Supported from day one. Three roles:
   - **owner**: full access — manage users, billing, practice settings, all sessions
   - **provider**: create/edit/publish sessions, view analytics, manage credits
   - **staff**: view sessions, redeem credits, look up reward codes (front desk use case)

5. **Credit expiration**: Practices can customize expiration period from 30 days to 12 months. Default is 6 months. Stored as `credit_expiration_days` on the practice model. Celery beat job runs daily to expire old credits.

6. **Auto-publish**: Per-practice toggle stored as `auto_publish` boolean on the practice model. When enabled, sessions auto-transition to "published" after consent is recorded (in-app or via patient portal). When disabled, sessions move to a "ready_to_publish" state and require manual publish action.

7. **Patient upload quality**: No validation checks in v1. Accept whatever the patient uploads. AI-powered quality evaluation (lighting consistency, angle matching, blur detection, visible difference scoring) planned for v2.

8. **Email branding**: All follow-up emails are Veribā-branded (Veribā logo, colors, footer). Practice name appears in the email body text and subject line (e.g., "Your visit to Luxe Aesthetics — share your results"). White-label/practice-branded emails deferred to Growth/Enterprise tiers.

9. **Reminder cadence**: Two automatic reminders if the patient hasn't uploaded:
   - Reminder 1: 7 days after initial email
   - Reminder 2: 14 days after initial email (7 days after first reminder)
   - After that, no more auto-reminders. Provider can manually resend.
   - Celery beat job checks for pending reminders daily and queues them via Resend.
