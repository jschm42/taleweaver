"""Library updates for installed adventures.

An installed adventure has a library update when the catalog lists its ``origin_id`` with
a higher version. Applying it reuses the local update path (``update_single_adventure``),
which keeps game sessions linked: the newer bundle is only downloaded into the download
directory, where the update scanner picks it up like any local file.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from backend.models.adventure_template import AdventureTemplate
from backend.services.adventure_library.catalog import LibraryError, LibraryService
from backend.services.adventure_library.installer import download_bundle
from backend.services.adventure_library.models import (
    AdventureLibrary,
    LibraryEntry,
    is_newer_version,
    is_version_at_least,
)

logger = logging.getLogger(__name__)


def library_update_for(
    library: AdventureLibrary, template: AdventureTemplate
) -> LibraryEntry | None:
    """The catalog entry that is newer than ``template``, if any."""
    if not template.origin_id:
        return None
    entry = LibraryService.resolve_entry(library, template.origin_id)
    if entry is None or not is_newer_version(entry.version, template.version or ""):
        return None
    return entry


def _bundle_on_disk(template: AdventureTemplate, version: str) -> bool:
    """True when a local file for ``template`` already has ``version`` or newer."""
    # Imported lazily: adventure_updates has an import cycle through the API routers.
    from backend.engine.adventures.adventure_updates import (
        find_matching_file_for_template,
        scan_available_adventure_files,
    )

    matching = find_matching_file_for_template(template, scan_available_adventure_files())
    file_version = (matching or {}).get("version")
    return bool(file_version) and is_version_at_least(str(file_version), version)


async def stage_library_updates(
    templates: Iterable[AdventureTemplate],
    service: LibraryService | None = None,
) -> list[str]:
    """Download newer library bundles for ``templates`` so a local update can apply them.

    Uses the cached catalog. Without a catalog nothing is staged and local updates still
    work. Returns one message per bundle that could not be downloaded.
    """
    service = service or LibraryService()
    try:
        library = await service.get_library()
    except LibraryError as exc:
        logger.info("No library catalog for update staging: %s", exc)
        return []

    errors: list[str] = []
    for template in templates:
        entry = library_update_for(library, template)
        if entry is None:
            continue
        on_disk = await asyncio.to_thread(_bundle_on_disk, template, entry.version)
        if on_disk:
            continue
        try:
            await download_bundle(entry)
        except LibraryError as exc:
            logger.warning("Downloading the update of %s failed: %s", entry.slug, exc)
            errors.append(f"{template.title}: download failed ({exc})")
    return errors
