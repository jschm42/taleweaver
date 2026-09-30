#!/usr/bin/env python3
"""
TaleWeaver State, Database & Manifest Inspector (CLI)

Provides deep diagnostic inspection and management for:
- Database Health & Table Counts (SQLite stats, WAL, storage sizes)
- Adventure Templates (Manifests, Scenes, Entities, Exits, Rules, Quests, Awards)
- Disk Adventures (.adv, .adz, manifests on disk & import status)
- Game Sessions (SessionState, Avatar, Inventory, Entity Overrides, Dialogue Turns, Checkpoints)
- Adventure Import / Ingestion

Usage:
  python scripts/inspect_state.py db-status [--json]
  python scripts/inspect_state.py list-adventures [--json]
  python scripts/inspect_state.py list-disk-adventures [--json]
  python scripts/inspect_state.py show-adventure <id_or_title> [--entities] [--scenes] [--exits] [--manifest] [--json]
  python scripts/inspect_state.py dump-manifest <id_or_title>
  python scripts/inspect_state.py import-adventure [path] [--user <username>] [--overwrite]
  python scripts/inspect_state.py list-sessions [--limit 10] [--all] [--json]
  python scripts/inspect_state.py show-session <session_id> [--inventory] [--entities] [--hidden-only] [--chat] [--checkpoints] [--json]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sqlalchemy import desc, func, select, text

from backend.core.config import settings
from backend.core.database import AsyncSessionLocal
from backend.engine.adventure_importer import AdventureTemplateImporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.character import Character
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_checkpoint import SessionCheckpoint
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene


def _format_json(data: Any) -> str:
    """Format dictionary/list as pretty JSON string."""
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


def _format_bytes(size: int) -> str:
    """Format bytes into human-readable size."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def _get_dir_size(path: Path) -> tuple[int, int]:
    """Calculate total byte size and file count for a directory."""
    total_bytes = 0
    file_count = 0
    if not path.exists():
        return 0, 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = Path(root) / f
            try:
                total_bytes += fp.stat().st_size
                file_count += 1
            except OSError:
                pass
    return total_bytes, file_count


def _print_header(title: str, char: str = "="):
    """Print formatted section banner."""
    print(f"\n{char * 70}")
    print(f"  {title.upper()}")
    print(f"{char * 70}")


def _print_kv(key: str, value: Any, indent: int = 2):
    """Print aligned key-value pair."""
    prefix = " " * indent
    if isinstance(value, (dict, list)):
        print(f"{prefix}\033[1m{key}\033[0m:")
        lines = _format_json(value).splitlines()
        for line in lines:
            print(f"{prefix}  {line}")
    else:
        print(f"{prefix}\033[1m{key:<24}\033[0m: {value}")


# -----------------------------------------------------------------------------
# DATABASE & STORAGE STATUS
# -----------------------------------------------------------------------------


