"""Item, container, switch, NPC, and protagonist checks."""

from __future__ import annotations

from typing import Any

from backend.core.world_validation.context import (
    ValidationContext,
    entity_field,
    entity_id,
    entity_kind,
    finding,
    item_type,
    metadata,
    ref_id,
    ref_ids,
)
from backend.engine.switch_states import (
    STATE_ID_MAX,
    STATE_LABEL_MAX,
    invalid_state_ids,
    long_state_labels,
)
from backend.schemas.validation import ValidationFinding

# Hard caps that mirror the engine-side thresholds (world_schemas.py / world_generator.py).
NPC_OVERPOWERED_HP = 200
NPC_OVERPOWERED_STRENGTH = 18
NPC_OVERPOWERED_AC = 20
CONTAINER_INVENTORY_CAP = 10
# Combat defaults used by the engine when an NPC has no explicit value (combat/combatants.py).
_NPC_BASE_ATTRIBUTE = 10
_NPC_BASE_AC = 10

_LOCK_KEY_FIELDS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock", "unlock_expression")
_NPC_EQUIPMENT_FIELDS = ("equipped_weapon_id", "equipped_armor_id")


def _int_or_none(value: Any) -> int | None:
    try:
        return None if value is None or value == "" else int(value)
    except (TypeError, ValueError):
        return None


def _missing_ref(
    code: str, eid: str, message: str, missing: str, severity: str = "error"
) -> ValidationFinding:
    return finding(
        severity, code, message, location=f"entity:{eid}", entity_id=eid, missing_ref=missing
    )


def _rule_npc_tokens(rule: Any) -> list[str]:
    # Rough heuristic for rules like 'Protagonist defeats NPC_X'; only NPC_/ENEMY_ tokens count.
    if not isinstance(rule, str) or "defeats" not in rule.lower():
        return []
    return [t for t in rule.replace(",", " ").split() if t.startswith(("NPC_", "ENEMY_"))]


def check_item_references(ctx: ValidationContext) -> list[ValidationFinding]:
    """Unlock items must exist; locked entities need some way to open them."""
    findings: list[ValidationFinding] = []
    for entity in ctx.entities:
        eid = entity_id(entity) or "?"
        kind = entity_kind(entity)
        target = entity_field(entity, "item_to_unlock")
        if target and target not in ctx.object_ids:
            findings.append(
                _missing_ref(
                    "missing_item_ref",
                    eid,
                    f"{kind} '{eid}' references unlock-item '{target}' which does not exist.",
                    target,
                )
            )
        for token in _rule_npc_tokens(entity_field(entity, "rule_to_unlock")):
            if token in ctx.entity_ids:
                continue
            findings.append(
                finding(
                    "warn",
                    "rule_to_unlock_missing_target",
                    f"{kind} '{eid}' has rule_to_unlock referencing unknown NPC '{token}'.",
                    location=f"entity:{eid}",
                    entity_id=eid,
                    missing_npc=token,
                )
            )
        has_key = any(entity_field(entity, k) for k in _LOCK_KEY_FIELDS)
        if metadata(entity).get("locked") is True and not has_key:
            findings.append(
                finding(
                    "warn",
                    "locked_but_no_unlock_key",
                    f"{kind} '{eid}' is marked locked but has no code/item/rule unlock key.",
                    location=f"entity:{eid}",
                    entity_id=eid,
                )
            )
    return findings


def check_container_inventory(ctx: ValidationContext) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for entity in ctx.entities_of("OBJECT"):
        if item_type(entity) != "CONTAINER" or not isinstance(entity.get("inventory"), list):
            continue
        eid = entity_id(entity) or "?"
        contents = ref_ids(entity["inventory"])
        if len(contents) > CONTAINER_INVENTORY_CAP:
            findings.append(
                finding(
                    "warn",
                    "container_inventory_too_large",
                    f"Container '{eid}' has {len(contents)} items — consider splitting.",
                    location=f"entity:{eid}",
                    entity_id=eid,
                    count=len(contents),
                )
            )
        findings.extend(
            _missing_ref(
                "container_inventory_orphan",
                eid,
                f"Container '{eid}' lists unknown item '{target}' in its inventory.",
                target,
            )
            for target in contents
            if target not in ctx.object_ids
        )
    return findings


def check_switch_state_consistency(ctx: ValidationContext) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for entity in ctx.entities:
        if item_type(entity) != "SWITCH":
            continue
        eid = entity_id(entity) or "?"
        states = entity.get("switch_states")
        # An empty initial state is the serializer's "not set" value, not a bad state.
        initial = str(entity.get("switch_initial_state") or "").strip()
        if not isinstance(states, list) or len(states) < 2:
            findings.append(
                finding(
                    "warn",
                    "switch_missing_states",
                    f"Switch '{eid}' has fewer than two states defined.",
                    location=f"entity:{eid}",
                    entity_id=eid,
                )
            )
        elif initial and initial not in states:
            findings.append(
                finding(
                    "warn",
                    "switch_unreachable_state",
                    f"Switch '{eid}' initial state '{initial}' is not in its states list.",
                    location=f"entity:{eid}",
                    entity_id=eid,
                    initial_state=initial,
                    states=states,
                )
            )
    return findings


