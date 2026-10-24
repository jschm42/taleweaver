"""Remote adventure index: fetch ``library.json`` from the adventures repository.

Lookup order: in-memory cache -> network -> last good copy on disk. The disk copy keeps
the library dialog usable offline; without one, the caller gets :class:`LibraryError`.

Every URL is built from ``settings.ADVENTURE_LIBRARY_URL`` plus validated index values;
no API caller can supply one, so there is no SSRF surface (CWE-918).
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from pydantic import ValidationError

from backend.core.config import settings
from backend.services.adventure_library.models import AdventureLibrary, LibraryEntry

logger = logging.getLogger(__name__)

SUPPORTED_SCHEMA = 1
INDEX_FILE = "library.json"
_FETCH_TIMEOUT = httpx.Timeout(15.0)
# A stale copy is retried soon, so an app coming back online sees the live index.
_STALE_TTL_SECONDS = 60.0

# Process-wide cache; tests reset it through ``LibraryService().invalidate()``.
_MEMORY_CACHE: dict[str, Any] = {"library": None, "timestamp": 0.0, "ttl": 0.0, "stale": False}


class LibraryError(Exception):
    """The index or an adventure file could not be fetched or is invalid."""


def library_url(*parts: str) -> str:
    """``ADVENTURE_LIBRARY_URL`` joined with percent-encoded path segments.

    Only ``https`` is accepted: the repository content is the integrity anchor, so the
    transport must not be tamperable.
    """
    base = settings.ADVENTURE_LIBRARY_URL.rstrip("/")
    if urlsplit(base).scheme != "https":
        raise LibraryError("ADVENTURE_LIBRARY_URL must be an https URL")
    return "/".join([base, *(quote(part, safe="/") for part in parts)])


def cache_path() -> Path:
    """Disk copy location; resolved per call so a patched ``DATA_DIR`` is honoured."""
    return Path(settings.DATA_DIR) / "adventure_library" / "library_cache.json"


def _parse_entry(raw: Any) -> LibraryEntry | None:
    """Validate one entry; a broken entry is logged and skipped, never fatal."""
    try:
        return LibraryEntry.model_validate(raw)
    except ValidationError as exc:
        label = raw.get("slug") if isinstance(raw, dict) else repr(raw)[:40]
        logger.warning("Skipping library entry %r: %s", label, exc.errors()[0]["msg"])
        return None


def parse_library(payload: Any) -> AdventureLibrary:
    """Validate a decoded ``library.json``; unknown schemas reject the whole document."""
    if not isinstance(payload, dict):
        raise LibraryError("library index is not a JSON object")
    if payload.get("schema") != SUPPORTED_SCHEMA:
        raise LibraryError(f"unsupported library schema {payload.get('schema')!r}")
    raw_entries = payload.get("adventures")
    if not isinstance(raw_entries, list):
        raise LibraryError("'adventures' is missing or not a list")
    unique: dict[str, LibraryEntry] = {}
    for entry in filter(None, map(_parse_entry, raw_entries)):
        unique.setdefault(entry.id, entry)
    return AdventureLibrary(schema=SUPPORTED_SCHEMA, adventures=list(unique.values()))


def _read_disk_copy() -> AdventureLibrary | None:
    try:
        return parse_library(json.loads(cache_path().read_text(encoding="utf-8")))
    except (OSError, ValueError, LibraryError) as exc:
        logger.debug("No usable disk copy of the adventure library: %s", exc)
        return None


def _write_disk_copy(payload: dict[str, Any]) -> None:
    """Persist atomically; a failure only disables the offline fallback."""
    path = cache_path()
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp_path, path)
    except OSError as exc:
        logger.warning("Could not write adventure library cache %s: %s", path, exc)


def _remember(library: AdventureLibrary, ttl: float, stale: bool) -> AdventureLibrary:
    _MEMORY_CACHE.update(library=library, timestamp=time.monotonic(), ttl=ttl, stale=stale)
    return library


class LibraryService:
    """Facade over the cache layers. The HTTP client is injectable for tests."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client

    async def get_library(self, *, force_refresh: bool = False) -> AdventureLibrary:
        """Return the current index; raises :class:`LibraryError` only without any copy."""
        cached = _MEMORY_CACHE["library"]
        age = time.monotonic() - _MEMORY_CACHE["timestamp"]
        if cached is not None and not force_refresh and age < _MEMORY_CACHE["ttl"]:
            return cached
        try:
            return _remember(await self._fetch(), settings.ADVENTURE_LIBRARY_TTL, stale=False)
        except LibraryError as exc:
            fallback = _read_disk_copy()
            if fallback is None:
                raise
            logger.warning("Using the cached adventure library: %s", exc)
            return _remember(fallback, _STALE_TTL_SECONDS, stale=True)

    def is_stale(self) -> bool:
        """True when the last index served came from the disk copy."""
        return bool(_MEMORY_CACHE["stale"])

    def invalidate(self) -> None:
        _MEMORY_CACHE.update(library=None, timestamp=0.0, ttl=0.0, stale=False)

    @staticmethod
    def resolve_entry(library: AdventureLibrary, adventure_id: str) -> LibraryEntry | None:
        return next((entry for entry in library.adventures if entry.id == adventure_id), None)

    async def _get(self, url: str) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.get(url, follow_redirects=False)
        async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
            return await client.get(url, follow_redirects=False)

    async def _fetch(self) -> AdventureLibrary:
        url = library_url(INDEX_FILE)
        try:
            response = await self._get(url)
        except httpx.HTTPError as exc:
            raise LibraryError(f"request failed: {exc.__class__.__name__}") from exc
        if response.status_code != httpx.codes.OK:
            raise LibraryError(f"unexpected HTTP status {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise LibraryError("library index is not valid JSON") from exc
        library = parse_library(payload)
        _write_disk_copy(payload)
        return library
