"""Turns a parsed blueprint into LLM prompt text and legacy sequence dicts."""

from __future__ import annotations

import json
from typing import Any

from backend.engine.blueprint.models import Blueprint, BlueprintBlock

COLLECTIONS = {
    "scene": "scenes",
    "exit": "exits",
    "npc": "npcs",
    "item": "objects",
    "sequence": "sequences",
    "script": "scripts",
    "sidequest": "quests",
    "award": "awards",
}
_CHILD_COLLECTIONS = {"rule": "soft_rules", "script": "scripts", "ability": "special_actions"}

_RULES = (
    "- Every entity below MUST exist in your JSON output with EXACTLY the given `id` "
    "(scenes -> `scenes`, NPCs -> `npcs`, items -> `objects`, sidequests -> `quests`, "
    "awards -> `awards` with `key` = id, scripts -> `scripts`). Exits are identified by "
    "`from_scene_id` + `to_scene_id`. Sequences are identified by `order`.\n"
    "- `fixed` values are FINAL: copy them verbatim. They are re-applied after generation.\n"
    "- `hints` are suggestions: use them unless they break coherence.\n"
    "- `open` fields and every field that is not listed are yours to fill so the world is "
    "complete, coherent and playable.\n"
    "- `notes` are the author's design intent for that entity: honor them when writing "
    "descriptions, walkthroughs and puzzles.\n"
    "- Fixed scripts and guard expressions are deterministic engine code. Do not rewrite them; "
    "build the world so they work (create every ID, variable and flag they use).\n"
)
_STRICT_TEXT = (
    "- STRICT ADHERENCE: keep the blueprint's structure. Only add scenes, NPCs or items that are "
    "required to make the blueprint playable (e.g. a clue or an exit the author left out).\n"
)
_CREATIVE_TEXT = (
    "- CREATIVE EXPANSION: the blueprint is the backbone. You may add further scenes, NPCs, "
    "items, quests and side content around it.\n"
)


def block_payload(block: BlueprintBlock) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if block.ref and block.kind not in {"world", "protagonist", "exit"}:
        payload["order" if block.kind == "sequence" else "id"] = (
            int(block.ref) if block.kind == "sequence" else block.ref
        )
    for key, value in (
        ("fixed", block.fixed()),
        ("hints", block.hints()),
        ("open", block.open_fields),
        ("notes", block.description),
    ):
        if value:
            payload[key] = value
    for child in block.children:
        collection = _CHILD_COLLECTIONS[child.kind]
        payload.setdefault(collection, []).append(block_payload(child))
    return payload


def blueprint_payload(blueprint: Blueprint) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for kind in ("world", "protagonist"):
        block = blueprint.first(kind)
        if block:
            payload[kind] = block_payload(block)
    for kind, collection in COLLECTIONS.items():
        blocks = blueprint.of_kind(kind)
        if blocks:
            payload[collection] = [block_payload(block) for block in blocks]
    return payload


def render_blueprint_prompt(
    blueprint: Blueprint, missing_ids: list[str], generation_strictness: str
) -> str:
    if blueprint.is_empty:
        return ""
    text = "STRUCTURED BLUEPRINT\nThe author supplied a structured blueprint. Rules:\n" + _RULES
    text += _STRICT_TEXT if generation_strictness == "strict" else _CREATIVE_TEXT
    if missing_ids:
        text += (
            "- These IDs are referenced but not declared. Create a fitting entity for each, "
            f"using exactly this ID: {', '.join(missing_ids)}\n"
        )
    text += "\nBlueprint JSON:\n" + json.dumps(blueprint_payload(blueprint), indent=1)
    divider = "=" * 80
    return f"\n\n{divider}\n{text}\n{divider}\n"


def blueprint_sequences(blueprint: Blueprint) -> list[dict[str, Any]]:
    """Sequence dicts in the shape the sequence prompt builder already understands."""
    sequences: list[dict[str, Any]] = []
    for block in blueprint.of_kind("sequence"):
        order = int(block.ref)
        values = {**block.hints(), **block.fixed()}
        description = block.description or "Follow the sequence blueprint."
        sequences.append(
            {
                "id": f"SEQ_{order}",
                "order": order,
                "title": values.get("title") or f"Sequence {order}",
                "description": description[:500],
                "walkthrough": values.get("walkthrough") or description,
                "end_condition": values.get("end_condition") or "Complete the sequence objectives.",
                "required_item_id": values.get("required_item_id", ""),
                "required_scene_id": values.get("required_scene_id", ""),
                "required_defeated_npc_id": values.get("required_defeated_npc_id", ""),
                "exp_reward": values.get("exp_reward", 100),
            }
        )
    return sequences
