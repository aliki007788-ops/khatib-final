def test_register_and_login(client):
    register = client.post(
        "/api/auth/register",
        json={
            "email": "auth2@example.com",
            "password": "Secure123",
            "name": "Auth User",
        },
    )
    assert register.status_code in {201, 409}

    login = client.post(
        "/api/auth/login",
        json={
            "email": "auth2@example.com",
            "password": "Secure123",
        },
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


def test_me_requires_authentication(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "wrongpw@example.com", "password": "Test1234", "name": "X"},
    )
    response = client.post(
        "/api/auth/login",
        json={"email": "wrongpw@example.com", "password": "bad-password"},
    )
    assert response.status_code in {401, 423}
