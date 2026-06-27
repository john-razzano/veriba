def test_register_login_and_profile(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "supersecret",
            "name": "Jane Owner",
            "practice_name": "Luxe Aesthetics",
            "practice_location": "Reno, NV",
            "practice_website": "luxeaesthetics.com",
        },
    )
    assert register_response.status_code == 201
    payload = register_response.json()["data"]
    assert payload["user"]["email"] == "owner@example.com"
    assert payload["practice"]["widget_slug"] == "luxe-aesthetics"

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

