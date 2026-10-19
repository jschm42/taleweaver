"""Copies an entity image when an entity is cloned in the editor."""

import logging
import os
import shutil
import uuid
from typing import Optional

from backend.core.config import settings
from backend.utils.path_security import (
    assert_within_base_dir,
    assert_within_data_dir,
    data_url_to_local_path,
    ensure_within_base_dir,
    ensure_within_data_dir,
    local_path_to_data_url,
    sanitize_path_component,
    sanitize_relative_segment,
)

logger = logging.getLogger(__name__)

_CLONE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _require_inside(path: str, root: str) -> str:
    """Raise ``ValueError`` unless ``path`` lies strictly inside ``root``.

    The redundant prefix + commonpath checks are deliberate: they keep taint-tracking
    static analysers (CodeQL path-injection) convinced at each filesystem sink.
    """
    if not path.startswith(root + os.sep) or os.path.commonpath([path, root]) != root:
        raise ValueError(f"Path escapes {root}.")
    return path


def _resolved_inside_data(path: str, data_root: str) -> str:
    return _require_inside(
        os.path.abspath(os.path.realpath(ensure_within_data_dir(path))), data_root
    )


def _clone_file_name(new_entity_id: str, source_path: str) -> str:
    # Restrict the extension to a hard-coded allowlist to satisfy the
    # path-traversal linter: a user-controlled image URL could otherwise inject
    # an arbitrary suffix into the constructed file name.
    raw_ext = os.path.splitext(source_path)[1].lower()
    safe_ext = raw_ext if raw_ext in _CLONE_IMAGE_EXTENSIONS else ".png"
    safe_entity_token = sanitize_path_component(new_entity_id) or "entity"
    target_name = f"{safe_entity_token}_clone_{uuid.uuid4().hex[:8]}{safe_ext}"
    return os.path.basename(
        sanitize_relative_segment(target_name) or f"entity_clone_{uuid.uuid4().hex}{safe_ext}"
    )


def _clone_paths(source_image_url: str, new_entity_id: str) -> tuple[str, str]:
    """Validated (source, target) paths for the copy. Raises ``ValueError`` when unsafe."""
    source_path = data_url_to_local_path(source_image_url)
    if not source_path or not os.path.isfile(source_path):
        raise ValueError("Source image is not on disk.")

    data_root = os.path.abspath(os.path.realpath(settings.DATA_DIR))
    safe_source_path = _resolved_inside_data(source_path, data_root)
    target_dir = os.path.dirname(safe_source_path)
    if not target_dir or not os.path.isdir(target_dir):
        raise ValueError("Target directory does not exist.")
    safe_target_dir = _resolved_inside_data(target_dir, data_root)

    candidate = os.path.join(safe_target_dir, _clone_file_name(new_entity_id, safe_source_path))
    candidate_path = os.path.abspath(
        os.path.realpath(ensure_within_base_dir(candidate, safe_target_dir))
    )
    _require_inside(candidate_path, safe_target_dir)
    _require_inside(candidate_path, data_root)

    # Re-validate before filesystem sink for taint-tracking static analysers
    safe_source_path = _require_inside(assert_within_data_dir(safe_source_path), data_root)
    candidate_path = _require_inside(
        assert_within_base_dir(candidate_path, safe_target_dir), data_root
    )
    return safe_source_path, candidate_path


async def _clone_entity_image(
    *,
    source_image_url: Optional[str],
    template_id: str,
    new_entity_id: str,
) -> Optional[str]:
    """Copy the source entity image into a new file under the same adventure's entities dir.

    Returns the new ``/data/...`` URL on success, or ``None`` when the source has no
    image, the image is not on disk, or the copy fails. The original image is preserved.
    """
    if not source_image_url:
        return None
    try:
        source_path, candidate_path = _clone_paths(source_image_url, new_entity_id)
        shutil.copy2(source_path, candidate_path)
    except ValueError:
        return None
    except OSError as exc:
        logger.warning("Failed to clone image for entity %s: %s", new_entity_id, exc)
        return None
    return local_path_to_data_url(candidate_path)
