"""Tests for OAUTH-SPEC: Sign in with Apple + Google."""

from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fake claims returned by mocked verify_google / verify_apple
# ---------------------------------------------------------------------------

GOOGLE_CLAIMS = {
    "sub": "google-sub-001",
    "email": "guser@gmail.com",
    "email_verified": True,
    "name": "Google User",
    "iss": "https://accounts.google.com",
}

APPLE_CLAIMS_FULL = {
    "sub": "apple-sub-001",
    "email": "appleuser@privaterelay.appleid.com",
    "email_verified": True,
    "iss": "https://appleid.apple.com",
}

APPLE_CLAIMS_NO_EMAIL = {
    "sub": "apple-sub-001",
    "iss": "https://appleid.apple.com",
    # No email — repeat Apple auth after user revoked and re-authorised
}


def _google(client, claims=None, token="fake-google-token"):
    with patch("app.api.routes.auth.verify_google", return_value=claims or GOOGLE_CLAIMS):
        return client.post("/api/auth/oauth", json={"provider": "google", "id_token": token})


def _apple(client, claims=None, full_name=None, token="fake-apple-token"):
    body = {"provider": "apple", "id_token": token}
    if full_name:
        body["full_name"] = full_name
    with patch("app.api.routes.auth.verify_apple", return_value=claims or APPLE_CLAIMS_FULL):
        return client.post("/api/auth/oauth", json=body)


# ---------------------------------------------------------------------------
# Google: basic create + subject-match idempotency
# ---------------------------------------------------------------------------

def test_google_oauth_creates_member(client):
    r = _google(client)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["user"]["role"] == "member"
    assert d["user"]["email"] == "guser@gmail.com"
    assert d["access_token"]
    assert d["refresh_token"]


def test_google_second_call_returns_same_user(client):
    r1 = _google(client)
    r2 = _google(client)
    assert r1.json()["data"]["user"]["id"] == r2.json()["data"]["user"]["id"]


# ---------------------------------------------------------------------------
# Email-link: verified email matches existing email-password user
# ---------------------------------------------------------------------------

def test_google_links_to_existing_email_password_user(client):
    # Register a provider with the same email
    reg = client.post("/api/auth/register", json={
        "email": "guser@gmail.com",
        "password": "supersecret123",
        "name": "Existing Provider",
        "practice_name": "Link Clinic Demo",
        "practice_location": "LA, CA",
    })
    assert reg.status_code == 201
    existing_id = reg.json()["data"]["user"]["id"]
    existing_role = reg.json()["data"]["user"]["role"]

    # OAuth with same verified email → links, keeps existing role
    r = _google(client)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["user"]["id"] == existing_id
    assert d["user"]["role"] == existing_role  # role preserved


def test_unverified_email_does_not_link_and_collides(client):
    """Unverified email: link step skipped. If email already exists the DB constraint
    returns 409 — never 500, and the existing account is untouched."""
    client.post("/api/auth/register", json={
        "email": "unverified@gmail.com",
        "password": "supersecret123",
        "name": "Unverified",
        "role": "member",
    })

    unverified_claims = {**GOOGLE_CLAIMS, "email": "unverified@gmail.com", "email_verified": False}
    r = _google(client, claims=unverified_claims)
    # Can't link (unverified) and can't create (email taken) → 409, not 500
    assert r.status_code == 409

    # Original account is still accessible via password
    login = client.post("/api/auth/login", json={
        "email": "unverified@gmail.com", "password": "supersecret123",
    })
    assert login.status_code == 200


# ---------------------------------------------------------------------------
# Apple: first-auth with full_name; repeat auth without email via subject match
# ---------------------------------------------------------------------------

def test_apple_first_auth_with_full_name(client):
    r = _apple(client, full_name="Mia Verde")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["user"]["name"] == "Mia Verde"
    assert d["user"]["role"] == "member"


def test_apple_repeat_auth_without_email_uses_subject_match(client):
    # First auth registers the user
    r1 = _apple(client, full_name="Apple User")
    user_id = r1.json()["data"]["user"]["id"]

    # Repeat auth sends no email — should find by subject
    r2 = _apple(client, claims=APPLE_CLAIMS_NO_EMAIL)
    assert r2.status_code == 200
    assert r2.json()["data"]["user"]["id"] == user_id


def test_apple_no_email_no_subject_match_returns_409(client):
    # Brand new sub, no email → 409
    no_email_new_sub = {**APPLE_CLAIMS_NO_EMAIL, "sub": "apple-sub-new-999"}
    with patch("app.api.routes.auth.verify_apple", return_value=no_email_new_sub):
        r = client.post("/api/auth/oauth", json={"provider": "apple", "id_token": "fake"})
    assert r.status_code == 409
    assert "Settings" in r.json()["error"]["message"]


# ---------------------------------------------------------------------------
# Bad-token guard: 401 on invalid/expired/wrong-aud token
# ---------------------------------------------------------------------------

def test_bad_signature_returns_401(client):
    with patch("app.api.routes.auth.verify_google", side_effect=ValueError("bad sig")):
        r = client.post("/api/auth/oauth", json={"provider": "google", "id_token": "bad"})
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Sign-in failed"


def test_unconfigured_google_returns_503(client):
    # Temporarily unset GOOGLE_IOS_CLIENT_ID by mocking settings
    from app.core.config import Settings
    with patch("app.api.routes.auth.get_settings", return_value=Settings(
        database_url="sqlite:///./test_veriba.db",
        secret_key="test-secret-key-for-testing",
        google_ios_client_id=None,
    )):
        r = client.post("/api/auth/oauth", json={"provider": "google", "id_token": "t"})
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# Null password_hash: OAuth-only account can't log in via password
# ---------------------------------------------------------------------------

def test_oauth_only_account_rejects_password_login(client):
    _google(client)  # creates OAuth-only member (password_hash=None)

    r = client.post("/api/auth/login", json={
        "email": "guser@gmail.com",
        "password": "any-password",
    })
    assert r.status_code == 401
    assert "Invalid" in r.json()["error"]["message"]


def test_oauth_only_account_rejects_empty_password(client):
    _google(client)
    r = client.post("/api/auth/login", json={"email": "guser@gmail.com", "password": "x"})
    assert r.status_code == 401
