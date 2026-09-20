def test_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_request_id_is_returned(client):
    response = client.get(
        "/health/live",
        headers={"X-Request-ID": "test-request-123"},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-123"


def test_security_headers(client):
    response = client.get("/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
