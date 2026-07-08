"""Tests for GROWTH-SPEC sections 1-5."""

import base64
from unittest.mock import MagicMock, patch

import pytest

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


def _register_provider(client, email="grow_prov@test.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "Dr Grow",
        "practice_name": "Grow Clinic Demo", "practice_location": "LA, CA",
    })
    assert r.status_code == 201
    d = r.json()["data"]
    return d["access_token"], d["practice"]["id"]


def _register_member(client, email="grow_mem@test.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "Grow Member", "role": "member",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


def _make_published_session(client, provider_token):
    h = {"Authorization": f"Bearer {provider_token}"}
    s = client.post("/api/sessions", json={
        "patient_initials": "GP", "treatment": "Botox", "category": "Botox", "status": "draft",
    }, headers=h)
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
# §1 Consult requests
# ---------------------------------------------------------------------------

def test_create_consult_happy_path(client):
    provider_token, practice_id = _register_provider(client)
    member_token = _register_member(client)
    mh = {"Authorization": f"Bearer {member_token}"}

    r = client.post("/api/me/consults", headers=mh, json={
        "practice_id": practice_id,
        "message": "Interested in lip filler",
        "contact_email": "grow_mem@test.com",
    })
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["status"] == "new"
    assert d["practice"]["id"] == practice_id
    assert d["member"]["name"] == "Grow Member"
    assert d["message"] == "Interested in lip filler"


def test_duplicate_new_consult_returns_409(client):
    provider_token, practice_id = _register_provider(client, "grow_prov2@test.com")
    member_token = _register_member(client, "grow_mem2@test.com")
    mh = {"Authorization": f"Bearer {member_token}"}

    client.post("/api/me/consults", headers=mh, json={
        "practice_id": practice_id, "contact_email": "grow_mem2@test.com",
    })
    r = client.post("/api/me/consults", headers=mh, json={
        "practice_id": practice_id, "contact_email": "grow_mem2@test.com",
    })
    assert r.status_code == 409


def test_member_list_consults(client):
    provider_token, practice_id = _register_provider(client, "grow_prov3@test.com")
    member_token = _register_member(client, "grow_mem3@test.com")
    mh = {"Authorization": f"Bearer {member_token}"}

    client.post("/api/me/consults", headers=mh, json={
        "practice_id": practice_id, "contact_email": "grow_mem3@test.com",
    })
    r = client.get("/api/me/consults", headers=mh)
    assert r.status_code == 200
    assert len(r.json()["data"]["consults"]) == 1


def test_practice_inbox_and_mark_handled(client):
    provider_token, practice_id = _register_provider(client, "grow_prov4@test.com")
    member_token = _register_member(client, "grow_mem4@test.com")
    mh = {"Authorization": f"Bearer {member_token}"}
    ph = {"Authorization": f"Bearer {provider_token}"}

    create_r = client.post("/api/me/consults", headers=mh, json={
        "practice_id": practice_id, "contact_email": "grow_mem4@test.com",
    })
    consult_id = create_r.json()["data"]["id"]

    # Provider sees it
    inbox = client.get("/api/consults?status=new", headers=ph)
    assert inbox.status_code == 200
    assert inbox.json()["data"]["total"] == 1

    # Provider marks handled
    h_r = client.post(f"/api/consults/{consult_id}/handled", headers=ph)
    assert h_r.status_code == 200
    assert h_r.json()["data"]["status"] == "handled"

    # Idempotent
    h_r2 = client.post(f"/api/consults/{consult_id}/handled", headers=ph)
    assert h_r2.status_code == 200

    # Moves to handled bucket
    inbox2 = client.get("/api/consults?status=handled", headers=ph)
    assert inbox2.json()["data"]["total"] == 1


def test_consult_in_activity_feed(client):
    provider_token, practice_id = _register_provider(client, "grow_prov5@test.com")
    member_token = _register_member(client, "grow_mem5@test.com")
    mh = {"Authorization": f"Bearer {member_token}"}

    client.post("/api/me/consults", headers=mh, json={
        "practice_id": practice_id, "contact_email": "grow_mem5@test.com",
    })
    activity = client.get("/api/me/activity", headers=mh)
    kinds = {i["kind"] for i in activity.json()["data"]["items"]}
    assert "consult_request" in kinds


# ---------------------------------------------------------------------------
# §2 Multi-photo
# ---------------------------------------------------------------------------

def test_upload_and_delete_session_photo(client):
    provider_token, _ = _register_provider(client, "grow_prov6@test.com")
    h = {"Authorization": f"Bearer {provider_token}"}
    sid = _make_published_session(client, provider_token)

    # Upload extra photo
    r = client.post(f"/api/sessions/{sid}/photos", headers=h,
        files={"file": ("extra.jpg", TINY_JPEG, "image/jpeg")},
        data={"label": "Side view", "sort_order": "0"})
    assert r.status_code == 201
    photo_id = r.json()["data"]["id"]
    assert r.json()["data"]["label"] == "Side view"

    # Delete
    d = client.delete(f"/api/sessions/{sid}/photos/{photo_id}", headers=h)
    assert d.status_code == 200
    assert d.json()["data"]["removed"] is True


def test_session_detail_includes_photos(client):
    provider_token, _ = _register_provider(client, "grow_prov7@test.com")
    h = {"Authorization": f"Bearer {provider_token}"}
    sid = _make_published_session(client, provider_token)

    client.post(f"/api/sessions/{sid}/photos", headers=h,
        files={"file": ("extra.jpg", TINY_JPEG, "image/jpeg")},
        data={"label": "2 weeks"})

    detail = client.get(f"/api/sessions/{sid}", headers=h)
    assert detail.status_code == 200
    photos = detail.json()["data"]["photos"]
    assert len(photos) == 1
    assert photos[0]["label"] == "2 weeks"
    assert "url" in photos[0]
    assert "blurhash" in photos[0]


def test_session_with_no_photos_returns_empty_list(client):
    provider_token, _ = _register_provider(client, "grow_prov8@test.com")
    h = {"Authorization": f"Bearer {provider_token}"}
    sid = _make_published_session(client, provider_token)

    detail = client.get(f"/api/sessions/{sid}", headers=h)
    assert detail.json()["data"]["photos"] == []


# ---------------------------------------------------------------------------
# §3 Practice hours
# ---------------------------------------------------------------------------

def test_patch_hours_roundtrip(client):
    provider_token, _ = _register_provider(client, "grow_prov9@test.com")
    h = {"Authorization": f"Bearer {provider_token}"}
    hours = {"mon": "9:00–17:00", "tue": "9:00–17:00", "sat": "10:00–14:00", "sun": None}

    r = client.patch("/api/practices/me", headers=h, json={"hours": hours})
    assert r.status_code == 200
    assert r.json()["data"]["hours"] == hours


def test_hours_null_clears(client):
    provider_token, _ = _register_provider(client, "grow_prova@test.com")
    h = {"Authorization": f"Bearer {provider_token}"}
    client.patch("/api/practices/me", headers=h, json={"hours": {"mon": "9:00–17:00"}})
    r = client.patch("/api/practices/me", headers=h, json={"hours": None})
    assert r.json()["data"]["hours"] is None


def test_hours_in_public_practice_payload(client):
    provider_token, _ = _register_provider(client, "grow_provb@test.com")
    h = {"Authorization": f"Bearer {provider_token}"}
    client.patch("/api/practices/me", headers=h, json={"hours": {"mon": "9:00–17:00"}})

    me = client.get("/api/practices/me", headers=h)
    assert "hours" in me.json()["data"]
    assert me.json()["data"]["hours"]["mon"] == "9:00–17:00"


# ---------------------------------------------------------------------------
# §4 Push tokens
# ---------------------------------------------------------------------------

def test_upsert_push_token(client):
    member_token = _register_member(client, "grow_push1@test.com")
    mh = {"Authorization": f"Bearer {member_token}"}

    r = client.post("/api/me/push-token", headers=mh, json={
        "token": "ExpoToken[abc123]", "platform": "ios",
    })
    assert r.status_code == 200
    assert r.json()["data"]["stored"] is True


def test_push_token_upsert_moves_account(client):
    """Same device token registered by user A, then re-registered by user B.
    Must succeed (not 409) and ownership must transfer to B."""
    token_a = _register_member(client, "push_ua@test.com")
    token_b = _register_member(client, "push_ub@test.com")

    r1 = client.post("/api/me/push-token", headers={"Authorization": f"Bearer {token_a}"},
        json={"token": "ExpoToken[shared]", "platform": "android"})
    assert r1.status_code == 200

    # Same Expo token, different account — must NOT 409
    r2 = client.post("/api/me/push-token", headers={"Authorization": f"Bearer {token_b}"},
        json={"token": "ExpoToken[shared]", "platform": "android"})
    assert r2.status_code == 200
    assert r2.json()["data"]["stored"] is True

    # Token is now owned by B: delete via B succeeds
    d = client.request("DELETE", "/api/me/push-token",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"token": "ExpoToken[shared]"})
    assert d.json()["data"]["removed"] is True

    # And no longer present for A
    d2 = client.request("DELETE", "/api/me/push-token",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"token": "ExpoToken[shared]"})
    assert d2.json()["data"]["removed"] is False


