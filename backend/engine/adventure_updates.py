import io
import json
import logging
import os
import re
import time
import zipfile
from typing import Any, Optional

from packaging.version import InvalidVersion
from packaging.version import parse as parse_semver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.adventure_format import CURRENT_VERSION
from backend.core.config import settings
from backend.engine.adventure_importer import AdventureTemplateImporter
from backend.models.adventure_template import AdventureTemplate

logger = logging.getLogger(__name__)

# Cache scanned file entries for 5 seconds to prevent repeated disk/zip operations during batch requests
_SCANNED_FILES_CACHE: list[dict[str, Any]] = []
_SCANNED_FILES_TIMESTAMP: float = 0.0
_CACHE_TTL_SECONDS = 5.0


def _parse_version_tuple(v: Optional[str]) -> tuple[int, ...]:
    """Fallback version parser that extracts numbers into a tuple."""
    if not v:
        return (0,)
    parts = re.findall(r"\d+", str(v))
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def is_version_newer(
    file_version: Optional[str] = None,
    db_version: Optional[str] = None,
    file_has_sequences: bool = False,
    db_has_sequences: bool = False,
    file_format_version: Optional[str] = None,
    db_format_version: Optional[str] = None,
) -> bool:
    """Compares file version and format against database version.

    Returns True if:
    - The file has sequences while the DB template does not (upgrade to new format)
    - The file format version is strictly newer than the DB format version
    - The file has a version string and the DB template has none
    - The file version is strictly greater than the DB version
    """
    if file_has_sequences and not db_has_sequences:
        return True

    # If the file manifest format version is higher than DB manifest format version
    if file_format_version and db_format_version:
        try:
            pv_file_fmt = parse_semver(str(file_format_version).strip())
            pv_db_fmt = parse_semver(str(db_format_version).strip())
            if pv_file_fmt > pv_db_fmt:
                return True
        except Exception:
            pass

    if not file_version or not str(file_version).strip():
        return False

    if not db_version or not str(db_version).strip():
        return True

    clean_file_ver = str(file_version).strip()
    clean_db_ver = str(db_version).strip()

    try:
        pv_file = parse_semver(clean_file_ver)
        pv_db = parse_semver(clean_db_ver)
        if pv_file > pv_db:
            return True
        if pv_file == pv_db and file_has_sequences and not db_has_sequences:
            return True
        return False
    except InvalidVersion:
        # Fall back to numeric tuple comparison
        vt_file = _parse_version_tuple(clean_file_ver)
        vt_db = _parse_version_tuple(clean_db_ver)
        if vt_file > vt_db:
            return True
        if vt_file == vt_db and file_has_sequences and not db_has_sequences:
            return True
        return False


def scan_available_adventure_files(force_refresh: bool = False) -> list[dict[str, Any]]:
    """Recursively scans /adventures and /presets directories for .adz and .adv files."""
    global _SCANNED_FILES_CACHE, _SCANNED_FILES_TIMESTAMP

    now = time.time()
    if not force_refresh and (now - _SCANNED_FILES_TIMESTAMP) < _CACHE_TTL_SECONDS and _SCANNED_FILES_CACHE:
        return _SCANNED_FILES_CACHE

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidate_dirs = [
        "adventures",
        os.path.join(repo_root, "adventures"),
        os.path.join(settings.DATA_DIR, "presets", "adventures"),
        os.path.join(settings.DATA_DIR, "adventures"),
    ]
    seen_dirs = set()
    directories = []
    for d in candidate_dirs:
        norm = os.path.abspath(d)
        if norm not in seen_dirs and os.path.exists(norm):
            seen_dirs.add(norm)
            directories.append(norm)

    scanned: list[dict[str, Any]] = []

    for base_dir in directories:
        for root, _, files in os.walk(base_dir):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in (".adz", ".adv"):
                    continue

                file_path = os.path.abspath(os.path.join(root, filename))
                try:
                    if ext == ".adz":
                        with open(file_path, "rb") as f:
                            with zipfile.ZipFile(io.BytesIO(f.read()), "r") as zf:
                                if "adventure.adv" not in zf.namelist():
                                    continue
                                manifest = json.loads(zf.read("adventure.adv").decode("utf-8"))
                    else:
                        with open(file_path, "r", encoding="utf-8") as f:
                            manifest = json.load(f)

                    is_session = manifest.get("type") == "SESSION_BUNDLE"
                    adv_data = manifest.get("adventure", {}) if is_session else (manifest.get("adventure") or manifest)

                    title = adv_data.get("title") or manifest.get("title")
                    if not title or not isinstance(title, str):
                        continue

                    origin_id = adv_data.get("origin_id") or manifest.get("origin_id")
                    version = adv_data.get("version") or manifest.get("version")
                    format_version = str(manifest.get("version") or "").strip()
                    sequences = adv_data.get("sequences") or manifest.get("sequences") or []
                    has_sequences = isinstance(sequences, list) and len(sequences) > 0

                    scanned.append({
                        "file_path": file_path,
                        "filename": filename,
                        "stem": os.path.splitext(filename)[0],
                        "title": title.strip(),
                        "origin_id": str(origin_id).strip() if origin_id else None,
                        "version": str(version).strip() if version else None,
                        "format_version": format_version,
                        "sequences": sequences,
                        "has_sequences": has_sequences,
                    })
                except Exception as exc:
                    logger.debug("Could not parse adventure candidate %s: %s", file_path, exc)

    _SCANNED_FILES_CACHE = scanned
    _SCANNED_FILES_TIMESTAMP = now
    return scanned


