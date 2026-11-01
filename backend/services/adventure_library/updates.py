"""Update badges and updates for installed adventures from the adventure library.

An installed adventure (``AdventureTemplate``) belongs to a library entry when its
``origin_id`` equals the entry id. A newer entry version marks the template as updatable in
"My Adventures", next to the local ``/adventures`` file check of ``adventure_updates``.

- ``merge_library_update``: overlays the library status on ``check_template_update``'s result.
  It uses the cached index only (``LibraryService.peek_library``), never the network.
- ``update_template``: updates one template from whichever source has the newer version.
- ``update_all_templates``: the same for every template of a user.

Existing sessions are kept and re-linked to the updated template, as for local updates.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.adventures.adventure_updates import (
    check_template_update,
    delete_replaced_template,
    linked_session_ids,
    relink_sessions,
    scan_available_adventure_files,
    update_single_adventure,
)
from backend.models.adventure_template import AdventureTemplate
from backend.services.adventure_library.catalog import LibraryError, LibraryService
from backend.services.adventure_library.installer import install_entry
from backend.services.adventure_library.models import (
    AdventureLibrary,
    LibraryEntry,
    is_version_at_least,
)

logger = logging.getLogger(__name__)

SOURCE_LOCAL = "local"
SOURCE_LIBRARY = "library"


def is_newer_version(candidate: Optional[str], installed: Optional[str]) -> bool:
    """Same rule as the library catalog's ``update_available``."""
    candidate = str(candidate or "").strip()
    installed = str(installed or "").strip()
    if not candidate or candidate == installed:
        return False
    return not installed or is_version_at_least(candidate, installed)


def library_update(template: Any, library: Optional[AdventureLibrary]) -> Optional[LibraryEntry]:
    """The library entry of ``template`` when it is newer than the installed version."""
    origin_id = str(getattr(template, "origin_id", "") or "").strip()
    if library is None or not origin_id:
        return None
    entry = next((e for e in library.adventures if e.id == origin_id), None)
    if entry is None or not is_newer_version(entry.version, getattr(template, "version", None)):
        return None
    return entry


def _library_wins(entry: Optional[LibraryEntry], status: dict[str, Any]) -> bool:
    if entry is None:
        return False
    if not status.get("has_update"):
        return True
    return is_version_at_least(entry.version, str(status.get("available_version") or ""))


def merge_library_update(
    status: dict[str, Any], template: Any, library: Optional[AdventureLibrary]
) -> dict[str, Any]:
    """``check_template_update`` result plus ``update_source`` (local, library or None)."""
    merged = {**status, "update_source": SOURCE_LOCAL if status.get("has_update") else None}
    entry = library_update(template, library)
    if not _library_wins(entry, status):
        return merged
    merged.update(has_update=True, available_version=entry.version, update_source=SOURCE_LIBRARY)
    return merged


async def _owned_template(db: AsyncSession, template_id: str, user_id: str) -> AdventureTemplate:
    result = await db.execute(
        select(AdventureTemplate).where(
            AdventureTemplate.id == template_id, AdventureTemplate.owner_id == user_id
        )
    )
    template = result.scalars().first()
    if not template:
        raise ValueError("Adventure template not found or unauthorized.")
    return template


async def _fresh_library(service: LibraryService) -> Optional[AdventureLibrary]:
    try:
        return await service.get_library()
    except LibraryError as exc:
        logger.warning("Adventure library unavailable for updates: %s", exc)
        return None


async def update_from_library(
    db: AsyncSession, template: AdventureTemplate, entry: LibraryEntry, user_id: str
) -> dict[str, Any]:
    """Installs the newer library version over ``template`` and keeps its sessions."""
    template_id = template.id
    title = template.title
    session_ids = await linked_session_ids(db, template_id)
    new_id = await install_entry(db, entry, owner_id=user_id) or template_id
    if new_id != template_id:
        await delete_replaced_template(db, template_id)
    await relink_sessions(db, session_ids, new_id)
    await db.commit()
    return {
        "status": "success",
        "message": f"Successfully updated '{title}' to version {entry.version}.",
        "template_id": new_id,
        "new_version": entry.version,
        "source": SOURCE_LIBRARY,
    }


async def update_template(
    db: AsyncSession, template_id: str, user_id: str, service: Optional[LibraryService] = None
) -> dict[str, Any]:
    """Updates one template from the source with the newer version (library or /adventures)."""
    template = await _owned_template(db, template_id, user_id)
    status = check_template_update(template, scan_available_adventure_files(force_refresh=True))
    entry = library_update(template, await _fresh_library(service or LibraryService()))
    if _library_wins(entry, status):
        return await update_from_library(db, template, entry, user_id)
    if status.get("has_update"):
        return await update_single_adventure(db=db, template_id=template_id, user_id=user_id)
    raise ValueError(f"No newer version of '{template.title}' was found.")


def _has_any_update(
    template: AdventureTemplate, files: list[dict[str, Any]], library: Optional[AdventureLibrary]
) -> bool:
    return bool(check_template_update(template, files)["has_update"]) or (
        library_update(template, library) is not None
    )


async def update_all_templates(
    db: AsyncSession, user_id: str, service: Optional[LibraryService] = None
) -> dict[str, Any]:
    """Updates every template of ``user_id`` that has a newer local or library version."""
    result = await db.execute(
        select(AdventureTemplate).where(AdventureTemplate.owner_id == user_id)
    )
    files = scan_available_adventure_files(force_refresh=True)
    library = await _fresh_library(service or LibraryService())
    pending = [
        (t.id, t.title) for t in result.scalars().all() if _has_any_update(t, files, library)
    ]
    updated_titles: list[str] = []
    errors: list[str] = []
    for template_id, title in pending:
        try:
            await update_template(db, template_id, user_id, service)
            updated_titles.append(title)
        except Exception as exc:
            logger.error("Error updating template %s: %s", template_id, exc)
            errors.append(f"{title}: {exc}")
    return {
        "status": "success",
        "updated_count": len(updated_titles),
        "updated_titles": updated_titles,
        "errors": errors,
    }
