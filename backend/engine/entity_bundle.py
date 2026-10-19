"""TaleWeaver entity bundle (``.twe``): a ZIP holding one protagonist, NPC, or item.

Layout::

    entity.json        -> {"format", "version", "kind", "source", "entity", "image"}
    assets/image.<ext> -> optional portrait / item image

This module only handles the file format (packing, unpacking, validation). Reading
from and writing to the database lives in the editor entity transfer service.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from PIL import Image

BUNDLE_FORMAT = "TaleWeaverEntity"
BUNDLE_VERSION = 1
BUNDLE_EXTENSION = "twe"
MANIFEST_NAME = "entity.json"
BUNDLE_KINDS = ("protagonist", "npc", "item")

MAX_BUNDLE_BYTES = 25 * 1024 * 1024
MAX_BUNDLE_ENTRIES = 8
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100

# Detected Pillow format -> file extension stored in the bundle and on disk.
_IMAGE_EXT_BY_FORMAT = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}
IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "webp"})


class EntityBundleError(ValueError):
    """Raised when a bundle cannot be built or is malformed."""


@dataclass(frozen=True)
class EntityBundle:
    kind: str
    entity: dict[str, Any]
    image_bytes: Optional[bytes] = None
    image_ext: Optional[str] = None
    source_title: Optional[str] = None


def pack_entity_bundle(bundle: EntityBundle) -> bytes:
    """Serialize a bundle into ``.twe`` (ZIP) bytes."""
    if bundle.kind not in BUNDLE_KINDS:
        raise EntityBundleError(f"Unsupported bundle kind '{bundle.kind}'.")

    image_entry = None
    if bundle.image_bytes:
        ext = str(bundle.image_ext or "png").lower()
        if ext not in IMAGE_EXTENSIONS:
            raise EntityBundleError(f"Unsupported image extension '{ext}'.")
        image_entry = f"assets/image.{ext}"

    manifest = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "kind": bundle.kind,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": {"adventure_title": bundle.source_title},
        "entity": jsonable_encoder(bundle.entity),
        "image": image_entry,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False))
        if image_entry and bundle.image_bytes:
            zip_file.writestr(image_entry, bundle.image_bytes)
    return buffer.getvalue()


def unpack_entity_bundle(data: bytes) -> EntityBundle:
    """Parse and validate ``.twe`` bytes. Raises :class:`EntityBundleError`."""
    if len(data) > MAX_BUNDLE_BYTES:
        raise EntityBundleError("Bundle file is too large.")
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r") as zip_file:
            _check_zip_limits(zip_file.infolist())
            manifest = _read_manifest(zip_file)
            image_bytes, image_ext = _read_image(zip_file, manifest.get("image"))
    except zipfile.BadZipFile as exc:
        raise EntityBundleError("File is not a valid entity bundle (ZIP expected).") from exc

    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    return EntityBundle(
        kind=manifest["kind"],
        entity=manifest["entity"],
        image_bytes=image_bytes,
        image_ext=image_ext,
        source_title=source.get("adventure_title"),
    )


def _check_zip_limits(infos: list[zipfile.ZipInfo]) -> None:
    if len(infos) > MAX_BUNDLE_ENTRIES:
        raise EntityBundleError("Bundle contains too many files.")
    for info in infos:
        if info.file_size > MAX_IMAGE_BYTES:
            raise EntityBundleError(f"Bundle entry '{info.filename}' is too large.")
        if info.compress_size > 0 and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise EntityBundleError(f"Bundle entry '{info.filename}' has a suspicious size.")


def _read_manifest(zip_file: zipfile.ZipFile) -> dict[str, Any]:
    if MANIFEST_NAME not in zip_file.namelist():
        raise EntityBundleError(f"Bundle is missing {MANIFEST_NAME}.")
    if zip_file.getinfo(MANIFEST_NAME).file_size > MAX_MANIFEST_BYTES:
        raise EntityBundleError(f"{MANIFEST_NAME} is too large.")
    try:
        manifest = json.loads(zip_file.read(MANIFEST_NAME).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EntityBundleError(f"{MANIFEST_NAME} is not valid JSON.") from exc

    if not isinstance(manifest, dict) or manifest.get("format") != BUNDLE_FORMAT:
        raise EntityBundleError("File is not a TaleWeaver entity bundle.")
    version = manifest.get("version")
    if not isinstance(version, int) or version > BUNDLE_VERSION:
        raise EntityBundleError(f"Unsupported entity bundle version '{version}'.")
    if manifest.get("kind") not in BUNDLE_KINDS:
        raise EntityBundleError(f"Unsupported bundle kind '{manifest.get('kind')}'.")
    if not isinstance(manifest.get("entity"), dict):
        raise EntityBundleError("Bundle has no entity data.")
    return manifest


def _read_image(zip_file: zipfile.ZipFile, entry: Any) -> tuple[Optional[bytes], Optional[str]]:
    if not entry:
        return None, None
    if not isinstance(entry, str) or not entry.startswith("assets/"):
        raise EntityBundleError("Bundle image path is invalid.")
    if entry not in zip_file.namelist():
        raise EntityBundleError("Bundle image file is missing.")

    image_bytes = zip_file.read(entry)
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            detected_format = img.format
            img.verify()
    except Exception as exc:
        raise EntityBundleError("Bundle image is not a readable image.") from exc

    image_ext = _IMAGE_EXT_BY_FORMAT.get(str(detected_format or "").upper())
    if not image_ext:
        raise EntityBundleError("Bundle image must be PNG, JPEG, or WEBP.")
    return image_bytes, image_ext
