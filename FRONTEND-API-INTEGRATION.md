# Veriba Frontend API Integration Guide

This document is for the frontend implementation layer. It reflects the API that is currently running in Docker and was verified locally on March 28, 2026 with registration, auth, session creation, image upload, consent, publish, SEO, and public widget flows.

## 1. Base URL Strategy

You do **not** need the final production domain yet.

Use a frontend environment variable for the API base URL and keep every request path relative to that variable.

Recommended patterns:

- Next.js: `NEXT_PUBLIC_VERIBA_API_BASE_URL`
- Vite: `VITE_VERIBA_API_BASE_URL`

Recommended usage:

```ts
const API_BASE_URL =
  process.env.NEXT_PUBLIC_VERIBA_API_BASE_URL ??
  process.env.VITE_VERIBA_API_BASE_URL ??
  "";

export function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}
```

### Current local options

- Direct FastAPI app: `http://localhost:8000`
- Through Caddy reverse proxy: `http://localhost`

All documented API routes below already include the `/api` prefix.

Examples:

- Direct local health URL: `http://localhost:8000/api/health`
- Proxied local health URL: `http://localhost/api/health`

### Best recommendation

If the frontend will eventually be served from the same domain as the API, use a blank base URL and call relative paths like:

```ts
fetch("/api/auth/login")
```

If the frontend and API will live on separate origins, use the env var:

```ts
fetch(apiUrl("/api/auth/login"))
```

## 2. CORS

Browser CORS is enabled and currently configured for:

- `http://localhost:3000`
- `http://127.0.0.1:3000`

Backend setting:

- `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`

When you get the real frontend domain, update `CORS_ORIGINS` on the backend.

## 3. Authentication

Protected routes require:

```http
Authorization: Bearer <access_token>
```

Auth token flow:

1. `POST /api/auth/register` or `POST /api/auth/login`
2. Store `access_token` and `refresh_token`
3. Send `Authorization: Bearer <access_token>` on protected requests
4. If the access token expires, call `POST /api/auth/refresh`

## 4. Response Envelope

Every route returns the same outer JSON shape:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

Error responses look like:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "validation_error",
    "message": "Validation failed",
    "details": []
  }
}
```

## 5. Important Enum Values

### Session categories

- `Botox`
- `Fillers`
- `Skin`
- `Hair`
- `Body`
- `Other`

### Session statuses

- `draft`
- `pending_after`
- `pending_consent`
- `ready_to_publish`
- `published`
- `declined`
- `unpublished`

### Consent tiers

- `full`
- `partial`
- `full_blur`
- `decline`

### Obscure modes

- `none`
- `eyes`
- `upper`
- `full`

### Credit statuses

- `active`
- `redeemed`
- `expired`
- `voided`

### Follow-up statuses

- `scheduled`
- `sent`
- `opened`
- `completed`
- `expired`
- `cancelled`

## 6. Common Frontend Notes

- Do **not** hardcode storage URLs. Use `before_image_url`, `after_image_url`, `consent_signature_url`, and other URLs returned by the API.
- Session image uploads are `multipart/form-data`.
- Public widget routes do **not** require auth.
- Patient upload routes do **not** use bearer auth. They use the upload token in the URL.
- The backend also exposes interactive FastAPI docs locally at `http://localhost:8000/docs`.

## 7. Core Provider Flow

This is the main authenticated admin/provider flow the frontend should support:

1. Register or log in
2. Load `GET /api/users/me`
3. Load `GET /api/practices/me`
4. Create a session with `POST /api/sessions`
5. Upload `before` image
6. Upload `after` image
7. Record consent
8. Publish session
9. Show widget/public preview from `/api/widget/...`

## 8. Endpoint Reference

### Auth

### `POST /api/auth/register`

Creates the first user and practice together.

Request:

```json
{
  "email": "owner@example.com",
  "password": "supersecret123",
  "name": "Dr. Jane Doe",
  "practice_name": "Widget Clinic",
  "practice_location": "Los Angeles, CA",
  "practice_website": "https://widgetclinic.com"
}
```

Response `data`:

```json
{
  "user": {
    "id": "uuid",
    "email": "owner@example.com",
    "name": "Dr. Jane Doe",
    "initials": "DJD",
    "practice_id": "uuid",
    "role": "owner",
    "created_at": "2026-03-28T17:00:00+00:00"
  },
  "practice": {
    "id": "uuid",
    "name": "Widget Clinic",
    "location": "Los Angeles, CA",
    "coordinates": null,
    "website": "https://widgetclinic.com",
    "widget_slug": "widget-clinic",
    "default_discounts": {
      "full": 150,
      "partial": 75,
      "full_blur": 25
    },
    "credit_expiration_days": 180,
    "auto_publish": false,
    "owner_id": "uuid",
    "created_at": "2026-03-28T17:00:00+00:00",
    "updated_at": "2026-03-28T17:00:00+00:00"
  },
  "access_token": "jwt",
  "refresh_token": "jwt",
  "token_type": "bearer"
}
```

### `POST /api/auth/login`

Request:

```json
{
  "email": "owner@example.com",
  "password": "supersecret123"
}
```

Response `data`:

```json
{
  "access_token": "jwt",
  "refresh_token": "jwt",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "owner@example.com",
    "name": "Dr. Jane Doe",
    "initials": "DJD",
    "practice_id": "uuid",
    "role": "owner",
    "created_at": "2026-03-28T17:00:00+00:00"
  }
}
```

### `POST /api/auth/refresh`

Request:

```json
{
  "refresh_token": "jwt"
}
```

Response `data`:

```json
{
  "access_token": "jwt",
  "refresh_token": "jwt",
  "token_type": "bearer"
}
```

### `POST /api/auth/logout`

Protected.

Invalidates active refresh tokens for the current user.

### User

### `GET /api/users/me`

Protected. Returns the current user.

### `PATCH /api/users/me`

Protected.

Request:

```json
{
  "name": "Dr. Jane Updated",
  "email": "owner-updated@example.com"
}
```

### `PATCH /api/users/me/password`

Protected.

Request:

```json
{
  "current_password": "supersecret123",
  "new_password": "newsecret456"
}
```

### Practice

### `GET /api/practices/me`

Protected. Returns the current practice.

### `PATCH /api/practices/me`

Protected.

Request:

```json
{
  "name": "Widget Clinic Beverly Hills",
  "location": "Beverly Hills, CA",
  "website": "https://widgetclinic.com",
  "lat": 34.0736,
  "lng": -118.4004,
  "auto_publish": false,
  "credit_expiration_days": 180,
  "default_discounts": {
    "full": 150,
    "partial": 75,
    "full_blur": 25
  }
}
```

### `GET /api/practices/me/stats`

Protected.

Response `data`:

```json
{
  "total_published": 5,
  "total_pending": 2,
  "total_declined": 1,
  "profile_views_total": 48,
  "profile_views_this_week": 12,
  "seo_impressions_total": 0,
  "seo_impressions_this_week": 0
}
```

### Sessions

### `GET /api/sessions`

Protected.

Query params:

- `status`
- `category`
- `sort=created_at|updated_at|page_views`
- `order=asc|desc`
- `limit`
- `offset`

Response `data`:

