"""Structural adventure-template validator.

Pure-function linter that walks the editor payload (AdventureTemplateDebugResponse)
and emits ValidationFinding objects. No LLM, no I/O — fully deterministic and fast.

The checks are intentionally conservative: only emit findings the engine can prove
from the data structure. Speculative or narrative judgments belong in the AI pass.
"""

import logging
from collections import deque
from typing import Any, Iterable, Optional

from backend.core.config import settings
from backend.schemas.validation import ValidationFinding

logger = logging.getLogger(__name__)


# Hard caps that mirror the engine-side thresholds. Tuned to the values used
# in world_schemas.py / world_generator.py.
_NPC_OVERPOWERED_HP = 200
_NPC_OVERPOWERED_STRENGTH = 18
_NPC_OVERPOWERED_AC = 20
_DECORATIVE_OBJECTS_CAP = 7
_CONTAINER_INVENTORY_CAP = 10
_RULES_MIN_LENGTH = 100
_WALKTHROUGH_MIN_LENGTH = 50


def _f(
    severity: str,
    code: str,
    message: str,
    location: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> ValidationFinding:
    return ValidationFinding(
        severity=severity,
        code=code,
        message=message,
        location=location,
        context=context,
    )


def _scene_id(scene: dict[str, Any]) -> Optional[str]:
    return scene.get("id") or scene.get("scene_id")


def _exit_scene_ids(exit_: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    return exit_.get("from_scene_id"), exit_.get("to_scene_id")


def _exit_is_bidirectional(exit_: dict[str, Any]) -> bool:
    """True when the exit can be traversed in both directions.

    Matches the engine's default semantics: an exit row with exit_type
    'bidirectional' or with no explicit one_way flag is bidirectional.
    """
    exit_type = (exit_.get("exit_type") or "").lower()
    if exit_type == "one_way":
        return False
    return True


def _entity_id(entity: dict[str, Any]) -> Optional[str]:
    return entity.get("id") or entity.get("entity_id")


def _entity_kind(entity: dict[str, Any]) -> str:
    """Return 'NPC', 'OBJECT', or 'UNKNOWN' for an entity dict."""
    et = (entity.get("entity_type") or entity.get("type") or "").upper()
    if et in {"NPC", "OBJECT"}:
        return et
    if entity.get("npc_type"):
        return "NPC"
    if entity.get("item_type"):
        return "OBJECT"
    return "UNKNOWN"


def _entity_lock_keys(entity: dict[str, Any]) -> list[str]:
    """Return the lock fields present on a locked container / exit / object."""
    md = entity.get("metadata_json") or {}
    keys = []
    for k in ("code_to_unlock", "item_to_unlock", "rule_to_unlock"):
        val = entity.get(k) or md.get(k)
        if val:
            keys.append(k)
    return keys


def _bfs_reachable(start_scene_id: Optional[str], exits: Iterable[dict[str, Any]]) -> set[str]:
    """BFS from the start scene along all bidirectional exits.

    One-way exits only contribute an edge in the direction they declare, but
    for reachability we still walk both endpoints because the engine mirrors
    one-way rows in only one direction. We keep the simple model here: every
    exit's ``to_scene_id`` is reachable from its ``from_scene_id``.
    """
    if not start_scene_id:
        return set()
    visited: set[str] = {start_scene_id}
    queue: deque[str] = deque([start_scene_id])
    adjacency: dict[str, set[str]] = {}
    for exit_ in exits:
        a, b = _exit_scene_ids(exit_)
        if not a or not b:
            continue
        adjacency.setdefault(a, set()).add(b)
        if _exit_is_bidirectional(exit_):
            adjacency.setdefault(b, set()).add(a)
    while queue:
        cur = queue.popleft()
        for nxt in adjacency.get(cur, ()):  # type: ignore[arg-type]
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return visited


def _check_unreachable_scenes(
    scenes: list[dict[str, Any]],
    exits: list[dict[str, Any]],
    start_scene_id: Optional[str],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if not scenes:
        return findings
    scene_ids = {_scene_id(s) for s in scenes if _scene_id(s)}
    if not start_scene_id or start_scene_id not in scene_ids:
        findings.append(
            _f(
                "error",
                "missing_start_scene",
                "Adventure has no reachable start scene.",
                location=f"scene:{start_scene_id}" if start_scene_id else None,
                context={"start_scene_id": start_scene_id, "scene_count": len(scenes)},
            )
        )
        return findings
    reachable = _bfs_reachable(start_scene_id, exits)
    for sid in sorted(scene_ids - reachable):
        findings.append(
            _f(
                "error",
                "unreachable_scene",
                f"Scene '{sid}' is not reachable from the start scene.",
                location=f"scene:{sid}",
                context={"scene_id": sid, "start_scene_id": start_scene_id},
            )
        )
    return findings


def _check_exit_targets_exist(
    scenes: list[dict[str, Any]],
    exits: list[dict[str, Any]],
) -> list[ValidationFinding]:
    scene_ids = {_scene_id(s) for s in scenes if _scene_id(s)}
    findings: list[ValidationFinding] = []
    for ex in exits:
        from_id, to_id = _exit_scene_ids(ex)
        if to_id and to_id not in scene_ids:
            findings.append(
                _f(
                    "error",
                    "exit_to_missing_scene",
                    f"Exit references scene '{to_id}' which does not exist.",
                    location=f"exit:{ex.get('id', '?')}",
                    context={"exit_id": ex.get("id"), "missing_scene": to_id},
                )
            )
        if from_id and from_id not in scene_ids:
            findings.append(
                _f(
                    "error",
                    "exit_from_missing_scene",
                    f"Exit originates from scene '{from_id}' which does not exist.",
                    location=f"exit:{ex.get('id', '?')}",
                    context={"exit_id": ex.get("id"), "missing_scene": from_id},
                )
            )
    return findings


def _check_exit_labels(exits: list[dict[str, Any]]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for ex in exits:
        label = (ex.get("label") or "").strip()
        if not label:
            findings.append(
                _f(
                    "warn",
                    "exit_without_label",
                    "Exit has no label — players will see a blank transition.",
                    location=f"exit:{ex.get('id', '?')}",
                    context={"exit_id": ex.get("id")},
                )
            )
    return findings


def _check_duplicate_ids(
    scenes: list[dict[str, Any]],
    entities: list[dict[str, Any]],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    seen: dict[str, str] = {}
    for s in scenes:
        sid = _scene_id(s)
        if sid and sid in seen:
            findings.append(
                _f(
                    "error",
                    "duplicate_scene_id",
                    f"Scene id '{sid}' is used more than once.",
                    location=f"scene:{sid}",
                    context={"scene_id": sid},
                )
            )
        elif sid:
            seen[sid] = "scene"
    seen_e: dict[str, str] = {}
    for e in entities:
        eid = _entity_id(e)
        if eid and eid in seen_e:
            findings.append(
                _f(
                    "error",
                    "duplicate_entity_id",
                    f"Entity id '{eid}' is used more than once.",
                    location=f"entity:{eid}",
                    context={"entity_id": eid},
                )
            )
        elif eid:
            seen_e[eid] = _entity_kind(e)
    return findings


def _check_item_references(
    entities: list[dict[str, Any]],
) -> list[ValidationFinding]:
    """Verify that every ``item_to_unlock`` reference points at a known entity
    AND that ``code_to_unlock`` / ``rule_to_unlock`` are non-empty on entities
    that the engine treats as locked."""
    known_ids = {_entity_id(e) for e in entities if _entity_id(e)}
    findings: list[ValidationFinding] = []
    for e in entities:
        eid = _entity_id(e) or "?"
        kind = _entity_kind(e)
        # item_to_unlock
        target = e.get("item_to_unlock") or (e.get("metadata_json") or {}).get("item_to_unlock")
        if target and target not in known_ids:
            findings.append(
                _f(
                    "error",
                    "missing_item_ref",
                    f"{kind} '{eid}' references unlock-item '{target}' which does not exist.",
                    location=f"entity:{eid}",
                    context={"entity_id": eid, "missing_ref": target},
                )
            )
        # rule_to_unlock references (rule target is an NPC id when of the form
        # 'Protagonist defeats NPC_X'; we treat NPC_X as a soft reference).
        rule = e.get("rule_to_unlock") or (e.get("metadata_json") or {}).get("rule_to_unlock")
        if isinstance(rule, str) and "defeats" in rule.lower():
            # very rough heuristic; skip false positives
            tokens = [t for t in rule.replace(",", " ").split() if t.startswith("NPC_") or t.startswith("ENEMY_")]
            for tok in tokens:
                if tok not in known_ids:
                    findings.append(
                        _f(
                            "warn",
                            "rule_to_unlock_missing_target",
                            f"{kind} '{eid}' has rule_to_unlock referencing unknown NPC '{tok}'.",
                            location=f"entity:{eid}",
                            context={"entity_id": eid, "missing_npc": tok},
                        )
                    )
        # code_to_unlock / rule_to_unlock may simply be empty strings — that's
        # fine. The engine enforces locked-ness; if the user claims something is
        # locked via metadata but provides no key, warn them.
        md = e.get("metadata_json") or {}
        if md.get("locked") is True and not _entity_lock_keys(e):
            findings.append(
                _f(
                    "warn",
                    "locked_but_no_unlock_key",
                    f"{kind} '{eid}' is marked locked but has no code/item/rule unlock key.",
                    location=f"entity:{eid}",
                    context={"entity_id": eid},
                )
            )
    return findings


def _check_container_inventory(
    entities: list[dict[str, Any]],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    known_ids = {_entity_id(e) for e in entities if _entity_id(e)}
    for e in entities:
        if _entity_kind(e) != "OBJECT":
            continue
        item_type = (e.get("item_type") or "").upper()
        if item_type != "CONTAINER":
            continue
        eid = _entity_id(e) or "?"
        inv = e.get("inventory")
        if not isinstance(inv, list):
            continue
        if len(inv) > _CONTAINER_INVENTORY_CAP:
            findings.append(
                _f(
                    "warn",
                    "container_inventory_too_large",
                    f"Container '{eid}' has {len(inv)} items — consider splitting.",
                    location=f"entity:{eid}",
                    context={"entity_id": eid, "count": len(inv)},
                )
            )
        for ref in inv:
            target = ref.get("item_id") if isinstance(ref, dict) else None
            if target and target not in known_ids:
                findings.append(
                    _f(
                        "error",
                        "container_inventory_orphan",
                        f"Container '{eid}' lists unknown item '{target}' in its inventory.",
                        location=f"entity:{eid}",
                        context={"entity_id": eid, "missing_ref": target},
                    )
                )
    return findings


def _check_constructable_ingredients(
    entities: list[dict[str, Any]],
) -> list[ValidationFinding]:
    """Validate CONSTRUCTABLE objects.

    A CONSTRUCTABLE is a hidden item that materializes deterministically when the
    player combines all of its ``combination_ingredients``. The engine requires
    at least two distinct ingredients that reference real entities, and the
    constructable should start hidden (reveal is automatic, so ``reveal_rule``
    /``reveals_item_id`` are ignored for this type).
    """
    known_ids = {_entity_id(e) for e in entities if _entity_id(e)}
    findings: list[ValidationFinding] = []
    for e in entities:
        if _entity_kind(e) != "OBJECT":
            continue
        if (e.get("item_type") or "").upper() != "CONSTRUCTABLE":
            continue
        eid = _entity_id(e) or "?"
        raw = e.get("combination_ingredients")
        ingredients = [i for i in (raw or []) if isinstance(i, str) and i.strip()]
        distinct = {i.strip() for i in ingredients}

        if len(ingredients) < 2:
            findings.append(
                _f(
                    "error",
                    "constructable_needs_ingredients",
                    f"CONSTRUCTABLE '{eid}' requires at least 2 combination_ingredients (found {len(ingredients)}).",
                    location=f"entity:{eid}",
                    context={"entity_id": eid, "count": len(ingredients)},
                )
            )
        elif len(distinct) != len(ingredients):
            findings.append(
                _f(
                    "warn",
                    "constructable_duplicate_ingredients",
                    f"CONSTRUCTABLE '{eid}' has duplicate ingredient ids.",
                    location=f"entity:{eid}",
                    context={"entity_id": eid, "ingredients": ingredients},
                )
            )

        for ref in ingredients:
            if ref.strip() not in known_ids:
                findings.append(
                    _f(
                        "error",
                        "constructable_ingredient_missing",
                        f"CONSTRUCTABLE '{eid}' references unknown ingredient '{ref}'.",
                        location=f"entity:{eid}",
                        context={"entity_id": eid, "missing_ref": ref},
                    )
                )

        if not e.get("is_hidden"):
            findings.append(
                _f(
                    "warn",
                    "constructable_not_hidden",
                    f"CONSTRUCTABLE '{eid}' should start is_hidden=true (it auto-reveals on construction).",
                    location=f"entity:{eid}",
                    context={"entity_id": eid},
                )
            )
    return findings


def _check_npc_stats(entities: list[dict[str, Any]]) -> list[ValidationFinding]:
    findings = []
    for e in entities:
        if _entity_kind(e) != "NPC":
            continue
        eid = _entity_id(e) or "?"
        hp = int(e.get("hp") or 0)
        stamina = int(e.get("stamina") or 0)
        mana = int(e.get("mana") or 0)
        strength = int(e.get("strength") or 0)
        ac = int(e.get("armor_class") or 0)

        if hp == 0 or (stamina == 0 and mana == 0):
            findings.append(
                _f(
                    "warn",
                    "npc_zero_stats",
                    f"NPC '{eid}' has zero vital stats and may be un-interactable.",
                    location=f"entity:{eid}",
                    context={"entity_id": eid, "hp": hp, "stamina": stamina, "mana": mana},
                )
            )
        if hp > _NPC_OVERPOWERED_HP or strength > _NPC_OVERPOWERED_STRENGTH or ac > _NPC_OVERPOWERED_AC:
            findings.append(
                _f(
                    "warn",
                    "npc_overpowered",
                    f"NPC '{eid}' has unusually high stats (hp={hp}, str={strength}, AC={ac}).",
                    location=f"entity:{eid}",
                    context={
                        "entity_id": eid,
                        "hp": hp,
                        "strength": strength,
                        "armor_class": ac,
                    },
                )
            )
    return findings


def _check_image_coverage(
    adventure: dict[str, Any],
    scenes: list[dict[str, Any]],
    entities: list[dict[str, Any]],
) -> list[ValidationFinding]:
    """Warn when image-generation is enabled but coverage is < 100%."""
    findings: list[ValidationFinding] = []
    if adventure.get("generate_scene_images") and scenes:
        missing = [s for s in scenes if not (s.get("image_url") or "").strip()]
        if missing:
            findings.append(
                _f(
                    "warn",
                    "scene_image_coverage",
                    f"{len(missing)} of {len(scenes)} scenes have no image despite image generation being enabled.",
                    context={
                        "missing_count": len(missing),
                        "total_count": len(scenes),
                        "missing_ids": [_scene_id(s) for s in missing[:10]],
                    },
                )
            )
    if adventure.get("generate_npc_images"):
        npcs = [e for e in entities if _entity_kind(e) == "NPC"]
        missing = [e for e in npcs if not (e.get("image_url") or "").strip()]
        if missing:
            findings.append(
                _f(
                    "warn",
                    "npc_image_coverage",
                    f"{len(missing)} of {len(npcs)} NPCs have no image despite image generation being enabled.",
                    context={
                        "missing_count": len(missing),
                        "total_count": len(npcs),
                        "missing_ids": [_entity_id(e) for e in missing[:10]],
                    },
                )
            )
    if adventure.get("generate_item_images"):
        objects_ = [e for e in entities if _entity_kind(e) == "OBJECT"]
        missing = [e for e in objects_ if not (e.get("image_url") or "").strip()]
        if missing:
            findings.append(
                _f(
                    "warn",
                    "object_image_coverage",
                    f"{len(missing)} of {len(objects_)} objects have no image despite image generation being enabled.",
                    context={
                        "missing_count": len(missing),
                        "total_count": len(objects_),
                        "missing_ids": [_entity_id(e) for e in missing[:10]],
                    },
                )
            )
    return findings


def _check_rpg_mode_with_combatants(
    adventure: dict[str, Any],
    entities: list[dict[str, Any]],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    mode = (adventure.get("rule_enforcement_mode") or "rpg").lower()
    if mode == "rpg":
        return findings
    has_attackable_npc = any(
        _entity_kind(e) == "NPC" and e.get("is_attackable") for e in entities
    )
    has_weapon = any(
        _entity_kind(e) == "OBJECT" and (e.get("item_type") or "").upper() == "WEAPON"
        for e in entities
    )
    if has_attackable_npc or has_weapon:
        kind_bits = []
        if has_attackable_npc:
            kind_bits.append("attackable NPC")
        if has_weapon:
            kind_bits.append("weapon object")
        findings.append(
            _f(
                "warn",
                "rpg_mode_required_for_combat",
                f"Adventure is in '{mode}' mode but contains {' + '.join(kind_bits)}. "
                "Consider switching to rule_enforcement_mode='rpg'.",
                context={"mode": mode, "has_attackable_npc": has_attackable_npc, "has_weapon": has_weapon},
            )
        )
    return findings


def _check_empty_story_fields(adventure: dict[str, Any]) -> list[ValidationFinding]:
    fields = (
        "teaser",
        "rules",
        "plot",
        "intro_text",
        "walkthrough",
        "completed_condition",
        "gameover_condition",
        "tts_director_notes",
    )
    findings: list[ValidationFinding] = []
    for f in fields:
        val = (adventure.get(f) or "").strip()
        if not val:
            findings.append(
                _f(
                    "warn",
                    "empty_story_field",
                    f"Story field '{f}' is empty.",
                    context={"field": f},
                )
            )
            continue
        if f == "rules" and len(val) < _RULES_MIN_LENGTH:
            findings.append(
                _f(
                    "warn",
                    "rules_too_short",
                    f"Story field 'rules' is only {len(val)} characters — RPG mode typically needs more guidance.",
                    context={"field": f, "length": len(val)},
                )
            )
        if f == "walkthrough" and len(val) < _WALKTHROUGH_MIN_LENGTH:
            findings.append(
                _f(
                    "warn",
                    "walkthrough_too_short",
                    f"Story field 'walkthrough' is only {len(val)} characters — secret GM notes look thin.",
                    context={"field": f, "length": len(val)},
                )
            )
    return findings


def _check_decorative_objects_overflow(scenes: list[dict[str, Any]]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for s in scenes:
        decos = s.get("decorative_objects") or []
        if isinstance(decos, list) and len(decos) > _DECORATIVE_OBJECTS_CAP:
            sid = _scene_id(s) or "?"
            findings.append(
                _f(
                    "warn",
                    "decorative_objects_overflow",
                    f"Scene '{sid}' has {len(decos)} decorative objects (cap is {_DECORATIVE_OBJECTS_CAP}).",
                    location=f"scene:{sid}",
                    context={"scene_id": sid, "count": len(decos)},
                )
            )
    return findings


def _check_switch_state_consistency(entities: list[dict[str, Any]]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for e in entities:
        item_type = (e.get("item_type") or "").upper()
        if item_type != "SWITCH":
            continue
        eid = _entity_id(e) or "?"
        states = e.get("switch_states")
        initial = e.get("switch_initial_state")
        if not states or not isinstance(states, list) or len(states) < 2:
            findings.append(
                _f(
                    "warn",
                    "switch_missing_states",
                    f"Switch '{eid}' has fewer than two states defined.",
                    location=f"entity:{eid}",
                    context={"entity_id": eid},
                )
            )
        elif initial is not None and initial not in states:
            findings.append(
                _f(
                    "warn",
                    "switch_unreachable_state",
                    f"Switch '{eid}' initial state '{initial}' is not in its states list.",
                    location=f"entity:{eid}",
                    context={"entity_id": eid, "initial_state": initial, "states": states},
                )
            )
    return findings


def _check_empty_adventure(adventure: dict[str, Any]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    # Story field presence is a loose signal — titles/short adventures are valid.
    title = (adventure.get("title") or "").strip()
    if not title:
        findings.append(
            _f(
                "error",
                "empty_adventure",
                "Adventure has no title.",
            )
        )
    return findings


def _check_quest_references(
    adventure: dict[str, Any],
    entities: list[dict[str, Any]],
) -> list[ValidationFinding]:
    quests = adventure.get("quests") or []
    if not isinstance(quests, list) or not quests:
        return []
    scene_ids: set[str] = set()
    entity_ids = {_entity_id(e) for e in entities if _entity_id(e)}
    known_refs = set(entity_ids)
    findings: list[ValidationFinding] = []
    for i, q in enumerate(quests):
        if not isinstance(q, dict):
            continue
        qid = q.get("id") or f"quest_{i}"
        for ref_key in ("target_scene_id", "target_object_id", "target_npc_id", "trigger_scene_id"):
            target = q.get(ref_key)
            if target and target not in known_refs and target not in scene_ids:
                findings.append(
                    _f(
                        "error",
                        "quest_references_missing_entity",
                        f"Quest '{qid}' references unknown '{ref_key}'='{target}'.",
                        context={"quest_id": qid, "ref_key": ref_key, "missing": target},
                    )
                )
    return findings


def validate_adventure(payload: dict[str, Any]) -> list[ValidationFinding]:
    """Run the structural validator over a debug payload.

    Accepts either an AdventureTemplateDebugResponse instance or a plain dict
    with the same shape (``adventure``, ``scenes``, ``npcs``, ``objects``,
    ``exits``).
    """
    # Pydantic v2 BaseModel supports .model_dump(); dicts pass through unchanged.
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    adventure = payload.get("adventure") or {}
    scenes = payload.get("scenes") or []
    npcs = payload.get("npcs") or []
    objects_ = payload.get("objects") or []
    exits = payload.get("exits") or []
    entities = list(npcs) + list(objects_)
    if payload.get("entities_all"):
        entities = list(payload["entities_all"])

    start_scene_id = adventure.get("start_scene_id")

    findings: list[ValidationFinding] = []
    findings.extend(_check_empty_adventure(adventure))
    findings.extend(_check_unreachable_scenes(scenes, exits, start_scene_id))
    findings.extend(_check_exit_targets_exist(scenes, exits))
    findings.extend(_check_exit_labels(exits))
    findings.extend(_check_duplicate_ids(scenes, entities))
    findings.extend(_check_item_references(entities))
    findings.extend(_check_container_inventory(entities))
    findings.extend(_check_constructable_ingredients(entities))
    findings.extend(_check_npc_stats(entities))
    findings.extend(_check_image_coverage(adventure, scenes, entities))
    findings.extend(_check_rpg_mode_with_combatants(adventure, entities))
    findings.extend(_check_empty_story_fields(adventure))
    findings.extend(_check_decorative_objects_overflow(scenes))
    findings.extend(_check_switch_state_consistency(entities))
    findings.extend(_check_quest_references(adventure, entities))

    # Sort: errors first, then by code (stable order for UI).
    severity_order = {"error": 0, "warn": 1}
    findings.sort(key=lambda f: (severity_order.get(f.severity, 99), f.code, f.location or ""))
    return findings


__all__ = ["validate_adventure", "ValidationFinding", "settings"]