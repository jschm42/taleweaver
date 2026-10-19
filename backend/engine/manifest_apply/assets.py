"""Image URL checks and reuse of source-adventure assets (path-safe copies)."""

from __future__ import annotations

import logging
import os
import re
import shutil
import uuid
from typing import Any, Optional

from backend.core.config import settings
from backend.utils.path_security import (
    assert_within_base_dir,
    assert_within_data_dir,
    data_url_to_local_path,
    ensure_within_base_dir,
    ensure_within_data_dir,
    local_path_to_data_url,
    sanitize_relative_segment,
)
from backend.utils.text_utils import slugify

logger = logging.getLogger(__name__)

_SAFE_BASENAME_RX = re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_PREFIX_RX = re.compile(r"^[A-Za-z0-9_-]+$")
_ASSET_BUCKETS = {"scene": "scenes", "npc": "npcs", "object": "objects"}


def get_base_slug(entity_id: str) -> str:
    return re.sub(r"(_COPY)?(_\d+)?$", "", entity_id, flags=re.IGNORECASE)


def local_path_to_public_data_url(local_path: str) -> Optional[str]:
    try:
        return local_path_to_data_url(local_path)
    except ValueError:
        return None


def _safe_data_path(path: str) -> Optional[str]:
    try:
        return ensure_within_data_dir(path)
    except ValueError:
        return None


def _is_inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def is_usable_image_url(url: Optional[str]) -> bool:
    value = str(url or "").strip()
    if not value:
        return False
    if not value.startswith("/data/"):
        return True
    local_path = data_url_to_local_path(value)
    safe_local_path = _safe_data_path(local_path) if local_path else None
    return bool(safe_local_path and os.path.isfile(safe_local_path))


def needs_image(url: Optional[str]) -> bool:
    return not url or url.startswith("assets/")


def _existing_source_file(source_url: Optional[str]) -> Optional[str]:
    source_local = data_url_to_local_path(source_url)
    safe_source = _safe_data_path(source_local) if source_local else None
    return safe_source if safe_source and os.path.isfile(safe_source) else None


def _reuse_target_file(target_root: str, entity_type: str, source_file: str) -> Optional[str]:
    """Builds a validated destination path inside the adventure's reused-visuals folder."""
    safe_prefix = f"{slugify(str(entity_type)) or 'source'}_{uuid.uuid4().hex[:8]}"
    safe_basename = sanitize_relative_segment(os.path.basename(source_file))
    if not safe_basename or not _SAFE_BASENAME_RX.match(safe_basename):
        return None
    if not _SAFE_PREFIX_RX.match(safe_prefix):
        return None
    target_dir = _safe_data_path(os.path.join(target_root, "visuals", "reused", str(entity_type)))
    if not target_dir:
        return None
    os.makedirs(target_dir, exist_ok=True)
    target_local = _safe_data_path(os.path.join(target_dir, f"{safe_prefix}_{safe_basename}"))
    try:
        target_local = ensure_within_base_dir(target_local, target_dir) if target_local else None
    except ValueError:
        return None
    resolved = os.path.realpath(target_local) if target_local else None
    if not resolved or not _is_inside(resolved, os.path.realpath(target_dir)):
        return None
    return resolved


def copy_source_asset_to_current_adventure(
    source_url: Optional[str], *, template_id: str, entity_type: str
) -> Optional[str]:
    """Copies an image from another adventure into this one and returns its public URL."""
    source_file = _existing_source_file(source_url)
    if not source_file:
        return None
    target_root = ensure_within_data_dir(
        os.path.join(settings.DATA_DIR, "adventures", "library", str(template_id))
    )
    if _is_inside(source_file, target_root):
        return source_url
    target_file = _reuse_target_file(target_root, entity_type, source_file)
    if not target_file:
        return None

    # Re-validate at the sink so taint-tracking static analysers (CodeQL path injection)
    # see the guarantee right before the filesystem mutation.
    source_resolved = assert_within_data_dir(os.path.realpath(source_file))
    target_file = assert_within_base_dir(target_file, os.path.dirname(target_file))
    if not os.path.isfile(target_file):
        try:
            shutil.copy2(source_resolved, target_file)
        except Exception as exc:
            logger.warning(
                "Failed to localize reused source asset for %s/%s from %s: %s",
                template_id,
                entity_type,
                source_url,
                exc,
            )
            return None
    return local_path_to_public_data_url(target_file)


def _source_asset_url(
    source_assets: dict[str, Any], entity_type: str, source_asset_id: str
) -> Optional[str]:
    if entity_type == "cover":
        return source_assets.get("cover")
    if entity_type == "protagonist":
        protagonist = source_assets.get("protagonist") or {}
        return protagonist.get("image_url") if source_asset_id == "PROTAGONIST" else None
    bucket = source_assets.get(_ASSET_BUCKETS.get(entity_type, "")) or []
    if not isinstance(bucket, list):
        return None
    return next(
        (
            asset.get("image_url")
            for asset in bucket
            if isinstance(asset, dict)
            and asset.get("id") == source_asset_id
            and asset.get("image_url")
        ),
        None,
    )


def resolve_source_asset_image(
    source_assets: Optional[dict[str, Any]],
    template_id: str,
    entity_type: str,
    source_asset_id: Optional[str] = None,
) -> Optional[str]:
    """Returns the localized URL for a reused source asset, or None."""
    if not source_assets or not source_asset_id:
        return None
    url = _source_asset_url(source_assets, entity_type, source_asset_id)
    if not url:
        return None
    return copy_source_asset_to_current_adventure(
        url, template_id=template_id, entity_type=entity_type
    )


def _same_text(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (a["name"].lower().strip(), a["description"].lower().strip()) == (
        b["name"].lower().strip(),
        b["description"].lower().strip(),
    )


def find_duplicate_image_url(
    entity: dict[str, Any], processed: list[dict], image_cache: dict[str, str]
) -> Optional[str]:
    """Returns a cached image URL when the entity visually duplicates an earlier one."""
    source_id = entity.get("source_asset_id")
    for prev in processed:
        same_slug = get_base_slug(prev["id"]) == get_base_slug(entity["id"])
        same_source = bool(source_id) and prev.get("source_asset_id") == source_id
        if same_slug or _same_text(prev, entity) or same_source:
            return image_cache.get(prev["id"])
    return None