async def cmd_db_status(args):
    db_url = settings.DATABASE_URL
    db_path = None
    if ":///" in db_url:
        raw_path = db_url.split(":///", 1)[1]
        db_path = Path(raw_path) if Path(raw_path).is_absolute() else Path(PROJECT_ROOT) / raw_path
    if not db_path or not db_path.exists():
        fallback = Path(PROJECT_ROOT) / "data" / "taleweaver.db"
        if fallback.exists():
            db_path = fallback

    async with AsyncSessionLocal() as db:
        # Table counts
        counts: dict[str, Any] = {}
        tables_to_count = [
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
        ]
        for name, model in tables_to_count:
            try:
                res = await db.execute(select(func.count()).select_from(model))
                counts[name] = res.scalar_one()
            except Exception as e:
                counts[name] = f"error ({e})"

        # Pragmas
        try:
            j_res = await db.execute(text("PRAGMA journal_mode;"))
            journal_mode = j_res.scalar_one()
        except Exception:
            journal_mode = "unknown"

        try:
            page_res = await db.execute(text("PRAGMA page_count;"))
            page_count = page_res.scalar_one()
            page_size_res = await db.execute(text("PRAGMA page_size;"))
            page_size = page_size_res.scalar_one()
            calc_size = page_count * page_size
        except Exception:
            calc_size = 0

    # Files on disk
    files_info: dict[str, Any] = {}
    if db_path and db_path.exists():
        files_info["database_file"] = {
            "path": str(db_path),
            "size_bytes": db_path.stat().st_size,
            "size_formatted": _format_bytes(db_path.stat().st_size),
        }
        for ext in ["-wal", "-shm"]:
            sidecar = Path(str(db_path) + ext)
            if sidecar.exists():
                files_info[f"database{ext}"] = {
                    "path": str(sidecar),
                    "size_bytes": sidecar.stat().st_size,
                    "size_formatted": _format_bytes(sidecar.stat().st_size),
                }

    # Data directory breakdown
    data_dir = Path(PROJECT_ROOT) / settings.DATA_DIR
    dirs_info: dict[str, Any] = {}
    subdirs = [
        "adventures/library",
        "adventures/sessions",
        "characters",
        "audio",
        "logs",
        "presets/adventures",
        "imports/adventures",
    ]
    for sub in subdirs:
        target = data_dir / sub
        if target.exists():
            b, c = _get_dir_size(target)
            dirs_info[sub] = {
                "bytes": b,
                "formatted": _format_bytes(b),
                "count": c,
            }

    if args.json:
        print(
            _format_json(
                {
                    "database_url": db_url,
                    "journal_mode": journal_mode,
                    "calculated_size_bytes": calc_size,
                    "calculated_size_formatted": _format_bytes(calc_size),
                    "files": files_info,
                    "table_counts": counts,
                    "storage_usage": dirs_info,
                }
            )
        )
        return

    _print_header("TaleWeaver Database & Storage Status")
    if db_path and db_path.exists():
        _print_kv("Database File", f"{db_path} ({_format_bytes(db_path.stat().st_size)})")
        for ext in ["-wal", "-shm"]:
            sidecar = Path(str(db_path) + ext)
            if sidecar.exists():
                _print_kv(
                    f"Sidecar ({ext})", f"{sidecar.name} ({_format_bytes(sidecar.stat().st_size)})"
                )
    else:
        _print_kv("Database URL", db_url)
    _print_kv("Journal Mode", journal_mode)
    if calc_size:
        _print_kv("Calculated DB Size", _format_bytes(calc_size))

    _print_header("Database Table Records", char="-")
    for tbl, cnt in counts.items():
        _print_kv(tbl, cnt)

    _print_header(f"Data Directory Storage ({data_dir.name}/)", char="-")
    for sdir, info in dirs_info.items():
        _print_kv(sdir, f"{info['formatted']} ({info['count']} files)")


# -----------------------------------------------------------------------------
# ADVENTURE COMMANDS
# -----------------------------------------------------------------------------


async def cmd_list_adventures(args):
    async with AsyncSessionLocal() as db:
        query = select(AdventureTemplate).order_by(desc(AdventureTemplate.created_at))
        res = await db.execute(query)
        templates = res.scalars().all()

        if args.json:
            out = [
                {
                    "id": t.id,
                    "title": t.title,
                    "version": t.version,
                    "language": t.language,
                    "origin_id": t.origin_id,
                    "is_ready": t.is_ready,
                    "creation_status": t.creation_status,
                    "created_at": str(t.created_at),
                }
                for t in templates
            ]
            print(_format_json(out))
            return

        _print_header(f"Adventure Templates ({len(templates)} found in database)")
        if not templates:
            print("  No adventure templates found in database.")
            return

        for t in templates:
            status = "READY" if t.is_ready else f"PENDING ({t.creation_status or 'unknown'})"
            print(f"  • \033[1;36m{t.title}\033[0m (v{t.version or '1.0'}, {t.language or 'en'})")
            print(f"    ID        : {t.id}")
            if t.origin_id:
                print(f"    Origin ID : {t.origin_id}")
            print(f"    Status    : {status}")
            print(f"    Created   : {t.created_at}")
            print()


