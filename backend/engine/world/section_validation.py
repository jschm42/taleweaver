"""Deterministic checks and fix-ups of a generated region before anything is written.

``prepare_section`` fixes what can be fixed without asking (scene regions, chapter numbers,
init scripts); ``validate_section`` returns the errors that make the region unusable. With
errors the generator retries once with them in the prompt, then gives up and nothing is
applied. Spec: docs/specs/world_sections.md (9.5).
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.engine.world.section_ledger import Ledger

# Inventory pseudo-scenes an item may start in instead of a scene.
_HOLDERS = {"INVENTORY", "PLAYER", "PROTAGONIST"}
_SCRIPT_KEYS = ("on_enter_scene_script", "on_leave_scene_script", "helpers_script")


def _ids(entries: list[dict[str, Any]], key: str = "id") -> list[str]:
    return [str(e.get(key) or "").strip().upper() for e in entries if isinstance(e, dict)]


def prepare_section(manifest: dict[str, Any], section_id: str, ledger: Ledger) -> list[str]:
    """Fixes the region in place; returns notes about what was changed."""
    notes: list[str] = []
    for scene in manifest.get("scenes") or []:
        scene["section_id"] = section_id
    for quest in manifest.get("quests") or []:
        quest["section_id"] = quest.get("section_id") or section_id
    next_order = max(ledger.sequence_orders, default=0) + 1
    for offset, sequence in enumerate(manifest.get("sequences") or []):
        sequence["order"] = next_order + offset
    scripts = manifest.get("scripts") or []
    kept = [s for s in scripts if s.get("trigger") != "on_init"]
    if len(kept) != len(scripts):
        notes.append("Dropped on_init scripts: setup belongs into on_enter_scene scripts.")
    manifest["scripts"] = kept
    return notes


def _collisions(manifest: dict[str, Any], ledger: Ledger) -> list[str]:
    new_ids = [
        *_ids(manifest.get("scenes") or []),
        *_ids(manifest.get("npcs") or []),
        *_ids(manifest.get("objects") or []),
    ]
    errors = [
        f"Id '{i}' already exists in the adventure." for i in new_ids if i in ledger.taken_ids
    ]
    seen: set[str] = set()
    for new_id in new_ids:
        if new_id in seen:
            errors.append(f"Id '{new_id}' is used twice in the region.")
        seen.add(new_id)
    errors.extend(
        f"Quest id '{q}' already exists."
        for q in _ids(manifest.get("quests") or [])
        if q in ledger.quest_ids
    )
    errors.extend(
        f"Award key '{a}' already exists."
        for a in _ids(manifest.get("awards") or [], "key")
        if a in ledger.award_keys
    )
    return errors


def _graph(exits: list[dict[str, Any]]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for ex in exits:
        a, b = str(ex.get("from_scene_id") or ""), str(ex.get("to_scene_id") or "")
        graph[a].add(b)
        if str(ex.get("exit_type") or "").lower() == "bidirectional" or ex.get("is_bidirectional"):
            graph[b].add(a)
    return graph


def _reachable(starts: set[str], graph: dict[str, set[str]]) -> set[str]:
    seen, queue = set(starts), deque(starts)
    while queue:
        for target in graph.get(queue.popleft(), ()):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def _exit_errors(manifest: dict[str, Any], ledger: Ledger, neighbours: list[str]) -> list[str]:
    new_scenes = set(_ids(manifest.get("scenes") or []))
    exits = [e for e in manifest.get("exits") or [] if isinstance(e, dict)]
    errors: list[str] = []
    gateways: list[dict[str, Any]] = []
    for ex in exits:
        ends = {str(ex.get("from_scene_id") or ""), str(ex.get("to_scene_id") or "")}
        unknown = ends - new_scenes - ledger.scene_ids
        if unknown:
            errors.append(
                f"Exit {ex.get('from_scene_id')} -> {ex.get('to_scene_id')} uses unknown scenes."
            )
        elif not ends & new_scenes:
            errors.append(
                f"Exit {ex.get('from_scene_id')} -> {ex.get('to_scene_id')} only joins existing scenes."
            )
        elif ends - new_scenes:
            gateways.append(ex)
    if not gateways:
        return [*errors, "No exit connects the region to an existing scene."]
    touched = {e.get("from_scene_id") for e in gateways} | {e.get("to_scene_id") for e in gateways}
    errors.extend(
        f"No exit connects the region to the neighbouring region {n}."
        for n in neighbours
        if not touched & set(ledger.scenes_of(n))
    )
    starts = {s for s in touched if s in ledger.scene_ids}
    unreachable = new_scenes - _reachable(starts, _graph(exits))
    errors.extend(
        f"Scene '{s}' cannot be reached from the rest of the world." for s in sorted(unreachable)
    )
    return errors


def _placement_errors(manifest: dict[str, Any], ledger: Ledger) -> list[str]:
    places = set(_ids(manifest.get("scenes") or [])) | _HOLDERS
    holders = (
        places | set(_ids(manifest.get("npcs") or [])) | set(_ids(manifest.get("objects") or []))
    )
    errors = [
        f"Character '{n.get('id')}' starts in '{n.get('start_scene_id')}', which is not a new scene."
        for n in manifest.get("npcs") or []
        if str(n.get("start_scene_id") or "").upper() not in places
    ]
    errors.extend(
        f"Item '{o.get('id')}' starts in '{o.get('start_scene_id')}', which is not part of the region."
        for o in manifest.get("objects") or []
        if str(o.get("start_scene_id") or "").upper() not in holders
    )
    items = set(_ids(manifest.get("objects") or [])) | ledger.item_ids
    errors.extend(
        f"Exit {e.get('from_scene_id')} -> {e.get('to_scene_id')} needs item '{e['item_to_unlock']}', which does not exist."
        for e in manifest.get("exits") or []
        if e.get("item_to_unlock") and str(e["item_to_unlock"]).upper() not in items
    )
    return errors


def _script_errors(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for script in manifest.get("scripts") or []:
        errors.extend(
            f"Script '{script.get('id')}': {e}"
            for e in SafeAstInterpreter.check_syntax(str(script.get("code") or ""))
        )
    for scene in manifest.get("scenes") or []:
        for key in _SCRIPT_KEYS:
            code = str(scene.get(key) or "")
            errors.extend(
                f"Scene '{scene.get('id')}' {key}: {e}"
                for e in SafeAstInterpreter.check_syntax(code)
                if code
            )
    return errors


def validate_section(manifest: dict[str, Any], ledger: Ledger, neighbours: list[str]) -> list[str]:
    """Errors that make the generated region unusable; [] when it can be applied."""
    if not manifest.get("scenes"):
        return ["The region has no scenes."]
    return [
        *_collisions(manifest, ledger),
        *_exit_errors(manifest, ledger, neighbours),
        *_placement_errors(manifest, ledger),
        *_script_errors(manifest),
    ]
