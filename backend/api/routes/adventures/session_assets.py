"""Copies /data visuals into a session's own folder so template edits never leak into it."""

from __future__ import annotations

import glob
import logging
import os
import shutil
import time
import uuid
from typing import Any, Optional

from backend.core.config import settings
from backend.engine.rules.item_logic import normalize_equipment_keys
from backend.models.avatar import Avatar
from backend.utils.path_security import (
    data_url_to_local_path,
    ensure_within_data_dir,
    local_path_to_data_url,
    sanitize_path_component,
)

logger = logging.getLogger(__name__)

SAFE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
_THUMBNAIL_SIZE = (480, 480)
_SECONDS_PER_DAY = 24 * 60 * 60
# Monotonic timestamp of the last stale-dir sweep (see cleanup_stale_empty_session_dirs).
_CLEANUP_STATE: dict[str, Optional[float]] = {"last_run": None}


def sessions_root() -> str:
    return ensure_within_data_dir(os.path.join(settings.DATA_DIR, "adventures", "sessions"))


def ensure_session_dir(session_id: str) -> None:
    """Concrete filesystem root for session-bound artifacts (visuals, TTS, ...)."""
    os.makedirs(
        os.path.join(settings.DATA_DIR, "adventures", "sessions", session_id), exist_ok=True
    )


def normalize_data_asset_url(source_url: Optional[str]) -> Optional[str]:
    """Normalize legacy relative asset URLs to the canonical /data/... form."""
    if not isinstance(source_url, str):
        return source_url

    candidate = source_url.strip()
    if not candidate:
        return candidate

    lowered = candidate.lower()
    if lowered.startswith(("http://", "https://", "data:", "blob:")):
        return candidate
    if candidate.startswith("/data/"):
        return candidate
    if candidate.startswith("/"):
        return f"/data{candidate}"
    return f"/data/{candidate.lstrip('/')}"


def _first_existing_file(pattern: str) -> Optional[str]:
    for candidate in glob.iglob(pattern, recursive=True):
        try:
            resolved = ensure_within_data_dir(candidate)
        except ValueError:
            continue
        if os.path.isfile(resolved):
            return resolved
    return None


def find_existing_data_asset_path(filename: str) -> Optional[str]:
    """Search the library and session folders for a file with this name."""
    if not filename:
        return None

    for bucket in ("library", "sessions"):
        root = ensure_within_data_dir(os.path.join(settings.DATA_DIR, "adventures", bucket))
        if not os.path.isdir(root):
            continue
        found = _first_existing_file(os.path.join(root, "**", filename))
        if found:
            return found
    return None


def _existing_source_path(source_path: str) -> Optional[str]:
    """The file itself, or a same-named file elsewhere in the data folders."""
    if os.path.isfile(source_path):
        return source_path
    return find_existing_data_asset_path(os.path.basename(source_path))


def _session_visuals_target(safe_session_id: str, safe_bucket: str, source_path: str) -> str:
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in SAFE_IMAGE_EXTENSIONS:
        ext = ".png"
    target_dir = ensure_within_data_dir(
        os.path.join(
            settings.DATA_DIR, "adventures", "sessions", safe_session_id, "visuals", safe_bucket
        )
    )
    os.makedirs(target_dir, exist_ok=True)
    return ensure_within_data_dir(os.path.join(target_dir, f"{uuid.uuid4().hex}{ext}"))


def _thumb_path(path: str) -> str:
    stem, ext = os.path.splitext(path)
    return f"{stem}_thumb{ext}"


def is_svg_file(file_path: str) -> bool:
    """Check if file is an SVG by extension or header sniffing."""
    if file_path.lower().endswith(".svg"):
        return True
    if not os.path.isfile(file_path):
        return False
    try:
        with open(file_path, "rb") as f:
            return b"<svg" in f.read(512).lower()
    except OSError:
        return False


def _copy_thumbnail(source: str, target: str) -> None:
    try:
        shutil.copy2(source, target)
    except OSError:
        logger.warning("Failed copying asset thumbnail to session folder: %s -> %s", source, target)