async def cmd_list_disk_adventures(args):
    search_dirs = [
        Path(PROJECT_ROOT) / "adventures",
        Path(PROJECT_ROOT) / settings.DATA_DIR / "imports" / "adventures",
        Path(PROJECT_ROOT) / settings.DATA_DIR / "presets" / "adventures",
    ]
    disk_files: list[Path] = []
    for d in search_dirs:
        if not d.exists():
            continue
        for ext in ["*.adv", "*.adz", "*.json"]:
            for f in d.rglob(ext):
                # Skip package/config files
                if f.name in (
                    "package.json",
                    "tsconfig.json",
                    "version.json",
                    "scratch_manifest.json",
                ):
                    continue
                disk_files.append(f)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(AdventureTemplate))
        db_templates = res.scalars().all()
        db_titles = {t.title.lower(): t for t in db_templates if t.title}
        db_origins = {t.origin_id: t for t in db_templates if t.origin_id}
        db_ids = {t.id: t for t in db_templates if t.id}

    records = []
    for f in sorted(disk_files):
        size = f.stat().st_size
        try:
            rel_path = f.relative_to(PROJECT_ROOT)
        except ValueError:
            rel_path = f

        stem = f.stem.lower()
        matched = db_titles.get(stem) or db_origins.get(stem) or db_ids.get(stem)

        status = f"IMPORTED ({matched.id})" if matched else "AVAILABLE TO IMPORT"
        records.append(
            {
                "path": str(rel_path),
                "filename": f.name,
                "size_bytes": size,
                "size_formatted": _format_bytes(size),
                "status": status,
                "imported": matched is not None,
                "template_id": matched.id if matched else None,
            }
        )

    if args.json:
        print(_format_json(records))
        return

    _print_header(f"Disk Adventures ({len(records)} found)")
    if not records:
        print("  No adventure files found on disk.")
        return

    for r in records:
        status_color = "\033[1;32m" if r["imported"] else "\033[1;33m"
        print(f"  • \033[1;36m{r['path']}\033[0m ({r['size_formatted']})")
        print(f"    Status: {status_color}{r['status']}\033[0m")
        print()


