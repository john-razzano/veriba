"""Tests for PRACTICE-PROFILE-SPEC Phase 2: featured case, services, blurhash."""

import base64

TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
    "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBh"
    "JBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1"
    "RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uL"
    "m6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwAooooA/9k="
)
_SVG = "M10 35 Q30 10 50 30 T90 25"


def _register_provider(client, email="prov@p2.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "Dr P2",
        "practice_name": "P2 Clinic Demo", "practice_location": "LA, CA",
    })
    assert r.status_code == 201
    d = r.json()["data"]
    return d["access_token"], d["practice"]["id"]


def _make_published_session(client, token):
    h = {"Authorization": f"Bearer {token}"}
    s = client.post("/api/sessions", json={
        "patient_initials": "TP", "treatment": "Botox", "category": "Botox", "status": "draft",
    }, headers=h)
    assert s.status_code == 201
    sid = s.json()["data"]["id"]
    client.post(f"/api/sessions/{sid}/images/before", headers=h,
        files={"file": ("b.jpg", TINY_JPEG, "image/jpeg")},
        data={"capture_hash": "h1", "capture_lat": "34.0", "capture_lng": "-118.0"})
    client.post(f"/api/sessions/{sid}/images/after", headers=h,
        files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})
    client.post(f"/api/sessions/{sid}/consent", headers=h,
        json={"consent_tier": "full", "signature_svg": _SVG})
    client.post(f"/api/sessions/{sid}/publish", headers=h,
        json={"destinations": ["gallery"], "treatment_details": ""})
    return sid


# ---------------------------------------------------------------------------
# Featured case
# ---------------------------------------------------------------------------

def test_featured_pin_happy_path(client):
    token, practice_id = _register_provider(client)
    h = {"Authorization": f"Bearer {token}"}
    sid = _make_published_session(client, token)

    r = client.patch("/api/practices/me", headers=h, json={"featured_session_id": sid})
    assert r.status_code == 200
    assert r.json()["data"]["featured_session_id"] == sid


def test_featured_pin_wrong_practice_rejected(client):
    token_a, _ = _register_provider(client, "provA@p2.com")
    token_b, _ = _register_provider(client, "provB@p2.com")

    # Session belongs to provider A's practice
    sid = _make_published_session(client, token_a)

    # Provider B tries to pin it — should 400
    r = client.patch("/api/practices/me",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"featured_session_id": sid})
    assert r.status_code == 400


