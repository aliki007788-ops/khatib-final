from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-testing-123456789"
os.environ["PASSWORD_PEPPER"] = "test-password-pepper-12345678901234567890"
os.environ["COOKIE_SECURE"] = "false"
os.environ["PAYMENT_PROVIDER"] = "demo"
os.environ["REDIS_REQUIRED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.core.db import Base, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    import os
    os.makedirs("data", exist_ok=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def registered_user(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "Test1234",
            "name": "Test User",
        },
    )
    login = client.post(
        "/api/auth/login",
        json={
            "email": "user@example.com",
            "password": "Test1234",
        },
    )
    assert login.status_code == 200
    return login.json()["access_token"]
