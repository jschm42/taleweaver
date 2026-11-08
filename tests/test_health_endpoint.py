"""The liveness endpoint the frontend's backend status banner probes."""

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import backend.main

INDEX_HTML = "<!doctype html><html><body>TaleWeaver SPA</body></html>"


def _load_app_with_frontend_dist(project_root: Path):
    """Execute ``backend/main.py`` as a fresh module that sees ``<project_root>/frontend_dist``.

    The SPA routes are registered at import time from a path derived from ``__file__``,
    so the module is loaded from the real source but with ``__file__`` inside ``project_root``.
    """
    dist_dir = project_root / "frontend_dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")

    module_name = "backend_main_with_frontend_dist"
    loader = SourceFileLoader(module_name, backend.main.__file__)
    fake_file = project_root / "backend" / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, str(fake_file), loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module.app


@pytest.mark.asyncio
async def test_api_health_returns_json_ok(client):
    # Act
    response = await client.get("/api/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_root_health_returns_ok(client):
    # Act
    response = await client.get("/health")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_spa_catchall_does_not_shadow_api_routes(tmp_path):
    # Arrange
    app = _load_app_with_frontend_dist(tmp_path)

    # Act
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        health = await ac.get("/api/health")
        root_health = await ac.get("/health")
        unknown_api = await ac.get("/api/nonexistent")
        bare_api = await ac.get("/api")
        spa_page = await ac.get("/some/client/route")

    # Assert
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert "application/json" in health.headers["content-type"]
    assert root_health.status_code == 200
    assert root_health.json() == {"status": "ok"}
    assert unknown_api.status_code == 404
    assert "TaleWeaver SPA" not in unknown_api.text
    assert unknown_api.json() == {"detail": "API endpoint not found"}
    assert bare_api.status_code == 404
    assert spa_page.status_code == 200
    assert "TaleWeaver SPA" in spa_page.text
