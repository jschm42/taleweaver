"""Install a library adventure: fetch its files, build the ``.adz``, run the importer.

The bundle is assembled in memory from the files ``library.json`` lists for the entry.
Import logic is not re-implemented here: ``AdventureTemplateImporter`` already enforces
the zip-bomb limits, manifest validation and conflict detection. After a successful
import the bundle is written to ``settings.adventure_download_dir``, the directory the
update scanner reads, so the installed adventure shows up there like any local file.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.engine.adventure_import_support import find_existing_template
from backend.engine.adventure_importer import AdventureTemplateImporter
from backend.services.adventure_library.catalog import LibraryError, library_url
from backend.services.adventure_library.models import BLUEPRINT_NAME, LibraryEntry

logger = logging.getLogger(__name__)

FETCH_CONCURRENCY = 8
CHUNK_SIZE = 64 * 1024
_FETCH_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class AdventureInstallError(Exception):
    """The importer rejected the assembled bundle."""


class _ByteBudget:
    """Shared download cap across all files of one adventure (disk/memory-fill guard)."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def take(self, size: int) -> None:
        self.used += size
        if self.used > self.limit:
            raise LibraryError(f"adventure exceeds the {self.limit} byte download limit")


@asynccontextmanager
async def _client(injected: httpx.AsyncClient | None) -> AsyncIterator[httpx.AsyncClient]:
    if injected is not None:
        yield injected
        return
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, follow_redirects=False) as client:
        yield client


async def _fetch_file(
    client: httpx.AsyncClient, entry: LibraryEntry, path: str, budget: _ByteBudget
) -> bytes:
    chunks: list[bytes] = []
    url = library_url(entry.slug, path)
    async with client.stream("GET", url, follow_redirects=False) as response:
        if response.status_code != httpx.codes.OK:
            raise LibraryError(f"{entry.slug}/{path}: HTTP {response.status_code}")
        async for chunk in response.aiter_bytes(CHUNK_SIZE):
            budget.take(len(chunk))
            chunks.append(chunk)
    return b"".join(chunks)


async def fetch_files(
    entry: LibraryEntry, http_client: httpx.AsyncClient | None = None
) -> dict[str, bytes]:
    """Download every listed file of ``entry``; the first failure aborts the rest."""
    budget = _ByteBudget(settings.ADVENTURE_DOWNLOAD_MAX_BYTES)
    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def fetch_one(client: httpx.AsyncClient, path: str) -> bytes:
        async with semaphore:
            return await _fetch_file(client, entry, path, budget)

    async with _client(http_client) as client:
        tasks = [asyncio.ensure_future(fetch_one(client, path)) for path in entry.files]
        try:
            contents = await asyncio.gather(*tasks)
        except httpx.HTTPError as exc:
            raise LibraryError(f"download failed: {exc.__class__.__name__}") from exc
        finally:
            for task in tasks:
                task.cancel()
    return dict(zip(entry.files, contents, strict=True))


def build_bundle(files: dict[str, bytes]) -> bytes:
    """Zip the files into an ``.adz``; the blueprint goes first, like every exported bundle."""
    names = sorted(files, key=lambda name: (name != BLUEPRINT_NAME, name))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            archive.writestr(name, files[name])
    return buffer.getvalue()


def bundle_path(slug: str) -> Path:
    """``<download dir>/<slug>.adz``; the slug is pattern-validated, containment is re-checked."""
    base = Path(settings.adventure_download_dir).resolve()
    target = (base / f"{slug}.adz").resolve()
    if target.parent != base:
        raise AdventureInstallError(f"bundle path for {slug!r} escapes {base}")
    return target


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)


def _manifest_title(files: dict[str, bytes]) -> str | None:
    try:
        manifest = json.loads(files[BLUEPRINT_NAME].decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    adventure = manifest.get("adventure") if isinstance(manifest, dict) else None
    return adventure.get("title") if isinstance(adventure, dict) else None


async def install_entry(
    db: AsyncSession,
    entry: LibraryEntry,
    *,
    owner_id: str,
    http_client: httpx.AsyncClient | None = None,
) -> str | None:
    """Fetch, import and store ``entry``; return the template id when resolvable.

    ``AdventureConflictError`` from the importer propagates unchanged so the API layer
    can map it to HTTP 409.
    """
    files = await fetch_files(entry, http_client)
    data = build_bundle(files)
    imported = await AdventureTemplateImporter.import_adz(
        db, data, owner_id=owner_id, overwrite=True
    )
    if not imported:
        raise AdventureInstallError(f"the importer rejected {entry.slug} {entry.version}")
    await asyncio.to_thread(_write_atomic, bundle_path(entry.slug), data)

    # Imported lazily: adventure_updates has an import cycle through the API routers.
    from backend.engine.adventure_updates import scan_available_adventure_files

    await asyncio.to_thread(scan_available_adventure_files, True)
    logger.info("Installed library adventure %s %s", entry.slug, entry.version)

    title = _manifest_title(files) or entry.title
    template = await find_existing_template(db, owner_id, title, entry.id)
    return template.id if template else None
