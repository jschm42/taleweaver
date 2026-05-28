import os
import re
from pathlib import PurePosixPath
from typing import Optional

from backend.core.config import settings

_SAFE_PATH_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SAFE_RELATIVE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]{1,255}$")


def sanitize_path_component(value: Optional[str]) -> Optional[str]:
    """Return a safe single path component (folder/id style), or None when invalid."""
    if value is None:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    if any(sep in candidate for sep in (os.sep, os.altsep) if sep):
        return None
    if candidate in {".", ".."} or ".." in candidate:
        return None
    if not _SAFE_PATH_COMPONENT_RE.fullmatch(candidate):
        return None
    return candidate


def sanitize_relative_segment(value: Optional[str]) -> Optional[str]:
    """Return a safe relative-path segment (filename/folder), or None when invalid."""
    if value is None:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    if any(sep in candidate for sep in ("/", "\\", os.sep, os.altsep) if sep):
        return None
    if candidate in {".", ".."} or ".." in candidate:
        return None
    if not _SAFE_RELATIVE_SEGMENT_RE.fullmatch(candidate):
        return None
    return candidate


def ensure_within_base_dir(path: str, base_dir: str) -> str:
    """Resolve a path and ensure it stays inside a base directory."""
    base_root = os.path.realpath(base_dir)
    resolved = os.path.realpath(path)
    try:
        if os.path.commonpath([resolved, base_root]) != base_root:
            raise ValueError("Resolved path escapes configured base directory.")
    except ValueError as exc:
        raise ValueError("Invalid path: cannot resolve against configured base directory.") from exc
    return resolved


def ensure_within_data_dir(path: str) -> str:
    """Resolve a path and ensure it stays inside DATA_DIR."""
    return ensure_within_base_dir(path, settings.DATA_DIR)


def safe_data_path(*parts: str) -> str:
    """Build a safe path rooted at DATA_DIR from trusted path components."""
    safe_parts: list[str] = []
    for part in parts:
        safe_part = sanitize_path_component(part)
        if not safe_part:
            raise ValueError("Invalid path component.")
        safe_parts.append(safe_part)

    return ensure_within_data_dir(os.path.join(settings.DATA_DIR, *safe_parts))


def data_url_to_local_path(url: Optional[str]) -> Optional[str]:
    """Convert a /data/... URL to a validated local DATA_DIR path."""
    raw = str(url or "").strip()
    if not raw.startswith("/data/"):
        return None

    relative = raw[len("/data/"):].lstrip("/")
    if not relative:
        return None

    posix_path = PurePosixPath(relative)
    if posix_path.is_absolute():
        return None

    safe_parts: list[str] = []
    for part in posix_path.parts:
        safe_part = sanitize_relative_segment(part)
        if not safe_part:
            return None
        safe_parts.append(safe_part)

    if not safe_parts:
        return None

    return ensure_within_data_dir(os.path.join(settings.DATA_DIR, *safe_parts))


def local_path_to_data_url(path: str) -> str:
    """Convert a local DATA_DIR path to canonical /data/... URL."""
    resolved = ensure_within_data_dir(path)
    data_root = os.path.realpath(settings.DATA_DIR)
    rel = os.path.relpath(resolved, data_root).replace("\\", "/")
    return f"/data/{rel}"
