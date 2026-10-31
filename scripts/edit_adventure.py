#!/usr/bin/env python3
"""
TaleWeaver Adventure Editor CLI (for agents)

Reads and modifies adventure templates in the database through the same code paths as the
Adventure Editor. Changes are written as a JSON change set and applied in one transaction;
``apply`` is a dry run unless ``--commit`` is given.

Usage:
  python scripts/edit_adventure.py summary <adventure>
  python scripts/edit_adventure.py export <adventure> [--scene <SCENE_ID>] [--out <file>]
  python scripts/edit_adventure.py validate <adventure> [--json]
  python scripts/edit_adventure.py ops [<op>]
  python scripts/edit_adventure.py apply <changes.json> [--adventure <adventure>] [--commit] [--allow-errors]

<adventure> is a template ID, origin_id, or a unique title substring.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.api.routes.adventures.editing.change_set import (
    OPERATION_MODELS,
    OPERATIONS,
    ChangeSetError,
    DeferredCommitSession,
    apply_change_set,
    structural_findings,
)
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.core.database import AsyncSessionLocal
from backend.models.adventure_template import AdventureTemplate

# Export noise: duplicated manifest, media paths and bookkeeping columns.
_DROPPED_KEYS = frozenset(
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


# Fields of the operations that have no request model.
_OP_FIELDS = {
    "set_init_script": "code",
    "append_init_script": "code",
    "delete_scene": "scene_id",
    "delete_exit": "exit_id ($ref, FROM->TO or id)",
    "delete_entity": "entity_id",
    "delete_script": "script_id",
    "delete_quest": "quest_id",
    "delete_award": "award_key",
}


class CliError(Exception):
    pass


def _session_factory() -> async_sessionmaker:
    return async_sessionmaker(
        bind=AsyncSessionLocal.kw["bind"], class_=DeferredCommitSession, expire_on_commit=False
    )


async def _resolve_template_id(db: Any, ident: str) -> str:
    ident = ident.strip()
    exact = await db.execute(
        select(AdventureTemplate.id).where(
            (AdventureTemplate.id == ident) | (AdventureTemplate.origin_id == ident)
        )
    )
    exact_ids = list(exact.scalars().all())
    if len(exact_ids) == 1:
        return exact_ids[0]
    rows = await db.execute(
        select(AdventureTemplate.id, AdventureTemplate.title).where(
            AdventureTemplate.title.ilike(f"%{ident}%")
        )
    )
    matches = rows.all()
    if len(matches) == 1:
        return matches[0][0]
    if not matches:
        raise CliError(f"No adventure matches '{ident}'.")
    listing = "\n".join(f"  {row[0]}  {row[1]}" for row in matches)
    raise CliError(f"'{ident}' matches several adventures; use the ID:\n{listing}")


def _compact(value: Any) -> Any:
    """Drops empty values and noise keys so exports stay small."""
    if isinstance(value, dict):
        pairs = ((k, _compact(v)) for k, v in value.items() if k not in _DROPPED_KEYS)
        return {k: v for k, v in pairs if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [_compact(v) for v in value]
    return value


async def _assets(db: Any, template_id: str) -> dict[str, Any]:
    payload = await _build_adventure_editor_assets(template_id, db)
    data = payload.model_dump()
    data.pop("entities_all", None)
    return _compact(data)


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
    return {
        "adventure": {k: data["adventure"].get(k) for k in ("id", "title", "start_scene_id")},
        "scene": next((s for s in data.get("scenes", []) if s.get("id") == scene_id), None),
        "neighbour_scenes": [
            {"id": s.get("id"), "label": s.get("label")}
            for s in data.get("scenes", [])
            if s.get("id") in near - {scene_id}
        ],
        "exits": exits,
        "entities": in_scene,
    }


def _summary(data: dict[str, Any]) -> dict[str, Any]:
    adventure = data.get("adventure", {})
    return {
        "adventure": {k: adventure.get(k) for k in ("id", "title", "start_scene_id")},
        "init_script_lines": len(str(adventure.get("init_script") or "").splitlines()),
        "scripts": [f"{s.get('id')} ({s.get('trigger')})" for s in adventure.get("scripts") or []],
        "quests": [q.get("id") for q in adventure.get("quests") or []],
        "scenes": {s.get("id"): s.get("label") for s in data.get("scenes", [])},
        "exits": [
            f"{e.get('from_scene_id')}->{e.get('to_scene_id')} [{e.get('exit_type')}"
            f"{', locked' if e.get('is_locked') else ''}] {e.get('label')} (id {e.get('id')})"
            for e in data.get("exits", [])
        ],
        "npcs": {
            n.get("id"): f"{n.get('name')} @ {n.get('current_scene_id')}"
            for n in data.get("npcs", [])
        },
        "objects": {
            o.get(
                "id"
            ): f"{o.get('name')} [{o.get('item_type') or 'ITEM'}] @ {o.get('current_scene_id')}"
            for o in data.get("objects", [])
        },
    }


def _print_findings(findings: list[Any]) -> None:
    if not findings:
        print("  (none)")
    for f in findings:
        print(f"  [{f.severity}] {f.code} @ {f.location or '-'}: {f.message}")


async def cmd_summary(args: argparse.Namespace) -> None:
    async with _session_factory()() as db:
        data = await _assets(db, await _resolve_template_id(db, args.adventure))
    print(json.dumps(_summary(data), indent=2, ensure_ascii=False))


async def cmd_export(args: argparse.Namespace) -> None:
    async with _session_factory()() as db:
        data = await _assets(db, await _resolve_template_id(db, args.adventure))
    if args.scene:
        data = _scene_slice(data, args.scene)
    text = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if not args.out:
        print(text)
        return
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"Wrote {args.out}")


async def cmd_validate(args: argparse.Namespace) -> None:
    async with _session_factory()() as db:
        findings = await structural_findings(db, await _resolve_template_id(db, args.adventure))
    if args.json:
        print(json.dumps([f.model_dump() for f in findings], indent=2, ensure_ascii=False))
        return
    print(f"{len(findings)} finding(s):")
    _print_findings(findings)


def cmd_ops(args: argparse.Namespace) -> None:
    names = [args.op] if args.op else sorted(OPERATIONS)
    for name in names:
        if name not in OPERATIONS:
            raise CliError(f"Unknown op '{name}'.")
        model = OPERATION_MODELS.get(name)
        fields = ", ".join(model.model_fields) if model else _OP_FIELDS[name]
        if name == "create_exit":
            fields += ", ref (local name for later '$ref' targets)"
        print(f"{name}: {fields}")


def _load_change_set(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"Cannot read change set {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("operations"), list):
        raise CliError("A change set is an object with an 'operations' list.")
    return data


async def cmd_apply(args: argparse.Namespace) -> None:
    path = Path(args.changes)
    change_set = _load_change_set(path)
    ident = args.adventure or change_set.get("adventure")
    if not ident:
        raise CliError("Name the adventure in the change set ('adventure') or via --adventure.")
    async with _session_factory()() as db:
        template_id = await _resolve_template_id(db, str(ident))
        try:
            result = await apply_change_set(db, template_id, change_set["operations"], path.parent)
        except ChangeSetError as exc:
            await db.rollback()
            raise CliError(f"Rejected, nothing was changed.\n  {exc}") from exc
        print(f"Applied {len(result.applied)} operation(s) to {template_id}:")
        for line in result.applied:
            print(f"  {line}")
        print("New validation findings:")
        _print_findings(result.new_findings)
        if result.new_errors and not args.allow_errors:
            await db.rollback()
            raise CliError("The change set introduces validation errors; nothing was committed.")
        if not args.commit:
            await db.rollback()
            print("Dry run: rolled back. Re-run with --commit to save.")
            return
        await db.commit_for_real()
        print("Committed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="TaleWeaver adventure editor CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sum = sub.add_parser("summary", help="Compact ID index of an adventure")
    p_sum.add_argument("adventure")
    p_exp = sub.add_parser("export", help="Export editor data as JSON")
    p_exp.add_argument("adventure")
    p_exp.add_argument("--scene", help="Only this scene, its exits, neighbours and entities")
    p_exp.add_argument("--out", help="Write to a file instead of stdout")
    p_val = sub.add_parser("validate", help="Run the structural validator")
    p_val.add_argument("adventure")
    p_val.add_argument("--json", action="store_true")
    p_ops = sub.add_parser("ops", help="List change set operations and their fields")
    p_ops.add_argument("op", nargs="?")
    p_app = sub.add_parser("apply", help="Apply a change set (dry run unless --commit)")
    p_app.add_argument("changes", help="Path to the change set JSON")
    p_app.add_argument("--adventure", help="Overrides the change set's 'adventure'")
    p_app.add_argument("--commit", action="store_true", help="Save the changes")
    p_app.add_argument(
        "--allow-errors", action="store_true", help="Commit even with new validation errors"
    )

    args = parser.parse_args()
    commands = {
        "summary": cmd_summary,
        "export": cmd_export,
        "validate": cmd_validate,
        "apply": cmd_apply,
    }
    try:
        if args.command == "ops":
            cmd_ops(args)
            return
        asyncio.run(commands[args.command](args))
    except CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
