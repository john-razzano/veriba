"""Tests for consent-privacy bugs and the full_blur publish gate."""

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


def _register_provider(client, email="prov@priv.com", slug="priv-clinic"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "Dr P",
        "practice_name": "Priv Clinic Demo", "practice_location": "LA, CA",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


def _session_with_images(client, token):
    h = {"Authorization": f"Bearer {token}"}
    s = client.post("/api/sessions", json={
        "patient_initials": "TP", "treatment": "Test", "category": "Botox", "status": "draft",
    }, headers=h)
    assert s.status_code == 201
    sid = s.json()["data"]["id"]

    client.post(f"/api/sessions/{sid}/images/before", headers=h,
        files={"file": ("b.jpg", TINY_JPEG, "image/jpeg")},
        data={"capture_hash": "h1", "capture_lat": "34.0", "capture_lng": "-118.0"})
    client.post(f"/api/sessions/{sid}/images/after", headers=h,
        files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})
    return sid


# ---------------------------------------------------------------------------
# Bug 1: partial consent must hide before_image_url in public responses
# ---------------------------------------------------------------------------

def test_partial_consent_hides_before_image_in_gallery(client):
    token = _register_provider(client)
    h = {"Authorization": f"Bearer {token}"}
    sid = _session_with_images(client, token)

    # Record partial consent and publish
    client.post(f"/api/sessions/{sid}/consent", headers=h,
        json={"consent_tier": "partial", "signature_svg": _SVG})
    pub = client.post(f"/api/sessions/{sid}/publish", headers=h,
        json={"destinations": ["gallery"], "treatment_details": ""})
    assert pub.status_code == 200

    # Gallery endpoint must return before_image_url: null
    gallery = client.get("/api/gallery/sessions?limit=10")
    sessions = gallery.json()["data"]["sessions"]
    match = [s for s in sessions if s["id"] == sid]
    assert match, "session not found in gallery"
    assert match[0]["before_image_url"] is None, "before_image_url should be null for partial consent"
    assert match[0]["after_image_url"] is not None, "after_image_url should still be present"


def test_full_consent_still_shows_before_image(client):
    token = _register_provider(client, "prov2@priv.com")
    h = {"Authorization": f"Bearer {token}"}
    sid = _session_with_images(client, token)

    client.post(f"/api/sessions/{sid}/consent", headers=h,
        json={"consent_tier": "full", "signature_svg": _SVG})
    client.post(f"/api/sessions/{sid}/publish", headers=h,
        json={"destinations": ["gallery"], "treatment_details": ""})

    gallery = client.get("/api/gallery/sessions?limit=10")
    sessions = gallery.json()["data"]["sessions"]
    match = [s for s in sessions if s["id"] == sid]
    assert match
    assert match[0]["before_image_url"] is not None, "full consent must expose before_image_url"


# ---------------------------------------------------------------------------
# Bug 2: full_blur must never reach published status
# ---------------------------------------------------------------------------

def test_full_blur_consent_stays_at_ready_to_publish(client):
    token = _register_provider(client, "prov3@priv.com")
    h = {"Authorization": f"Bearer {token}"}
    sid = _session_with_images(client, token)

    r = client.post(f"/api/sessions/{sid}/consent", headers=h,
        json={"consent_tier": "full_blur", "signature_svg": _SVG})
    assert r.status_code == 200
    assert r.json()["data"]["session_status"] == "ready_to_publish"


def test_full_blur_manual_publish_returns_400(client):
    token = _register_provider(client, "prov4@priv.com")
    h = {"Authorization": f"Bearer {token}"}
    sid = _session_with_images(client, token)

    client.post(f"/api/sessions/{sid}/consent", headers=h,
        json={"consent_tier": "full_blur", "signature_svg": _SVG})

    pub = client.post(f"/api/sessions/{sid}/publish", headers=h,
        json={"destinations": ["gallery"], "treatment_details": ""})
    assert pub.status_code == 400
    assert "full_blur" in pub.json()["error"]["message"].lower()


def test_full_blur_does_not_auto_publish(client):
    """Even with auto_publish=True, full_blur must stay at ready_to_publish."""
    token = _register_provider(client, "prov5@priv.com")
    h = {"Authorization": f"Bearer {token}"}

    # Enable auto_publish on the practice
    practice_id = client.get("/api/users/me", headers=h).json()["data"]["practice_id"]
    client.patch(f"/api/practices/{practice_id}", headers=h, json={"auto_publish": True})

    sid = _session_with_images(client, token)
    r = client.post(f"/api/sessions/{sid}/consent", headers=h,
        json={"consent_tier": "full_blur", "signature_svg": _SVG})
    assert r.status_code == 200
    assert r.json()["data"]["session_status"] == "ready_to_publish"
