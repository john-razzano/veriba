# OAuth Spec — Sign in with Apple + Google (native token exchange)

Written July 7, 2026 for the backend agent. The app performs the OAuth flow
natively (Apple/Google sheets) and hands us an **identity token (JWT)**; the
backend's only OAuth job is verifying that JWT against the provider's public
keys and minting our normal token pair. No redirect URIs, no OAuth secrets,
no browser flows server-side.

## 1. Schema (migration 0008)

On `users`:

| column | type | notes |
| --- | --- | --- |
| password_hash | → nullable | OAuth-only accounts have none; login-with-password must fail cleanly (treat NULL as never-matching, don't 500) |
| auth_provider | String(20), default `"email"` | `email` / `google` / `apple` |
| oauth_subject | String(255), nullable | provider's stable user id (`sub` claim) |

Add a partial/composite unique constraint on `(auth_provider, oauth_subject)`
where oauth_subject is not null.

## 2. Endpoint

`POST /api/auth/oauth` — body:

```json
{
  "provider": "google" | "apple",
  "id_token": "<JWT from the native SDK>",
  "full_name": "Mia Verde"   // optional; Apple only sends the name on FIRST auth — the app forwards it
}
```

Response: identical shape to `/api/auth/login` (access_token, refresh_token,
token_type, user). New users are created with `role="member"` — clinics keep
email registration.

### Token verification (server-side, mandatory)

- **Google**: verify signature against Google's JWKS
  (`https://www.googleapis.com/oauth2/v3/certs`), `iss` in
  {`https://accounts.google.com`, `accounts.google.com`}, `aud` ==
  `GOOGLE_IOS_CLIENT_ID` env, `exp` valid. Claims used: `sub`, `email`,
  `email_verified`, `name`.
- **Apple**: verify against `https://appleid.apple.com/auth/keys`, `iss` ==
  `https://appleid.apple.com`, `aud` == `APPLE_BUNDLE_ID` env
  (`com.jrazzano.proveagence`), `exp` valid. Claims: `sub`, `email`
  (may be a private-relay address, may be absent after first auth),
  `email_verified`.
- Cache JWKS in-process with a TTL (~6h) and refetch on unknown `kid`.
  `python-jose` is already a dependency for our own JWTs — reuse it.
- Any verification failure → 401 with a generic "Sign-in failed" message
  (never echo validation internals).

### Account resolution (in order)

1. `(auth_provider, oauth_subject)` exact match → log them in.
2. Else, if the token has a **verified** email matching an existing user
   (case-insensitive): link — set `auth_provider`+`oauth_subject` on that
   user (keep their existing role and password_hash; a provider signing in
   with Google gets their provider account). Note: a user can only hold one
   linked provider this way — fine for now.
3. Else create a new member: email from token (Apple private relay is fine),
   name from `full_name` (Apple first-auth) or the `name` claim or the email
   local-part; initials derived like normal registration. If Apple sends no
   email at all on a repeat auth and no subject match exists, 409 with
   "We couldn't retrieve your account email — remove Veriba from
   Settings → Apple ID → Sign-In & Security and try again."

## 3. Config

New env vars (add to .env.example + compose): `GOOGLE_IOS_CLIENT_ID`,
`APPLE_BUNDLE_ID=com.jrazzano.proveagence`. If `GOOGLE_IOS_CLIENT_ID` is
unset, google requests → 503 "Google sign-in not configured" (Apple works
independently).

## 4. Tests

Mock the JWKS endpoints (or monkeypatch the decode step) — no live calls:
- valid google token → creates member, second call → same user (subject match)
- verified-email match links to an existing email-password user, role kept
- apple first-auth with full_name + private relay email → member created;
  repeat auth without email → subject match still logs in
- bad signature / wrong aud / expired → 401; unverified email never links
- password login with NULL password_hash fails cleanly
- migration up/down clean on live data

Report: migration number, test count, any deviations.
