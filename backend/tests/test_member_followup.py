"""Tests for GROWTH-SPEC §6 + §7: member-linked followups."""

import base64
from unittest.mock import MagicMock, patch

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


def _register_provider(client, email="mf_prov@test.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "Dr MF",
        "practice_name": "MF Clinic Demo", "practice_location": "LA, CA",
    })
    assert r.status_code == 201
    d = r.json()["data"]
    return d["access_token"], d["practice"]["id"]


def _register_member(client, email="mf_mem@test.com"):
    r = client.post("/api/auth/register", json={
        "email": email, "password": "secret123", "name": "MF Member", "role": "member",
    })
    assert r.status_code == 201
    d = r.json()["data"]
    return d["access_token"], d["user"]["id"]


def _session_with_images(client, provider_token):
    h = {"Authorization": f"Bearer {provider_token}"}
    s = client.post("/api/sessions", json={
        "patient_initials": "MF", "treatment": "Botox", "category": "Botox", "status": "draft",
    }, headers=h)
    sid = s.json()["data"]["id"]
    client.post(f"/api/sessions/{sid}/images/before", headers=h,
        files={"file": ("b.jpg", TINY_JPEG, "image/jpeg")},
        data={"capture_hash": "h1", "capture_lat": "34.0", "capture_lng": "-118.0"})
    client.post(f"/api/sessions/{sid}/images/after", headers=h,
        files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})
    return sid


# ---------------------------------------------------------------------------
# patient_user_id creation + validation
# ---------------------------------------------------------------------------

def test_create_followup_with_patient_user_id(client):
    provider_token, _ = _register_provider(client)
    member_token, member_id = _register_member(client)
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    r = client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_email": "other-email@example.com",
        "patient_user_id": member_id,
        "send_at": "2020-01-01T00:00:00Z",
    })
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["patient_user_id"] == member_id
    # member_match resolved from user_id even though email differs
    assert d["member_match"] is not None
    assert d["member_match"]["id"] == member_id


def test_patient_user_id_must_be_member(client):
    provider_token, _ = _register_provider(client, "mf_prov2@test.com")
    provider_token2, provider2_id = _register_provider(client, "mf_prov3@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    # Try to link a provider account — should 422
    r = client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_email": "x@example.com",
        "patient_user_id": provider2_id,  # provider, not member
        "send_at": "2020-01-01T00:00:00Z",
    })
    assert r.status_code == 422


def test_member_match_null_for_unknown_email(client):
    provider_token, _ = _register_provider(client, "mf_prov4@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    r = client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_email": "nobody@example.com",
        "send_at": "2020-01-01T00:00:00Z",
    })
    assert r.status_code == 201
    assert r.json()["data"]["member_match"] is None


def test_member_match_resolves_from_email_when_no_user_id(client):
    provider_token, _ = _register_provider(client, "mf_prov5@test.com")
    member_token, member_id = _register_member(client, "mf_mem5@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    r = client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_email": "mf_mem5@test.com",
        "send_at": "2020-01-01T00:00:00Z",
    })
    assert r.status_code == 201
    mm = r.json()["data"]["member_match"]
    assert mm is not None
    assert mm["id"] == member_id
    assert "email" not in mm  # no email leakage


# ---------------------------------------------------------------------------
# Resolution rule: user_id wins; QR-bound followup appears in approvals/results
# ---------------------------------------------------------------------------

def test_user_id_wins_over_email_in_approvals(client):
    """Followup bound to member A's user_id with member B's email → only A sees it."""
    provider_token, _ = _register_provider(client, "mf_prov6@test.com")
    member_a_token, member_a_id = _register_member(client, "mf_a@test.com")
    member_b_token, _ = _register_member(client, "mf_b@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    # Bound to member A but email says member B
    client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_email": "mf_b@test.com",  # member B's email
        "patient_user_id": member_a_id,    # member A's ID — wins
        "send_at": "2020-01-01T00:00:00Z",
    })

    # Member A should see it
    ra = client.get("/api/me/approvals", headers={"Authorization": f"Bearer {member_a_token}"})
    assert len(ra.json()["data"]["approvals"]) == 1

    # Member B should NOT see it (user_id wins, email is not used)
    rb = client.get("/api/me/approvals", headers={"Authorization": f"Bearer {member_b_token}"})
    assert len(rb.json()["data"]["approvals"]) == 0