def test_featured_pin_unpublished_rejected(client):
    token, _ = _register_provider(client, "provC@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    # Create session but don't publish it
    s = client.post("/api/sessions", json={
        "patient_initials": "TP", "treatment": "Botox", "category": "Botox", "status": "draft",
    }, headers=h)
    sid = s.json()["data"]["id"]

    r = client.patch("/api/practices/me", headers=h, json={"featured_session_id": sid})
    assert r.status_code == 400


def test_featured_pin_null_clears(client):
    token, _ = _register_provider(client, "provD@p2.com")
    h = {"Authorization": f"Bearer {token}"}
    sid = _make_published_session(client, token)

    client.patch("/api/practices/me", headers=h, json={"featured_session_id": sid})
    r = client.patch("/api/practices/me", headers=h, json={"featured_session_id": None})
    assert r.status_code == 200
    assert r.json()["data"]["featured_session_id"] is None


def test_featured_pin_fallback_when_unpublished(client):
    """Unpublishing the pinned session must not break the gallery endpoint."""
    token, practice_id = _register_provider(client, "provE@p2.com")
    h = {"Authorization": f"Bearer {token}"}
    sid = _make_published_session(client, token)
    _ = _make_published_session(client, token)  # second session as fallback

    # Pin first session, then unpublish it
    client.patch("/api/practices/me", headers=h, json={"featured_session_id": sid})
    client.post(f"/api/sessions/{sid}/unpublish", headers=h)

    # GET provider practice payload — should not error
    r = client.get("/api/practices/me", headers=h)
    assert r.status_code == 200
    # featured_session_id still stored in DB
    assert r.json()["data"]["featured_session_id"] == sid


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def test_services_happy_path(client):
    token, _ = _register_provider(client, "provF@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/practices/me", headers=h,
        json={"services": ["Botox", "Fillers", "Laser"]})
    assert r.status_code == 200
    assert r.json()["data"]["services"] == ["Botox", "Fillers", "Laser"]


def test_services_deduped_case_insensitively(client):
    token, _ = _register_provider(client, "provG@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/practices/me", headers=h,
        json={"services": ["Botox", "botox", "BOTOX", "Fillers"]})
    assert r.status_code == 200
    assert r.json()["data"]["services"] == ["Botox", "Fillers"]  # first occurrence preserved


def test_services_too_many_items(client):
    token, _ = _register_provider(client, "provH@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/practices/me", headers=h,
        json={"services": [f"Service {i}" for i in range(31)]})
    assert r.status_code == 422


def test_services_item_too_long(client):
    token, _ = _register_provider(client, "provI@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/practices/me", headers=h,
        json={"services": ["x" * 61]})
    assert r.status_code == 422


def test_services_null_clears(client):
    token, _ = _register_provider(client, "provJ@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    client.patch("/api/practices/me", headers=h, json={"services": ["Botox"]})
    r = client.patch("/api/practices/me", headers=h, json={"services": None})
    assert r.status_code == 200
    assert r.json()["data"]["services"] is None


def test_services_exposed_in_public_serializer(client):
    token, practice_id = _register_provider(client, "provK@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    client.patch("/api/practices/me", headers=h, json={"services": ["Botox", "PDO Threads"]})

    me = client.get("/api/practices/me", headers=h)
    assert me.json()["data"]["services"] == ["Botox", "PDO Threads"]


# ---------------------------------------------------------------------------
# Blurhash
# ---------------------------------------------------------------------------

def test_blurhash_computed_after_image_upload(client):
    token, _ = _register_provider(client, "provL@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    s = client.post("/api/sessions", json={
        "patient_initials": "BH", "treatment": "Botox", "category": "Botox", "status": "draft",
    }, headers=h)
    sid = s.json()["data"]["id"]

    before_r = client.post(f"/api/sessions/{sid}/images/before", headers=h,
        files={"file": ("b.jpg", TINY_JPEG, "image/jpeg")},
        data={"capture_hash": "h1", "capture_lat": "34.0", "capture_lng": "-118.0"})
    assert before_r.status_code == 200

    after_r = client.post(f"/api/sessions/{sid}/images/after", headers=h,
        files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})
    assert after_r.status_code == 200

    # Provider-facing detail should show the session with hashes stored
    sess = client.get(f"/api/sessions/{sid}", headers=h)
    assert sess.status_code == 200
    # Publish so it appears in the public gallery
    client.post(f"/api/sessions/{sid}/consent", headers=h,
        json={"consent_tier": "full", "signature_svg": _SVG})
    client.post(f"/api/sessions/{sid}/publish", headers=h,
        json={"destinations": ["gallery"], "treatment_details": ""})

    gallery = client.get("/api/gallery/sessions?limit=10")
    sessions = gallery.json()["data"]["sessions"]
    match = [s for s in sessions if s["id"] == sid]
    assert match, "session not in gallery"
    assert match[0]["before_blurhash"] is not None, "before_blurhash should be computed"
    assert match[0]["after_blurhash"] is not None, "after_blurhash should be computed"


def test_avatar_blurhash_computed_after_upload(client):
    token, _ = _register_provider(client, "provM@p2.com")
    h = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/practices/me/avatar", headers=h,
        files={"file": ("avatar.jpg", TINY_JPEG, "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["data"]["avatar_blurhash"] is not None

    me = client.get("/api/practices/me", headers=h)
    assert me.json()["data"]["avatar_blurhash"] is not None


def test_public_session_card_exposes_blurhashes(client):
    """Gallery sessions list includes before_blurhash and after_blurhash fields."""
    token, _ = _register_provider(client, "provN@p2.com")
    sid = _make_published_session(client, token)

    gallery = client.get("/api/gallery/sessions?limit=10")
    sessions = gallery.json()["data"]["sessions"]
    match = [s for s in sessions if s["id"] == sid]
    assert match
    s = match[0]
    assert "before_blurhash" in s
    assert "after_blurhash" in s
