import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.settings import Settings
from app.main import create_app


def test_health_endpoint():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_production_refuses_the_default_secret():
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key="dev-only-change-me")  # noqa: S106
    with pytest.raises(ValidationError):
        Settings(environment="production", secret_key="too-short")  # noqa: S106
    assert Settings(environment="production", secret_key="x" * 40).environment == "production"  # noqa: S106