async def cmd_import_adventure(args):
    target = args.file_path
    if not target:
        default_adv = Path(PROJECT_ROOT) / "adventures" / "default" / "combat_test_adventure.adv"
        if default_adv.exists():
            target = str(default_adv)
        else:
            print(
                "ERROR: Please specify an adventure file (.adv, .adz) or directory to import.",
                file=sys.stderr,
            )
            sys.exit(1)

    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = Path(PROJECT_ROOT) / target

    if not target_path.exists():
        print(f"ERROR: File or directory '{target_path}' not found.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        owner_id = None
        if args.user:
            u_res = await db.execute(
                select(User).where((User.id == args.user) | (User.username == args.user))
            )
            user = u_res.scalars().first()
            if user:
                owner_id = user.id
            else:
                print(
                    f"WARNING: User '{args.user}' not found. Falling back to admin.",
                    file=sys.stderr,
                )

        if not owner_id:
            adm_res = await db.execute(select(User).where(User.role == "admin").limit(1))
            admin = adm_res.scalars().first()
            if admin:
                owner_id = admin.id

        print(
            f"[*] Importing '{target_path.name}' (owner_id: {owner_id or 'None'}, overwrite: {args.overwrite})..."
        )
        if target_path.is_dir():
            success = await AdventureTemplateImporter.import_from_directory(
                db,
                str(target_path),
                owner_id=owner_id,
                overwrite=args.overwrite,
            )
        else:
            success = await AdventureTemplateImporter.import_file(
                db,
                str(target_path),
                owner_id=owner_id,
                overwrite=args.overwrite,
            )

        if success:
            print(f"\033[1;32m[+] Successfully imported '{target_path.name}'!\033[0m")
        else:
            print(f"\033[1;31m[-] Failed to import '{target_path.name}'.\033[0m", file=sys.stderr)
            sys.exit(1)


async def cmd_show_adventure(args):
    ident = args.identifier.strip()
    async with AsyncSessionLocal() as db:
        query = select(AdventureTemplate).where(
            (AdventureTemplate.id == ident)
            | (AdventureTemplate.origin_id == ident)
            | (AdventureTemplate.title.ilike(f"%{ident}%"))
        )
        res = await db.execute(query)
        template = res.scalars().first()

        if not template:
            print(f"ERROR: No adventure template found matching '{ident}'.", file=sys.stderr)
            sys.exit(1)

        scenes_res = await db.execute(
            select(WorldScene).where(WorldScene.template_id == template.id).order_by(WorldScene.id)
        )
        scenes = scenes_res.scalars().all()

        entities_res = await db.execute(
            select(WorldEntity)
            .where(WorldEntity.template_id == template.id)
            .order_by(WorldEntity.id)
        )
        entities = entities_res.scalars().all()

        exits_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template.id))
        exits = exits_res.scalars().all()

        if args.json:
            payload = {
                "template": {
                    "id": template.id,
                    "title": template.title,
                    "version": template.version,
                    "language": template.language,
                    "origin_id": template.origin_id,
                    "teaser": template.teaser,
                    "rule_enforcement_mode": template.rule_enforcement_mode,
                    "clock_enabled": template.clock_enabled,
                    "time_system": template.time_system,
                    "time_config": template.time_config,
                    "quests": template.quests,
                    "game_over_rules": template.game_over_rules,
                },
                "scenes": [
                    {
                        "id": s.id,
                        "label": s.label,
                        "description": s.description,
                        "image_url": s.image_url,
                    }
                    for s in scenes
                ],
                "entities": [
                    {
                        "id": e.id,
                        "name": e.name,
                        "entity_type": e.entity_type,
                        "item_type": e.item_type,
                        "current_scene_id": e.current_scene_id,
                        "spatial_position": e.spatial_position,
                        "is_hidden": e.is_hidden,
                        "reveal_rule": e.reveal_rule,
                        "unlock_rule": e.unlock_rule,
                        "combination_ingredients": e.combination_ingredients,
                        "reveals_item_id": e.reveals_item_id,
                    }
                    for e in entities
                ],
                "exits": [
                    {
                        "id": x.id,
                        "from_scene_id": x.from_scene_id,
                        "to_scene_id": x.to_scene_id,
                        "direction": x.direction,
                        "is_locked": x.is_locked,
                        "item_to_unlock": x.item_to_unlock,
                        "code_to_unlock": x.code_to_unlock,
                        "rule_to_unlock": x.rule_to_unlock,
                    }
                    for x in exits
                ],
            }
            if args.manifest and template.original_manifest:
                payload["original_manifest"] = template.original_manifest
            print(_format_json(payload))
            return

        # Header Details
        _print_header(f"Adventure: {template.title}")
        _print_kv("Template ID", template.id)
        if template.origin_id:
            _print_kv("Origin ID", template.origin_id)
        _print_kv("Version", f"{template.version or '1.0'} ({template.language or 'en'})")
        _print_kv(
            "Status", "READY" if template.is_ready else f"PENDING ({template.creation_status})"
        )
        _print_kv("Rule Enforcement", template.rule_enforcement_mode or "standard")
        _print_kv(
            "Clock Enabled", f"{template.clock_enabled} ({template.time_system or 'calendar'})"
        )
        if template.teaser:
            _print_kv("Teaser", template.teaser)

        # Scenes
        if not args.entities and not args.exits:
            _print_header(f"Scenes ({len(scenes)})", char="-")
            for s in scenes:
                print(f"  • [\033[1;33m{s.id}\033[0m] {s.label or '(unlabeled)'}")
                if s.description:
                    desc_snippet = s.description.strip()
                    if len(desc_snippet) > 120:
                        desc_snippet = desc_snippet[:117] + "..."
                    print(f"    {desc_snippet}")

        # Entities
        if not args.scenes and not args.exits:
            _print_header(f"Entities & Items ({len(entities)})", char="-")
            for e in entities:
                hidden_tag = (
                    "\033[1;31m[HIDDEN]\033[0m" if e.is_hidden else "\033[1;32m[VISIBLE]\033[0m"
                )
                itype = e.item_type or e.entity_type or "OBJECT"
                print(
                    f"  • [\033[1;36m{e.id}\033[0m] \033[1m{e.name}\033[0m ({itype}) {hidden_tag}"
                )
                print(
                    f"    Scene: {e.current_scene_id or 'none'} | Spatial: {e.spatial_position or 'default'}"
                )
                if e.combination_ingredients:
                    print(f"    Ingredients: {e.combination_ingredients}")
                if e.reveal_rule:
                    print(f"    Reveal Rule: {e.reveal_rule}")
                if e.unlock_rule:
                    print(f"    Unlock Rule: {e.unlock_rule}")

        # Exits
        if not args.scenes and not args.entities:
            _print_header(f"Exits & Passages ({len(exits)})", char="-")
            for x in exits:
                lock_tag = "\033[1;31m[LOCKED]\033[0m" if x.is_locked else "\033[1;32m[OPEN]\033[0m"
                print(
                    f"  • {x.from_scene_id} -> {x.to_scene_id} ({x.direction or 'path'}) {lock_tag}"
                )
                if x.is_locked:
                    if x.item_to_unlock:
                        print(f"    Key Item: {x.item_to_unlock}")
                    if x.code_to_unlock:
                        print(f"    Code/Password: {x.code_to_unlock}")
                    if x.rule_to_unlock:
                        print(f"    Rule: {x.rule_to_unlock}")

        # Quests
        if not args.scenes and not args.entities and not args.exits and template.quests:
            _print_header(f"Quests ({len(template.quests)})", char="-")
            for q in template.quests:
                print(
                    f"  • \033[1m{q.get('title') or q.get('id')}\033[0m: {q.get('description', '')}"
                )

        # Manifest
        if args.manifest:
            _print_header("Raw Original Manifest", char="-")
            print(_format_json(template.original_manifest))


