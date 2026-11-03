import io
import re

import pytest
from PIL import Image

from backend.engine.media.asset_naming import (
    asset_filename,
    encode_image,
    image_extension,
    normalize_image_format,
)


def _png_bytes(mode: str = "RGBA") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (8, 8)).save(buffer, "PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "webp"),
        ("", "webp"),
        ("WEBP", "webp"),
        ("jpg", "jpeg"),
        ("png", "png"),
        ("x", "webp"),
    ],
)
def test_normalize_image_format_defaults_to_webp(raw, expected):
    # Act / Assert
    assert normalize_image_format(raw) == expected


def test_asset_filename_uses_single_short_prefix_id():
    # Act
    name = asset_filename("The Loom-Console Of Doom And Gloom", None)

    # Assert
    assert re.fullmatch(r"[0-9a-f]{8}_[a-z0-9_-]{1,24}\.webp", name)


@pytest.mark.parametrize(("fmt", "pil_name"), [("webp", "WEBP"), ("jpeg", "JPEG"), ("png", "PNG")])
@pytest.mark.parametrize("mode", ["RGBA", "P", "RGB"])
def test_encode_image_writes_requested_format(fmt, pil_name, mode):
    # Act
    encoded = encode_image(_png_bytes(mode), fmt)

    # Assert
    assert Image.open(io.BytesIO(encoded)).format == pil_name
    assert image_extension(fmt) in {"webp", "jpg", "png"}
