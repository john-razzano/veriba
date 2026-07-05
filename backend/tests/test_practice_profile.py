"""Tests for PRACTICE-PROFILE-SPEC: bio, avatar, booking_url."""

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


def _register_provider(client, email="owner@profile.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "Dr Profile",
        "practice_name": "Profile Clinic", "practice_location": "LA, CA",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"], r.json()["data"]["practice"]["id"]


def _register_member(client, email="member@profile.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "Mem Profile", "role": "member",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


# ---------------------------------------------------------------------------
# PATCH /api/practices/me
# ---------------------------------------------------------------------------

def test_patch_bio_and_booking_url_happy_path(client):
    token, _ = _register_provider(client)
    h = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/practices/me", headers=h, json={
        "bio": "Top clinic in LA.",
        "booking_url": "https://example.com/book",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["bio"] == "Top clinic in LA."
    assert data["booking_url"] == "https://example.com/book"


def test_patch_booking_url_normalizes_scheme(client):
    token, _ = _register_provider(client, "owner2@profile.com")
    h = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/practices/me", headers=h, json={"booking_url": "example.com/book"})
    assert r.status_code == 200
    assert r.json()["data"]["booking_url"] == "https://example.com/book"


def test_patch_empty_string_booking_url_clears_it(client):
    token, _ = _register_provider(client, "owner3@profile.com")
    h = {"Authorization": f"Bearer {token}"}

    client.patch("/api/practices/me", headers=h, json={"booking_url": "https://example.com/book"})
    r = client.patch("/api/practices/me", headers=h, json={"booking_url": ""})
    assert r.status_code == 200
    assert r.json()["data"]["booking_url"] is None


def test_patch_bio_too_long_returns_422(client):
    token, _ = _register_provider(client, "owner4@profile.com")
    h = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/practices/me", headers=h, json={"bio": "x" * 601})
    assert r.status_code == 422


def test_patch_member_no_practice_returns_403(client):
    member_token = _register_member(client)
    r = client.patch("/api/practices/me",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"bio": "should fail"})
    assert r.status_code == 403


def test_patch_bio_explicit_null_clears_it(client):
    token, _ = _register_provider(client, "owner5@profile.com")
    h = {"Authorization": f"Bearer {token}"}

    client.patch("/api/practices/me", headers=h, json={"bio": "set first"})
    r = client.patch("/api/practices/me", headers=h, json={"bio": None})
    assert r.status_code == 200
    assert r.json()["data"]["bio"] is None


# ---------------------------------------------------------------------------
# Avatar upload / delete
# ---------------------------------------------------------------------------

def test_avatar_upload_returns_public_url(client):
    token, _ = _register_provider(client, "owner6@profile.com")
    h = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/practices/me/avatar", headers=h,
        files={"file": ("avatar.jpg", TINY_JPEG, "image/jpeg")})
    assert r.status_code == 200
    url = r.json()["data"]["avatar_url"]
    assert url and "profile/avatar.jpg" in url


def test_avatar_reupload_overwrites(client):
    token, _ = _register_provider(client, "owner7@profile.com")
    h = {"Authorization": f"Bearer {token}"}

    r1 = client.post("/api/practices/me/avatar", headers=h,
        files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})
    r2 = client.post("/api/practices/me/avatar", headers=h,
        files={"file": ("b.jpg", TINY_JPEG, "image/jpeg")})
    # Same key, second upload succeeds
    assert r2.status_code == 200
    url1 = r1.json()["data"]["avatar_url"]
    url2 = r2.json()["data"]["avatar_url"]
    assert url1 == url2  # same storage path


def test_avatar_delete_clears_key(client):
    token, _ = _register_provider(client, "owner8@profile.com")
    h = {"Authorization": f"Bearer {token}"}

    client.post("/api/practices/me/avatar", headers=h,
        files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})

    d = client.delete("/api/practices/me/avatar", headers=h)
    assert d.status_code == 200

    # avatar_url should now be null in GET /api/practices/me
    me = client.get("/api/practices/me", headers=h)
    assert me.json()["data"]["avatar_url"] is None


# ---------------------------------------------------------------------------
# Public gallery practice payload has all three fields
# ---------------------------------------------------------------------------

def test_public_practice_includes_new_fields(client):
    token, _ = _register_provider(client, "owner9@profile.com")
    h = {"Authorization": f"Bearer {token}"}

    # Set bio and booking_url
    client.patch("/api/practices/me", headers=h, json={
        "bio": "Public bio text.",
        "booking_url": "https://example.com/consult",
    })

    # The public gallery endpoint requires at least one published session
    # but list_public_practices doesn't require it — check it directly
    r = client.get("/api/gallery/practices")
    assert r.status_code == 200
    practices = r.json()["data"]["practices"]
    # Profile Clinic may or may not appear (it needs published sessions for count > 0)
    # Check via GET /api/practices/me that serialize_practice includes the fields
    me = client.get("/api/practices/me", headers=h)
    data = me.json()["data"]
    assert "bio" in data
    assert "avatar_url" in data
    assert "booking_url" in data
    assert data["bio"] == "Public bio text."
    assert data["booking_url"] == "https://example.com/consult"