def test_delete_push_token(client):
    member_token = _register_member(client, "grow_push2@test.com")
    mh = {"Authorization": f"Bearer {member_token}"}

    client.post("/api/me/push-token", headers=mh,
        json={"token": "ExpoToken[del]", "platform": "ios"})
    d = client.request("DELETE", "/api/me/push-token", headers=mh,
        json={"token": "ExpoToken[del]"})
    assert d.status_code == 200
    assert d.json()["data"]["removed"] is True

    # Idempotent
    d2 = client.request("DELETE", "/api/me/push-token", headers=mh,
        json={"token": "ExpoToken[del]"})
    assert d2.json()["data"]["removed"] is False


def test_send_push_chunks_and_removes_stale():
    """Unit-test the push sender against a mocked Expo endpoint."""
    from app.services.push import send_push, CHUNK_SIZE

    # Build 150 fake tokens so we get two chunks
    user_ids = [f"user-{i}" for i in range(3)]

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {"status": "ok"},
            {"status": "error", "details": {"error": "DeviceNotRegistered"}},
            {"status": "ok"},
        ]
    }

    with patch("app.services.push.SessionLocal") as mock_sl, \
         patch("app.services.push.httpx.post", return_value=mock_resp):
        mock_db = MagicMock()
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)

        from app.models import PushToken as PT
        fake_tokens = [
            MagicMock(spec=PT, token=f"tok-{i}", user_id=user_ids[i])
            for i in range(3)
        ]
        mock_db.scalars.return_value.all.return_value = fake_tokens

        send_push(user_ids, title="Test", body="Hello")

        # Should have deleted the stale token (index 1)
        mock_db.delete.assert_called_once_with(fake_tokens[1])
        mock_db.commit.assert_called_once()