def test_qr_bound_followup_appears_in_results(client):
    provider_token, _ = _register_provider(client, "mf_prov7@test.com")
    member_token, member_id = _register_member(client, "mf_c@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    # Bind via user_id with a completely different email
    client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_email": "unrelated@example.com",
        "patient_user_id": member_id,
        "send_at": "2020-01-01T00:00:00Z",
    })

    r = client.get("/api/me/results", headers={"Authorization": f"Bearer {member_token}"})
    assert r.json()["data"]["total"] == 1


# ---------------------------------------------------------------------------
# GET /api/members/lookup
# ---------------------------------------------------------------------------

def test_lookup_member_by_user_id(client):
    provider_token, _ = _register_provider(client, "mf_prov8@test.com")
    _, member_id = _register_member(client, "mf_d@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}

    r = client.get(f"/api/members/lookup?user_id={member_id}", headers=ph)
    assert r.status_code == 200
    m = r.json()["data"]["member"]
    assert m["id"] == member_id
    assert "name" in m
    assert "initials" in m
    assert "email" not in m


def test_lookup_member_by_email(client):
    provider_token, _ = _register_provider(client, "mf_prov9@test.com")
    _, member_id = _register_member(client, "mf_e@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}

    r = client.get("/api/members/lookup?email=mf_e@test.com", headers=ph)
    assert r.status_code == 200
    assert r.json()["data"]["member"]["id"] == member_id


def test_lookup_nonexistent_returns_null(client):
    provider_token, _ = _register_provider(client, "mf_prova@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}

    r = client.get("/api/members/lookup?email=nobody@nowhere.com", headers=ph)
    assert r.status_code == 200
    assert r.json()["data"]["member"] is None


def test_lookup_provider_by_user_id_returns_null(client):
    """lookup must not return non-member accounts."""
    provider_token, practice_id = _register_provider(client, "mf_provb@test.com")
    # get provider's own user id
    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {provider_token}"})
    provider_user_id = me.json()["data"]["id"]
    ph = {"Authorization": f"Bearer {provider_token}"}

    r = client.get(f"/api/members/lookup?user_id={provider_user_id}", headers=ph)
    assert r.json()["data"]["member"] is None


def test_lookup_requires_practice_auth(client):
    _, member_id = _register_member(client, "mf_f@test.com")
    member_token = client.post("/api/auth/login", json={"email": "mf_f@test.com", "password": "secret123"}).json()["data"]["access_token"]
    r = client.get(f"/api/members/lookup?user_id={member_id}",
        headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Push fires at send-time (dispatch_scheduled_followups), not creation
# ---------------------------------------------------------------------------

def test_push_fires_from_dispatch_not_creation(client):
    """Scheduled followup: no push at creation; push fires when dispatcher sends."""
    from app.tasks.jobs import dispatch_scheduled_followups

    provider_token, _ = _register_provider(client, "mf_provc@test.com")
    member_token, member_id = _register_member(client, "mf_g@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    push_calls = []

    def capture_push(user_ids, title, body, data=None):
        push_calls.append({"user_ids": user_ids, "title": title, "body": body, "data": data})

    with patch("app.services.push.send_push", side_effect=capture_push):
        # Create followup with far-future send_at → no immediate push
        r = client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
            "patient_email": "mf_g@test.com",
            "send_at": "2099-01-01T00:00:00Z",  # far future
        })
        assert r.status_code == 201
        assert len(push_calls) == 0, "no push at creation for scheduled followup"

        # Manually update send_at to the past so dispatcher picks it up
        followup_id = r.json()["data"]["id"]
        from app.db.session import SessionLocal
        from app.models import Followup
        from sqlalchemy import select
        from app.core.security import utcnow
        from datetime import timedelta
        with SessionLocal() as db:
            fu = db.scalar(select(Followup).where(Followup.id == followup_id))
            fu.send_at = utcnow() - timedelta(minutes=1)
            db.add(fu)
            db.commit()

        # Run dispatcher — should fire push
        dispatch_scheduled_followups()
        assert len(push_calls) == 1
        assert push_calls[0]["user_ids"] == [member_id]


def test_push_copy_pending_after_vs_approval(client):
    """pending_after session → 'after photo' copy; pending_consent → 'results' copy."""
    from app.services.push import send_followup_push
    from app.db.session import SessionLocal
    from app.models import Followup, Session as PhotoSession, SessionStatus
    from sqlalchemy import select

    provider_token, _ = _register_provider(client, "mf_provd@test.com")
    _, member_id = _register_member(client, "mf_h@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}

    # Session with only before image → pending_after
    s = client.post("/api/sessions", json={
        "patient_initials": "MH", "treatment": "Filler", "category": "Fillers", "status": "draft",
    }, headers=ph)
    sid = s.json()["data"]["id"]
    client.post(f"/api/sessions/{sid}/images/before", headers=ph,
        files={"file": ("b.jpg", TINY_JPEG, "image/jpeg")},
        data={"capture_hash": "h1", "capture_lat": "0.0", "capture_lng": "0.0"})

    # Create followup bound by user_id
    client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_email": "mf_h@test.com",
        "patient_user_id": member_id,
        "send_at": "2020-01-01T00:00:00Z",
    })

    captured = []
    with patch("app.services.push.send_push", side_effect=lambda *a, **kw: captured.append(kw or {"args": a})):
        with SessionLocal() as db:
            fu = db.scalars(select(Followup)).all()[-1]
            sess = db.get(PhotoSession, sid)
            send_followup_push(fu, sess, "Test Practice", db)

    assert len(captured) == 1
    call = captured[0]
    args = call.get("args", ())
    # body is positional arg 2 or keyword
    body_arg = args[2] if len(args) > 2 else call.get("body", "")
    assert "after photo" in body_arg.lower() or "upload" in body_arg.lower()


# ---------------------------------------------------------------------------
# §7: patient_email optional when patient_user_id provided
# ---------------------------------------------------------------------------

def test_create_followup_with_user_id_only_no_email(client):
    """QR path: patient_user_id alone is enough; stored email is user's account email."""
    from app.db.session import SessionLocal
    from app.models import Followup
    from sqlalchemy import select

    provider_token, _ = _register_provider(client, "s7_prov@test.com")
    member_token, member_id = _register_member(client, "s7_mem@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    r = client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_user_id": member_id,
        "send_at": "2020-01-01T00:00:00Z",
        # no patient_email
    })
    assert r.status_code == 201
    d = r.json()["data"]

    # Response must NOT expose the auto-resolved email
    assert d["patient_email"] is None

    # member_match is still populated
    assert d["member_match"] is not None
    assert d["member_match"]["id"] == member_id

    # DB record holds the linked user's own email internally
    with SessionLocal() as db:
        fu = db.scalar(select(Followup).where(Followup.id == d["id"]))
        assert fu.patient_email == "s7_mem@test.com"


def test_create_followup_with_neither_email_nor_user_id_returns_422(client):
    """Both absent → 422."""
    provider_token, _ = _register_provider(client, "s7_prov2@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    r = client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "send_at": "2020-01-01T00:00:00Z",
        # neither patient_email nor patient_user_id
    })
    assert r.status_code == 422


def test_email_only_path_unchanged(client):
    """Existing email-only path still works and returns patient_email in response."""
    provider_token, _ = _register_provider(client, "s7_prov3@test.com")
    ph = {"Authorization": f"Bearer {provider_token}"}
    sid = _session_with_images(client, provider_token)

    r = client.post(f"/api/sessions/{sid}/followup", headers=ph, json={
        "patient_email": "noapp@example.com",
        "send_at": "2020-01-01T00:00:00Z",
    })
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["patient_email"] == "noapp@example.com"
    assert d["member_match"] is None