async def cmd_dump_manifest(args):
    ident = args.identifier.strip()
    async with AsyncSessionLocal() as db:
        query = select(AdventureTemplate).where(
            (AdventureTemplate.id == ident)
            | (AdventureTemplate.origin_id == ident)
            | (AdventureTemplate.title.ilike(f"%{ident}%"))
        )
        res = await db.execute(query)
        template = res.scalars().first()
        if not template:
            print(f"ERROR: No adventure template found matching '{ident}'.", file=sys.stderr)
            sys.exit(1)
        print(_format_json(template.original_manifest or {}))


# -----------------------------------------------------------------------------
# SESSION COMMANDS
# -----------------------------------------------------------------------------


async def cmd_list_sessions(args):
    async with AsyncSessionLocal() as db:
        query = (
            select(GameSession, SessionState, Avatar, User)
            .outerjoin(SessionState, SessionState.session_id == GameSession.id)
            .outerjoin(Avatar, Avatar.id == GameSession.avatar_id)
            .outerjoin(User, User.id == GameSession.user_id)
            .order_by(desc(GameSession.updated_at))
        )
        if not args.all:
            query = query.limit(args.limit)

        res = await db.execute(query)
        rows = res.all()

        if args.json:
            out = [
                {
                    "session_id": g.id,
                    "adventure_title": g.adventure_title,
                    "template_id": g.template_id,
                    "status": g.status,
                    "user": u.username if u else None,
                    "avatar": av.name if av else None,
                    "current_scene": s.current_scene_id if s else None,
                    "in_game_time": s.in_game_time if s else 0,
                    "updated_at": str(g.updated_at),
                }
                for g, s, av, u in rows
            ]
            print(_format_json(out))
            return

        _print_header(f"Game Sessions ({len(rows)} shown)")
        if not rows:
            print("  No game sessions found.")
            return

        for g, s, av, u in rows:
            user_str = u.username if u else (g.user_id or "unknown")
            avatar_str = av.name if av else (g.avatar_id or "unknown")
            scene_str = s.current_scene_id if s else "unknown"
            status_tag = f"[{g.status.upper()}]" if g.status else "[UNKNOWN]"

            print(f"  • \033[1;36m{g.id}\033[0m {status_tag}")
            print(f"    Adventure : \033[1m{g.adventure_title or g.template_id or 'Custom'}\033[0m")
            print(f"    Player    : {avatar_str} (User: {user_str})")
            print(
                f"    Scene     : \033[1;33m{scene_str}\033[0m (Time: {s.in_game_time if s else 0} ticks)"
            )
            print(f"    Updated   : {g.updated_at}")
            print()