def test_send_push_chunks_large_batch():
    """Verify chunking: 150 tokens → 2 POST calls."""
    from app.services.push import send_push

    user_ids = [f"u{i}" for i in range(150)]
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": [{"status": "ok"}] * 100}

    with patch("app.services.push.SessionLocal") as mock_sl, \
         patch("app.services.push.httpx.post", return_value=mock_resp) as mock_post:
        mock_db = MagicMock()
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)

        from app.models import PushToken as PT
        fake_tokens = [MagicMock(spec=PT, token=f"t{i}", user_id=f"u{i}") for i in range(150)]
        mock_db.scalars.return_value.all.return_value = fake_tokens

        send_push(user_ids, title="T", body="B")
        assert mock_post.call_count == 2  # 150 / 100 = 2 chunks


# ---------------------------------------------------------------------------
# §5 Analytics counts
# ---------------------------------------------------------------------------

def test_saves_count_in_session_detail_and_list(client):
    provider_token, _ = _register_provider(client, "grow_provc@test.com")
    member_token = _register_member(client, "grow_memc@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    mh = {"Authorization": f"Bearer {member_token}"}

    sid = _make_published_session(client, provider_token)

    # Before save
    detail = client.get(f"/api/sessions/{sid}", headers=ph)
    assert detail.json()["data"]["saves_count"] == 0

    # Member saves it
    client.post(f"/api/me/saves/{sid}", headers=mh)

    # After save
    detail2 = client.get(f"/api/sessions/{sid}", headers=ph)
    assert detail2.json()["data"]["saves_count"] == 1

    # Session list also shows saves_count
    lst = client.get("/api/sessions", headers=ph)
    row = next((s for s in lst.json()["data"]["sessions"] if s["id"] == sid), None)
    assert row is not None
    assert row["saves_count"] == 1


def test_followers_count_on_practice_me(client):
    provider_token, practice_id = _register_provider(client, "grow_provd@test.com")
    member_token = _register_member(client, "grow_memd@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}

    # Before follow
    me = client.get("/api/practices/me", headers=ph)
    assert me.json()["data"]["followers_count"] == 0

    # Member follows
    client.post(f"/api/me/follows/{practice_id}",
        headers={"Authorization": f"Bearer {member_token}"})

    # After follow
    me2 = client.get("/api/practices/me", headers=ph)
    assert me2.json()["data"]["followers_count"] == 1
