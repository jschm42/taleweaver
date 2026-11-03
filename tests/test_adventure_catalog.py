"""Tests for library.json parsing, path validation and the cache/fallback layers.

All HTTP traffic goes through ``httpx.MockTransport``; no test touches the network.
"""

import json
from typing import Any

import httpx
import pytest

from backend.core.config import settings
from backend.services.adventure_library import catalog as catalog_module
from backend.services.adventure_library.catalog import (
    LibraryError,
    LibraryService,
    library_url,
    parse_library,
)
from backend.services.adventure_library.models import is_safe_member_path

BASE = "https://raw.githubusercontent.com/jschm42/taleweaver-adventures/main"
COMMIT_API = "https://api.github.com/repos/jschm42/taleweaver-adventures/commits/main"
SHA = "0123456789abcdef0123456789abcdef01234567"
PINNED = f"https://raw.githubusercontent.com/jschm42/taleweaver-adventures/{SHA}"


def _entry(slug: str = "dark-forest", **overrides: Any) -> dict[str, Any]:
    """A library.json entry that passes every validation rule."""
    entry = {
        "id": f"origin-{slug}",
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "version": "1.0.0",
        "cover": "assets/cover.jpg",
        "size_bytes": 2048,
        "files": ["adventure.adv", "assets/cover.jpg"],
    }
    entry.update(overrides)
    return entry


def _index(*entries: dict[str, Any], schema: int = 1) -> dict[str, Any]:
    return {"schema": schema, "adventures": list(entries)}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def isolated_library_cache(monkeypatch, tmp_path):
    """Point the disk copy at tmp_path and start every test with an empty memory cache."""
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ADVENTURE_LIBRARY_URL", BASE)
    LibraryService().invalidate()
    yield
    LibraryService().invalidate()


def test_valid_index_parses_into_model():
    # Arrange
    payload = _index(_entry("dark-forest"), _entry("sunken-city"))

    # Act
    library = parse_library(payload)

    # Assert
    assert library.schema_ == 1
    assert [entry.slug for entry in library.adventures] == ["dark-forest", "sunken-city"]


def test_unknown_fields_are_ignored():
    # Arrange
    payload = _index(_entry(rating=5, future_field={"nested": True}))

    # Act
    library = parse_library(payload)

    # Assert
    assert len(library.adventures) == 1
    assert not hasattr(library.adventures[0], "future_field")


def test_deprecated_flag_defaults_to_false():
    # Arrange
    payload = _index(_entry("dark-forest"), _entry("sunken-city", deprecated=True))

    # Act
    library = parse_library(payload)

    # Assert
    assert [entry.deprecated for entry in library.adventures] == [False, True]


def test_unsupported_schema_is_rejected():
    # Arrange
    payload = _index(_entry(), schema=2)

    # Act / Assert
    with pytest.raises(LibraryError, match="unsupported library schema"):
        parse_library(payload)


@pytest.mark.parametrize(
    "files",
    [
        ["adventure.adv", "../secrets.txt"],
        ["adventure.adv", "assets/../../etc/passwd"],
        ["adventure.adv", "/etc/passwd"],
        ["adventure.adv", "assets\\cover.jpg"],
        ["adventure.adv", "notes.txt"],
        ["adventure.adv", "assets/cover.jpg?raw=1"],
        ["assets/cover.jpg"],
    ],
)
def test_entry_with_unsafe_or_incomplete_file_list_is_dropped(files):
    # Arrange
    payload = _index(_entry("broken", files=files), _entry("intact"))

    # Act
    library = parse_library(payload)

    # Assert
    assert [entry.slug for entry in library.adventures] == ["intact"]


def test_unsafe_cover_is_cleared_but_entry_is_kept():
    # Arrange
    payload = _index(_entry("ugly-card", cover="../cover.jpg"))

    # Act
    library = parse_library(payload)

    # Assert
    assert library.adventures[0].slug == "ugly-card"
    assert library.adventures[0].cover is None


def test_duplicate_ids_keep_the_first_entry():
    # Arrange
    payload = _index(_entry("first", id="same"), _entry("second", id="same"))

    # Act
    library = parse_library(payload)

    # Assert
    assert [entry.slug for entry in library.adventures] == ["first"]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("adventure.adv", True),
        ("assets/npc_hero.jpg", True),
        ("assets/sub/dir/scene.png", True),
        ("assets", False),
        ("assets/", False),
        ("./adventure.adv", False),
        ("assets/./x.jpg", False),
        ("C:/x.jpg", False),
        ("", False),
    ],
)
def test_member_path_policy(path, expected):
    # Act / Assert
    assert is_safe_member_path(path) is expected


def test_library_url_encodes_segments():
    # Act
    url = library_url("dark-forest", "assets/a b.jpg")

    # Assert
    assert url == f"{BASE}/dark-forest/assets/a%20b.jpg"


def test_library_url_refuses_plain_http(monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "ADVENTURE_LIBRARY_URL", "http://example.com/repo")

    # Act / Assert
    with pytest.raises(LibraryError, match="https"):
        library_url("library.json")


