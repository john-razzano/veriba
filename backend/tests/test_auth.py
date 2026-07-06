def test_register_login_and_profile(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "supersecret",
            "name": "Jane Owner",
            "practice_name": "Luxe Aesthetics Demo",
            "practice_location": "Reno, NV",
            "practice_website": "luxeaesthetics.com",
        },
    )
    assert register_response.status_code == 201
    payload = register_response.json()["data"]
    assert payload["user"]["email"] == "owner@example.com"
    assert payload["practice"]["widget_slug"] == "luxe-aesthetics-demo"

    login_response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "supersecret"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["data"]["access_token"]

    me_response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["data"]["name"] == "Jane Owner"


def test_member_registration_and_login(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "member@example.com",
            "password": "supersecret",
            "name": "Mia Member",
            "role": "member",
        },
    )
    assert register_response.status_code == 201
    payload = register_response.json()["data"]
    assert payload["user"]["email"] == "member@example.com"
    assert payload["user"]["role"] == "member"
    assert payload["user"]["practice_id"] is None
    assert payload["practice"] is None

    login_response = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "supersecret"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["data"]["access_token"]

    me_response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["data"]["role"] == "member"


def test_member_cannot_access_practice_endpoints(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "member2@example.com",
            "password": "supersecret",
            "name": "Max Member",
            "role": "member",
        },
    )
    access_token = register_response.json()["data"]["access_token"]

    stats_response = client.get(
        "/api/credits/stats",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert stats_response.status_code == 403


def test_provider_registration_requires_practice_fields(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "owner2@example.com",
            "password": "supersecret",
            "name": "Paul Provider",
        },
    )
    assert response.status_code == 422
