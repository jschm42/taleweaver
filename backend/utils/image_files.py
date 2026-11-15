"""Resolve a ``/data/...`` image URL to a local file only when it really is an image.

Downloads that pack files by an entity's ``image_url`` (debug ZIP, ``.twe`` export) must not
become a file-read primitive: ``image_url`` can come from imported or scripted data, and
``DATA_DIR`` also holds the database and other non-image files. A file qualifies only when it
lies inside ``DATA_DIR`` (``path_security``), has an image extension and Pillow recognises its
content as that kind of image.
"""

from __future__ import annotations

import os
from typing import Optional

from PIL import Image, UnidentifiedImageError

from backend.utils.path_security import assert_within_data_dir, data_url_to_local_path

IMAGE_FILE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "webp", "gif"})
_PIL_FORMATS = {"PNG", "JPEG", "WEBP", "GIF", "MPO"}


def _is_image(path: str) -> bool:
    try:
        with Image.open(path) as image:
            fmt = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return False
    return fmt in _PIL_FORMATS


def local_image_file(url: Optional[str]) -> Optional[str]:
    """The validated local path of an image URL, or None for anything that is not one."""
    raw = str(url or "").split("?", 1)[0].split("#", 1)[0]
    path = data_url_to_local_path(raw)
    if not path or not os.path.isfile(path):
        return None
    safe_path = assert_within_data_dir(path)
    ext = os.path.splitext(safe_path)[1].lstrip(".").lower()
    if ext not in IMAGE_FILE_EXTENSIONS or not _is_image(safe_path):
        return None
    return safe_path
