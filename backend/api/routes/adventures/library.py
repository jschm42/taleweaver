"""Adventure library API: browse ``library.json`` and install adventures from it.

SSRF boundary (CWE-918): no endpoint accepts a URL from the client. Requests carry
library entry ids only; file URLs are built server-side from
``settings.ADVENTURE_LIBRARY_URL`` and the validated index.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.adventures.adventure_importer import AdventureConflictError
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.services.adventure_library import (
    AdventureInstallError,
    AdventureLibrary,
    LibraryEntry,
    LibraryError,
    LibraryItemView,
    LibraryService,
    install_entry,
    is_newer_version,
    is_version_at_least,
    library_url,
)
from backend.services.adventure_library.updates import library_update_for

router = APIRouter(tags=["Adventures"])
logger = logging.getLogger(__name__)

_library_service = LibraryService()
# Entry ids with an install in flight; a second click must not import twice in parallel.
_installing: set[str] = set()


class LibraryInstallRequest(BaseModel):
    """A library entry id; never a URL."""

    id: str = Field(min_length=1, max_length=200)


async def _installed_versions(
    db: AsyncSession, owner_id: str, origin_ids: list[str]
) -> dict[str, str | None]:
    """Map ``origin_id`` -> highest installed version of this owner, in one query."""
    if not origin_ids:
        return {}
    result = await db.execute(
        select(AdventureTemplate.origin_id, AdventureTemplate.version).where(
            AdventureTemplate.owner_id == owner_id,
            AdventureTemplate.origin_id.in_(origin_ids),
        )
    )
    installed: dict[str, str | None] = {}
    for origin_id, version in result.all():
        current = installed.get(origin_id)
        if current is None or is_version_at_least(version or "", current):
            installed[origin_id] = version
    return installed


def _item_view(entry: LibraryEntry, installed_version: str | None) -> LibraryItemView:
    return LibraryItemView(
        entry=entry,
        cover_url=library_url(entry.slug, entry.cover) if entry.cover else None,
        installed_version=installed_version,
        update_available=is_newer_version(entry.version, installed_version),
    )


async def _library_response(
    library: AdventureLibrary, db: AsyncSession, owner_id: str
) -> dict[str, Any]:
    installed = await _installed_versions(db, owner_id, [e.id for e in library.adventures])
    items = [_item_view(entry, installed.get(entry.id)) for entry in library.adventures]
    items.sort(key=lambda item: item.entry.title.casefold())
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "stale": _library_service.is_stale(),
    }


async def _load_library(*, force_refresh: bool = False) -> AdventureLibrary:
    try:
        return await _library_service.get_library(force_refresh=force_refresh)
    except LibraryError as exc:
        logger.warning("Adventure library unavailable: %s", exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Adventure library unavailable") from exc


@router.get("/library/catalog")
async def get_library_catalog(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return library entries merged with the caller's install state."""
    library = await _load_library()
    return await _library_response(library, db, current_user.id)


@router.post("/library/refresh")
async def refresh_library_catalog(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Bypass the cache, then return the same view as ``GET /library/catalog``."""
    library = await _load_library(force_refresh=True)
    return await _library_response(library, db, current_user.id)


@router.get("/library/updates")
async def get_library_updates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Installed adventures of the caller that have a newer version in the library.

    Uses the cached catalog like ``GET /library/catalog``. The portal calls this in the
    background, so an unreachable repository yields an empty list instead of an error.
    """
    try:
        library = await _library_service.get_library()
    except LibraryError as exc:
        logger.info("Library updates unavailable: %s", exc)
        return {"updates": [], "stale": True}
    ids = [entry.id for entry in library.adventures]
    result = await db.execute(
        select(AdventureTemplate).where(
            AdventureTemplate.owner_id == current_user.id,
            AdventureTemplate.origin_id.in_(ids),
        )
    )
    updates = []
    for template in result.scalars().all():
        entry = library_update_for(library, template)
        if entry is not None:
            updates.append(
                {"template_id": template.id, "library_id": entry.id, "version": entry.version}
            )
    return {"updates": updates, "stale": _library_service.is_stale()}


@router.post("/library/install")
async def install_library_adventure(
    payload: LibraryInstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Download one adventure from the library and import it; returns when done."""
    entry = _library_service.resolve_entry(await _load_library(), payload.id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown library id: {payload.id}")
    if entry.id in _installing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{entry.title} is already being installed")

    _installing.add(entry.id)
    try:
        template_id = await install_entry(db, entry, owner_id=current_user.id)
    except LibraryError as exc:
        logger.warning("Downloading %s failed: %s", entry.slug, exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Download failed: {exc}") from exc
    except AdventureInstallError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except AdventureConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{exc.title} already exists") from exc
    finally:
        _installing.discard(entry.id)
    return {"template_id": template_id, "version": entry.version}
