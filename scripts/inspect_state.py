#!/usr/bin/env python3
"""
TaleWeaver State & Manifest Inspector (CLI)

Provides deep diagnostic inspection for:
- Adventure Templates (Manifests, Scenes, Entities, Exits, Rules, Quests, Awards)
- Game Sessions (SessionState, Avatar, Inventory, Entity Overrides, Runtime Flags)

Usage:
  python scripts/inspect_state.py list-adventures
  python scripts/inspect_state.py show-adventure <template_id_or_title> [--entities] [--scenes] [--exits] [--manifest] [--json]
  python scripts/inspect_state.py list-sessions [--limit 10] [--all] [--json]
  python scripts/inspect_state.py show-session <session_id> [--inventory] [--entities] [--hidden-only] [--json]
  python scripts/inspect_state.py dump-manifest <template_id>
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from backend.core.database import AsyncSessionLocal
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene


def _format_json(data: Any) -> str:
    """Format dictionary/list as pretty JSON string."""
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


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

        _print_header(f"Adventure Templates ({len(templates)} found)")
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


async def cmd_show_adventure(args):
    ident = args.identifier.strip()
    async with AsyncSessionLocal() as db:
        # Search by exact ID, origin_id, or title prefix/match
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

        # Load scenes, entities, exits for this template
        scenes_res = await db.execute(
            select(WorldScene).where(WorldScene.template_id == template.id).order_by(WorldScene.id)
        )
        scenes = scenes_res.scalars().all()

        entities_res = await db.execute(
            select(WorldEntity).where(WorldEntity.template_id == template.id).order_by(WorldEntity.id)
        )
        entities = entities_res.scalars().all()

        exits_res = await db.execute(
            select(WorldExit).where(WorldExit.template_id == template.id)
        )
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
                    {"id": s.id, "label": s.label, "description": s.description, "image_url": s.image_url}
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
                        "label": x.label,
                        "is_locked": x.is_locked,
                        "lock_description": x.lock_description,
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

        _print_header(f"Adventure: {template.title} (ID: {template.id})")
        _print_kv("Title", template.title)
        _print_kv("ID", template.id)
        _print_kv("Origin ID", template.origin_id or "N/A")
        _print_kv("Version", template.version or "1.0")
        _print_kv("Language", template.language or "en")
        _print_kv("Teaser", (template.teaser or "N/A")[:120] + ("..." if len(template.teaser or "") > 120 else ""))
        _print_kv("Rule Mode", template.rule_enforcement_mode)
        _print_kv("Clock Enabled", template.clock_enabled)
        _print_kv("Time System", f"{template.time_system} (Pacing: {template.pacing_minutes}m/turn)")
        _print_kv("Quests Count", len(template.quests or []))

        # Show Scenes
        if not args.entities and not args.exits and not args.manifest:
            _print_header(f"World Scenes ({len(scenes)})", char="-")
            for s in scenes:
                print(f"  • [\033[1;33m{s.id}\033[0m] {s.label}")
                desc_snippet = (s.description or "").replace("\n", " ")[:100]
                if desc_snippet:
                    print(f"    Description: {desc_snippet}...")

        # Show Entities / Items
        if not args.scenes and not args.exits and not args.manifest:
            _print_header(f"World Entities & Items ({len(entities)})", char="-")
            for e in entities:
                hidden_tag = "\033[1;31m[HIDDEN]\033[0m" if e.is_hidden else "\033[1;32m[VISIBLE]\033[0m"
                type_tag = f"({e.entity_type}:{e.item_type or 'STANDARD'})"
                print(f"  • [\033[1;33m{e.id}\033[0m] \033[1m{e.name}\033[0m {type_tag} {hidden_tag}")
                print(f"    Scene   : {e.current_scene_id} (Spatial: {e.spatial_position or 'default'})")
                if e.reveal_rule:
                    print(f"    Reveal Rule: {e.reveal_rule}")
                if e.combination_ingredients:
                    print(f"    Ingredients: {e.combination_ingredients}")
                if e.reveals_item_id:
                    print(f"    Reveals Item: {e.reveals_item_id}")
                if e.unlock_rule:
                    print(f"    Unlock Rule: {e.unlock_rule}")

        # Show Exits
        if not args.scenes and not args.entities and not args.manifest:
            _print_header(f"World Exits ({len(exits)})", char="-")
            for x in exits:
                lock_tag = f"\033[1;31m[LOCKED by {x.item_to_unlock or x.code_to_unlock or 'rule'}]\033[0m" if x.is_locked else "\033[1;32m[OPEN]\033[0m"
                arrow = "<->" if getattr(x, "exit_type", "one_way") == "bidirectional" else "->"
                type_tag = f"[{getattr(x, 'exit_type', 'one_way').upper()}]"
                print(f"  * {x.from_scene_id} {arrow} {x.to_scene_id} {type_tag} | \"{x.label}\" {lock_tag}")
                if x.rule_to_unlock:
                    print(f"    Rule to unlock: {x.rule_to_unlock}")

        # Manifest
        if args.manifest:
            _print_header("Original Manifest", char="-")
            print(_format_json(template.original_manifest or {}))


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
            print(f"ERROR: Template '{ident}' not found.", file=sys.stderr)
            sys.exit(1)

        print(_format_json(template.original_manifest or {}))


# -----------------------------------------------------------------------------
# SESSION COMMANDS
# -----------------------------------------------------------------------------

async def cmd_list_sessions(args):
    async with AsyncSessionLocal() as db:
        limit = None if args.all else (args.limit or 10)
        query = (
            select(GameSession, SessionState, Avatar, User)
            .outerjoin(SessionState, SessionState.session_id == GameSession.id)
            .outerjoin(Avatar, Avatar.id == GameSession.avatar_id)
            .outerjoin(User, User.id == GameSession.user_id)
            .order_by(desc(GameSession.updated_at))
        )
        if limit:
            query = query.limit(limit)

        res = await db.execute(query)
        rows = res.all()

        if args.json:
            out = []
            for g, s, av, u in rows:
                out.append({
                    "session_id": g.id,
                    "adventure_title": g.adventure_title,
                    "template_id": g.template_id,
                    "status": g.status,
                    "current_scene_id": s.current_scene_id if s else None,
                    "avatar_name": av.name if av else None,
                    "username": u.username if u else None,
                    "updated_at": str(g.updated_at),
                })
            print(_format_json(out))
            return

        _print_header(f"Game Sessions (Showing {len(rows)})")
        if not rows:
            print("  No game sessions found in database.")
            return

        for g, s, av, u in rows:
            user_str = u.username if u else "unknown"
            scene_str = s.current_scene_id if s else "N/A"
            avatar_str = av.name if av else "N/A"
            print(f"  • \033[1;36mSession: {g.id}\033[0m")
            print(f"    Adventure : {g.adventure_title or 'Unknown'} (Template: {g.template_id})")
            print(f"    Avatar    : {avatar_str} (User: {user_str})")
            print(f"    Scene     : \033[1;33m{scene_str}\033[0m | Status: {g.status}")
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
                select(WorldEntity).where(WorldEntity.template_id == g.template_id).order_by(WorldEntity.id)
            )
            session_entities = tpl_ent_res.scalars().all()

        # Calculate effective entity states with overrides
        entity_overrides = (s.entity_states or {}) if s else {}
        exit_overrides = (s.exit_states or {}) if s else {}

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
                    "allow_dynamic_items": s.allow_dynamic_items if s else False,
                    "is_completed": s.is_completed if s else False,
                    "is_debug_enabled": s.is_debug_enabled if s else False,
                },
                "entity_overrides": entity_overrides,
                "exit_overrides": exit_overrides,
            }
            print(_format_json(payload))
            return

        _print_header(f"Session Inspector: {g.id}")
        _print_kv("Adventure", f"{g.adventure_title} (Template: {g.template_id})")
        _print_kv("User", f"{u.username if u else 'N/A'} (ID: {g.user_id})")
        _print_kv("Status", f"{g.status} ({g.status_note or 'No notes'})")
        _print_kv("Updated At", g.updated_at)

        if av:
            _print_header("Protagonist / Avatar", char="-")
            _print_kv("Name", f"{av.name} ({av.role or 'Protagonist'})")
            _print_kv("Health / Stats", f"HP: {av.hp}/{av.max_hp} | Mana: {av.mana}/{av.max_mana} | Stamina: {av.stamina}/{av.max_stamina}")
            _print_kv("RPG Stats", f"STR:{av.strength} DEX:{av.dexterity} INT:{av.intelligence} WIS:{av.wisdom} CHA:{av.charisma} AC:{av.armor_class}")
            _print_kv("Status Effects", av.status_effects or "None")

            # Inventory display
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
                        print(f"    {idx}. \033[1;32m{iname}\033[0m [ID: {iid}] (Type: {itype}, Slot: {islot})")
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
                    q_status = "\033[1;32m[DONE]\033[0m" if q.get("completed") else "\033[1;33m[ACTIVE]\033[0m"
                    print(f"    • {q_status} {q.get('title') or q.get('id')}: {q.get('description', '')}")

            if s.world_memories:
                _print_header(f"World Memories ({len(s.world_memories)})", char="-")
                for mem in s.world_memories:
                    print(f"    • [{mem.get('scope', 'local').upper()}] ({mem.get('emotion', 'neutral')}): {mem.get('description')}")

        # Entities in World / Overrides
        if not args.inventory:
            _print_header("World Entities & State Overrides", char="-")
            for ent in session_entities:
                override = entity_overrides.get(ent.id, {})
                eff_hidden = override.get("is_hidden", ent.is_hidden)
                eff_in_inv = override.get("is_in_inventory", ent.is_in_inventory)
                eff_scene = override.get("current_scene_id", ent.current_scene_id)
                eff_spatial = override.get("spatial_position", ent.spatial_position)

                if args.hidden_only and not eff_hidden:
                    continue

                hidden_tag = "\033[1;31m[HIDDEN]\033[0m" if eff_hidden else "\033[1;32m[VISIBLE]\033[0m"
                inv_tag = "\033[1;36m[IN INVENTORY]\033[0m" if eff_in_inv else ""
                scene_tag = f"Scene: {eff_scene}"
                if eff_scene == (s.current_scene_id if s else None):
                    scene_tag = f"\033[1;33mScene: {eff_scene} (CURRENT)\033[0m"

                has_override = " \033[1;35m(OVERRIDDEN)\033[0m" if override else ""
                print(f"  • [\033[1;36m{ent.id}\033[0m] \033[1m{ent.name}\033[0m ({ent.item_type or 'OBJECT'}) {hidden_tag} {inv_tag}{has_override}")
                print(f"    {scene_tag} (Spatial: {eff_spatial or 'default'})")

                if override:
                    print(f"    Raw Overrides: {override}")
                if ent.combination_ingredients:
                    print(f"    Combination Ingredients: {ent.combination_ingredients}")
                if ent.reveal_rule:
                    print(f"    Reveal Rule: {ent.reveal_rule}")


# -----------------------------------------------------------------------------
# MAIN CLI ENTRYPOINT
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="TaleWeaver State & Manifest Debug Inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list-adventures
    p_la = subparsers.add_parser("list-adventures", aliases=["list-templates"], help="List all adventure templates")
    p_la.add_argument("--json", action="store_true", help="Output as raw JSON")
    p_la.set_defaults(func=cmd_list_adventures)

    # show-adventure
    p_sa = subparsers.add_parser("show-adventure", aliases=["show-template"], help="Show details of an adventure")
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
    p_ss.add_argument("--json", action="store_true", help="Output as raw JSON")
    p_ss.set_defaults(func=cmd_show_session)

    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
