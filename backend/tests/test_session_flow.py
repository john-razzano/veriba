import base64


TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBUQEBQWFRUVFRUVFRUVFRUVFRUVFRUWFhUV"
    "FRUYHSggGBolHRUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGhAQGi0fIB0tLS0tLS0tLS0t"
    "LS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/"
    "xAAbAAABBQEBAAAAAAAAAAAAAAAFAAIDBAYBB//EADQQAAIBAgQDBgQEBwAAAAAAAAECAwQRAAUS"
    "ITEGE0FRImFxgZEUMqGxwdHwI0JSYnKS8RUzQ1Oi/8QAGQEAAwEBAQAAAAAAAAAAAAAAAAECAwQF"
    "/8QAJBEAAgICAgICAgMBAAAAAAAAAAECEQMhEjEEQRMiUWEUMnH/2gAMAwEAAhEDEQA/APn6iii"
    "gAooooAKKKKACiiigAooooAKKKKACiiigD//2Q=="
)


def _register_and_auth(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "doctor@example.com",
            "password": "supersecret",
            "name": "Dr Provider",
            "practice_name": "Glow Clinic",
            "practice_location": "Reno, NV",
            "practice_website": "glowclinic.com",
        },
    )
    return response.json()["data"]["access_token"]


def test_session_upload_consent_publish_flow(client):
    token = _register_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/sessions",
        json={
            "patient_initials": "AM",
            "treatment": "Botox - Forehead",
            "category": "Botox",
            "status": "draft",
        },
        headers=headers,
    )
    assert created.status_code == 201
    session_id = created.json()["data"]["id"]

    before = client.post(
        f"/api/sessions/{session_id}/images/before",
        headers=headers,
        files={"file": ("before.jpg", TINY_JPEG, "image/jpeg")},
        data={"capture_hash": "manualhash", "capture_lat": "39.5296", "capture_lng": "-119.8138"},
    )
    assert before.status_code == 200
    assert before.json()["data"]["image_url"]

    after = client.post(
        f"/api/sessions/{session_id}/images/after",
        headers=headers,
        files={"file": ("after.jpg", TINY_JPEG, "image/jpeg")},
    )
    assert after.status_code == 200

    consent = client.post(
        f"/api/sessions/{session_id}/consent",
        headers=headers,
        json={"consent_tier": "full", "signature_svg": "M10 35 Q30 10 50 30 T90 25"},
    )
    assert consent.status_code == 200
    assert consent.json()["data"]["session_status"] == "ready_to_publish"

    publish = client.post(
        f"/api/sessions/{session_id}/publish",
        headers=headers,
        json={"destinations": ["widget", "gallery"], "treatment_details": "20 units"},
    )
    assert publish.status_code == 200
    assert publish.json()["data"]["status"] == "published"
