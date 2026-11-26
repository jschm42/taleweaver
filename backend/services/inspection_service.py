"""Shared read-only inspection helpers for adventures, database health, and sessions."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.api.routes.adventures.manifest_export import backfill_manifest_metadata
from backend.core.config import PROJECT_ROOT, settings
from backend.engine.adventures.adventure_exporter import AdventureExporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.character import Character
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.mcp_token import McpToken
from backend.models.session_checkpoint import SessionCheckpoint
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.services.session_inspection_service import (
    check_session_integrity,
    get_session_chat,
    get_session_checkpoints,
    get_session_state,
    list_sessions,
    resolve_game_session,
)

__all__ = [
    "check_session_integrity",
    "export_adventure_manifest",
    "get_adventure_details",
    "get_adventure_summary",
    "get_db_status",
    "get_session_chat",
    "get_session_checkpoints",
    "get_session_state",
    "list_adventures",
    "list_disk_adventures",
    "list_sessions",
    "resolve_adventure_template",
    "resolve_game_session",
]

_COMPACT_DROPPED_KEYS = frozenset(
    {
        "original_manifest",
        "image_url",
        "thumbnail_url",
        "created_at",
        "updated_at",
        "template_id",
        "session_id",
        "image_prompt",
        "cover_image_url",
    }
)
_SKIP_DISK_JSON = frozenset(
    {"package.json", "tsconfig.json", "version.json", "scratch_manifest.json"}
)
_ADVENTURE_DETAIL_SECTIONS = frozenset(
    {
        "adventure",
        "protagonist",
        "scenes",
        "npcs",
        "objects",
        "exits",
        "quests",
        "awards",
        "scripts",
        "cutscenes",
        "audio_tracks",
        "sections",
    }
)


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def _dir_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    total_bytes = 0
    file_count = 0
    for root, _, files in os.walk(path):
        for fname in files:
            try:
                total_bytes += (Path(root) / fname).stat().st_size
                file_count += 1
            except OSError:
                continue
    return total_bytes, file_count


def _compact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        pairs = (
            (k, _compact_payload(v)) for k, v in value.items() if k not in _COMPACT_DROPPED_KEYS
        )
        return {k: v for k, v in pairs if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [_compact_payload(v) for v in value]
    return value


def _resolve_db_file(db_url: str) -> Optional[Path]:
    if ":///" in db_url:
        raw_path = db_url.split(":///", 1)[1]
        candidate = Path(raw_path) if Path(raw_path).is_absolute() else PROJECT_ROOT / raw_path
        if candidate.exists():
            return candidate
    fallback = PROJECT_ROOT / settings.DATA_DIR / "taleweaver.db"
    return fallback if fallback.exists() else None


async def _collect_table_counts(db: AsyncSession) -> dict[str, Any]:
    tables = (
        ("users", User),
        ("adventure_templates", AdventureTemplate),
        ("game_sessions", GameSession),
        ("session_states", SessionState),
        ("avatars", Avatar),
        ("characters", Character),
        ("chat_messages", ChatMessage),
        ("session_checkpoints", SessionCheckpoint),
        ("world_scenes", WorldScene),
        ("world_entities", WorldEntity),
        ("world_exits", WorldExit),
        ("mcp_tokens", McpToken),
    )
    counts: dict[str, Any] = {}
    for name, model in tables:
        try:
            counts[name] = int(
                (await db.execute(select(func.count()).select_from(model))).scalar_one()
            )
        except Exception as exc:
            counts[name] = f"error ({exc})"
    return counts


async def _collect_sqlite_metrics(db: AsyncSession) -> tuple[str, int]:
    try:
        journal_mode = str((await db.execute(text("PRAGMA journal_mode;"))).scalar_one())
        page_count = int((await db.execute(text("PRAGMA page_count;"))).scalar_one())
        page_size = int((await db.execute(text("PRAGMA page_size;"))).scalar_one())
        return journal_mode, page_count * page_size
    except Exception:
        return "unknown", 0


async def get_db_status(db: AsyncSession) -> dict[str, Any]:
    """Return SQLite metrics, table record counts, and ``data/`` storage breakdown."""
    counts = await _collect_table_counts(db)
    journal_mode, calc_size = await _collect_sqlite_metrics(db)

    db_path = _resolve_db_file(settings.DATABASE_URL)
    files_info: dict[str, Any] = {}
    if db_path is not None:
        size = db_path.stat().st_size
        files_info["database_file"] = {
            "path": str(db_path),
            "size_bytes": size,
            "size_formatted": _format_bytes(size),
        }

    data_dir = PROJECT_ROOT / settings.DATA_DIR
    storage_usage: dict[str, Any] = {}
    for sub in (
        "adventures/library",
        "adventures/sessions",
        "characters",
        "audio",
        "logs",
        "presets/adventures",
        "imports/adventures",
    ):
        target = data_dir / sub
        if target.exists():
            num_bytes, num_files = _dir_size(target)
            storage_usage[sub] = {
                "bytes": num_bytes,
                "formatted": _format_bytes(num_bytes),
                "count": num_files,
            }

    return {
        "journal_mode": journal_mode,
        "calculated_size_bytes": calc_size,
        "calculated_size_formatted": _format_bytes(calc_size),
        "files": files_info,
        "table_counts": counts,
        "storage_usage": storage_usage,
    }


async def list_adventures(
    db: AsyncSession, *, owner_id: Optional[str] = None, limit: int = 100
) -> list[dict[str, Any]]:
    """List adventure templates, optionally scoped to one owner."""
    stmt = select(AdventureTemplate).order_by(desc(AdventureTemplate.created_at)).limit(limit)
    if owner_id is not None:
        stmt = stmt.where(AdventureTemplate.owner_id == owner_id)
    templates = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "version": t.version,
            "language": t.language,
            "origin_id": t.origin_id,
            "owner_id": t.owner_id,
            "is_ready": bool(t.is_ready),
            "creation_status": t.creation_status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in templates
    ]


def _scan_disk_files() -> list[Path]:
    search_dirs = (
        PROJECT_ROOT / "adventures",
        PROJECT_ROOT / settings.DATA_DIR / "imports" / "adventures",
        PROJECT_ROOT / settings.DATA_DIR / "presets" / "adventures",
    )
    disk_files: list[Path] = []
    for folder in search_dirs:
        if not folder.exists():
            continue
        for ext in ("*.adv", "*.adz", "*.json"):
            disk_files.extend(
                candidate
                for candidate in folder.rglob(ext)
                if candidate.name not in _SKIP_DISK_JSON
            )
    return sorted(disk_files)


async def list_disk_adventures(
    db: AsyncSession, *, owner_id: Optional[str] = None
) -> list[dict[str, Any]]:
    """Scan local adventure folders for ``.adv``, ``.adz``, and manifest JSON files."""
    stmt = select(AdventureTemplate)
    if owner_id is not None:
        stmt = stmt.where(AdventureTemplate.owner_id == owner_id)
    templates = (await db.execute(stmt)).scalars().all()
    by_title = {t.title.lower(): t for t in templates if t.title}
    by_origin = {t.origin_id: t for t in templates if t.origin_id}
    by_id = {t.id: t for t in templates if t.id}

    records: list[dict[str, Any]] = []
    for path in _scan_disk_files():
        stem = path.stem.lower()
        matched = by_title.get(stem) or by_origin.get(stem) or by_id.get(path.stem)
        try:
            rel_path = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
        except ValueError:
            rel_path = str(path)
        size = path.stat().st_size
        records.append(
            {
                "path": rel_path,
                "filename": path.name,
                "size_bytes": size,
                "size_formatted": _format_bytes(size),
                "imported": matched is not None,
                "template_id": matched.id if matched else None,
            }
        )
    return records


async def resolve_adventure_template(
    db: AsyncSession, identifier: str, *, owner_id: Optional[str] = None
) -> AdventureTemplate:
    """Resolve an adventure template by ID, ``origin_id``, or unique title substring."""
    ident = identifier.strip()
    if not ident:
        raise ValueError("Adventure identifier must not be empty.")

    exact_stmt = select(AdventureTemplate).where(
        (AdventureTemplate.id == ident) | (AdventureTemplate.origin_id == ident)
    )
    if owner_id is not None:
        exact_stmt = exact_stmt.where(AdventureTemplate.owner_id == owner_id)
    exact_matches = list((await db.execute(exact_stmt)).scalars().all())
    if len(exact_matches) == 1:
        return exact_matches[0]

    like_stmt = select(AdventureTemplate).where(AdventureTemplate.title.ilike(f"%{ident}%"))
    if owner_id is not None:
        like_stmt = like_stmt.where(AdventureTemplate.owner_id == owner_id)
    matches = list((await db.execute(like_stmt)).scalars().all())
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise LookupError(f"No adventure matches '{ident}'.")
    options = ", ".join(f"{m.id} ({m.title})" for m in matches[:10])
    raise ValueError(f"'{ident}' matches multiple adventures; specify the ID: {options}")


async def get_adventure_summary(db: AsyncSession, template_id: str) -> dict[str, Any]:
    """Return a compact ID index of an adventure's scenes, exits, entities, and story blocks."""
    payload = (await _build_adventure_editor_assets(template_id, db)).model_dump()
    adventure = payload.get("adventure", {})
    return {
        "adventure": {
            "id": adventure.get("id"),
            "title": adventure.get("title"),
            "version": adventure.get("version"),
            "language": adventure.get("language"),
            "start_scene_id": adventure.get("start_scene_id"),
        },
        "init_script_lines": len(str(adventure.get("init_script") or "").splitlines()),
        "sections": [
            {"id": s.get("id"), "label": s.get("label"), "status": s.get("status")}
            for s in (adventure.get("world_sections") or [])
            if isinstance(s, dict)
        ],
        "scripts": [
            f"{s.get('id')} ({s.get('trigger')})" for s in (adventure.get("scripts") or [])
        ],
        "quests": [q.get("id") for q in (adventure.get("quests") or [])],
        "cutscenes": [c.get("id") for c in (adventure.get("cutscenes") or [])],
        "audio_tracks": [t.get("id") for t in (adventure.get("audio_tracks") or [])],
        "scenes": {s.get("id"): s.get("label") for s in payload.get("scenes", [])},
        "exits": [
            {
                "id": e.get("id"),
                "route": f"{e.get('from_scene_id')}->{e.get('to_scene_id')}",
                "exit_type": e.get("exit_type"),
                "is_locked": bool(e.get("is_locked")),
                "label": e.get("label"),
            }
            for e in payload.get("exits", [])
        ],
        "npcs": {
            n.get("id"): f"{n.get('name')} @ {n.get('current_scene_id')}"
            for n in payload.get("npcs", [])
        },
        "objects": {
            o.get(
                "id"
            ): f"{o.get('name')} [{o.get('item_type') or 'OBJECT'}] @ {o.get('current_scene_id')}"
            for o in payload.get("objects", [])
        },
    }


