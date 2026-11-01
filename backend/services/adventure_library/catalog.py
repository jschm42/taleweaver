"""Remote adventure index: fetch ``library.json`` from the adventures repository.

Lookup order: in-memory cache -> network -> last good copy on disk. The disk copy keeps
the library dialog usable offline; without one, the caller gets :class:`LibraryError`.

Every URL is built from ``settings.ADVENTURE_LIBRARY_URL`` plus validated index values;
no API caller can supply one, so there is no SSRF surface (CWE-918).

Commit pinning: ``raw.githubusercontent.com`` caches every file for five minutes, so a
branch URL would serve the previous push for that long. When the base URL names a branch on
that host, each fetch first asks the GitHub API for the branch's commit and then reads
``library.json`` and every adventure file below that commit. A new commit is a new URL, so
the CDN cache never hides a push, and catalog and installs always read the same revision.
Without an answer from the API the branch URL is used as before.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from pydantic import ValidationError

from backend.core.config import settings
from backend.services.adventure_library.format_probe import probe_format_versions
from backend.services.adventure_library.models import (
    BLUEPRINT_NAME,
    AdventureLibrary,
    LibraryEntry,
)

logger = logging.getLogger(__name__)

SUPPORTED_SCHEMA = 1
INDEX_FILE = "library.json"
_FETCH_TIMEOUT = httpx.Timeout(15.0)
# Header probes are best effort; a slow repository must not hold up the catalog.
_PROBE_TIMEOUT = httpx.Timeout(5.0)
# A stale copy is retried soon, so an app coming back online sees the live index.
_STALE_TTL_SECONDS = 60.0
# Commit lookups are best effort; without an answer the branch URL is used.
_COMMIT_TIMEOUT = httpx.Timeout(5.0)
_GITHUB_RAW_HOST = "raw.githubusercontent.com"
_GITHUB_API = "https://api.github.com"
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")

# Process-wide cache; tests reset it through ``LibraryService().invalidate()``.
# ``commit`` is the revision the cached index was read from (None: the configured ref).
_MEMORY_CACHE: dict[str, Any] = {
    "library": None,
    "timestamp": 0.0,
    "ttl": 0.0,
    "stale": False,
    "commit": None,
}


class LibraryError(Exception):
    """The index or an adventure file could not be fetched or is invalid."""


def _configured_base() -> str:
    """``ADVENTURE_LIBRARY_URL`` without a trailing slash; only ``https`` is accepted.

    The repository content is the integrity anchor, so the transport must not be tamperable.
    """
    base = settings.ADVENTURE_LIBRARY_URL.rstrip("/")
    if urlsplit(base).scheme != "https":
        raise LibraryError("ADVENTURE_LIBRARY_URL must be an https URL")
    return base


def github_location(base: str) -> tuple[str, str, str] | None:
    """``(owner, repo, ref)`` of a ``raw.githubusercontent.com/<owner>/<repo>/<ref>`` URL."""
    parts = urlsplit(base)
    segments = [segment for segment in parts.path.split("/") if segment]
    if parts.netloc != _GITHUB_RAW_HOST or len(segments) != 3:
        return None
    owner, repo, ref = segments
    return owner, repo, ref


def _url_at(commit: str | None, *parts: str) -> str:
    """URL of ``parts`` at ``commit``, or at the configured ref when there is none."""
    base = _configured_base()
    if commit and _COMMIT_SHA.match(commit) and github_location(base):
        base = f"{base.rsplit('/', 1)[0]}/{commit}"
    return "/".join([base, *(quote(part, safe="/") for part in parts)])


def library_url(*parts: str) -> str:
    """Percent-encoded URL of ``parts`` in the revision the cached index was read from.

    Installs and cover images therefore always match the catalog the user is looking at.
    """
    return _url_at(_MEMORY_CACHE["commit"], *parts)


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


def _remember(
    library: AdventureLibrary, ttl: float, stale: bool, commit: str | None = None
) -> AdventureLibrary:
    _MEMORY_CACHE.update(
        library=library, timestamp=time.monotonic(), ttl=ttl, stale=stale, commit=commit
    )
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
            library, commit = await self._fetch()
            return _remember(library, settings.ADVENTURE_LIBRARY_TTL, stale=False, commit=commit)
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
        _MEMORY_CACHE.update(library=None, timestamp=0.0, ttl=0.0, stale=False, commit=None)

    @staticmethod
    def resolve_entry(library: AdventureLibrary, adventure_id: str) -> LibraryEntry | None:
        return next((entry for entry in library.adventures if entry.id == adventure_id), None)

    async def _get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout = _FETCH_TIMEOUT,
    ) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.get(
                url, headers=headers, timeout=timeout, follow_redirects=False
            )
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.get(url, headers=headers, follow_redirects=False)

    async def _resolve_commit(self) -> str | None:
        """Current commit of the configured GitHub branch; None when unknown or not needed."""
        location = github_location(_configured_base())
        if location is None or _COMMIT_SHA.match(location[2]):
            return None
        owner, repo, ref = (quote(segment, safe="") for segment in location)
        url = f"{_GITHUB_API}/repos/{owner}/{repo}/commits/{ref}"
        try:
            response = await self._get(
                url,
                headers={"Accept": "application/vnd.github.sha"},
                timeout=_COMMIT_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            logger.debug("Commit lookup failed: %s", exc.__class__.__name__)
            return None
        sha = response.text.strip() if response.status_code == httpx.codes.OK else ""
        if not _COMMIT_SHA.match(sha):
            # Typically the unauthenticated rate limit (60/h); the branch URL still works.
            logger.info(
                "Commit lookup returned HTTP %s; using the branch URL", response.status_code
            )
            return None
        return sha

    async def _fetch(self) -> tuple[AdventureLibrary, str | None]:
        commit = await self._resolve_commit()
        url = _url_at(commit, INDEX_FILE)
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
        library = await self._with_format_versions(parse_library(payload), payload, commit)
        _write_disk_copy(payload)
        return library, commit

    async def _with_format_versions(
        self, library: AdventureLibrary, payload: dict[str, Any], commit: str | None
    ) -> AdventureLibrary:
        """Fills in missing ``format_version`` values from the file headers.

        The values are written into ``payload`` so the disk copy keeps them too.
        """
        targets = [
            (entry.id, _url_at(commit, entry.slug, BLUEPRINT_NAME))
            for entry in library.adventures
            if not entry.format_version
        ]
        if not targets:
            return library
        if self._http_client is not None:
            versions = await probe_format_versions(self._http_client, targets)
        else:
            async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
                versions = await probe_format_versions(client, targets)
        if not versions:
            return library
        for raw in payload.get("adventures") or []:
            if isinstance(raw, dict) and raw.get("id") in versions:
                raw.setdefault("format_version", versions[raw["id"]])
        return parse_library(payload)
