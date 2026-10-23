"""Tests for catalog parsing, validation and the cache/fallback layers (spec section 9).

All HTTP traffic goes through ``httpx.MockTransport``; no test touches the network.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest

from backend.core.config import settings
from backend.services.adventure_library import catalog as catalog_module
from backend.services.adventure_library.catalog import CatalogError, CatalogService, parse_catalog
from backend.services.adventure_library.models import AdventureCatalog

RELEASES = "https://github.com/jschm42/taleweaver-adventures/releases/download"


def _entry(slug: str = "dark-forest", **overrides: Any) -> dict[str, Any]:
    """A schema-1 catalog entry that passes every validation rule."""
    entry = {
        "id": f"origin-{slug}",
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "version": "1.0.0",
        "size_bytes": 1024,
        "sha256": "a" * 64,
        "download_url": f"{RELEASES}/{slug}-1.0.0/{slug}-1.0.0.adz",
    }
    entry.update(overrides)
    return entry


def _catalog(*entries: dict[str, Any], schema: int = 1) -> dict[str, Any]:
    return {"schema": schema, "generator": "test", "adventures": list(entries)}


@pytest.fixture(autouse=True)
def isolated_catalog_cache(monkeypatch, tmp_path):
    """Point the disk cache at tmp_path and start every test with an empty memory cache."""
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setitem(catalog_module._MEMORY_CACHE, "catalog", None)
    monkeypatch.setitem(catalog_module._MEMORY_CACHE, "timestamp", 0.0)
    monkeypatch.setitem(catalog_module._MEMORY_CACHE, "ttl", 0.0)
    monkeypatch.setitem(catalog_module._MEMORY_CACHE, "stale", False)


def _write_cache(payload: dict[str, Any], etag: str | None, age: timedelta) -> None:
    path = catalog_module.catalog_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc) - age
    record = {"etag": etag, "fetched_at": fetched_at.isoformat(), "payload": payload}
    path.write_text(json.dumps(record), encoding="utf-8")


def test_valid_catalog_parses_into_model():
    # Arrange
    payload = _catalog(_entry("dark-forest"), _entry("sunken-city"))

    # Act
    catalog = parse_catalog(payload)

    # Assert
    assert isinstance(catalog, AdventureCatalog)
    assert catalog.schema_ == 1
    assert [entry.slug for entry in catalog.adventures] == ["dark-forest", "sunken-city"]


def test_unknown_entry_fields_are_ignored():
    # Arrange
    payload = _catalog(_entry(rating=5, future_field={"nested": True}))

    # Act
    catalog = parse_catalog(payload)

    # Assert
    assert len(catalog.adventures) == 1
    assert not hasattr(catalog.adventures[0], "future_field")


def test_unsupported_schema_is_rejected():
    # Arrange
    payload = _catalog(_entry(), schema=2)

    # Act / Assert
    with pytest.raises(CatalogError, match="unsupported catalog schema"):
        parse_catalog(payload)


async def test_unsupported_remote_schema_falls_back_to_snapshot(monkeypatch, tmp_path):
    # Arrange
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(_catalog(_entry("bundled"))), encoding="utf-8")
    monkeypatch.setattr(catalog_module, "SNAPSHOT_PATH", snapshot)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=_catalog(schema=2)))

    # Act
    async with httpx.AsyncClient(transport=transport) as client:
        service = CatalogService(http_client=client)
        catalog = await service.get_catalog()

    # Assert
    assert [entry.slug for entry in catalog.adventures] == ["bundled"]
    assert service.is_stale() is True


def test_entry_missing_mandatory_field_is_rejected():
    # Arrange
    broken = _entry("broken")
    del broken["sha256"]
    payload = _catalog(broken, _entry("intact"))

    # Act
    catalog = parse_catalog(payload)

    # Assert
    assert [entry.slug for entry in catalog.adventures] == ["intact"]


def test_http_download_url_entry_is_dropped_rest_survives():
    # Arrange
    insecure = _entry("insecure", download_url="http://github.com/x/insecure.adz")
    payload = _catalog(insecure, _entry("secure"))

    # Act
    catalog = parse_catalog(payload)

    # Assert
    assert [entry.slug for entry in catalog.adventures] == ["secure"]


def test_non_allowlisted_host_entry_is_dropped():
    # Arrange
    foreign = _entry("foreign", download_url="https://evil.example/foreign.adz")
    payload = _catalog(foreign, _entry("trusted"))

    # Act
    catalog = parse_catalog(payload)

    # Assert
    assert [entry.slug for entry in catalog.adventures] == ["trusted"]


def test_size_above_download_cap_is_dropped(monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "ADVENTURE_DOWNLOAD_MAX_BYTES", 2048)
    payload = _catalog(_entry("huge", size_bytes=2049), _entry("small", size_bytes=2048))

    # Act
    catalog = parse_catalog(payload)

    # Assert
    assert [entry.slug for entry in catalog.adventures] == ["small"]


async def test_snapshot_fallback_when_fetch_raises(monkeypatch, tmp_path):
    # Arrange
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(_catalog(_entry("offline"))), encoding="utf-8")
    monkeypatch.setattr(catalog_module, "SNAPSHOT_PATH", snapshot)

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network unreachable", request=request)

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as client:
        service = CatalogService(http_client=client)
        catalog = await service.get_catalog()

    # Assert
    assert [entry.slug for entry in catalog.adventures] == ["offline"]
    assert service.is_stale() is True


async def test_not_modified_keeps_previously_cached_catalog():
    # Arrange
    _write_cache(_catalog(_entry("cached")), etag='"v1"', age=timedelta(days=1))
    seen_etags: list[str | None] = []

    def not_modified(request: httpx.Request) -> httpx.Response:
        seen_etags.append(request.headers.get("if-none-match"))
        return httpx.Response(304)

    # Act
    async with httpx.AsyncClient(transport=httpx.MockTransport(not_modified)) as client:
        service = CatalogService(http_client=client)
        catalog = await service.get_catalog()

    # Assert
    assert seen_etags == ['"v1"']
    assert [entry.slug for entry in catalog.adventures] == ["cached"]
    assert service.is_stale() is False