def _render_thumbnail(image_path: str, thumb_path: str) -> None:
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            img.thumbnail(_THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            output = img.convert("RGB") if img.mode in ("RGBA", "P") else img
            output.save(thumb_path, optimize=True, quality=80)
    except Exception as exc:
        logger.warning("Could not generate thumbnail for session asset %s: %s", image_path, exc)


def _ensure_thumbnail(source_path: str, target_path: str) -> None:
    """Reuse the source thumbnail, copy SVGs as-is, otherwise render a new one."""
    target_thumb = _thumb_path(target_path)
    source_thumb = _thumb_path(source_path)
    if os.path.isfile(source_thumb):
        _copy_thumbnail(source_thumb, target_thumb)
    elif is_svg_file(target_path):
        _copy_thumbnail(target_path, target_thumb)
    else:
        _render_thumbnail(target_path, target_thumb)


def _copy_into_session(session_id: str, bucket: str, normalized_url: str) -> Optional[str]:
    """Copied URL; ``normalized_url`` when the source is missing; None on any failure."""
    safe_session_id = sanitize_path_component(session_id)
    safe_bucket = sanitize_path_component(bucket)
    if not safe_session_id or not safe_bucket:
        logger.warning(
            "Skipping asset copy due to invalid session/bucket: %s / %s", session_id, bucket
        )
        return None

    local_path = data_url_to_local_path(normalized_url)
    if not local_path:
        logger.warning("Skipping asset copy for unsafe source URL: %s", normalized_url)
        return None
    source_path = _existing_source_path(local_path)
    if not source_path:
        logger.warning("Skipping asset copy because source file does not exist: %s", local_path)
        return normalized_url

    target_path = _session_visuals_target(safe_session_id, safe_bucket, source_path)
    try:
        shutil.copy2(source_path, target_path)
    except OSError:
        logger.exception(
            "Failed copying asset to session folder: %s -> %s", source_path, target_path
        )
        return None
    _ensure_thumbnail(source_path, target_path)
    return local_path_to_data_url(target_path)


def copy_data_asset_to_session(
    session_id: str,
    bucket: str,
    source_url: Optional[str],
    cache: dict[str, str],
) -> Optional[str]:
    """Copy a /data asset into the session's visuals folder and return its new URL.

    Non-/data URLs, unsafe input and copy failures return the original URL.
    """
    normalized_url = normalize_data_asset_url(source_url)
    if not isinstance(normalized_url, str) or not normalized_url.startswith("/data/"):
        return source_url
    if cache.get(normalized_url):
        return cache[normalized_url]

    copied = _copy_into_session(session_id, bucket, normalized_url)
    if copied is None:
        return source_url
    if copied != normalized_url:
        cache[normalized_url] = copied
    return copied


def _with_session_image(item: Any, session_id: str, cache: dict[str, str]) -> Any:
    if not isinstance(item, dict):
        return item
    item_copy = dict(item)
    item_copy["image_url"] = copy_data_asset_to_session(
        session_id, "items", item_copy.get("image_url"), cache
    )
    return item_copy


def rewrite_avatar_item_visual_urls(avatar: Avatar, session_id: str, cache: dict[str, str]) -> None:
    """Rewrite avatar inventory/equipment image URLs to copied session-local assets."""
    avatar.inventory = [
        _with_session_image(item, session_id, cache) for item in (avatar.inventory or [])
    ]
    avatar.equipment = {
        slot: _with_session_image(item, session_id, cache)
        for slot, item in normalize_equipment_keys(avatar.equipment).items()
    }


def rewrite_asset_snapshot_urls(
    session_id: str, snapshot: dict[str, Any], cache: dict[str, str]
) -> dict[str, Any]:
    """Rewrite known asset snapshot URL fields to copied session-local assets."""
    rewritten = dict(snapshot or {})
    rewritten["cover"] = copy_data_asset_to_session(
        session_id, "cover", rewritten.get("cover"), cache
    )
    rewritten["protagonist"] = copy_data_asset_to_session(
        session_id, "protagonist", rewritten.get("protagonist"), cache
    )

    entity_images = rewritten.get("entity_images")
    if isinstance(entity_images, dict):
        rewritten["entity_images"] = {
            ent_id: copy_data_asset_to_session(session_id, "entities", image_url, cache)
            for ent_id, image_url in entity_images.items()
        }

    for key, value in list(rewritten.items()):
        if key not in {"cover", "protagonist", "entity_images"} and isinstance(value, str):
            rewritten[key] = copy_data_asset_to_session(session_id, "snapshot", value, cache)
    return rewritten


def _remove_if_stale_and_empty(path: str, cutoff_ts: float) -> bool:
    try:
        if os.listdir(path) or os.path.getmtime(path) >= cutoff_ts:
            return False
        os.rmdir(path)
    except OSError:
        # Ignore race conditions and permission errors; cleanup is best-effort.
        return False
    return True


def _orphaned_session_dirs(root: str, active_session_ids: set[str]) -> list[str]:
    try:
        entries = os.listdir(root)
    except OSError:
        logger.exception("Failed to list session directory root for stale cleanup.")
        return []
    safe_ids = (sanitize_path_component(entry) for entry in entries)
    candidates = (
        ensure_within_data_dir(os.path.join(root, safe_id))
        for safe_id in safe_ids
        if safe_id and safe_id not in active_session_ids
    )
    return [path for path in candidates if os.path.isdir(path)]


def cleanup_stale_empty_session_dirs(
    active_session_ids: set[str], max_age_days: int, min_interval_seconds: float = 0.0
) -> int:
    """Remove orphaned empty session directories older than max_age_days.

    With ``min_interval_seconds`` the sweep is skipped when the last one ran more recently;
    it touches every session folder, which takes seconds once thousands exist.
    """
    if max_age_days <= 0:
        return 0
    now = time.monotonic()
    last_run = _CLEANUP_STATE["last_run"]
    if last_run is not None and now - last_run < min_interval_seconds:
        return 0
    _CLEANUP_STATE["last_run"] = now
    root = sessions_root()
    if not os.path.isdir(root):
        return 0
    cutoff_ts = time.time() - (max_age_days * _SECONDS_PER_DAY)
    orphans = _orphaned_session_dirs(root, active_session_ids)
    return sum(1 for path in orphans if _remove_if_stale_and_empty(path, cutoff_ts))
