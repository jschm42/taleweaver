import json
import logging
import os
import re
import time
import zipfile
from copy import deepcopy
from typing import Any, Optional

from packaging.version import InvalidVersion
from packaging.version import parse as parse_semver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.adventure_format import (
    CURRENT_VERSION,
    PLAYABLE_MIN_VERSION,
    is_deprecated_version,
    is_version_below,
)
from backend.core.adventure_identity import manifest_origin_id
from backend.core.config import settings
from backend.engine.adventures.adventure_importer import AdventureTemplateImporter
from backend.engine.rules.sequence_walkthrough import legacy_main_sequence
from backend.models.adventure_template import AdventureTemplate
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState

logger = logging.getLogger(__name__)

# Cache scanned file entries for 5 seconds to prevent repeated directory walks during batch requests
_SCAN_CACHE: dict[str, Any] = {"entries": [], "timestamp": 0.0}
_CACHE_TTL_SECONDS = 5.0
# data/adventures also holds the per-template asset store (library/) and session data with
# thousands of folders; walking them made every library load take one to several seconds.
_SKIPPED_DIR_NAMES = frozenset(
    {"library", "sessions", "images", "assets", "thumbnails", "__pycache__"}
)
_ASSET_DIR_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
_MAX_SCAN_DEPTH = 3
# Parsed entry per file path, keyed by (mtime_ns, size): unchanged archives are never reopened.
_FILE_CACHE: dict[str, tuple[tuple[int, int], Optional[dict[str, Any]]]] = {}
_ADVENTURE_FILE_EXTENSIONS = (".adz", ".adv")


def _parse_version_tuple(v: Optional[str]) -> tuple[int, ...]:
    """Fallback version parser that extracts numbers into a tuple."""
    if not v:
        return (0,)
    parts = re.findall(r"\d+", str(v))
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def _format_version_newer(file_format: Optional[str], db_format: Optional[str]) -> bool:
    """True when both manifest format versions parse and the file's is strictly newer."""
    if not (file_format and db_format):
        return False
    try:
        return parse_semver(str(file_format).strip()) > parse_semver(str(db_format).strip())
    except InvalidVersion:
        logger.debug("Unparseable format versions: %r vs %r", file_format, db_format)
        return False


def _version_greater(file_version: str, db_version: str) -> bool:
    """Semantic comparison, falling back to numeric tuples for non-PEP 440 versions."""
    try:
        return parse_semver(file_version) > parse_semver(db_version)
    except InvalidVersion:
        return _parse_version_tuple(file_version) > _parse_version_tuple(db_version)


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
    if _format_version_newer(file_format_version, db_format_version):
        return True
    clean_file_ver = str(file_version or "").strip()
    if not clean_file_ver:
        return False
    clean_db_ver = str(db_version or "").strip()
    if not clean_db_ver:
        return True
    return _version_greater(clean_file_ver, clean_db_ver)


def _adventure_directories() -> list[str]:
    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    candidate_dirs = [
        "adventures",
        os.path.join(repo_root, "adventures"),
        os.path.join(settings.DATA_DIR, "presets", "adventures"),
        os.path.join(settings.DATA_DIR, "adventures"),
    ]
    directories: list[str] = []
    for candidate in candidate_dirs:
        norm = os.path.abspath(candidate)
        if norm not in directories and os.path.exists(norm):
            directories.append(norm)
    return directories


def _read_manifest(file_path: str, ext: str) -> Optional[dict[str, Any]]:
    """Loads the adventure manifest from an .adv file or the adventure.adv inside an .adz.

    The archive is opened from disk so only its directory and the manifest member are read,
    not the bundled images.
    """
    if ext != ".adz":
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    with zipfile.ZipFile(file_path, "r") as zf:
        if "adventure.adv" not in zf.namelist():
            return None
        return json.loads(zf.read("adventure.adv").decode("utf-8"))


def _scan_entry(
    file_path: str, filename: str, manifest: dict[str, Any]
) -> Optional[dict[str, Any]]:
    is_session = manifest.get("type") == "SESSION_BUNDLE"
    adv_data = (
        manifest.get("adventure", {}) if is_session else (manifest.get("adventure") or manifest)
    )
    title = adv_data.get("title") or manifest.get("title")
    if not title or not isinstance(title, str):
        return None

    origin_id = manifest_origin_id(manifest)
    version = adv_data.get("version") or manifest.get("version")
    sequences = adv_data.get("sequences") or manifest.get("sequences") or []
    return {
        "file_path": file_path,
        "filename": filename,
        "stem": os.path.splitext(filename)[0],
        "title": title.strip(),
        "origin_id": origin_id,
        "version": str(version).strip() if version else None,
        "format_version": str(manifest.get("version") or "").strip(),
        "sequences": sequences,
        "has_sequences": isinstance(sequences, list) and len(sequences) > 0,
    }


def _parse_file(file_path: str, filename: str, ext: str) -> Optional[dict[str, Any]]:
    try:
        manifest = _read_manifest(file_path, ext)
        return _scan_entry(file_path, filename, manifest) if manifest else None
    except Exception as exc:
        logger.debug("Could not parse adventure candidate %s: %s", file_path, exc)
        return None


