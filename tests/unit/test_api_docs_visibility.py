"""API documentation routes are disabled in production by default."""

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.config import settings


def test_docs_and_openapi_routes_are_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_DOCS", False)
    app = main_module.create_app()
    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert app.docs_url is None
    assert app.openapi_url is None


def test_docs_route_can_be_enabled_for_development(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_DOCS", True)
    app = main_module.create_app()
    client = TestClient(app)

    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"
    assert client.get("/openapi.json").status_code == 200