def _scene_slice(data: dict[str, Any], scene_id: str) -> dict[str, Any]:
    exits = [
        e
        for e in data.get("exits", [])
        if scene_id in (e.get("from_scene_id"), e.get("to_scene_id"))
    ]
    near = (
        {scene_id} | {e.get("from_scene_id") for e in exits} | {e.get("to_scene_id") for e in exits}
    )
    in_scene = [
        ent
        for ent in data.get("npcs", []) + data.get("objects", [])
        if ent.get("current_scene_id") == scene_id
    ]
    scene = next((s for s in data.get("scenes", []) if s.get("id") == scene_id), None)
    if scene is None:
        raise LookupError(f"Scene '{scene_id}' not found in adventure.")
    return {
        "adventure": {k: data["adventure"].get(k) for k in ("id", "title", "start_scene_id")},
        "scene": scene,
        "neighbour_scenes": [
            {"id": s.get("id"), "label": s.get("label")}
            for s in data.get("scenes", [])
            if s.get("id") in near - {scene_id}
        ],
        "exits": exits,
        "entities": in_scene,
    }


def _section_slice(data: dict[str, Any], section: str) -> dict[str, Any]:
    if section not in _ADVENTURE_DETAIL_SECTIONS:
        allowed = ", ".join(sorted(_ADVENTURE_DETAIL_SECTIONS))
        raise ValueError(f"Unknown section '{section}'. Allowed: {allowed}")
    adventure = data.get("adventure", {})
    header = {"id": adventure.get("id"), "title": adventure.get("title")}
    if section in ("adventure", "protagonist", "scenes", "npcs", "objects", "exits"):
        return {"adventure": header, section: data.get(section)}
    adv_key = "world_sections" if section == "sections" else section
    return {"adventure": header, section: adventure.get(adv_key)}


async def get_adventure_details(
    db: AsyncSession,
    template_id: str,
    *,
    scene_id: Optional[str] = None,
    section: Optional[str] = None,
    compact: bool = True,
) -> dict[str, Any]:
    """Return full or sliced editor asset data for an adventure template."""
    data = (await _build_adventure_editor_assets(template_id, db)).model_dump()
    data.pop("entities_all", None)
    if compact:
        data = _compact_payload(data)
    if scene_id:
        return _scene_slice(data, scene_id.strip())
    if section:
        return _section_slice(data, section.strip().lower())
    return data


async def export_adventure_manifest(db: AsyncSession, template_id: str) -> dict[str, Any]:
    """Export an adventure template as a complete ``.adv`` manifest JSON dict."""
    try:
        return await AdventureExporter.build_full_manifest(db, template_id)
    except Exception:
        adventure = await db.get(AdventureTemplate, template_id)
        if not adventure or not isinstance(adventure.original_manifest, dict):
            raise
        manifest = dict(adventure.original_manifest)
        backfill_manifest_metadata(manifest, adventure)
        return manifest