def _scan_file(root: str, filename: str) -> Optional[dict[str, Any]]:
    """Scan entry for one adventure file, re-parsed only when its mtime or size changed."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ADVENTURE_FILE_EXTENSIONS:
        return None
    file_path = os.path.abspath(os.path.join(root, filename))
    try:
        stat = os.stat(file_path)
    except OSError:
        return None
    signature = (stat.st_mtime_ns, stat.st_size)
    cached = _FILE_CACHE.get(file_path)
    if cached and cached[0] == signature:
        return cached[1]
    entry = _parse_file(file_path, filename, ext)
    _FILE_CACHE[file_path] = (signature, entry)
    return entry


def _is_scannable_dir(name: str) -> bool:
    """Skips session data and per-template asset folders, which never hold adventure files."""
    return name.lower() not in _SKIPPED_DIR_NAMES and not _ASSET_DIR_PATTERN.match(name)


def _walk_adventure_dirs(base_dir: str):
    """os.walk limited to _MAX_SCAN_DEPTH levels below base_dir, pruning asset/session folders."""
    for root, dirs, files in os.walk(base_dir):
        depth = os.path.relpath(root, base_dir).count(os.sep) + (root != base_dir)
        dirs[:] = [] if depth >= _MAX_SCAN_DEPTH else [d for d in dirs if _is_scannable_dir(d)]
        yield root, files


def scan_available_adventure_files(force_refresh: bool = False) -> list[dict[str, Any]]:
    """Scans the /adventures and /presets directories for .adz and .adv files."""
    now = time.time()
    cached = _SCAN_CACHE["entries"]
    if not force_refresh and cached and (now - _SCAN_CACHE["timestamp"]) < _CACHE_TTL_SECONDS:
        return cached

    scanned: list[dict[str, Any]] = []
    for base_dir in _adventure_directories():
        for root, files in _walk_adventure_dirs(base_dir):
            entries = (_scan_file(root, filename) for filename in files)
            scanned.extend(entry for entry in entries if entry)

    _SCAN_CACHE["entries"] = scanned
    _SCAN_CACHE["timestamp"] = now
    return scanned


def _normalize_string(s: Optional[str]) -> str:
    """Normalizes string for fuzzy title/stem comparison."""
    if not s:
        return ""
    cleaned = re.sub(r"[_\-\s]+", " ", s.lower()).strip()
    return cleaned


def _matches_by_name(t_title_norm: str, f: dict[str, Any]) -> bool:
    """Legacy fallback: normalized title or filename stem equals the template title."""
    if not t_title_norm:
        return False
    names = (_normalize_string(f.get("title")), _normalize_string(f.get("stem")))
    return t_title_norm in names


def find_matching_file_for_template(
    template: AdventureTemplate,
    available_files: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Matches an AdventureTemplate to the most relevant file in /adventures.

    An origin_id match is authoritative. Title/stem matching is only a fallback when one side
    has no origin_id yet; two different origin_ids are always different adventures.
    """
    t_origin = str(template.origin_id or "").strip()
    candidates = [f for f in available_files if t_origin and f.get("origin_id") == t_origin]
    if not candidates:
        t_title_norm = _normalize_string(template.title)
        candidates = [
            f
            for f in available_files
            if not (t_origin and f.get("origin_id")) and _matches_by_name(t_title_norm, f)
        ]
    if not candidates:
        return None

    # Pick candidate with newest version or sequence support
    best = candidates[0]
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
    Checks if a template was imported from an ADV format older than PLAYABLE_MIN_VERSION
    or lacks required sequences for imported adventures.
    """
    manifest = template.original_manifest or {}
    manifest_version = manifest.get("format_version") or manifest.get("version")

    # Below the playable minimum the adventure must be migrated first; versions between that
    # and DEPRECATED_BELOW_VERSION stay playable and are only flagged as deprecated.
    if is_version_below(manifest_version, PLAYABLE_MIN_VERSION):
        return True

    # Imported (has a manifest) but lacks sequences; origin_id is set on every template now.
    is_imported = bool(template.original_manifest)
    return is_imported and not template.sequences


def is_legacy_session(
    session: Optional[GameSession] = None,
    state: Optional[SessionState] = None,
    template: Optional[AdventureTemplate] = None,
) -> bool:
    """
    Checks if a game session was created with an adventure format older than PLAYABLE_MIN_VERSION
    or is linked to a legacy template without sequence support.
    """
    if template and is_legacy_template(template):
        return True

    if not state and session and getattr(session, "state", None):
        state = session.state

    if state:
        from backend.api.routes.adventures.logic import AdventureLogic

        snapshot = AdventureLogic.extract_manifest_snapshot(state)
        manifest = snapshot.get("original_manifest") or {}
        manifest_version = manifest.get("format_version") or manifest.get("version")
        if is_version_below(manifest_version, PLAYABLE_MIN_VERSION):
            return True

        # Check if imported but lacks sequences
        is_imported = bool(manifest or (template and template.original_manifest))
        has_sequences = bool(
            (manifest.get("sequences") and len(manifest["sequences"]) > 0)
            or (template and template.sequences and len(template.sequences) > 0)
            or getattr(state, "active_sequence_id", None)
        )
        if is_imported and not has_sequences:
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
        "is_deprecated": is_deprecated_version(db_format_version),
        "can_start": can_start,
    }


async def _delete_replaced_template(db: AsyncSession, template_id: str) -> None:
    """Deletes the outdated template if the import did not already overwrite it."""
    still_exists = await db.execute(
        select(AdventureTemplate.id).where(AdventureTemplate.id == template_id)
    )
    if not still_exists.scalars().first():
        return
    logger.info("Removing replaced adventure template %s after update.", template_id)
    await AdventureTemplateImporter.delete_template_for_overwrite(db, template_id)


async def update_single_adventure(
    db: AsyncSession,
    template_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Updates an individual adventure template from its matching file in /adventures.

    NOTE: Existing game sessions are NOT updated. Their narrative snapshot and state
    remain preserved as-is.
    """
    from sqlalchemy import update

    from backend.models.game_session import GameSession
    from backend.models.session_state import SessionState

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

    # Fetch the newly imported template (by stable ID when the file carries one)
    identity_clause = (
        AdventureTemplate.origin_id == matching["origin_id"]
        if matching.get("origin_id")
        else AdventureTemplate.title == matching["title"]
    )
    updated_res = await db.execute(
        select(AdventureTemplate)
        .where(AdventureTemplate.owner_id == user_id, identity_clause)
        .order_by(AdventureTemplate.created_at.desc())
    )
    updated_template = updated_res.scalars().first()

    # The importer only overwrites origin_id/exact-title matches; a legacy template matched by
    # filename stem (e.g. a renamed title) would otherwise remain as a duplicate.
    if updated_template and updated_template.id != template_id:
        await _delete_replaced_template(db, template_id)

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


