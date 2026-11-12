"""Tests for basic API availability."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_healthy_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root_endpoint_returns_running_message() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "CAT Prep AI API is running"}


def test_access_token_protects_study_data(monkeypatch) -> None:
    monkeypatch.setenv("APP_ACCESS_TOKEN", "test-secret")
    assert client.get("/health").status_code == 200
    assert client.get("/performance/dashboard").status_code == 401
    assert client.get("/performance/dashboard", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/performance/dashboard", headers={"Authorization": "Bearer test-secret"}).status_code == 200
