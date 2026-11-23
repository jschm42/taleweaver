"""Cut-scenes across manifest apply, ``.adz`` export/import and cloning.

Slide images travel like the world map tiles: exported as ``assets/`` files, mapped back to the
extracted files on import (other URLs are dropped), rewritten to the clone's folder on a copy.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from backend.engine.cutscenes.library import map_image_urls, normalize_cutscenes


def merged_cutscenes(current: Any, incoming: Any) -> Optional[list[dict[str, Any]]]:
    """The manifest's cut-scenes merged into the stored ones (by id).

    An incoming cut-scene replaces the stored one; a slide without an image keeps the image the
    stored cut-scene has at the same position, so re-applying a World-Builder manifest does not
    lose drawn images. A manifest without cut-scenes keeps the stored list.
    """
    new = normalize_cutscenes(incoming)
    if not new:
        return normalize_cutscenes(current) or None
    stored = {c["id"]: c for c in normalize_cutscenes(current)}
    for cutscene in new:
        old_slides = (stored.get(cutscene["id"]) or {}).get("slides") or []
        for index, slide in enumerate(cutscene["slides"]):
            if not slide["image_url"] and index < len(old_slides):
                slide["image_url"] = old_slides[index]["image_url"]
        stored[cutscene["id"]] = cutscene
    return list(stored.values()) or None


def localized_cutscenes(cutscenes: Any, localize: Callable[[str], Any]) -> list[dict[str, Any]]:
    """Export: every slide image URL replaced by its bundle path (``localize``)."""
    return map_image_urls(cutscenes, localize)


def imported_cutscenes(raw: Any, asset_mapping: dict[str, str]) -> Optional[list[dict[str, Any]]]:
    """Import: slide images that came with the bundle, at their new path; others are dropped."""
    return map_image_urls(raw, asset_mapping.get) or None


def cloned_cutscenes(raw: Any, rewrite: Callable[[str], Any]) -> Optional[list[dict[str, Any]]]:
    """Clone: slide image URLs pointing into the clone's library."""
    return map_image_urls(raw, rewrite) or None