```json
{
  "sessions": [
    {
      "id": "uuid",
      "patient_initials": "AB",
      "treatment": "Lip Filler",
      "category": "Fillers",
      "status": "published",
      "obscure_mode": "none",
      "consent_tier": "full",
      "before_image_url": "http://localhost/storage/veriba/...",
      "after_image_url": "http://localhost/storage/veriba/...",
      "page_views": 3,
      "captured_at": "2026-03-28T17:00:00+00:00",
      "published_at": "2026-03-28T17:10:00+00:00",
      "created_at": "2026-03-28T17:00:00+00:00",
      "updated_at": "2026-03-28T17:10:00+00:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### `POST /api/sessions`

Protected.

Allowed starting statuses:

- `draft`
- `pending_after`

Request:

```json
{
  "patient_initials": "AB",
  "treatment": "Lip Filler",
  "category": "Fillers",
  "status": "draft"
}
```

Returns a full session detail object.

### `GET /api/sessions/{session_id}`

Protected. Returns full session detail.

### `PATCH /api/sessions/{session_id}`

Protected.

Request:

```json
{
  "patient_initials": "AB",
  "treatment": "Lip Filler Revision",
  "category": "Fillers",
  "obscure_mode": "eyes",
  "treatment_details": "1 syringe, upper lip focus"
}
```

### `DELETE /api/sessions/{session_id}`

Protected.

Soft deletes by setting `archived_at`.

Response `data`:

```json
{
  "archived": true
}
```

### Session Images

### `POST /api/sessions/{session_id}/images/before`

Protected. `multipart/form-data`.

Fields:

- `file`: required
- `capture_hash`: optional
- `capture_lat`: optional
- `capture_lng`: optional
- `captured_at`: optional ISO datetime

### `POST /api/sessions/{session_id}/images/after`

Protected. `multipart/form-data`.

Fields:

- `file`: required
- `capture_hash`: optional
- `capture_lat`: optional
- `capture_lng`: optional
- `captured_at`: optional ISO datetime

Upload response `data`:

```json
{
  "image_url": "http://localhost/storage/veriba/...",
  "capture_hash": "sha256...",
  "capture_coordinates": {
    "lat": 34.07,
    "lng": -118.40
  },
  "captured_at": "2026-03-28T17:00:00+00:00",
  "server_hash": "sha256...",
  "hash_match": true,
  "chain_of_custody_updated": true
}
```

### `GET /api/sessions/{session_id}/images/{image_kind}`

Protected.

Route values:

- `image_kind`: `before` or `after`

Query params:

- `size=thumb|medium|full`

Response `data`:

```json
{
  "url": "http://localhost/storage/veriba/...",
  "size": "medium",
  "width": 1600,
  "height": 1200
}
```

### `POST /api/sessions/{session_id}/images/{image_kind}/presign`

Protected.

Returns a future direct-upload contract.

Response `data`:

```json
{
  "upload_url": "http://...",
  "expires_in": 3600,
  "fields": {}
}
```

### Consent and Publish

### `POST /api/sessions/{session_id}/consent`

Protected.

For non-decline consent, both `before` and `after` images must already exist.

Request:

```json
{
  "consent_tier": "full",
  "obscure_mode": "none",
  "discount_applied": 150,
  "signature_svg": "<svg>...</svg>"
}
```

Response `data`:

```json
{
  "consent_tier": "full",
  "obscure_mode": "none",
  "consent_at": "2026-03-28T17:05:00+00:00",
  "discount_applied": 150,
  "signature_url": "http://localhost/storage/veriba/...",
  "chain_of_custody_updated": true,
  "session_status": "ready_to_publish"
}
```

### `POST /api/sessions/{session_id}/consent/decline`

Protected.

Sets:

- `consent_tier=decline`
- `obscure_mode=full`
- `status=declined`

### `POST /api/sessions/{session_id}/publish`

Protected.

Request:

```json
{
  "destinations": ["widget", "gallery"],
  "treatment_details": "1 syringe, upper lip focus"
}
```

Response `data`:

```json
{
  "status": "published",
  "published_at": "2026-03-28T17:10:00+00:00",
  "publish_hash": "sha256...",
  "seo": {
    "title": "Before and After Lip Filler | Widget Clinic",
    "alt_text": "Lip filler before and after result",
    "meta_description": "Before and after lip filler result at Widget Clinic",
    "filename": "before-after-lip-filler-widget-clinic.jpg",
    "url_slug": "before-after-lip-filler-widget-clinic"
  },
  "destinations": ["widget", "gallery"],
  "chain_of_custody_updated": true
}
```

### `POST /api/sessions/{session_id}/unpublish`

Protected.

Only allowed when current status is `published`.

### `GET /api/sessions/{session_id}/seo`

Protected.

Returns the current SEO payload or `null` if SEO has not been generated yet.

### `POST /api/sessions/{session_id}/seo/regenerate`

Protected.

Rebuilds title, alt text, description, filename, and URL slug.

### Session Detail Shape

`GET /api/sessions/{session_id}` and several other session endpoints return this detail shape:

```json
{
  "id": "uuid",
  "patient_initials": "AB",
  "treatment": "Lip Filler",
  "category": "Fillers",
  "status": "published",
  "obscure_mode": "none",
  "consent_tier": "full",
  "before_image_url": "http://localhost/storage/veriba/...",
  "after_image_url": "http://localhost/storage/veriba/...",
  "page_views": 3,
  "captured_at": "2026-03-28T17:00:00+00:00",
  "published_at": "2026-03-28T17:10:00+00:00",
  "created_at": "2026-03-28T17:00:00+00:00",
  "updated_at": "2026-03-28T17:10:00+00:00",
  "chain_of_custody": {
    "all_verified": true,
    "checkpoints": []
  },
  "consent_signature_url": "http://localhost/storage/veriba/...",
  "consent_at": "2026-03-28T17:05:00+00:00",
  "discount_applied": 150,
  "seo": {
    "title": "Before and After Lip Filler | Widget Clinic",
    "alt_text": "Lip filler before and after result",
    "meta_description": "Before and after lip filler result at Widget Clinic",
    "filename": "before-after-lip-filler-widget-clinic.jpg",
    "url_slug": "before-after-lip-filler-widget-clinic"
  }
}
```

### Follow-Ups

These routes are protected and tied to a provider session.

### `POST /api/sessions/{session_id}/followup`

Request:

```json
{
  "patient_email": "patient@example.com",
  "patient_first_name": "Ava",
  "send_at": "2026-03-29T18:00:00+00:00",
  "message": "Thanks for visiting us."
}
```

Response includes:

- `upload_token`
- `upload_url`
- `status`
- send/open/upload timestamps

### `GET /api/sessions/{session_id}/followups`

Returns:

```json
{
  "followups": []
}
```

### `POST /api/sessions/{session_id}/followup/{followup_id}/resend`

Regenerates token and re-sends the upload link.

### `DELETE /api/sessions/{session_id}/followup/{followup_id}`

Cancels a scheduled follow-up.

### Patient Upload Portal

These routes are for the patient-facing upload flow. They are token-based, not bearer-token-based.

Frontend route recommendation:

- Build a page like `/upload/[token]` or `/upload/:token`

The backend generates upload links using `PATIENT_PORTAL_BASE_URL`. Right now that is configured as:

- `http://localhost:3000/upload`