async def migrate_single_adventure(
    db: AsyncSession,
    template_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Migrates a legacy adventure template to the current sequence-supported format.

    Converts the legacy walkthrough into Sequence 1 ('Main Journey') and bumps format version
    to CURRENT_VERSION so that the adventure is fully compatible and playable.
    """
    result = await db.execute(
        select(AdventureTemplate).where(
            AdventureTemplate.id == template_id,
            AdventureTemplate.owner_id == user_id,
        )
    )
    template = result.scalars().first()
    if not template:
        raise ValueError("Adventure template not found or unauthorized.")

    manifest = template.original_manifest or {}
    adv_manifest = manifest.get("adventure") if isinstance(manifest.get("adventure"), dict) else {}

    if not template.sequences:
        template.sequences = [
            legacy_main_sequence(
                adv_manifest.get("walkthrough") or manifest.get("walkthrough") or "",
                template.plot or adv_manifest.get("plot"),
                template.completed_condition or adv_manifest.get("completed_condition"),
            )
        ]

    # Synchronize manifest format version and sequences
    if template.original_manifest and isinstance(template.original_manifest, dict):
        new_manifest = deepcopy(template.original_manifest)
        new_manifest["format_version"] = CURRENT_VERSION
        new_manifest["version"] = new_manifest.get("version") or CURRENT_VERSION
        new_manifest["sequences"] = template.sequences
        if "adventure" in new_manifest and isinstance(new_manifest["adventure"], dict):
            new_adv = dict(new_manifest["adventure"])
            new_adv["sequences"] = template.sequences
            new_manifest["adventure"] = new_adv
        template.original_manifest = new_manifest
    else:
        template.original_manifest = {
            "format_version": CURRENT_VERSION,
            "version": CURRENT_VERSION,
            "title": template.title,
            "sequences": template.sequences,
        }

    template.version = CURRENT_VERSION

    # If the template has no world entities in the database yet, populate them from original_manifest
    from backend.models.world_entity import WorldScene

    scene_check = await db.execute(
        select(WorldScene.id)
        .where(
            WorldScene.template_id == template.id,
            WorldScene.session_id.is_(None),
        )
        .limit(1)
    )
    if not scene_check.scalars().first() and template.original_manifest:
        manifest_data = template.original_manifest
        if isinstance(manifest_data, dict) and (
            manifest_data.get("scenes") or manifest_data.get("npcs") or manifest_data.get("objects")
        ):
            from backend.engine.world.world_generator import WorldGenerator
            from backend.models.user import User

            user_res = await db.execute(select(User).where(User.id == user_id))
            user = user_res.scalars().first()
            await WorldGenerator.apply_manifest(
                db=db,
                template_id=template.id,
                manifest_dict=manifest_data,
                user=user,
            )
            template.is_ready = True
            template.creation_status = "Ready"

    await db.commit()
    await db.refresh(template)

    return {
        "success": True,
        "status": "success",
        "message": f"Adventure '{template.title}' successfully migrated to the latest format.",
        "template_id": template.id,
        "has_sequences": True,
        "is_legacy_format": False,
        "is_deprecated": False,
        "can_start": True,
    }
