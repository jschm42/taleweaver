"""Remote adventure catalog: fetch, validate and cache ``catalog.json``.

Lookup order: in-memory cache -> fresh disk cache -> network (ETag aware) -> stale disk
cache -> bundled snapshot. Every layer degrades silently to the next one, so the library
dialog keeps working offline and a broken cache file never surfaces as an error.

The catalog URL comes from ``settings.ADVENTURE_CATALOG_URL`` only. No method accepts a
URL argument, so there is no SSRF surface reachable from API callers.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from backend.core.config import settings
from backend.services.adventure_library.models import AdventureCatalog, CatalogEntry
from backend.services.adventure_library.url_policy import http_client, url_rejection_reason

logger = logging.getLogger(__name__)

SUPPORTED_CATALOG_SCHEMA = 1
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "catalog_snapshot.json"

_FETCH_TIMEOUT = httpx.Timeout(10.0)
# A snapshot/stale fallback is retried sooner than a real catalog so that an app that
# comes back online picks up the live catalog without waiting a full TTL.
_FALLBACK_TTL_SECONDS = 60.0

# Process-wide in-memory cache; tests reset it via ``_MEMORY_CACHE.update(...)``.
_MEMORY_CACHE: dict[str, Any] = {"catalog": None, "timestamp": 0.0, "ttl": 0.0, "stale": False}


class CatalogError(Exception):
    """The catalog could not be fetched or failed validation (internal, triggers fallback)."""


def catalog_cache_path() -> Path:
    """Disk cache location; resolved per call so a patched ``DATA_DIR`` is honoured."""
    return Path(settings.DATA_DIR) / "adventure_library" / "catalog_cache.json"


def _entry_rejection_reason(entry: CatalogEntry) -> str | None:
    """Return why an otherwise well-formed entry must be dropped, or ``None``.

    URLs are checked here, at parse time, so the UI never offers an entry that the
    downloader would refuse anyway. ``size_bytes`` is checked against the download cap
    because the cap is the disk-fill guard; an entry announcing more is never fetched.

    Covers are deliberately NOT validated here. Per spec D9 a cover is cosmetic, so a
    broken cover degrades the card and must never make a downloadable adventure vanish
    from the catalog; see :func:`_without_unusable_cover`.
    """
    reason = url_rejection_reason(entry.download_url)
    if reason:
        return f"download_url rejected: {reason}"
    if entry.size_bytes > settings.ADVENTURE_DOWNLOAD_MAX_BYTES:
        return f"size_bytes {entry.size_bytes} exceeds ADVENTURE_DOWNLOAD_MAX_BYTES"
    return None


def _without_unusable_cover(entry: CatalogEntry) -> CatalogEntry:
    """Strip a cover the client could not legitimately load, keeping the entry (D9).

    ``cover_url`` and ``cover_sha256`` are an optional pair: both present or neither.
    A half-specified pair, a non-https URL or a host outside the allowlist would make the
    dialog request something the outbound policy forbids, so the cover is dropped and the
    UI falls back to its typographic placeholder. The bundle stays downloadable.
    """
    cover_url, cover_sha256 = entry.cover_url, entry.cover_sha256
    if not cover_url and not cover_sha256:
        return entry
    if not cover_url or not cover_sha256:
        logger.warning("Dropping incomplete cover pair for catalog entry %r", entry.slug)
        return entry.model_copy(update={"cover_url": None, "cover_sha256": None})
    reason = url_rejection_reason(cover_url)
    if reason:
        logger.warning(
            "Dropping cover of catalog entry %r (%s); the adventure stays available",
            entry.slug,
            reason,
        )
        return entry.model_copy(update={"cover_url": None, "cover_sha256": None})
    return entry


def _summarize(exc: ValidationError) -> str:
    """Field/message pairs only; the raw input may be long and is not worth logging."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )


def _parse_entry(raw: Any) -> CatalogEntry | None:
    """Validate a single entry; invalid entries are logged and skipped, not fatal."""
    label = (raw.get("slug") or raw.get("id")) if isinstance(raw, dict) else repr(raw)[:40]
    try:
        entry = CatalogEntry.model_validate(raw)
    except ValidationError as exc:
        logger.warning("Rejected catalog entry %r: %s", label, _summarize(exc))
        return None
    reason = _entry_rejection_reason(entry)
    if reason:
        logger.warning("Rejected catalog entry %r: %s", label, reason)
        return None
    return _without_unusable_cover(entry)


def _dedupe(entries: list[CatalogEntry]) -> list[CatalogEntry]:
    """Keep the first entry per id; ``id`` is the primary key of the catalog."""
    seen: set[str] = set()
    unique: list[CatalogEntry] = []
    for entry in entries:
        if entry.id in seen:
            logger.warning("Rejected duplicate catalog entry id %r", entry.id)
            continue
        seen.add(entry.id)
        unique.append(entry)
    return unique


def parse_catalog(payload: Any) -> AdventureCatalog:
    """Validate a decoded ``catalog.json`` document.

    A wrong ``schema`` rejects the whole document (an older client cannot know what a
    newer schema means). Individual bad entries are dropped so one broken entry cannot
    take the whole library offline.
    """
    if not isinstance(payload, dict):
        raise CatalogError("catalog root is not a JSON object")
    schema = payload.get("schema")
    if schema != SUPPORTED_CATALOG_SCHEMA:
        raise CatalogError(f"unsupported catalog schema {schema!r}")
    raw_entries = payload.get("adventures")
    if not isinstance(raw_entries, list):
        raise CatalogError("'adventures' is missing or not a list")
    try:
        catalog = AdventureCatalog.model_validate({**payload, "adventures": []})
    except ValidationError as exc:
        raise CatalogError(f"invalid catalog header: {exc.error_count()} error(s)") from exc
    parsed = (_parse_entry(raw) for raw in raw_entries)
    catalog.adventures = _dedupe([entry for entry in parsed if entry])
    return catalog