So a follow-up email will point to:

- `http://localhost:3000/upload/{token}`

### `GET /api/patient/upload/{token}`

Validates the token and returns the context needed to render the patient page.

Important behavior:

- If the token is invalid or expired, this route still returns `200`
- The invalid state is represented inside `data.valid`

Valid response `data`:

```json
{
  "valid": true,
  "practice_name": "Widget Clinic",
  "patient_first_name": "Ava",
  "treatment": "Lip Filler",
  "before_image_url": "http://localhost/storage/veriba/...",
  "captured_at": "2026-03-28T17:00:00+00:00",
  "reward_amount": 150,
  "reward_description": "$150 off",
  "consent_options": [
    {
      "tier": "full",
      "label": "Full face — no obscuring",
      "reward": "$150 off"
    }
  ],
  "expires_at": "2026-04-27T17:00:00+00:00"
}
```

Invalid response `data`:

```json
{
  "valid": false,
  "error": "This link has expired. Please contact your provider for a new one."
}
```

### `POST /api/patient/upload/{token}/photo`

`multipart/form-data`

Fields:

- `file`: required

Response `data`:

```json
{
  "success": true,
  "message": "Photo uploaded successfully! Please select your sharing preference below to claim your reward."
}
```

### `POST /api/patient/upload/{token}/consent`

Request:

```json
{
  "consent_tier": "full",
  "signature_data": "<svg>...</svg>"
}
```

Response `data`:

```json
{
  "success": true,
  "consent_tier": "full",
  "reward_earned": {
    "id": "uuid",
    "code": "ABC123",
    "amount": 150,
    "status": "active"
  },
  "message": "Thank you! Your reward code is ABC123."
}
```

### `GET /api/patient/upload/{token}/status`

Response `data`:

```json
{
  "photo_uploaded": true,
  "consent_given": true,
  "reward_earned": true,
  "reward_code": "ABC123",
  "session_status": "published"
}
```