def _switch_state_findings(eid: str, entity: dict[str, Any]) -> list[ValidationFinding]:
    states = [str(s) for s in entity.get("switch_states") or []]
    messages = [
        (
            "switch_invalid_state_id",
            f"Switch '{eid}' state ID '{state}' must be 1-{STATE_ID_MAX} characters "
            "(letters, digits, '_' or '-').",
        )
        for state in invalid_state_ids([s.strip().upper() for s in states])
    ]
    messages += [
        (
            "switch_state_label_too_long",
            f"Switch '{eid}' label of state '{state}' is longer than {STATE_LABEL_MAX} "
            "characters and will be shortened.",
        )
        for state in long_state_labels(entity.get("switch_state_labels"))
    ]
    return [
        finding("warn", code, message, location=f"entity:{eid}", entity_id=eid)
        for code, message in messages
    ]


def check_switch_state_ids(ctx: ValidationContext) -> list[ValidationFinding]:
    """State IDs are script keys (A-Z, 0-9, _ and -, max 15); labels are max 20 characters."""
    findings: list[ValidationFinding] = []
    for entity in ctx.entities:
        if item_type(entity) == "SWITCH":
            findings += _switch_state_findings(entity_id(entity) or "?", entity)
    return findings


def _npc_combat_stats(npc: dict[str, Any]) -> tuple[int | None, int, int]:
    """(hp, strength, armor_class) as the combat engine computes them."""
    strength = _int_or_none(npc.get("stat_modifier_strength"))
    ac_mod = _int_or_none(npc.get("stat_modifier_armor_class")) or 0
    return (
        _int_or_none(npc.get("hp")),
        _NPC_BASE_ATTRIBUTE if strength is None else strength,
        _NPC_BASE_AC + ac_mod,
    )


def check_npc_stats(ctx: ValidationContext) -> list[ValidationFinding]:
    """Combat balance hints. Combat only runs in rpg mode, so other modes are skipped."""
    if not ctx.is_rpg:
        return []
    findings: list[ValidationFinding] = []
    for npc in ctx.entities_of("NPC"):
        eid = entity_id(npc) or "?"
        hp, strength, ac = _npc_combat_stats(npc)
        stamina, mana = _int_or_none(npc.get("stamina")), _int_or_none(npc.get("mana"))
        if (hp is not None and hp <= 0) or (stamina == 0 and mana == 0):
            findings.append(
                finding(
                    "warn",
                    "npc_zero_stats",
                    f"NPC '{eid}' has zero vital stats and may be un-interactable.",
                    location=f"entity:{eid}",
                    entity_id=eid,
                    hp=hp,
                    stamina=stamina,
                    mana=mana,
                )
            )
        if (
            (hp or 0) > NPC_OVERPOWERED_HP
            or strength > NPC_OVERPOWERED_STRENGTH
            or (ac > NPC_OVERPOWERED_AC)
        ):
            findings.append(
                finding(
                    "warn",
                    "npc_overpowered",
                    f"NPC '{eid}' has unusually high stats (hp={hp}, str={strength}, AC={ac}).",
                    location=f"entity:{eid}",
                    entity_id=eid,
                    hp=hp,
                    strength=strength,
                    armor_class=ac,
                )
            )
    return findings


def check_npc_references(ctx: ValidationContext) -> list[ValidationFinding]:
    """NPC inventories and equipped weapon/armor must point at existing items."""
    findings: list[ValidationFinding] = []
    for npc in ctx.entities_of("NPC"):
        eid = entity_id(npc) or "?"
        refs = ref_ids(npc.get("inventory"))
        refs += [str(metadata(npc).get(f)) for f in _NPC_EQUIPMENT_FIELDS if metadata(npc).get(f)]
        findings.extend(
            _missing_ref(
                "npc_item_missing",
                eid,
                f"NPC '{eid}' carries or equips item '{target}' which does not exist.",
                target,
            )
            for target in refs
            if target not in ctx.object_ids
        )
    return findings


def check_reveal_targets(ctx: ValidationContext) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for entity in ctx.entities_of("OBJECT"):
        target = str(entity.get("reveals_item_id") or "").strip()
        if not target or target in ctx.object_ids:
            continue
        eid = entity_id(entity) or "?"
        findings.append(
            _missing_ref(
                "reveal_target_missing",
                eid,
                f"Item '{eid}' reveals item '{target}' which does not exist.",
                target,
            )
        )
    return findings


def _protagonist_item_refs(protagonist: dict[str, Any]) -> list[str]:
    """Item IDs the protagonist starts with; inline item definitions (dicts with a name) are skipped."""
    equipment = protagonist.get("equipment")
    entries = list(protagonist.get("inventory") or [])
    entries += list(equipment.values()) if isinstance(equipment, dict) else []
    plain = [e for e in entries if not (isinstance(e, dict) and e.get("name"))]
    return [rid for rid in (ref_id(e) for e in plain) if rid]


def check_protagonist_items(ctx: ValidationContext) -> list[ValidationFinding]:
    """Starting inventory and equipment must reference existing items."""
    refs = _protagonist_item_refs(ctx.protagonist)
    return [
        finding(
            "error",
            "protagonist_item_missing",
            f"Protagonist starts with item '{target}' which does not exist.",
            location="protagonist",
            missing_ref=target,
        )
        for target in dict.fromkeys(refs)
        if target not in ctx.object_ids
    ]
