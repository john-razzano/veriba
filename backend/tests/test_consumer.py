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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_provider(client, email="provider@test.com"):
    r = client.post("/api/auth/register", json={
        "email": email,
        "password": "secret123",
        "name": "Dr Provider",
        "practice_name": "Test Clinic Demo",
        "practice_location": "LA, CA",
    })
    assert r.status_code == 201
    d = r.json()["data"]
    return d["access_token"], d["practice"]["id"]


def _register_member(client, email="member@test.com"):
    r = client.post("/api/auth/register", json={
        "email": email,
        "password": "secret123",
        "name": "Test Member",
        "role": "member",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


def _make_published_session(client, provider_token):
    h = {"Authorization": f"Bearer {provider_token}"}

    s = client.post("/api/sessions", json={
        "patient_initials": "TP",
        "treatment": "Botox",
        "category": "Botox",
        "status": "draft",
    }, headers=h)
    assert s.status_code == 201
    sid = s.json()["data"]["id"]

    b = client.post(f"/api/sessions/{sid}/images/before", headers=h,
        files={"file": ("b.jpg", TINY_JPEG, "image/jpeg")},
        data={"capture_hash": "hash1", "capture_lat": "34.05", "capture_lng": "-118.24"})
    assert b.status_code == 200

    a = client.post(f"/api/sessions/{sid}/images/after", headers=h,
        files={"file": ("a.jpg", TINY_JPEG, "image/jpeg")})
    assert a.status_code == 200

    c = client.post(f"/api/sessions/{sid}/consent", headers=h,
        json={"consent_tier": "full", "signature_svg": "M10 35 Q30 10 50 30 T90 25"})
    assert c.status_code == 200

    p = client.post(f"/api/sessions/{sid}/publish", headers=h,
        json={"destinations": ["widget", "gallery"], "treatment_details": "20u"})
    assert p.status_code == 200
    assert p.json()["data"]["status"] == "published"

    return sid


def _create_sent_followup(client, provider_token, session_id, patient_email):
    """Create a followup that is immediately sent (send_at in the past, email is no-op in tests)."""
    h = {"Authorization": f"Bearer {provider_token}"}
    r = client.post(f"/api/sessions/{session_id}/followup", headers=h, json={
        "patient_email": patient_email,
        "patient_first_name": "Tester",
        "send_at": "2020-01-01T00:00:00Z",
    })
    assert r.status_code == 201
    return r.json()["data"]["id"]


# ---------------------------------------------------------------------------
# Saves
# ---------------------------------------------------------------------------

def test_save_unsave_and_list(client):
    provider_token, _ = _register_provider(client)
    member_token = _register_member(client)
    session_id = _make_published_session(client, provider_token)

    mh = {"Authorization": f"Bearer {member_token}"}

    # Save — expect 201
    r = client.post(f"/api/me/saves/{session_id}", headers=mh)
    assert r.status_code == 201
    assert r.json()["data"]["session_id"] == session_id

    # Idempotent — expect 200
    r2 = client.post(f"/api/me/saves/{session_id}", headers=mh)
    assert r2.status_code == 200
    assert r2.json()["data"]["session_id"] == session_id

    # List
    lst = client.get("/api/me/saves", headers=mh)
    assert lst.status_code == 200
    data = lst.json()["data"]
    assert data["total"] == 1
    assert data["sessions"][0]["id"] == session_id
    assert "saved_at" in data["sessions"][0]

    # Unsave
    d = client.delete(f"/api/me/saves/{session_id}", headers=mh)
    assert d.status_code == 200
    assert d.json()["data"]["removed"] is True

    # Unsave again — idempotent
    d2 = client.delete(f"/api/me/saves/{session_id}", headers=mh)
    assert d2.status_code == 200
    assert d2.json()["data"]["removed"] is False

    # List now empty
    lst2 = client.get("/api/me/saves", headers=mh)
    assert lst2.json()["data"]["total"] == 0


def test_save_unpublished_session_returns_404(client):
    provider_token, _ = _register_provider(client)
    member_token = _register_member(client)

    h = {"Authorization": f"Bearer {provider_token}"}
    s = client.post("/api/sessions", json={
        "patient_initials": "TP", "treatment": "Botox", "category": "Botox", "status": "draft",
    }, headers=h)
    draft_id = s.json()["data"]["id"]

    r = client.post(f"/api/me/saves/{draft_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 404


def test_save_requires_auth(client):
    r = client.post("/api/me/saves/some-id")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Follows
# ---------------------------------------------------------------------------

def test_follow_unfollow_and_list(client):
    provider_token, practice_id = _register_provider(client)
    member_token = _register_member(client)
    mh = {"Authorization": f"Bearer {member_token}"}

    # Follow — expect 201
    r = client.post(f"/api/me/follows/{practice_id}", headers=mh)
    assert r.status_code == 201
    assert r.json()["data"]["practice_id"] == practice_id

    # Idempotent — expect 200
    r2 = client.post(f"/api/me/follows/{practice_id}", headers=mh)
    assert r2.status_code == 200

    # List
    lst = client.get("/api/me/follows", headers=mh)
    assert lst.status_code == 200
    data = lst.json()["data"]
    assert data["total"] == 1
    assert data["practices"][0]["id"] == practice_id
    assert "followed_at" in data["practices"][0]
    assert "published_session_count" in data["practices"][0]

    # Unfollow
    d = client.delete(f"/api/me/follows/{practice_id}", headers=mh)
    assert d.status_code == 200
    assert d.json()["data"]["removed"] is True

    # Unfollow again — idempotent
    d2 = client.delete(f"/api/me/follows/{practice_id}", headers=mh)
    assert d2.json()["data"]["removed"] is False

    # List now empty
    assert client.get("/api/me/follows", headers=mh).json()["data"]["total"] == 0


def test_follow_nonexistent_practice_returns_404(client):
    member_token = _register_member(client)
    r = client.post("/api/me/follows/does-not-exist", headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

def test_approvals_only_shows_callers_followups(client):
    provider_token, _ = _register_provider(client, "prov2@test.com")
    member_a_token = _register_member(client, "member_a@test.com")
    member_b_token = _register_member(client, "member_b@test.com")

    session_id = _make_published_session(client, provider_token)
    _create_sent_followup(client, provider_token, session_id, "member_a@test.com")

    # member_a sees the approval
    ra = client.get("/api/me/approvals", headers={"Authorization": f"Bearer {member_a_token}"})
    assert ra.status_code == 200
    assert len(ra.json()["data"]["approvals"]) == 1

    # member_b sees nothing
    rb = client.get("/api/me/approvals", headers={"Authorization": f"Bearer {member_b_token}"})
    assert rb.status_code == 200
    assert len(rb.json()["data"]["approvals"]) == 0


def test_approval_respond_mirrors_token_flow(client):
    provider_token, _ = _register_provider(client, "prov3@test.com")
    member_token = _register_member(client, "patient@test.com")

    session_id = _make_published_session(client, provider_token)
    followup_id = _create_sent_followup(client, provider_token, session_id, "patient@test.com")

    mh = {"Authorization": f"Bearer {member_token}"}

    # Approvals list shows the followup
    approvals = client.get("/api/me/approvals", headers=mh).json()["data"]["approvals"]
    assert len(approvals) == 1
    assert approvals[0]["id"] == followup_id
    assert "discount_offer" in approvals[0]
    assert "session" in approvals[0]

    # Respond with full_blur
    r = client.post(f"/api/me/approvals/{followup_id}/respond", headers=mh, json={
        "decision": "full_blur",
        "signature_svg": "M10 35 Q30 10 50 30 T90 25",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["consent_tier"] == "full_blur"
    assert data["reward_earned"] is not None
    assert data["reward_earned"]["consent_tier"] == "full_blur"

    # Session transitioned to ready_to_publish (auto_publish is False by default)
    ph = {"Authorization": f"Bearer {provider_token}"}
    sess = client.get(f"/api/sessions/{session_id}", headers=ph).json()["data"]
    assert sess["consent_tier"] == "full_blur"
    assert sess["status"] == "ready_to_publish"

    # Credit was created
    credits = client.get("/api/credits", headers=ph).json()["data"]["credits"]
    session_credits = [c for c in credits if c["session_id"] == session_id]
    assert len(session_credits) == 1
    assert session_credits[0]["consent_tier"] == "full_blur"

    # Approval no longer shows (followup completed)
    approvals_after = client.get("/api/me/approvals", headers=mh).json()["data"]["approvals"]
    assert len(approvals_after) == 0


_SVG = "M10 35 Q30 10 50 30 T90 25"


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def test_results_shows_own_sessions_including_unpublished(client):
    provider_token, _ = _register_provider(client, "prov_res@test.com")
    member_token = _register_member(client, "patient_res@test.com")

    session_id = _make_published_session(client, provider_token)
    _create_sent_followup(client, provider_token, session_id, "patient_res@test.com")

    mh = {"Authorization": f"Bearer {member_token}"}
    r = client.get("/api/me/results", headers=mh)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 1
    s = data["sessions"][0]
    assert s["id"] == session_id
    assert "status" in s
    assert "consent_tier" in s


def test_results_deduplicates_multiple_followups_on_same_session(client):
    provider_token, _ = _register_provider(client, "prov_res2@test.com")
    member_token = _register_member(client, "patient_res2@test.com")

    session_id = _make_published_session(client, provider_token)
    # Create two followups on the same session
    _create_sent_followup(client, provider_token, session_id, "patient_res2@test.com")
    _create_sent_followup(client, provider_token, session_id, "patient_res2@test.com")

    mh = {"Authorization": f"Bearer {member_token}"}
    r = client.get("/api/me/results", headers=mh)
    assert r.json()["data"]["total"] == 1  # deduplicated


def test_results_does_not_show_other_users_sessions(client):
    provider_token, _ = _register_provider(client, "prov_res3@test.com")
    member_a = _register_member(client, "patient_resa@test.com")
    member_b = _register_member(client, "patient_resb@test.com")

    session_id = _make_published_session(client, provider_token)
    _create_sent_followup(client, provider_token, session_id, "patient_resa@test.com")

    r = client.get("/api/me/results", headers={"Authorization": f"Bearer {member_b}"})
    assert r.json()["data"]["total"] == 0


def test_approval_respond_wrong_user_gets_404(client):
    """Wrong user gets 404 (not 403) — safer: doesn't confirm resource exists."""
    provider_token, _ = _register_provider(client, "prov4@test.com")
    _register_member(client, "owner@test.com")
    intruder_token = _register_member(client, "intruder@test.com")

    session_id = _make_published_session(client, provider_token)
    followup_id = _create_sent_followup(client, provider_token, session_id, "owner@test.com")

    r = client.post(f"/api/me/approvals/{followup_id}/respond",
        headers={"Authorization": f"Bearer {intruder_token}"},
        json={"decision": "full_blur", "signature_svg": _SVG})
    assert r.status_code == 404


def test_approval_respond_already_completed_gets_409(client):
    provider_token, _ = _register_provider(client, "prov5@test.com")
    member_token = _register_member(client, "patient2@test.com")

    session_id = _make_published_session(client, provider_token)
    followup_id = _create_sent_followup(client, provider_token, session_id, "patient2@test.com")

    mh = {"Authorization": f"Bearer {member_token}"}
    # First response succeeds
    client.post(f"/api/me/approvals/{followup_id}/respond", headers=mh,
        json={"decision": "full_blur", "signature_svg": _SVG})

    # Second response is 409
    r2 = client.post(f"/api/me/approvals/{followup_id}/respond", headers=mh,
        json={"decision": "full_blur", "signature_svg": _SVG})
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# Activity feed
# ---------------------------------------------------------------------------

def _session_with_images(client, provider_token):
    """Create a session with before+after images in pending_consent state (not published)."""
    h = {"Authorization": f"Bearer {provider_token}"}
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
    return sid


def _complete_followup(client, provider_token, session_id, member_email, member_token):
    """Create a sent followup, member responds (→ ready_to_publish), provider publishes."""
    followup_id = _create_sent_followup(client, provider_token, session_id, member_email)
    mh = {"Authorization": f"Bearer {member_token}"}
    r = client.post(f"/api/me/approvals/{followup_id}/respond", headers=mh,
        json={"decision": "full", "signature_svg": _SVG})
    assert r.status_code == 200
    # Provider publishes so the case_published event appears in the feed
    ph = {"Authorization": f"Bearer {provider_token}"}
    pub = client.post(f"/api/sessions/{session_id}/publish", headers=ph,
        json={"destinations": ["gallery"], "treatment_details": ""})
    assert pub.status_code == 200
    return followup_id


def test_activity_member_sees_own_events(client):
    provider_token, _ = _register_provider(client, "prov_act@test.com")
    member_token = _register_member(client, "patient_act@test.com")

    session_id = _session_with_images(client, provider_token)
    _complete_followup(client, provider_token, session_id, "patient_act@test.com", member_token)

    mh = {"Authorization": f"Bearer {member_token}"}
    r = client.get("/api/me/activity", headers=mh)
    assert r.status_code == 200
    data = r.json()["data"]
    assert "items" in data
    assert "total" in data

    kinds = {item["kind"] for item in data["items"]}
    # approval_completed is always generated for a completed followup
    assert "approval_completed" in kinds
    # credit_earned since full consent was given
    assert "credit_earned" in kinds
    # case was published (by _make_published_session) + followup is completed
    assert "case_published" in kinds

    # All items have required fields with correct types
    for item in data["items"]:
        assert item["id"].startswith(item["kind"] + "-")
        assert isinstance(item["text"], str) and item["text"]
        assert isinstance(item["timestamp"], str)
        assert "session_id" in item

    assert data["total"] == len(data["items"])


def test_activity_another_users_rows_never_leak(client):
    provider_token, _ = _register_provider(client, "prov_act2@test.com")
    member_a_token = _register_member(client, "act_a@test.com")
    member_b_token = _register_member(client, "act_b@test.com")

    session_id = _session_with_images(client, provider_token)
    _complete_followup(client, provider_token, session_id, "act_a@test.com", member_a_token)

    # member_b should see nothing
    r = client.get("/api/me/activity", headers={"Authorization": f"Bearer {member_b_token}"})
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 0
    assert r.json()["data"]["items"] == []


def test_activity_empty_returns_zero(client):
    member_token = _register_member(client, "act_empty@test.com")
    r = client.get("/api/me/activity", headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data == {"items": [], "total": 0}


def test_activity_requires_auth(client):
    r = client.get("/api/me/activity")
    assert r.status_code == 401


def test_activity_case_published_appears_at_most_once_per_session(client):
    """A published session must produce exactly one case_published event regardless of
    how many completed followups reference it."""
    provider_token, _ = _register_provider(client, "prov_act3@test.com")
    member_token = _register_member(client, "act_dedup@test.com")

    session_id = _session_with_images(client, provider_token)
    _complete_followup(client, provider_token, session_id, "act_dedup@test.com", member_token)

    mh = {"Authorization": f"Bearer {member_token}"}
    items = client.get("/api/me/activity", headers=mh).json()["data"]["items"]

    published_ids = [i["id"] for i in items if i["kind"] == "case_published"]
    # At most one case_published per session — IDs must be unique
    assert len(published_ids) == len(set(published_ids)), "case_published IDs must be unique"
    # Exactly one for this session
    assert len(published_ids) == 1


def test_activity_sorted_newest_first(client):
    provider_token, _ = _register_provider(client, "prov_act4@test.com")
    member_token = _register_member(client, "act_sort@test.com")

    session_id = _session_with_images(client, provider_token)
    _complete_followup(client, provider_token, session_id, "act_sort@test.com", member_token)

    mh = {"Authorization": f"Bearer {member_token}"}
    items = client.get("/api/me/activity", headers=mh).json()["data"]["items"]

    timestamps = [item["timestamp"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True), "events must be newest-first"


# ---------------------------------------------------------------------------
# §9 Member-facing rewards list + credit_id in activity events
# ---------------------------------------------------------------------------

def _earn_credit(client, provider_token, member_email, member_token):
    """Full flow that results in a credit: session + followup + member responds."""
    session_id = _session_with_images(client, provider_token)
    followup_id = _create_sent_followup(client, provider_token, session_id, member_email)
    mh = {"Authorization": f"Bearer {member_token}"}
    client.post(f"/api/me/approvals/{followup_id}/respond", headers=mh,
        json={"decision": "full", "signature_svg": _SVG})
    # Publish so after_image_url resolves
    ph = {"Authorization": f"Bearer {provider_token}"}
    client.post(f"/api/sessions/{session_id}/publish", headers=ph,
        json={"destinations": ["gallery"], "treatment_details": ""})
    return session_id


def test_credits_returns_earned_credits_newest_first(client):
    provider_token, _ = _register_provider(client, "cred_prov@test.com")
    member_token = _register_member(client, "cred_mem@test.com")
    mh = {"Authorization": f"Bearer {member_token}"}

    _earn_credit(client, provider_token, "cred_mem@test.com", member_token)
    _earn_credit(client, provider_token, "cred_mem@test.com", member_token)

    r = client.get("/api/me/credits", headers=mh)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 2
    credits = data["credits"]
    assert len(credits) == 2

    # Newest first
    assert credits[0]["earned_at"] >= credits[1]["earned_at"]

    # Each item has practice and session nested
    c = credits[0]
    assert c["practice"]["name"] is not None
    assert c["session"]["treatment"] is not None
    assert "after_image_url" in c["session"]


def test_credits_empty_for_member_with_none(client):
    member_token = _register_member(client, "cred_empty@test.com")
    r = client.get("/api/me/credits", headers={"Authorization": f"Bearer {member_token}"})
    assert r.status_code == 200
    assert r.json()["data"] == {"credits": [], "total": 0}


def test_credits_excludes_other_members(client):
    provider_token, _ = _register_provider(client, "cred_prov2@test.com")
    member_a_token = _register_member(client, "cred_a@test.com")
    member_b_token = _register_member(client, "cred_b@test.com")

    _earn_credit(client, provider_token, "cred_a@test.com", member_a_token)

    r = client.get("/api/me/credits", headers={"Authorization": f"Bearer {member_b_token}"})
    assert r.json()["data"]["total"] == 0


def test_credits_qr_linked_member_sees_credit(client):
    """QR-linked followup (patient_user_id, no typed email): §7 backfills account email
    onto followup.patient_email, so the plain email filter still finds the credit."""
    provider_token, _ = _register_provider(client, "cred_prov3@test.com")
    member_token = _register_member(client, "cred_qr@test.com")
    member_id = client.get("/api/users/me",
        headers={"Authorization": f"Bearer {member_token}"}).json()["data"]["id"]
    ph = {"Authorization": f"Bearer {provider_token}"}
    mh = {"Authorization": f"Bearer {member_token}"}

    session_id = _session_with_images(client, provider_token)

    # Create followup via patient_user_id only (no email)
    fid_r = client.post(f"/api/sessions/{session_id}/followup", headers=ph, json={
        "patient_user_id": member_id,
        "send_at": "2020-01-01T00:00:00Z",
    })
    assert fid_r.status_code == 201
    followup_id = fid_r.json()["data"]["id"]

    # Member responds → credit created with account email as patient_email
    client.post(f"/api/me/approvals/{followup_id}/respond", headers=mh,
        json={"decision": "full", "signature_svg": _SVG})

    r = client.get("/api/me/credits", headers=mh)
    assert r.json()["data"]["total"] == 1


def test_activity_credit_events_include_credit_id(client):
    provider_token, _ = _register_provider(client, "cred_prov4@test.com")
    member_token = _register_member(client, "cred_act@test.com")

    _earn_credit(client, provider_token, "cred_act@test.com", member_token)

    activity = client.get("/api/me/activity",
        headers={"Authorization": f"Bearer {member_token}"})
    items = activity.json()["data"]["items"]

    credit_events = [i for i in items if i["kind"] in ("credit_earned", "credit_expiring")]
    assert len(credit_events) >= 1
    for event in credit_events:
        assert "credit_id" in event, f"credit_id missing from {event['kind']}"
        assert event["credit_id"] is not None
        assert "session_id" in event  # existing field still present