async def cmd_show_session(args):
    sid = args.session_id.strip()
    async with AsyncSessionLocal() as db:
        query = (
            select(GameSession, SessionState, Avatar, User)
            .outerjoin(SessionState, SessionState.session_id == GameSession.id)
            .outerjoin(Avatar, Avatar.id == GameSession.avatar_id)
            .outerjoin(User, User.id == GameSession.user_id)
            .where((GameSession.id == sid) | (GameSession.id.startswith(sid)))
        )
        res = await db.execute(query)
        row = res.first()

        if not row:
            print(f"ERROR: Session matching '{sid}' not found.", file=sys.stderr)
            sys.exit(1)

        g, s, av, u = row

        # Fetch session-bound entities
        ent_res = await db.execute(
            select(WorldEntity).where(WorldEntity.session_id == g.id).order_by(WorldEntity.id)
        )
        session_entities = ent_res.scalars().all()

        # If no session entities cloned, fetch template entities
        if not session_entities and g.template_id:
            tpl_ent_res = await db.execute(
                select(WorldEntity)
                .where(WorldEntity.template_id == g.template_id)
                .order_by(WorldEntity.id)
            )
            session_entities = tpl_ent_res.scalars().all()

        entity_overrides = (s.entity_states or {}) if s else {}
        exit_overrides = (s.exit_states or {}) if s else {}

        # Chat history
        chat_messages = []
        if getattr(args, "chat", False):
            msg_res = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == g.id)
                .order_by(ChatMessage.created_at.asc())
            )
            chat_messages = msg_res.scalars().all()

        # Checkpoints
        checkpoints = []
        if getattr(args, "checkpoints", False):
            cp_res = await db.execute(
                select(SessionCheckpoint)
                .where(SessionCheckpoint.session_id == g.id)
                .order_by(SessionCheckpoint.created_at.desc())
            )
            checkpoints = cp_res.scalars().all()

        if args.json:
            payload = {
                "session": {
                    "id": g.id,
                    "template_id": g.template_id,
                    "adventure_title": g.adventure_title,
                    "status": g.status,
                    "status_note": g.status_note,
                    "created_at": str(g.created_at),
                    "updated_at": str(g.updated_at),
                },
                "avatar": {
                    "id": av.id if av else None,
                    "name": av.name if av else None,
                    "hp": av.hp if av else None,
                    "max_hp": av.max_hp if av else None,
                    "inventory": av.inventory if av else [],
                    "equipment": av.equipment if av else {},
                    "status_effects": av.status_effects if av else [],
                },
                "state": {
                    "current_scene_id": s.current_scene_id if s else None,
                    "in_game_time": s.in_game_time if s else 0,
                    "time_system": s.time_system if s else "calendar",
                    "discovered_scenes": s.discovered_scenes if s else [],
                    "quests": s.quests if s else [],
                    "world_memories": s.world_memories if s else [],
                    "world_rumors": s.world_rumors if s else [],
                    "entity_overrides": entity_overrides,
                    "exit_overrides": exit_overrides,
                    "is_completed": s.is_completed if s else False,
                    "is_debug_enabled": s.is_debug_enabled if s else False,
                },
                "chat_messages": [
                    {"role": m.role, "content": m.content, "created_at": str(m.created_at)}
                    for m in chat_messages
                ],
                "checkpoints": [
                    {"id": cp.id, "scene_id": cp.scene_id, "created_at": str(cp.created_at)}
                    for cp in checkpoints
                ],
            }
            print(_format_json(payload))
            return

        # Display Session State
        _print_header(f"Session: {g.id}")
        _print_kv(
            "Adventure", f"{g.adventure_title or 'Custom'} (Template: {g.template_id or 'none'})"
        )
        _print_kv("User", f"{u.username if u else g.user_id} (ID: {g.user_id})")
        _print_kv("Status", f"{g.status.upper()} ({g.status_note or 'normal'})")
        _print_kv("Last Played", g.updated_at)

        if av:
            _print_header("Protagonist / Avatar", char="-")
            _print_kv("Name", f"{av.name} ({av.role or 'Protagonist'})")
            _print_kv(
                "Health / Stats",
                f"HP: {av.hp}/{av.max_hp} | Mana: {av.mana}/{av.max_mana} | Stamina: {av.stamina}/{av.max_stamina}",
            )
            _print_kv(
                "RPG Stats",
                f"STR:{av.strength} DEX:{av.dexterity} INT:{av.intelligence} WIS:{av.wisdom} CHA:{av.charisma} AC:{av.armor_class}",
            )
            _print_kv("Status Effects", av.status_effects or "None")

            inv = av.inventory or []
            _print_header(f"Avatar Inventory ({len(inv)} items)", char="-")
            if not inv:
                print("    (Inventory is empty)")
            else:
                for idx, item in enumerate(inv, 1):
                    if isinstance(item, dict):
                        iid = item.get("id") or item.get("name") or "unknown"
                        iname = item.get("name") or iid
                        itype = item.get("item_type") or "PICKABLE"
                        islot = item.get("slot") or "generic"
                        print(
                            f"    {idx}. \033[1;32m{iname}\033[0m [ID: {iid}] (Type: {itype}, Slot: {islot})"
                        )
                    else:
                        print(f"    {idx}. {item}")

        if s:
            _print_header("Runtime Session State", char="-")
            _print_kv("Current Scene", f"\033[1;33m{s.current_scene_id}\033[0m")
            _print_kv("In-game Time", f"{s.in_game_time} ticks ({s.time_system})")
            _print_kv("Discovered Scenes", s.discovered_scenes or [])
            _print_kv("Allow Dynamic Items", s.allow_dynamic_items)
            _print_kv("Completed", s.is_completed)
            _print_kv("Debug Enabled", s.is_debug_enabled)

            if s.quests:
                _print_header(f"Quests ({len(s.quests)})", char="-")
                for q in s.quests:
                    q_status = (
                        "\033[1;32m[DONE]\033[0m"
                        if q.get("completed")
                        else "\033[1;33m[ACTIVE]\033[0m"
                    )
                    print(
                        f"    • {q_status} {q.get('title') or q.get('id')}: {q.get('description', '')}"
                    )

            if s.world_memories:
                _print_header(f"World Memories ({len(s.world_memories)})", char="-")
                for mem in s.world_memories:
                    print(
                        f"    • [{mem.get('scope', 'local').upper()}] ({mem.get('emotion', 'neutral')}): {mem.get('description')}"
                    )

        # Entities in World / Overrides
        if not args.inventory and not getattr(args, "chat", False):
            _print_header("World Entities & State Overrides", char="-")
            for ent in session_entities:
                override = entity_overrides.get(ent.id, {})
                eff_hidden = override.get("is_hidden", ent.is_hidden)
                eff_in_inv = override.get("is_in_inventory", ent.is_in_inventory)
                eff_scene = override.get("current_scene_id", ent.current_scene_id)
                eff_spatial = override.get("spatial_position", ent.spatial_position)

                if args.hidden_only and not eff_hidden:
                    continue

                hidden_tag = (
                    "\033[1;31m[HIDDEN]\033[0m" if eff_hidden else "\033[1;32m[VISIBLE]\033[0m"
                )
                inv_tag = "\033[1;36m[IN INVENTORY]\033[0m" if eff_in_inv else ""
                scene_tag = f"Scene: {eff_scene}"
                if eff_scene == (s.current_scene_id if s else None):
                    scene_tag = f"\033[1;33mScene: {eff_scene} (CURRENT)\033[0m"

                has_override = " \033[1;35m(OVERRIDDEN)\033[0m" if override else ""
                print(
                    f"  • [\033[1;36m{ent.id}\033[0m] \033[1m{ent.name}\033[0m ({ent.item_type or 'OBJECT'}) {hidden_tag} {inv_tag}{has_override}"
                )
                print(f"    {scene_tag} (Spatial: {eff_spatial or 'default'})")

                if override:
                    print(f"    Raw Overrides: {override}")
                if ent.combination_ingredients:
                    print(f"    Combination Ingredients: {ent.combination_ingredients}")
                if ent.reveal_rule:
                    print(f"    Reveal Rule: {ent.reveal_rule}")

        # Chat Turns / Messages
        if getattr(args, "chat", False):
            limit_m = getattr(args, "limit_messages", 30)
            messages_slice = (
                chat_messages[-limit_m:] if len(chat_messages) > limit_m else chat_messages
            )
            _print_header(
                f"Conversation Turns ({len(messages_slice)} of {len(chat_messages)} shown)",
                char="-",
            )
            if not messages_slice:
                print("    (No chat messages recorded in this session)")
            else:
                for idx, m in enumerate(messages_slice, 1):
                    role_color = "\033[1;36m" if m.role == "user" else "\033[1;35m"
                    print(f"\n  [{idx}] {role_color}{m.role.upper()}\033[0m ({m.created_at}):")
                    content_clean = m.content.strip()
                    for line in content_clean.splitlines():
                        print(f"    {line}")

        # Checkpoints
        if getattr(args, "checkpoints", False):
            _print_header(f"Checkpoints ({len(checkpoints)})", char="-")
            if not checkpoints:
                print("    (No checkpoints recorded)")
            else:
                for cp in checkpoints:
                    print(f"  • Checkpoint [{cp.id}] Scene: {cp.scene_id} at {cp.created_at}")


