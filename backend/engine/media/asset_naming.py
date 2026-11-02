"""File naming and encoding rules for generated image assets.

Generated files use a single short random ID as prefix followed by a short
descriptive label, e.g. ``3f9a1c2e_cover.webp``. The folder already tells
which adventure the file belongs to, so the adventure ID is not repeated.
"""

import io
import uuid
from typing import Any, Optional

from PIL import Image

from backend.utils.text_utils import slugify

DEFAULT_IMAGE_FORMAT = "webp"
DEFAULT_IMAGE_QUALITY = 85
ASSET_ID_LENGTH = 8
MAX_LABEL_LENGTH = 24

# format -> (file extension, Pillow format name)
_FORMATS: dict[str, tuple[str, str]] = {
    "webp": ("webp", "WEBP"),
    "jpeg": ("jpg", "JPEG"),
    "png": ("png", "PNG"),
}
_ALIASES = {"jpg": "jpeg"}


def normalize_image_format(image_format: Optional[str]) -> str:
    """Return a supported format key, falling back to the default (WEBP)."""
    key = str(image_format or "").strip().lower()
    key = _ALIASES.get(key, key)
    return key if key in _FORMATS else DEFAULT_IMAGE_FORMAT


def image_extension(image_format: Optional[str]) -> str:
    """File extension (without dot) for the given image format."""
    return _FORMATS[normalize_image_format(image_format)][0]


def short_asset_id() -> str:
    """Short random ID used as the single filename prefix."""
    return uuid.uuid4().hex[:ASSET_ID_LENGTH]


def asset_filename(label: str, image_format: Optional[str] = None) -> str:
    """Build ``<id>_<label>.<ext>`` with a short, slugified label."""
    safe_label = slugify(str(label or ""))[:MAX_LABEL_LENGTH].strip("-_") or "image"
    return f"{short_asset_id()}_{safe_label}.{image_extension(image_format)}"


def encode_image(
    image_bytes: bytes,
    image_format: Optional[str],
    quality: int = DEFAULT_IMAGE_QUALITY,
) -> bytes:
    """Re-encode raw provider image bytes into the configured storage format."""
    fmt = normalize_image_format(image_format)
    pil_format = _FORMATS[fmt][1]
    save_kwargs = _save_kwargs(fmt, quality)
    with Image.open(io.BytesIO(image_bytes)) as img:
        img_to_save = _convert_mode(img, fmt)
        buffer = io.BytesIO()
        img_to_save.save(buffer, pil_format, **save_kwargs)
    return buffer.getvalue()


def _save_kwargs(fmt: str, quality: int) -> dict[str, Any]:
    q = int(quality or DEFAULT_IMAGE_QUALITY)
    kwargs_by_format: dict[str, dict[str, Any]] = {
        "webp": {"quality": q, "method": 4},
        "jpeg": {"quality": q, "optimize": True},
        "png": {"optimize": True},
    }
    return kwargs_by_format[fmt]


def _convert_mode(img: Image.Image, fmt: str) -> Image.Image:
    """Convert palette/alpha modes the target format cannot store."""
    if fmt == "jpeg" and img.mode in ("RGBA", "P", "LA"):
        return img.convert("RGB")
    if fmt == "webp" and img.mode == "P":
        return img.convert("RGBA")
    return img
