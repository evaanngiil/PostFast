"""
Tests unitarios para la inicialización y endpoints de la API de FastAPI y servidor ASGI.
"""
from fastapi.testclient import TestClient
from uvicorn.config import Config

from src.main import app, OnboardingPayload


def test_app_initialization_and_metadata():
    assert app.title == "AIPost API"
    assert app.router is not None


def test_onboarding_payload_schema():
    payload = OnboardingPayload(role="Content Creator", goals=["engagement", "reach"])
    assert payload.role == "Content Creator"
    assert len(payload.goals) == 2


def test_uvicorn_config_loads_app():
    config = Config("src.main:app")
    assert hasattr(config, "http2")
    config.load()
    assert config.loaded is True
    assert config.app is not None


def test_fastapi_endpoints_without_auth():
    client = TestClient(app, raise_server_exceptions=False)
    
    # Root or auth routes redirect / respond
    response = client.get("/auth/email-confirmed", follow_redirects=False)
    assert response.status_code in (200, 307, 302)

    # Protected content route without auth token returns 401/403
    prot_response = client.get("/content/posts")
    assert prot_response.status_code in (401, 403)