# -----------------------------------------------------------------------------
# MAIN CLI ENTRYPOINT
# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="TaleWeaver State, Database & Manifest Debug Inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # db-status
    p_db = subparsers.add_parser(
        "db-status",
        aliases=["stats", "status"],
        help="Inspect database health, table row counts, and data disk usage",
    )
    p_db.add_argument("--json", action="store_true", help="Output as raw JSON")
    p_db.set_defaults(func=cmd_db_status)

    # list-adventures
    p_la = subparsers.add_parser(
        "list-adventures",
        aliases=["list-templates"],
        help="List all adventure templates in database",
    )
    p_la.add_argument("--json", action="store_true", help="Output as raw JSON")
    p_la.set_defaults(func=cmd_list_adventures)

    # list-disk-adventures
    p_lda = subparsers.add_parser(
        "list-disk-adventures",
        aliases=["scan-disk"],
        help="Scan disk for available .adv, .adz, or manifest files",
    )
    p_lda.add_argument("--json", action="store_true", help="Output as raw JSON")
    p_lda.set_defaults(func=cmd_list_disk_adventures)

    # import-adventure
    p_ia = subparsers.add_parser(
        "import-adventure",
        aliases=["import"],
        help="Import an adventure file or directory into the database",
    )
    p_ia.add_argument(
        "file_path",
        nargs="?",
        default="",
        help="Path to .adv, .adz, or directory (defaults to combat test adventure)",
    )
    p_ia.add_argument(
        "--user", help="Assign adventure to specific username or user_id (defaults to first admin)"
    )
    p_ia.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing adventure template if matched"
    )
    p_ia.set_defaults(func=cmd_import_adventure)

    # show-adventure
    p_sa = subparsers.add_parser(
        "show-adventure", aliases=["show-template"], help="Show details of an adventure"
    )
    p_sa.add_argument("identifier", help="Template ID, origin_id, or title substring")
    p_sa.add_argument("--scenes", action="store_true", help="Show only scenes")
    p_sa.add_argument("--entities", action="store_true", help="Show only entities/items")
    p_sa.add_argument("--exits", action="store_true", help="Show only exits")
    p_sa.add_argument("--manifest", action="store_true", help="Include raw original manifest")
    p_sa.add_argument("--json", action="store_true", help="Output as raw JSON")
    p_sa.set_defaults(func=cmd_show_adventure)

    # dump-manifest
    p_dm = subparsers.add_parser("dump-manifest", help="Dump raw original manifest JSON")
    p_dm.add_argument("identifier", help="Template ID, origin_id, or title substring")
    p_dm.set_defaults(func=cmd_dump_manifest)

    # list-sessions
    p_ls = subparsers.add_parser("list-sessions", help="List recent game sessions")
    p_ls.add_argument("--limit", type=int, default=10, help="Max sessions to list (default: 10)")
    p_ls.add_argument("--all", action="store_true", help="List all sessions")
    p_ls.add_argument("--json", action="store_true", help="Output as raw JSON")
    p_ls.set_defaults(func=cmd_list_sessions)

    # show-session
    p_ss = subparsers.add_parser("show-session", help="Inspect a specific game session state")
    p_ss.add_argument("session_id", help="Session ID or prefix")
    p_ss.add_argument("--inventory", action="store_true", help="Focus on inventory details")
    p_ss.add_argument("--entities", action="store_true", help="Focus on world entities & overrides")
    p_ss.add_argument("--hidden-only", action="store_true", help="Show only hidden entities")
    p_ss.add_argument(
        "--chat",
        "--messages",
        dest="chat",
        action="store_true",
        help="Display session dialogue history / turns",
    )
    p_ss.add_argument(
        "--limit-messages", type=int, default=30, help="Max chat messages to display (default: 30)"
    )
    p_ss.add_argument(
        "--checkpoints", action="store_true", help="Display saved session checkpoints"
    )
    p_ss.add_argument("--json", action="store_true", help="Output as raw JSON")
    p_ss.set_defaults(func=cmd_show_session)

    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