async def test_fetch_reads_index_and_keeps_a_disk_copy():
    # Arrange
    requested: list[str] = []

    def serve(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "api.github.com":
            return httpx.Response(403)  # rate limited: fall back to the branch URL
        # A listed format_version means no adventure.adv header probe is needed.
        return httpx.Response(200, json=_index(_entry("online", format_version="1.3.1")))

    # Act
    async with _client(serve) as client:
        service = LibraryService(http_client=client)
        library = await service.get_library()

    # Assert
    assert requested == [COMMIT_API, f"{BASE}/library.json"]
    assert [entry.slug for entry in library.adventures] == ["online"]
    assert service.is_stale() is False
    assert catalog_module.cache_path().is_file()


async def test_memory_cache_avoids_a_second_request():
    # Arrange
    calls = 0

    def serve(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.url.host == "api.github.com":
            return httpx.Response(200, text=SHA)
        calls += 1
        return httpx.Response(200, json=_index(_entry(format_version="1.3.1")))

    # Act
    async with _client(serve) as client:
        service = LibraryService(http_client=client)
        await service.get_library()
        await service.get_library()
        await service.get_library(force_refresh=True)

    # Assert
    assert calls == 2


async def test_offline_falls_back_to_the_disk_copy():
    # Arrange
    path = catalog_module.cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_index(_entry("cached"))), encoding="utf-8")

    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network unreachable", request=request)

    # Act
    async with _client(offline) as client:
        service = LibraryService(http_client=client)
        library = await service.get_library()

    # Assert
    assert [entry.slug for entry in library.adventures] == ["cached"]
    assert service.is_stale() is True


async def test_offline_without_a_disk_copy_raises():
    # Arrange
    def not_found(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    # Act / Assert
    async with _client(not_found) as client:
        with pytest.raises(LibraryError, match="HTTP status 404"):
            await LibraryService(http_client=client).get_library()


async def test_fetch_pins_index_files_and_probes_to_the_branch_commit():
    # Arrange
    requested: list[str] = []

    def serve(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "api.github.com":
            assert request.headers["Accept"] == "application/vnd.github.sha"
            return httpx.Response(200, text=f"{SHA}\n")
        if request.url.path.endswith("library.json"):
            return httpx.Response(200, json=_index(_entry("pinned")))
        return httpx.Response(206, content=b'{"format": "TaleWeaver", "version": "1.3.1"}')

    # Act
    async with _client(serve) as client:
        service = LibraryService(http_client=client)
        await service.get_library()

    # Assert
    assert requested == [
        COMMIT_API,
        f"{PINNED}/library.json",
        f"{PINNED}/pinned/adventure.adv",
    ]
    assert library_url("pinned", "assets/cover.jpg") == f"{PINNED}/pinned/assets/cover.jpg"


@pytest.mark.parametrize("answer", ["<html>rate limited</html>", "", "abc123"])
async def test_unusable_commit_answer_falls_back_to_the_branch(answer):
    # Arrange
    def serve(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            return httpx.Response(200, text=answer)
        return httpx.Response(200, json=_index(_entry(format_version="1.3.1")))

    # Act
    async with _client(serve) as client:
        await LibraryService(http_client=client).get_library()

    # Assert
    assert library_url("dark-forest", "adventure.adv") == f"{BASE}/dark-forest/adventure.adv"


async def test_commit_lookup_failure_does_not_block_the_index():
    # Arrange
    def serve(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            raise httpx.ConnectTimeout("slow api", request=request)
        return httpx.Response(200, json=_index(_entry("online", format_version="1.3.1")))

    # Act
    async with _client(serve) as client:
        library = await LibraryService(http_client=client).get_library()

    # Assert
    assert [entry.slug for entry in library.adventures] == ["online"]


@pytest.mark.parametrize(
    "base",
    [
        "https://example.com/adventures",
        f"https://raw.githubusercontent.com/jschm42/taleweaver-adventures/{SHA}",
    ],
)
async def test_no_commit_lookup_for_other_hosts_or_pinned_urls(monkeypatch, base):
    # Arrange
    monkeypatch.setattr(settings, "ADVENTURE_LIBRARY_URL", base)
    requested: list[str] = []

    def serve(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, json=_index(_entry(format_version="1.3.1")))

    # Act
    async with _client(serve) as client:
        await LibraryService(http_client=client).get_library()

    # Assert
    assert requested == [f"{base}/library.json"]


async def test_disk_fallback_reads_files_from_the_branch():
    # Arrange
    path = catalog_module.cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_index(_entry("cached"))), encoding="utf-8")

    def serve(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            return httpx.Response(200, text=SHA)
        return httpx.Response(503)

    # Act
    async with _client(serve) as client:
        await LibraryService(http_client=client).get_library()

    # Assert
    assert library_url("cached", "adventure.adv") == f"{BASE}/cached/adventure.adv"
