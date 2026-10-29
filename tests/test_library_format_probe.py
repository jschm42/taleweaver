"""Tests for reading library adventures' manifest format versions from file headers."""

import json

import httpx
import pytest

from backend.core.adventure_format import is_deprecated_version
from backend.core.config import settings
from backend.services.adventure_library.catalog import LibraryService, cache_path
from backend.services.adventure_library.format_probe import HEADER_BYTES, parse_format_version

OLD_ID = "11111111-1111-1111-1111-111111111111"
NEW_ID = "22222222-2222-2222-2222-222222222222"
LISTED_ID = "33333333-3333-3333-3333-333333333333"


def _entry(adventure_id: str, slug: str, **extra) -> dict:
    return {"id": adventure_id, "slug": slug, "title": slug, "version": "1.0.0",
            "files": ["adventure.adv"], **extra}  # fmt: skip


def _header(version: str) -> bytes:
    body = {"format": "TaleWeaver", "version": version, "adventure": {"version": "9.9.9"}}
    return json.dumps(body, indent=2).encode() + b" " * 4096


def test_parse_format_version_reads_only_the_top_level_key():
    # Act / Assert
    assert parse_format_version(_header("1.3")) == "1.3"
    assert parse_format_version(b'{"adventure": {"version": "3.0.0"}, "version": "1.3"}') is None
    assert parse_format_version(b"not json at all") is None


def test_deprecation_threshold_treats_missing_versions_as_unknown():
    # Act / Assert
    assert is_deprecated_version("1.3") is True
    assert is_deprecated_version("1.3.0") is True
    assert is_deprecated_version("1.3.1") is False
    assert is_deprecated_version(None) is False
    assert is_deprecated_version("next") is False


@pytest.mark.asyncio
async def test_catalog_marks_entries_with_old_format_as_deprecated(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    index = {
        "schema": 1,
        "adventures": [
            _entry(OLD_ID, "old-quest"),
            _entry(NEW_ID, "new-quest"),
            _entry(LISTED_ID, "listed-quest", format_version="1.3.1"),
        ],
    }
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path.endswith("library.json"):
            return httpx.Response(200, json=index)
        assert request.headers["Range"] == f"bytes=0-{HEADER_BYTES - 1}"
        if "old-quest" in request.url.path:
            return httpx.Response(206, content=_header("1.3")[:HEADER_BYTES])
        # A server that ignores Range still only gets read up to HEADER_BYTES.
        return httpx.Response(200, content=_header("1.3.1"))

    service = LibraryService(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    service.invalidate()

    # Act
    library = await service.get_library(force_refresh=True)
    service.invalidate()

    # Assert
    by_id = {entry.id: entry for entry in library.adventures}
    assert by_id[OLD_ID].format_version == "1.3"
    assert by_id[OLD_ID].deprecated is True
    assert by_id[NEW_ID].deprecated is False
    assert by_id[LISTED_ID].deprecated is False
    assert not any("listed-quest" in path for path in requested)
    disk_copy = json.loads(cache_path().read_text(encoding="utf-8"))
    assert disk_copy["adventures"][0]["format_version"] == "1.3"


@pytest.mark.asyncio
async def test_failed_probe_leaves_entry_unmarked(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    index = {"schema": 1, "adventures": [_entry(OLD_ID, "old-quest")]}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("library.json"):
            return httpx.Response(200, json=index)
        raise httpx.ConnectError("offline")

    service = LibraryService(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    service.invalidate()

    # Act
    library = await service.get_library(force_refresh=True)
    service.invalidate()

    # Assert
    assert library.adventures[0].format_version is None
    assert library.adventures[0].deprecated is False
