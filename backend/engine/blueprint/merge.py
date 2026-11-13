"""Re-applies the blueprint's fixed values to the generated manifest.

The LLM is asked to copy fixed values, but this step is what makes them reliable:
after generation every fixed field is written back over the LLM output, and small
entities the LLM dropped (scripts, rules, abilities, talents, exits, quests,
awards) are
re-created from the blueprint.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.engine.blueprint.models import Blueprint, BlueprintBlock
from backend.engine.blueprint.prompt import COLLECTIONS
from backend.engine.world.dynamic_scene_schemas import (
    build_dynamic_placeholder_scene_id,
    normalize_dynamic_generation,
    normalize_dynamic_zone,
)

_ID_KEYS = {"award": "key", "sequence": "order"}


def _default_script(block: BlueprintBlock) -> dict[str, Any]:
    return {"id": block.ref, "name": block.name or block.ref, "target_id": "", "description": ""}


def _default_rule(block: BlueprintBlock) -> dict[str, Any]:
    return {"id": block.ref, "script": "", "text": "", "guard_expression": "", "max_triggers": None}


def _default_ability(block: BlueprintBlock) -> dict[str, Any]:
    return {
        "id": block.ref,
        "name": block.name or block.ref,
        "description": block.description or block.name or block.ref,
        "action_type": "UTILITY",
        "effects": [],
    }


def _default_talent(block: BlueprintBlock) -> dict[str, Any]:
    return {
        "id": block.ref,
        # Players type the name ("use mind reading"), so an ID-only tag gets a readable one.
        "name": block.name or block.ref.replace("_", " ").title(),
        "description": block.description or block.name or block.ref,
    }


def _default_exit(block: BlueprintBlock) -> dict[str, Any]:
    # Labels are required and name the passage itself, so a generic one fills the gap.
    return {"label": "a passage", "is_bidirectional": True, "is_locked": False}


def _default_quest(block: BlueprintBlock) -> dict[str, Any]:
    text = block.description or block.name or block.ref
    return {
        "id": block.ref,
        "title": block.name or block.ref,
        "description": text,
        "goal": text,
        "exp_reward": 50,
        "status": "open",
    }


def _default_award(block: BlueprintBlock) -> dict[str, Any]:
    text = block.description or block.name or block.ref
    return {
        "key": block.ref,
        "title": block.name or block.ref,
        "description": text,
        "tier": "bronze",
        "requirement": text,
    }


def _default_audio(block: BlueprintBlock) -> dict[str, Any]:
    return {
        "id": block.ref,
        "name": block.name or block.ref.replace("_", " ").title(),
        "prompt": block.description or block.name or block.ref,
    }


# kind -> (factory for a missing entry, fields that must be present before inserting)
_INSERTABLE: dict[str, tuple[Callable[[BlueprintBlock], dict[str, Any]], tuple[str, ...]]] = {
    "script": (_default_script, ("trigger", "code")),
    "rule": (_default_rule, ("condition",)),
    "ability": (_default_ability, ()),
    "talent": (_default_talent, ()),
    "exit": (_default_exit, ("from_scene_id", "to_scene_id")),
    "sidequest": (_default_quest, ()),
    "award": (_default_award, ()),
    "audio": (_default_audio, ()),
}
_CHILD_COLLECTIONS = {
    "rule": "soft_rules",
    "script": "scripts",
    "ability": "special_actions",
    "talent": "talents",
}


def apply_blueprint(manifest: dict[str, Any], blueprint: Blueprint) -> list[str]:
    """Write fixed blueprint values into ``manifest``. Returns human-readable violations."""
    violations: list[str] = []
    world = blueprint.first("world")
    if world:
        _apply_fixed(manifest, world)
        _apply_world_hints(manifest, world)
    protagonist = blueprint.first("protagonist")
    if protagonist and isinstance(manifest.get("protagonist"), dict):
        _apply_fixed(manifest["protagonist"], protagonist)
        _apply_children(manifest["protagonist"], protagonist, violations)
    for kind, collection in COLLECTIONS.items():
        entries = manifest.setdefault(collection, [])
        for block in blueprint.of_kind(kind):
            if kind == "exit" and not _exit_scenes_exist(manifest, block, violations):
                continue
            entry = _find_or_insert(entries, block, violations)
            if entry is not None:
                _apply_children(entry, block, violations)
    _strip_virtual_dynamic_scenes(manifest, blueprint)
    return violations


def _strip_virtual_dynamic_scenes(manifest: dict[str, Any], blueprint: Blueprint) -> None:
    """Remove LLM-fabricated DYN_* or dynamic-target scenes unless explicitly declared as [Scene]."""
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list):
        return
    declared_scenes = {b.ref.upper() for b in blueprint.of_kind("scene") if b.ref}
    dynamic_targets: set[str] = set()
    for ex in manifest.get("exits") or []:
        if not isinstance(ex, dict) or not isinstance(ex.get("dynamic_zone"), dict):
            continue
        to_id = str(ex.get("to_scene_id") or "").strip().upper()
        zone_id = str(ex["dynamic_zone"].get("zone_id") or "").strip().upper()
        if to_id:
            dynamic_targets.add(to_id)
        if zone_id:
            dynamic_targets.add(zone_id)

    manifest["scenes"] = [
        s
        for s in scenes
        if not (
            isinstance(s, dict)
            and (
                (sid := str(s.get("id") or "").strip().upper()).startswith("DYN_")
                or (sid in dynamic_targets and sid not in declared_scenes)
            )
        )
    ]


def _is_dynamic_exit_block(block: BlueprintBlock) -> bool:
    fixed = block.fixed()
    return block.kind == "exit" and any(
        k == "dynamic_zone" or k.startswith("dynamic_zone.") for k in fixed
    )


def _exit_scenes_exist(
    manifest: dict[str, Any], block: BlueprintBlock, violations: list[str]
) -> bool:
    scene_ids = {str(scene.get("id") or "").upper() for scene in manifest.get("scenes") or []}
    ends = (block.fixed().get("from_scene_id"), block.fixed().get("to_scene_id"))
    if _is_dynamic_exit_block(block):
        if ends[0] in scene_ids:
            return True
        violations.append(
            f"exit {ends[0]} -> {ends[1]} skipped: origin scene missing in the generated world."
        )
        return False
    if all(end in scene_ids for end in ends):
        return True
    violations.append(f"exit {ends[0]} -> {ends[1]} skipped: scene missing in the generated world.")
    return False


def _apply_children(entry: dict[str, Any], block: BlueprintBlock, violations: list[str]) -> None:
    for child in block.children:
        entries = entry.get(_CHILD_COLLECTIONS[child.kind])
        if not isinstance(entries, list):
            entries = []
            entry[_CHILD_COLLECTIONS[child.kind]] = entries
        _find_or_insert(entries, child, violations)


def _find_or_insert(
    entries: list[Any], block: BlueprintBlock, violations: list[str]
) -> dict[str, Any] | None:
    entry = _find_entry(entries, block)
    if entry is None:
        entry = _insert_entry(entries, block)
    if entry is None:
        violations.append(f"{block.kind} '{block.ref}' is missing in the generated world.")
        return None
    _apply_fixed(entry, block)
    return entry


def _find_entry(entries: list[Any], block: BlueprintBlock) -> dict[str, Any] | None:
    for entry in entries:
        if isinstance(entry, dict) and _matches(entry, block):
            return entry
    return None


def _matches(entry: dict[str, Any], block: BlueprintBlock) -> bool:
    if block.kind == "exit":
        fixed = block.fixed()
        pair = (fixed.get("from_scene_id"), fixed.get("to_scene_id"))
        found = (entry.get("from_scene_id"), entry.get("to_scene_id"))
        if found in (pair, pair[::-1]):
            return True
        fixed_zone = str(fixed.get("dynamic_zone.zone_id") or "").strip().lower()
        entry_zone = entry.get("dynamic_zone")
        if (
            fixed_zone
            and isinstance(entry_zone, dict)
            and entry.get("from_scene_id") == fixed.get("from_scene_id")
        ):
            return str(entry_zone.get("zone_id") or "").strip().lower() == fixed_zone
        return False
    if block.kind == "sequence":
        return str(entry.get("order")) == block.ref
    key = _ID_KEYS.get(block.kind, "id")
    return str(entry.get(key) or "").strip().upper() == block.ref


def _insert_entry(entries: list[Any], block: BlueprintBlock) -> dict[str, Any] | None:
    factory_and_needs = _INSERTABLE.get(block.kind)
    if factory_and_needs is None:
        return None
    factory, needs = factory_and_needs
    fixed = block.fixed()
    if any(field not in fixed for field in needs):
        return None
    entry = factory(block)
    entries.append(entry)
    return entry


def _apply_world_hints(manifest: dict[str, Any], world: BlueprintBlock) -> None:
    hints = world.hints()
    for key in ("selected_image_styles", "selected_tone"):
        if key in hints:
            manifest.setdefault(key, hints[key])


def _apply_dynamic_exit_fixed(entry: dict[str, Any], block: BlueprintBlock) -> None:
    raw_zone = dict(entry["dynamic_zone"])
    raw_zone.setdefault("zone_id", "zone")
    raw_zone.setdefault("theme", block.description or entry.get("label") or "Uncharted zone")
    zone = normalize_dynamic_zone(raw_zone)
    if zone is None:
        entry["dynamic_zone"] = None
        return
    entry["dynamic_zone"] = zone
    entry["to_scene_id"] = build_dynamic_placeholder_scene_id(
        zone["zone_id"],
        1,
        1,
        f"{entry.get('from_scene_id') or ''}{entry.get('label') or ''}",
    )


def _apply_fixed(entry: dict[str, Any], block: BlueprintBlock) -> None:
    for path, value in block.fixed().items():
        _set_path(entry, path, value)
    if block.kind == "sequence" and "guard_expression" in block.fixed():
        entry["completion_guard_expression"] = block.fixed()["guard_expression"]
    if block.kind == "exit" and isinstance(entry.get("dynamic_zone"), dict):
        _apply_dynamic_exit_fixed(entry, block)
    if block.kind == "world" and isinstance(entry.get("dynamic_generation"), dict):
        entry["dynamic_generation"] = normalize_dynamic_generation(entry["dynamic_generation"])


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    *parents, leaf = path.split(".")
    for part in parents:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[leaf] = value
