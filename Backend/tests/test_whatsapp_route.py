from fastapi.testclient import TestClient
import pytest

from core import config
from main import app
from routes import whatsapp as whatsapp_route


@pytest.fixture(autouse=True)
def reset_cache():
    whatsapp_route._CACHED_QR_SVG = None
    whatsapp_route._CACHED_TARGET_URL = None
    yield
    whatsapp_route._CACHED_QR_SVG = None
    whatsapp_route._CACHED_TARGET_URL = None


def test_whatsapp_info_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PUBLIC_NUMBER", "")
    client = TestClient(app)
    response = client.get("/api/whatsapp")
    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "number": None,
        "display": None,
        "url": None,
        "qr_url": None,
    }


def test_whatsapp_qr_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PUBLIC_NUMBER", "")
    client = TestClient(app)
    response = client.get("/api/whatsapp/qr.svg")
    assert response.status_code == 404


def test_whatsapp_info_configured(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PUBLIC_NUMBER", "923492468494")
    client = TestClient(app)
    response = client.get("/api/whatsapp")
    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "number": "923492468494",
        "display": "+92 349 2468494",
        "url": "https://wa.me/923492468494",
        "qr_url": "/api/whatsapp/qr.svg",
    }


def test_whatsapp_qr_configured(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_PUBLIC_NUMBER", "923492468494")
    client = TestClient(app)
    response = client.get("/api/whatsapp/qr.svg")
    assert response.status_code == 200
    assert "image/svg+xml" in response.headers.get("content-type", "")
    assert response.headers.get("cache-control") == "public, max-age=3600"
    content = response.text
    assert "<svg" in content
    # Verify caching
    response2 = client.get("/api/whatsapp/qr.svg")
    assert response2.content == response.content