def _read_disk_cache() -> dict[str, Any] | None:
    """Return the cached record, or ``None`` when it is missing or unreadable."""
    try:
        record = json.loads(catalog_cache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.debug("Adventure catalog disk cache unavailable: %s", exc)
        return None
    if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
        return None
    return record


def _write_disk_cache(etag: str | None, payload: dict[str, Any]) -> None:
    """Persist the raw payload atomically; failures only disable the disk cache."""
    path = catalog_cache_path()
    record = {
        "etag": etag,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(record), encoding="utf-8")
        os.replace(tmp_path, path)
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("Could not write adventure catalog cache %s: %s", path, exc)


def _is_fresh(record: dict[str, Any]) -> bool:
    try:
        fetched_at = datetime.fromisoformat(str(record.get("fetched_at")))
    except ValueError:
        return False
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
    return 0 <= age < settings.ADVENTURE_CATALOG_TTL


def _try_parse(payload: Any, source: str) -> AdventureCatalog | None:
    try:
        return parse_catalog(payload)
    except CatalogError as exc:
        logger.warning("Ignoring adventure catalog from %s: %s", source, exc)
        return None


def load_snapshot() -> AdventureCatalog:
    """Return the bundled snapshot, or an empty catalog if even that is unusable."""
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        return parse_catalog(payload)
    except (OSError, ValueError, CatalogError) as exc:
        logger.error("Bundled adventure catalog snapshot unusable: %s", exc)
        return AdventureCatalog(schema=SUPPORTED_CATALOG_SCHEMA, generator="empty-fallback")


def _remember(catalog: AdventureCatalog, ttl: float, *, stale: bool = False) -> AdventureCatalog:
    _MEMORY_CACHE.update(catalog=catalog, timestamp=time.monotonic(), ttl=ttl, stale=stale)
    return catalog


def _memory_hit() -> AdventureCatalog | None:
    catalog = _MEMORY_CACHE.get("catalog")
    if catalog is None:
        return None
    age = time.monotonic() - float(_MEMORY_CACHE.get("timestamp") or 0.0)
    return catalog if age < float(_MEMORY_CACHE.get("ttl") or 0.0) else None


class CatalogService:
    """Facade over the catalog cache layers. The HTTP client is injectable for tests."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client

    async def get_catalog(self, *, force_refresh: bool = False) -> AdventureCatalog:
        """Return the current catalog; never raises for network or cache problems."""
        cached = None if force_refresh else _memory_hit()
        if cached is not None:
            return cached

        record = _read_disk_cache()
        if record and not force_refresh and _is_fresh(record):
            from_disk = _try_parse(record["payload"], "disk cache")
            if from_disk is not None:
                return _remember(from_disk, settings.ADVENTURE_CATALOG_TTL)

        try:
            return _remember(await self._fetch(record), settings.ADVENTURE_CATALOG_TTL)
        except CatalogError as exc:
            reason = str(exc)

        stale = _try_parse(record["payload"], "stale disk cache") if record else None
        if stale is not None:
            logger.warning("Using stale adventure catalog cache: %s", reason)
            return _remember(stale, _FALLBACK_TTL_SECONDS, stale=True)

        logger.warning("Falling back to bundled adventure catalog snapshot: %s", reason)
        return _remember(load_snapshot(), _FALLBACK_TTL_SECONDS, stale=True)

    async def refresh(self) -> AdventureCatalog:
        """Bypass the memory and TTL caches (ETag revalidation still applies)."""
        return await self.get_catalog(force_refresh=True)

    def invalidate(self) -> None:
        """Drop the in-memory catalog so the next call re-reads disk or network."""
        _MEMORY_CACHE.update(catalog=None, timestamp=0.0, ttl=0.0, stale=False)

    def is_stale(self) -> bool:
        """True when the last catalog served came from a stale cache or the snapshot."""
        return bool(_MEMORY_CACHE.get("stale", False))

    def resolve_entry(self, catalog: AdventureCatalog, adventure_id: str) -> CatalogEntry | None:
        """Look up an entry by its id (``origin_id``); the only way to obtain a URL."""
        return next((entry for entry in catalog.adventures if entry.id == adventure_id), None)

    async def _fetch(self, record: dict[str, Any] | None) -> AdventureCatalog:
        """Fetch and validate the remote catalog, revalidating via ETag when possible."""
        url = settings.ADVENTURE_CATALOG_URL
        reason = url_rejection_reason(url)
        if reason:
            raise CatalogError(f"ADVENTURE_CATALOG_URL rejected: {reason}")

        etag = record.get("etag") if record else None
        headers = {"Accept": "application/json"}
        if etag:
            headers["If-None-Match"] = str(etag)

        try:
            async with http_client(self._http_client, _FETCH_TIMEOUT) as client:
                response = await client.get(url, headers=headers, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise CatalogError(f"request failed: {exc.__class__.__name__}: {exc}") from exc

        if response.status_code == httpx.codes.NOT_MODIFIED and record:
            catalog = parse_catalog(record["payload"])
            _write_disk_cache(etag, record["payload"])
            return catalog
        if response.status_code != httpx.codes.OK:
            raise CatalogError(f"unexpected HTTP status {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise CatalogError("response is not valid JSON") from exc
        catalog = parse_catalog(payload)
        _write_disk_cache(response.headers.get("etag"), payload)
        return catalog
