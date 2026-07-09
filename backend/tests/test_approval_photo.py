"""Tests for GROWTH-SPEC §8: POST /api/me/approvals/{id}/photo (in-app after-photo upload)."""

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


def _register_provider(client, email="ap_prov@test.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "Dr AP",
        "practice_name": "AP Clinic Demo", "practice_location": "LA, CA",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


def _register_member(client, email="ap_mem@test.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "AP Member", "role": "member",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


def _session_with_before(client, provider_token):
    """Session with only a before image (pending_after state)."""
    h = {"Authorization": f"Bearer {provider_token}"}
    s = client.post("/api/sessions", json={
        "patient_initials": "AP", "treatment": "Botox", "category": "Botox", "status": "draft",
    }, headers=h)
    sid = s.json()["data"]["id"]
    client.post(f"/api/sessions/{sid}/images/before", headers=h,
        files={"file": ("b.jpg", TINY_JPEG, "image/jpeg")},
        data={"capture_hash": "h1", "capture_lat": "34.0", "capture_lng": "-118.0"})
    return sid


def _sent_followup(client, provider_token, session_id, patient_email):
    """Create a followup with immediate send."""
    h = {"Authorization": f"Bearer {provider_token}"}
    r = client.post(f"/api/sessions/{session_id}/followup", headers=h, json={
        "patient_email": patient_email,
        "send_at": "2020-01-01T00:00:00Z",
    })
    assert r.status_code == 201
    return r.json()["data"]["id"]


def _upload_photo(client, member_token, followup_id):
    mh = {"Authorization": f"Bearer {member_token}"}
    return client.post(f"/api/me/approvals/{followup_id}/photo", headers=mh,
        files={"file": ("after.jpg", TINY_JPEG, "image/jpeg")})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_upload_after_photo_happy_path(client):
    provider_token = _register_provider(client)
    member_token = _register_member(client)

    sid = _session_with_before(client, provider_token)
    fid = _sent_followup(client, provider_token, sid, "ap_mem@test.com")

    r = _upload_photo(client, member_token, fid)
    assert r.status_code == 200
    d = r.json()["data"]["session"]
    assert d["id"] == sid
    assert d["status"] == "pending_consent"
    assert d["after_image_url"] is not None
    assert d["after_blurhash"] is not None


def test_after_photo_sets_provenance_not_followup_status(client):
    """followup.status must not change; session.status becomes pending_consent."""
    from app.db.session import SessionLocal
    from app.models import Followup, Session as PhotoSession
    from sqlalchemy import select

    provider_token = _register_provider(client, "ap_prov2@test.com")
    member_token = _register_member(client, "ap_mem2@test.com")

    sid = _session_with_before(client, provider_token)
    fid = _sent_followup(client, provider_token, sid, "ap_mem2@test.com")

    _upload_photo(client, member_token, fid)

    with SessionLocal() as db:
        fu = db.scalar(select(Followup).where(Followup.id == fid))
        sess = db.scalar(select(PhotoSession).where(PhotoSession.id == sid))
        assert fu.status == "sent"  # followup NOT touched
        assert sess.status == "pending_consent"
        assert sess.after_provenance == "Uploaded by patient in-app"
        assert sess.after_image_key is not None
        assert sess.after_blurhash is not None


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_upload_returns_409_if_photo_already_present(client):
    provider_token = _register_provider(client, "ap_prov3@test.com")
    member_token = _register_member(client, "ap_mem3@test.com")

    sid = _session_with_before(client, provider_token)
    fid = _sent_followup(client, provider_token, sid, "ap_mem3@test.com")

    _upload_photo(client, member_token, fid)  # first upload
    r = _upload_photo(client, member_token, fid)  # second upload
    assert r.status_code == 409
    assert "already" in r.json()["error"]["message"].lower()


def test_upload_returns_404_for_other_members_followup(client):
    provider_token = _register_provider(client, "ap_prov4@test.com")
    owner_token = _register_member(client, "ap_owner@test.com")
    intruder_token = _register_member(client, "ap_intruder@test.com")

    sid = _session_with_before(client, provider_token)
    fid = _sent_followup(client, provider_token, sid, "ap_owner@test.com")

    r = client.post(f"/api/me/approvals/{fid}/photo",
        headers={"Authorization": f"Bearer {intruder_token}"},
        files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})
    assert r.status_code == 404


def test_upload_returns_409_for_expired_followup(client):
    from app.db.session import SessionLocal
    from app.models import Followup, FollowupStatus
    from sqlalchemy import select

    provider_token = _register_provider(client, "ap_prov5@test.com")
    member_token = _register_member(client, "ap_mem5@test.com")

    sid = _session_with_before(client, provider_token)
    fid = _sent_followup(client, provider_token, sid, "ap_mem5@test.com")

    # Force-expire the followup
    with SessionLocal() as db:
        fu = db.scalar(select(Followup).where(Followup.id == fid))
        fu.status = FollowupStatus.expired.value
        db.add(fu)
        db.commit()

    r = _upload_photo(client, member_token, fid)
    assert r.status_code == 409


def test_upload_returns_409_for_completed_followup(client):
    from app.db.session import SessionLocal
    from app.models import Followup, FollowupStatus
    from sqlalchemy import select

    provider_token = _register_provider(client, "ap_prov6@test.com")
    member_token = _register_member(client, "ap_mem6@test.com")

    sid = _session_with_before(client, provider_token)
    fid = _sent_followup(client, provider_token, sid, "ap_mem6@test.com")

    with SessionLocal() as db:
        fu = db.scalar(select(Followup).where(Followup.id == fid))
        fu.status = FollowupStatus.completed.value
        db.add(fu)
        db.commit()

    r = _upload_photo(client, member_token, fid)
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Web-link path unaffected
# ---------------------------------------------------------------------------

def test_web_link_upload_path_unchanged(client):
    """upload_patient_photo via /api/patient/upload/{token} still works."""
    provider_token = _register_provider(client, "ap_prov7@test.com")

    sid = _session_with_before(client, provider_token)
    fid = _sent_followup(client, provider_token, sid, "weblink@example.com")

    # Get the upload token from the followup
    h = {"Authorization": f"Bearer {provider_token}"}
    followups_r = client.get(f"/api/sessions/{sid}/followups", headers=h)
    token = followups_r.json()["data"]["followups"][0]["upload_token"]

    r = client.post(f"/api/patient/upload/{token}/photo",
        files={"file": ("after.jpg", TINY_JPEG, "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["success"] is True
