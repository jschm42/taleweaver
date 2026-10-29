"""Helpers shared by the .adv / .adz adventure import entry points.

Kept separate from ``adventure_importer`` so the importer only orchestrates:
archive guards, manifest reading, asset extraction, owner/user resolution and
small manifest normalization steps live here.
"""

import json
import logging
import os
import uuid
import zipfile
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.adventure_format import validate_manifest_version
from backend.core.auth import get_password_hash
from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

logger = logging.getLogger(__name__)

# ZIP-bomb / resource-exhaustion guards for .adz imports.
# Tuned to be permissive enough for legitimate adventures but tight enough
# to stop "decompression bomb" payloads (small archive → huge extracted tree).
MAX_ADZ_TOTAL_ENTRIES = 1000
MAX_ADZ_ENTRY_BYTES = 50 * 1024 * 1024  # 50 MB per file
MAX_ADZ_TOTAL_BYTES = 500 * 1024 * 1024  # 500 MB cumulative
MAX_ADZ_COMPRESSION_RATIO = 100  # uncompressed/compressed size cap


def ensure_within_data_dir(path: str) -> str:
    data_root = os.path.abspath(settings.DATA_DIR)
    resolved = os.path.abspath(path)
    try:
        if os.path.commonpath([resolved, data_root]) != data_root:
            raise ValueError("Resolved path escapes DATA_DIR.")
    except ValueError as exc:
        raise ValueError("Invalid path: cannot resolve against DATA_DIR.") from exc
    return resolved


def _entry_exceeds_limits(info: zipfile.ZipInfo) -> bool:
    if info.file_size > MAX_ADZ_ENTRY_BYTES:
        logger.error(
            "Refusing ADZ import: entry '%s' is %d bytes (limit %d).",
            info.filename,
            info.file_size,
            MAX_ADZ_ENTRY_BYTES,
        )
        return True
    if info.compress_size <= 0:
        return False
    ratio = info.file_size / info.compress_size
    if ratio > MAX_ADZ_COMPRESSION_RATIO:
        logger.error(
            "Refusing ADZ import: entry '%s' compression ratio %.1fx exceeds %dx.",
            info.filename,
            ratio,
            MAX_ADZ_COMPRESSION_RATIO,
        )
        return True
    return False


def check_adz_limits(infos: list[zipfile.ZipInfo]) -> bool:
    """Return False (and log why) when the archive trips a zip-bomb guard."""
    if len(infos) > MAX_ADZ_TOTAL_ENTRIES:
        logger.error(
            "Refusing ADZ import: %d entries exceeds limit of %d.",
            len(infos),
            MAX_ADZ_TOTAL_ENTRIES,
        )
        return False

    total_uncompressed = 0
    for info in infos:
        if _entry_exceeds_limits(info):
            return False
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_ADZ_TOTAL_BYTES:
            logger.error(
                "Refusing ADZ import: total uncompressed size exceeds %d bytes.",
                MAX_ADZ_TOTAL_BYTES,
            )
            return False
    return True


def read_adz_manifest(zip_file: zipfile.ZipFile) -> Optional[dict[str, Any]]:
    """Load and validate adventure.adv; returns None when the bundle is invalid."""
    if "adventure.adv" not in zip_file.namelist():
        logger.error("Invalid ADZ: Missing adventure.adv")
        return None

    manifest_data = json.loads(zip_file.read("adventure.adv").decode("utf-8"))
    try:
        validate_manifest_version(manifest_data, require_format=True)
    except ValueError as exc:
        logger.error("Invalid ADZ format: %s", exc)
        return None

    if not manifest_data.get("adventure"):
        logger.error("Invalid ADZ: Missing adventure section in manifest")
        return None
    return manifest_data


def extract_adz_assets(zip_file: zipfile.ZipFile, target_base_dir: str) -> dict[str, str]:
    """Extract assets/ entries into target_base_dir; returns zip_path -> local /data URL."""
    existing_images_mapping: dict[str, str] = {}
    for zip_path in zip_file.namelist():
        if not zip_path.startswith("assets/"):
            continue
        filename = os.path.basename(zip_path)
        if not filename:
            continue
        target_path = ensure_within_data_dir(os.path.join(target_base_dir, filename))
        with open(target_path, "wb") as f:
            f.write(zip_file.read(zip_path))

        rel_path = os.path.relpath(target_path, settings.DATA_DIR).replace("\\", "/")
        existing_images_mapping[zip_path] = f"/data/{rel_path}"
    return existing_images_mapping


def collect_existing_image_urls(
    manifest_data: dict[str, Any], existing_images_mapping: dict[str, str]
) -> dict[str, str]:
    """Map entity ids (and PROTAGONIST) to the already-extracted image URLs."""
    image_urls: dict[str, str] = {}
    prot = manifest_data.get("protagonist")
    if prot and prot.get("profile_image") in existing_images_mapping:
        image_urls["PROTAGONIST"] = existing_images_mapping[prot["profile_image"]]

    records = [
        *manifest_data.get("scenes", []),
        *manifest_data.get("npcs", []),
        *manifest_data.get("objects", []),
    ]
    for record in records:
        if record.get("image_url") in existing_images_mapping:
            image_urls[record["id"]] = existing_images_mapping[record["image_url"]]
    return image_urls


def fill_start_scene_ids(
    records: list[dict[str, Any]], default_scene_id: str, fallback_keys: tuple[str, ...]
) -> None:
    """Set start_scene_id from the first truthy fallback key, else default_scene_id."""
    for record in records:
        if "start_scene_id" in record:
            continue
        candidates = (record.get(key) for key in fallback_keys)
        record["start_scene_id"] = next((c for c in candidates if c), None) or default_scene_id


async def find_existing_template(
    db: AsyncSession, owner_id: Optional[str], title: str, origin_id: Optional[str]
) -> Optional[AdventureTemplate]:
    """Find a template of this owner with the same origin_id, else a legacy one with the same title.

    Templates carrying a different origin_id are distinct adventures and never match by title.
    """
    owner_clause = (
        (AdventureTemplate.owner_id == owner_id)
        if owner_id
        else AdventureTemplate.owner_id.is_(None)
    )
    query = select(AdventureTemplate).where(owner_clause)
    if origin_id:
        by_origin = await db.execute(query.where(AdventureTemplate.origin_id == origin_id))
        existing = by_origin.scalars().first()
        if existing:
            return existing
        query = query.where(AdventureTemplate.origin_id.is_(None))

    existing_res = await db.execute(query.where(AdventureTemplate.title == title))
    return existing_res.scalars().first()


async def load_owner(db: AsyncSession, owner_id: Optional[str]) -> Optional[User]:
    if not owner_id:
        return None
    user_res = await db.execute(select(User).where(User.id == owner_id))
    return user_res.scalars().first()


def build_local_default_user() -> User:
    # Import-only fallback user; password is intentionally random and unknown.
    return User(
        username="local_default_user",
        hashed_password=get_password_hash(uuid.uuid4().hex),
        role="user",
    )


async def resolve_import_user(db: AsyncSession, owner_id: Optional[str]) -> User:
    """Return the owner, else any existing user, else a freshly created local default user."""
    query = select(User).where(User.id == owner_id) if owner_id else select(User).limit(1)
    res = await db.execute(query)
    user = res.scalars().first()
    if user:
        return user

    user = build_local_default_user()
    db.add(user)
    await db.flush()
    return user