### Public Widget API

These routes are public and were verified end-to-end in the smoke test.

### `GET /api/widget/{practice_slug}/gallery`

Query params:

- `category`
- `limit`
- `offset`

Response `data`:

```json
{
  "practice": {
    "name": "Widget Clinic",
    "location": "Los Angeles, CA"
  },
  "sessions": [
    {
      "id": "uuid",
      "treatment": "Lip Filler",
      "category": "Fillers",
      "before_image_url": "http://localhost/storage/veriba/...",
      "after_image_url": "http://localhost/storage/veriba/...",
      "obscure_mode": "none",
      "seo": {
        "title": "Before and After Lip Filler | Widget Clinic",
        "alt_text": "Lip filler before and after result",
        "meta_description": "Before and after lip filler result at Widget Clinic",
        "filename": "before-after-lip-filler-widget-clinic.jpg",
        "url_slug": "before-after-lip-filler-widget-clinic"
      },
      "chain_of_custody": {
        "all_verified": true,
        "checkpoint_count": 5
      },
      "published_at": "2026-03-28T17:10:00+00:00"
    }
  ],
  "total": 1
}
```

### `GET /api/widget/{practice_slug}/session/{session_id}`

Returns one public session item plus basic practice info.

### `POST /api/widget/{practice_slug}/session/{session_id}/view`

Tracks a public view count.

Response `data`:

```json
{
  "recorded": true
}
```

### Credits

These routes are protected and useful for a rewards dashboard.

### `GET /api/credits`

Query params:

- `status`
- `patient_initials`
- `sort=created_at|expires_at|amount`
- `order=asc|desc`
- `limit`
- `offset`

Response includes:

- `credits`
- `total`
- `total_active_value`
- `total_redeemed_value`
- `total_expired_value`

### `GET /api/credits/lookup/{code}`

Lookup by reward code.

### `GET /api/credits/stats`

Returns rollup stats such as:

- `total_issued`
- `total_active`
- `total_redeemed`
- `active_value`
- `redemption_rate`
- `credits_expiring_30d`

### `GET /api/credits/{credit_id}`

Returns a full credit object.

### `POST /api/credits/{credit_id}/redeem`

Request:

```json
{
  "redeemed_by": "Front Desk",
  "notes": "Applied to next visit"
}
```

### `POST /api/credits/{credit_id}/void`

Request:

```json
{
  "reason": "Duplicate reward"
}
```

### Health

### `GET /api/health`

Response `data`:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "connected",
  "storage": "connected",
  "uptime": "0:00:02"
}
```

### `GET /api/health/db`

### `GET /api/health/storage`

## 9. Suggested Frontend API Client Shape

This is a good baseline:

```ts
export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  error: null | {
    code: string;
    message: string;
    details?: unknown;
  };
};
```

Recommended authenticated request helper:

```ts
export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  accessToken?: string
): Promise<ApiEnvelope<T>> {
  const headers = new Headers(init.headers);

  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    headers,
  });

  return response.json();
}
```

## 10. What To Change Later When The Real Domain Exists

When you get the real server hostname, you do **not** need to rewrite the frontend integration. You only need to update configuration.

Frontend:

- set `NEXT_PUBLIC_VERIBA_API_BASE_URL` or `VITE_VERIBA_API_BASE_URL`

Backend:

- `BASE_API_URL`
- `PUBLIC_STORAGE_BASE_URL`
- `PATIENT_PORTAL_BASE_URL`
- `CORS_ORIGINS`

## 11. Verified Working Routes

These flows were exercised successfully against the running Docker deployment:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/sessions`
- `POST /api/sessions/{session_id}/images/before`
- `POST /api/sessions/{session_id}/images/after`
- `POST /api/sessions/{session_id}/consent`
- `POST /api/sessions/{session_id}/publish`
- `GET /api/sessions/{session_id}/seo`
- `GET /api/widget/{practice_slug}/gallery`
- `GET /api/widget/{practice_slug}/session/{session_id}`
- `POST /api/widget/{practice_slug}/session/{session_id}/view`
- `GET /api/health`
