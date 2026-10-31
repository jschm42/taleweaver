"""Structural syntax validator for TaleWeaver scripts and guard expressions.

Pure-function linter that walks the editor payload and statically validates:
1. Script code (mode='exec') using SafeAstInterpreter.check_syntax
2. Guard expressions (mode='eval') using SafeAstInterpreter.check_expression_syntax

Emits ValidationFinding objects with codes 'script_syntax_error' and 'guard_syntax_error'.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.core.dialog_validator import check_dialog_handlers
from backend.core.helpers_validator import check_helper_blocks, helper_blocks
from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.schemas.validation import ValidationFinding


def _scene_id(scene: dict[str, Any]) -> Optional[str]:
    return scene.get("id") or scene.get("scene_id")


def _entity_id(entity: dict[str, Any]) -> Optional[str]:
    return entity.get("id") or entity.get("entity_id")


def _entity_kind(entity: dict[str, Any]) -> str:
    et = (entity.get("entity_type") or entity.get("type") or "").upper()
    if et in {"NPC", "OBJECT"}:
        return et
    if entity.get("npc_type"):
        return "NPC"
    if entity.get("item_type"):
        return "OBJECT"
    return "UNKNOWN"


def _validate_script_code(
    code: Any,
    field_name: str,
    location: Optional[str] = None,
    extra_context: Optional[dict[str, Any]] = None,
) -> list[ValidationFinding]:
    """Validate executable Python script syntax and sandbox rules."""
    if not isinstance(code, str) or not code.strip():
        return []

    errors = SafeAstInterpreter.check_syntax(code)
    if not errors:
        return []

    ctx: dict[str, Any] = {"field": field_name, "errors": errors}
    if extra_context:
        ctx.update(extra_context)

    first_err = errors[0]
    loc_desc = f" in {location}" if location else ""
    return [
        ValidationFinding(
            severity="error",
            code="script_syntax_error",
            message=f"Syntax error in script '{field_name}'{loc_desc}: {first_err}",
            location=location,
            context=ctx,
        )
    ]


def _validate_guard_expression(
    expr: Any,
    field_name: str,
    location: Optional[str] = None,
    extra_context: Optional[dict[str, Any]] = None,
) -> list[ValidationFinding]:
    """Validate boolean guard Python expression syntax and sandbox rules."""
    if not isinstance(expr, str) or not expr.strip():
        return []

    errors = SafeAstInterpreter.check_expression_syntax(expr)
    if not errors:
        return []

    ctx: dict[str, Any] = {"field": field_name, "expression": expr, "errors": errors}
    if extra_context:
        ctx.update(extra_context)

    first_err = errors[0]
    loc_desc = f" in {location}" if location else ""
    return [
        ValidationFinding(
            severity="error",
            code="guard_syntax_error",
            message=f"Syntax error in guard '{field_name}'{loc_desc}: {first_err}",
            location=location,
            context=ctx,
        )
    ]


def _init_script(adventure: dict[str, Any], payload: dict[str, Any]) -> Any:
    manifest = adventure.get("original_manifest")
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    return (
        adventure.get("init_script")
        or manifest_dict.get("init_script")
        or payload.get("init_script")
    )


def _check_adventure_level(
    adventure: dict[str, Any],
    payload: dict[str, Any],
) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    manifest = adventure.get("original_manifest")
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    init_script = _init_script(adventure, payload)
    findings.extend(
        _validate_script_code(
            init_script,
            "init_script",
            location="adventure",
            extra_context={"scope": "adventure"},
        )
    )

    scripts = (
        adventure.get("scripts") or manifest_dict.get("scripts") or payload.get("scripts") or []
    )
    if isinstance(scripts, list):
        for s in scripts:
            if not isinstance(s, dict):
                continue
            s_id = s.get("id") or s.get("name") or "unnamed_script"
            loc = f"script:{s_id}"
            code = s.get("code")
            extra = {
                "script_id": s_id,
                "trigger": s.get("trigger"),
                "target_id": s.get("target_id") or s.get("target"),
            }
            findings.extend(_validate_script_code(code, "code", location=loc, extra_context=extra))

    for guard_field in ("completed_guard_expression", "gameover_guard_expression"):
        expr = adventure.get(guard_field) or manifest_dict.get(guard_field)
        findings.extend(
            _validate_guard_expression(
                expr,
                guard_field,
                location="adventure",
                extra_context={"scope": "adventure"},
            )
        )

    return findings


def _check_scenes(scenes: list[dict[str, Any]]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        sid = _scene_id(scene) or "?"
        loc = f"scene:{sid}"
        meta = scene.get("metadata_json")
        meta_dict = meta if isinstance(meta, dict) else {}
        for field in ("on_enter_scene_script", "on_leave_scene_script", "helpers_script"):
            code = scene.get(field) or meta_dict.get(field)
            findings.extend(
                _validate_script_code(
                    code,
                    field,
                    location=loc,
                    extra_context={"scene_id": sid},
                )
            )
    return findings


def _check_exits(exits: list[dict[str, Any]]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for ex in exits:
        if not isinstance(ex, dict):
            continue
        eid = ex.get("id") or f"{ex.get('from_scene_id')}->{ex.get('to_scene_id')}"
        loc = f"exit:{eid}"
        meta = ex.get("metadata_json")
        meta_dict = meta if isinstance(meta, dict) else {}

        for guard_field in ("unlock_expression", "guard_expression"):
            expr = ex.get(guard_field) or meta_dict.get(guard_field)
            findings.extend(
                _validate_guard_expression(
                    expr,
                    guard_field,
                    location=loc,
                    extra_context={"exit_id": eid},
                )
            )

        for script_field in (
            "on_open_exit_script",
            "on_exit_used_script",
            "on_unlock_success_script",
            "on_unlock_failure_script",
        ):
            code = ex.get(script_field) or meta_dict.get(script_field)
            findings.extend(
                _validate_script_code(
                    code,
                    script_field,
                    location=loc,
                    extra_context={"exit_id": eid},
                )
            )
    return findings


def _check_switch_transitions(
    transitions: Any,
    loc: str,
    eid: str,
) -> list[ValidationFinding]:
    if not isinstance(transitions, list):
        return []
    findings: list[ValidationFinding] = []
    for idx, t in enumerate(transitions):
        if not isinstance(t, dict):
            continue
        gates = t.get("gates")
        gates_dict = gates if isinstance(gates, dict) else {}
        expr = (
            t.get("expression")
            or t.get("condition")
            or t.get("guard_expression")
            or gates_dict.get("expression")
            or gates_dict.get("condition")
        )
        findings.extend(
            _validate_guard_expression(
                expr,
                f"transition_{idx}_guard",
                location=loc,
                extra_context={"entity_id": eid, "transition_index": idx},
            )
        )
        for t_field in ("on_success_script", "on_failure_script"):
            t_code = t.get(t_field)
            findings.extend(
                _validate_script_code(
                    t_code,
                    f"transition_{idx}_{t_field}",
                    location=loc,
                    extra_context={"entity_id": eid, "transition_index": idx},
                )
            )
    return findings


def _check_entities(entities: list[dict[str, Any]]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        eid = _entity_id(ent) or "?"
        kind = _entity_kind(ent)
        loc = f"entity:{eid}"
        meta = ent.get("metadata_json")
        meta_dict = meta if isinstance(meta, dict) else {}

        if kind == "NPC":
            for field in (
                "on_defeat_script",
                "on_protagonist_enters_scene_script",
                "on_talk_script",
                "on_interact_script",
            ):
                code = ent.get(field) or meta_dict.get(field)
                findings.extend(
                    _validate_script_code(
                        code,
                        field,
                        location=loc,
                        extra_context={"entity_id": eid, "kind": "NPC"},
                    )
                )

        if kind == "OBJECT":
            for field in (
                "on_pickup_script",
                "on_drop_script",
                "on_equip_script",
                "on_unequip_script",
                "on_read_script",
                "on_unlock_success_script",
                "on_unlock_failure_script",
                "on_items_added_script",
                "on_craft_success_script",
                "on_craft_failure_script",
                "on_success_script",
                "on_failure_script",
                "on_interact_script",
            ):
                code = ent.get(field) or meta_dict.get(field)
                findings.extend(
                    _validate_script_code(
                        code,
                        field,
                        location=loc,
                        extra_context={"entity_id": eid, "kind": "OBJECT"},
                    )
                )

            unlock_expr = ent.get("unlock_expression") or meta_dict.get("unlock_expression")
            findings.extend(
                _validate_guard_expression(
                    unlock_expr,
                    "unlock_expression",
                    location=loc,
                    extra_context={"entity_id": eid},
                )
            )

            craft_guard = ent.get("craft_guard_expression") or meta_dict.get(
                "craft_guard_expression"
            )
            findings.extend(
                _validate_guard_expression(
                    craft_guard,
                    "craft_guard_expression",
                    location=loc,
                    extra_context={"entity_id": eid},
                )
            )

            switch_cfg = meta_dict.get("switch")
            switch_dict = switch_cfg if isinstance(switch_cfg, dict) else {}
            transitions = (
                ent.get("switch_transitions")
                or switch_dict.get("transitions")
                or meta_dict.get("switch_transitions")
            )
            findings.extend(_check_switch_transitions(transitions, loc, eid))

    return findings


def _check_protagonist(protagonist: Optional[dict[str, Any]]) -> list[ValidationFinding]:
    if not isinstance(protagonist, dict):
        return []
    findings: list[ValidationFinding] = []
    stats = protagonist.get("stats")
    stats_dict = stats if isinstance(stats, dict) else {}
    for field in ("on_hp_change_script", "on_status_change_script"):
        code = protagonist.get(field) or stats_dict.get(field)
        findings.extend(
            _validate_script_code(
                code,
                field,
                location="protagonist",
                extra_context={"scope": "protagonist"},
            )
        )
    return findings


def _check_sequences(sequences: Any) -> list[ValidationFinding]:
    if not isinstance(sequences, list):
        return []
    findings: list[ValidationFinding] = []
    for seq in sequences:
        if not isinstance(seq, dict):
            continue
        sid = seq.get("id") or "?"
        loc = f"sequence:{sid}"
        guard = seq.get("guard_expression") or seq.get("completion_guard_expression")
        findings.extend(
            _validate_guard_expression(
                guard,
                "guard_expression",
                location=loc,
                extra_context={"sequence_id": sid},
            )
        )
        for field in ("on_start_sequence_script", "on_end_sequence_script", "helpers_script"):
            code = seq.get(field)
            findings.extend(
                _validate_script_code(
                    code,
                    field,
                    location=loc,
                    extra_context={"sequence_id": sid},
                )
            )
        findings.extend(_check_soft_rules(seq.get("soft_rules"), loc, sid))
        findings.extend(_check_sequence_scripts(seq.get("scripts"), loc, sid))
    return findings


def _check_sequence_scripts(scripts: Any, loc: str, sid: str) -> list[ValidationFinding]:
    rows = [s for s in scripts if isinstance(s, dict)] if isinstance(scripts, list) else []
    return [
        finding
        for script in rows
        for finding in _validate_script_code(
            script.get("code"),
            "code",
            location=loc,
            extra_context={"sequence_id": sid, "script_id": script.get("id") or "?"},
        )
    ]


def _check_soft_rules(rules: Any, loc: str, sid: str) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for rule in rules if isinstance(rules, list) else []:
        if not isinstance(rule, dict):
            continue
        context = {"sequence_id": sid, "soft_rule_id": rule.get("id") or "?"}
        findings.extend(
            _validate_guard_expression(
                rule.get("guard_expression"),
                "guard_expression",
                location=loc,
                extra_context=context,
            )
        )
        findings.extend(
            _validate_script_code(rule.get("script"), "script", location=loc, extra_context=context)
        )
    return findings


def _check_quests(quests: Any) -> list[ValidationFinding]:
    if not isinstance(quests, list):
        return []
    findings: list[ValidationFinding] = []
    for quest in quests:
        if not isinstance(quest, dict):
            continue
        qid = quest.get("id") or "?"
        loc = f"quest:{qid}"
        guard = quest.get("guard_expression") or quest.get("completion_guard_expression")
        findings.extend(
            _validate_guard_expression(
                guard,
                "guard_expression",
                location=loc,
                extra_context={"quest_id": qid},
            )
        )
    return findings


def _check_awards(awards: Any) -> list[ValidationFinding]:
    if not isinstance(awards, list):
        return []
    findings: list[ValidationFinding] = []
    for award in awards:
        if not isinstance(award, dict):
            continue
        aid = award.get("key") or award.get("id") or "?"
        loc = f"award:{aid}"
        guard = award.get("guard_expression")
        findings.extend(
            _validate_guard_expression(
                guard,
                "guard_expression",
                location=loc,
                extra_context={"award_key": aid},
            )
        )
    return findings


def check_scripts_and_guards(
    payload: dict[str, Any],
    adventure: Optional[dict[str, Any]] = None,
    scenes: Optional[list[dict[str, Any]]] = None,
    entities: Optional[list[dict[str, Any]]] = None,
    exits: Optional[list[dict[str, Any]]] = None,
) -> list[ValidationFinding]:
    """Validate all scripts and guard expressions across an adventure payload.

    Pure-function, deterministic AST and syntax validation.
    """
    adv = adventure if adventure is not None else (payload.get("adventure") or {})
    scs = scenes if scenes is not None else (payload.get("scenes") or [])
    exs = exits if exits is not None else (payload.get("exits") or [])

    ents = entities
    if ents is None:
        npcs = payload.get("npcs") or []
        objs = payload.get("objects") or []
        ents = list(npcs) + list(objs)
        if payload.get("entities_all"):
            ents = list(payload["entities_all"])

    protagonist = payload.get("protagonist")

    sequences = adv.get("sequences") or payload.get("sequences") or []
    quests = adv.get("quests") or payload.get("quests") or []
    awards = adv.get("awards") or payload.get("awards") or []

    findings: list[ValidationFinding] = []
    findings.extend(_check_adventure_level(adv, payload))
    findings.extend(_check_scenes(scs))
    findings.extend(_check_exits(exs))
    findings.extend(_check_entities(ents))
    findings.extend(_check_protagonist(protagonist))
    findings.extend(_check_sequences(sequences))
    findings.extend(_check_quests(quests))
    findings.extend(_check_awards(awards))
    init_script = _init_script(adv, payload)
    helpers = tuple(block.code for block in helper_blocks(scs, sequences))
    findings.extend(
        check_dialog_handlers([adv, payload, scs, exs, ents, protagonist], init_script, helpers)
    )
    findings.extend(check_helper_blocks(scs, sequences, init_script))
    return findings


__all__ = ["check_scripts_and_guards"]