def _normalize_string(s: Optional[str]) -> str:
    """Normalizes string for fuzzy title/stem comparison."""
    if not s:
        return ""
    cleaned = re.sub(r"[_\-\s]+", " ", s.lower()).strip()
    return cleaned


def find_matching_file_for_template(
    template: AdventureTemplate,
    available_files: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Matches an AdventureTemplate to the most relevant file in /adventures."""
    t_origin = str(template.origin_id or "").strip()
    t_title_norm = _normalize_string(template.title)

    candidates: list[dict[str, Any]] = []

    for f in available_files:
        # 1. Exact origin_id match (highest priority)
        if t_origin and f.get("origin_id") and t_origin == f.get("origin_id"):
            candidates.append(f)
            continue

        # 2. Normalized title match
        f_title_norm = _normalize_string(f.get("title"))
        if t_title_norm and f_title_norm and t_title_norm == f_title_norm:
            candidates.append(f)
            continue

        # 3. Normalized filename stem match
        f_stem_norm = _normalize_string(f.get("stem"))
        if t_title_norm and f_stem_norm and t_title_norm == f_stem_norm:
            candidates.append(f)
            continue

    if not candidates:
        return None

    # Pick candidate with newest version or sequence support
    best = candidates[0]
    db_has_seq = bool(template.sequences and len(template.sequences) > 0)
    db_fmt_ver = (template.original_manifest or {}).get("version")
    for cand in candidates[1:]:
        if is_version_newer(
            file_version=cand.get("version"),
            db_version=best.get("version"),
            file_has_sequences=cand.get("has_sequences", False),
            db_has_sequences=best.get("has_sequences", False),
            file_format_version=cand.get("format_version"),
            db_format_version=best.get("format_version"),
        ):
            best = cand

    return best


def is_legacy_template(template: AdventureTemplate) -> bool:
    """
    Checks if a template was previously imported from an older ADV format version (< CURRENT_VERSION)
    or lacks required sequences for imported adventures.
    """
    manifest = template.original_manifest or {}
    manifest_version = manifest.get("format_version") or manifest.get("version")

    if manifest_version:
        try:
            if parse_semver(str(manifest_version)) < parse_semver(CURRENT_VERSION):
                return True
        except Exception:
            if str(manifest_version) < CURRENT_VERSION:
                return True

    # If it was imported (has origin_id or manifest) and lacks sequences:
    if (template.origin_id or template.original_manifest) and not (template.sequences and len(template.sequences) > 0):
        return True

    return False


def check_template_update(
    template: AdventureTemplate,
    available_files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculates update status and sequence format status for an AdventureTemplate."""
    db_has_sequences = bool(template.sequences and len(template.sequences) > 0)
    is_legacy = is_legacy_template(template)
    can_start = not is_legacy

    matching_file = find_matching_file_for_template(template, available_files)

    has_update = False
    available_version: Optional[str] = None
    update_file_path: Optional[str] = None

    manifest = template.original_manifest or {}
    db_format_version = manifest.get("format_version") or manifest.get("version")

    if matching_file:
        file_version = matching_file.get("version")
        file_has_sequences = matching_file.get("has_sequences", False)
        file_format_version = matching_file.get("format_version")

        has_update = is_version_newer(
            file_version=file_version,
            db_version=template.version,
            file_has_sequences=file_has_sequences,
            db_has_sequences=db_has_sequences,
            file_format_version=file_format_version,
            db_format_version=db_format_version,
        )

        if has_update:
            available_version = file_version or file_format_version
            update_file_path = matching_file.get("file_path")

    return {
        "has_update": has_update,
        "available_version": available_version,
        "update_file_path": update_file_path,
        "has_sequences": db_has_sequences,
        "is_legacy_format": is_legacy,
        "can_start": can_start,
    }


async def update_single_adventure(
    db: AsyncSession,
    template_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Updates an individual adventure template from its matching file in /adventures.
    
    NOTE: Existing game sessions are NOT updated. Their narrative snapshot and state
    remain preserved as-is.
    """
    from backend.models.game_session import GameSession
    from backend.models.session_state import SessionState
    from sqlalchemy import update

    result = await db.execute(
        select(AdventureTemplate).where(
            AdventureTemplate.id == template_id,
            AdventureTemplate.owner_id == user_id,
        )
    )
    template = result.scalars().first()
    if not template:
        raise ValueError("Adventure template not found or unauthorized.")

    files = scan_available_adventure_files(force_refresh=True)
    matching = find_matching_file_for_template(template, files)
    if not matching:
        raise ValueError(f"No update file found in /adventures for '{template.title}'.")

    file_path = matching["file_path"]

    # Capture linked sessions so they remain preserved and linked to the updated template
    session_res = await db.execute(
        select(GameSession.id).where(GameSession.template_id == template_id)
    )
    linked_session_ids = session_res.scalars().all()

    # Re-import template with overwrite=True; allow_session=False ensures sessions are never touched/imported
    success = await AdventureTemplateImporter.import_file(
        db=db,
        file_path=file_path,
        owner_id=user_id,
        allow_session=False,
        overwrite=True,
    )

    if not success:
        raise RuntimeError(f"Failed to import update from {file_path}")

    # Fetch newly created / updated template to confirm
    updated_res = await db.execute(
        select(AdventureTemplate).where(
            AdventureTemplate.owner_id == user_id,
            AdventureTemplate.title == matching["title"],
        ).order_by(AdventureTemplate.created_at.desc())
    )
    updated_template = updated_res.scalars().first()

    # Re-link existing session records to the new template without modifying their state
    if linked_session_ids and updated_template:
        await db.execute(
            update(GameSession)
            .where(GameSession.id.in_(linked_session_ids))
            .values(template_id=updated_template.id)
        )
        await db.execute(
            update(SessionState)
            .where(SessionState.session_id.in_(linked_session_ids))
            .values(template_id=updated_template.id)
        )
        await db.commit()

    return {
        "status": "success",
        "message": f"Successfully updated '{matching['title']}' to version {matching.get('version') or 'latest'}.",
        "template_id": updated_template.id if updated_template else template_id,
        "new_version": matching.get("version"),
    }


async def update_all_adventures(
    db: AsyncSession,
    user_id: str,
) -> dict[str, Any]:
    """Updates all adventure templates for the user that have newer versions in /adventures."""
    result = await db.execute(
        select(AdventureTemplate).where(AdventureTemplate.owner_id == user_id)
    )
    templates = result.scalars().all()
    if not templates:
        return {"status": "success", "updated_count": 0, "updated_titles": []}

    files = scan_available_adventure_files(force_refresh=True)

    updated_titles: list[str] = []
    errors: list[str] = []

    for template in templates:
        status = check_template_update(template, files)
        if status["has_update"] and status["update_file_path"]:
            try:
                res = await update_single_adventure(
                    db=db,
                    template_id=template.id,
                    user_id=user_id,
                )
                if res.get("status") == "success":
                    updated_titles.append(template.title)
                else:
                    errors.append(f"Failed to update {template.title}")
            except Exception as e:
                logger.error("Error updating template %s: %s", template.id, e)
                errors.append(f"{template.title}: {str(e)}")

    return {
        "status": "success",
        "updated_count": len(updated_titles),
        "updated_titles": updated_titles,
        "errors": errors,
    }
