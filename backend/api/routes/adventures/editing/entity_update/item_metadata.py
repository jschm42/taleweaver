"""Type-specific ``metadata_json`` updates for items (container, readable, switch, ...).

Each section writes its fields when the item has that type and removes them otherwise,
so a type change never leaves stale configuration behind.
"""

from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from backend.api.routes.adventures.editing.common import _normalize_lock_fields
from backend.api.routes.adventures.editing.entity_update.fields import given, put_metadata
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
from backend.engine.combat.special_attacks import SUCCESS_STATS, normalize_effects
from backend.engine.combat.weapons import MAX_WEAPON_EFFECTS, WEAPON_CATEGORIES, WEAPON_DICE_RX
from backend.engine.interaction.switch_states import (
    STATE_ID_MAX,
    STATE_LABEL_MAX,
    invalid_state_ids,
    long_state_labels,
    normalize_state_labels,
)
from backend.engine.rules.crafting_recipes import KEPT_FIELD, RESULT_FIELD, normalize_ids
from backend.models.world_entity import WorldEntity

_LOCK_FIELDS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock")
_UNLOCK_SCRIPT_FIELDS = (
    "unlock_expression",
    "on_unlock_success_script",
    "on_unlock_success_text",
    "on_unlock_failure_script",
    "on_unlock_failure_text",
)
_CONTAINER_KEYS = (*_LOCK_FIELDS, *_UNLOCK_SCRIPT_FIELDS, "locked")
_READABLE_SCRIPT_FIELDS = ("on_read_script", "on_read_text")
_READABLE_KEYS = ("text_log_content", "text_log_format", *_READABLE_SCRIPT_FIELDS)
_TEXT_LOG_FORMATS = {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}
_MAX_TEXT_LOG_LENGTH = 1000
_CRAFT_FIELDS = (
    "craft_guard_expression",
    "on_craft_success_script",
    "on_craft_success_text",
    "on_craft_failure_script",
    "on_craft_failure_text",
)
_ITEM_EVENT_FIELDS = (
    "on_pickup_script",
    "on_pickup_text",
    "on_drop_script",
    "on_drop_text",
    "on_equip_script",
    "on_equip_text",
    "on_unequip_script",
    "on_unequip_text",
    "on_interact_script",
    "on_interact_text",
)
_SWITCH_FLAT_KEYS = (
    "switch_states",
    "switch_state_labels",
    "switch_initial_state",
    "switch_transitions",
)
_SWITCH_FIELDS = (
    "switch_states",
    "switch_state_labels",
    "switch_initial_state",
    "switch_transitions",
    "on_success_script",
    "on_failure_script",
)
_PICKUP_TRIGGER_MODES = {"silent", "narration", "turn"}
_WEAPON_KEYS = (
    "damage_dice",
    "weapon_cost_type",
    "weapon_cost_value",
    "weapon_category",
    "weapon_hit_stat",
    "weapon_effects",
)


def _drop(metadata_json: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        metadata_json.pop(key, None)


def update_container(
    ent: WorldEntity, metadata_json: dict[str, Any], payload: EntityUpdateRequest, active: bool
) -> None:
    if not active:
        _drop(metadata_json, _CONTAINER_KEYS)
        return
    if not any(given(payload, f) for f in (*_LOCK_FIELDS, "locked")):
        return
    current = {f: metadata_json.get(f) or "" for f in _LOCK_FIELDS}
    sent = {f: str(getattr(payload, f) or "") for f in _LOCK_FIELDS if given(payload, f)}
    code, item, rule = _normalize_lock_fields(**{**current, **sent})
    metadata_json.update(code_to_unlock=code, item_to_unlock=item, rule_to_unlock=rule)
    locked = payload.locked if given(payload, "locked") else (code or item or rule)
    metadata_json["locked"] = bool(locked)
    put_metadata(metadata_json, payload, _UNLOCK_SCRIPT_FIELDS, empty_as_none=True)
    ent.unlock_rule = None


def update_readable(
    metadata_json: dict[str, Any], payload: EntityUpdateRequest, active: bool
) -> None:
    if not active:
        _drop(metadata_json, _READABLE_KEYS)
        return
    if given(payload, "text_log_content"):
        if len(payload.text_log_content or "") > _MAX_TEXT_LOG_LENGTH:
            raise HTTPException(
                status_code=400, detail="text_log_content must be at most 1000 characters."
            )
        metadata_json["text_log_content"] = (payload.text_log_content or "").strip()
    if given(payload, "text_log_format"):
        normalized_format = str(payload.text_log_format).strip().upper()
        if normalized_format not in _TEXT_LOG_FORMATS:
            raise HTTPException(
                status_code=400,
                detail="text_log_format must be one of DOCUMENT, SCROLL, BOOK, SIGN.",
            )
        metadata_json["text_log_format"] = normalized_format
    put_metadata(metadata_json, payload, _READABLE_SCRIPT_FIELDS, empty_as_none=True)


def update_constructable(
    metadata_json: dict[str, Any], payload: EntityUpdateRequest, active: bool
) -> None:
    """Recipe results, kept ingredients, craft guard and hooks of a CONSTRUCTABLE."""
    if not active:
        metadata_json.pop(RESULT_FIELD, None)
        metadata_json.pop(KEPT_FIELD, None)
        return
    put_metadata(metadata_json, payload, _CRAFT_FIELDS, empty_as_none=True)
    for field in (RESULT_FIELD, KEPT_FIELD):
        if given(payload, field):
            metadata_json[field] = normalize_ids(getattr(payload, field))


def update_item_events(metadata_json: dict[str, Any], payload: EntityUpdateRequest) -> None:
    put_metadata(metadata_json, payload, _ITEM_EVENT_FIELDS, empty_as_none=False)


def update_pickup_trigger(metadata_json: dict[str, Any], payload: EntityUpdateRequest) -> None:
    """Optional narration/turn pass after the player picks the item up."""
    if not (given(payload, "pickup_trigger_mode") or given(payload, "pickup_trigger_cue")):
        return
    existing = metadata_json.get("pickup_trigger")
    existing = existing if isinstance(existing, dict) else {}
    mode = payload.pickup_trigger_mode
    mode = str(mode if mode is not None else existing.get("mode") or "silent").strip().lower()
    if mode not in _PICKUP_TRIGGER_MODES:
        raise HTTPException(
            status_code=400,
            detail="pickup_trigger_mode must be one of silent, narration, turn.",
        )
    cue = payload.pickup_trigger_cue
    cue = str(cue if cue is not None else existing.get("cue") or "").strip()[:500]
    if mode == "silent" and not cue:
        metadata_json.pop("pickup_trigger", None)
    else:
        metadata_json["pickup_trigger"] = {"mode": mode, "cue": cue}


def _validated_state_ids(switch_config: dict[str, Any]) -> list[str]:
    states = [str(s).strip().upper() for s in switch_config.get("states") or [] if str(s).strip()]
    if len(states) < 2:
        raise HTTPException(status_code=400, detail="A switch must have at least 2 states.")
    invalid = invalid_state_ids(states)
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid switch state ID(s): {', '.join(invalid)}. Use 1-{STATE_ID_MAX} "
                "characters: letters, digits, '_' or '-'."
            ),
        )
    if len(set(states)) != len(states):
        raise HTTPException(status_code=400, detail="Switch state IDs must be unique.")
    return states


def validated_switch(switch_config: dict[str, Any]) -> dict[str, Any]:
    """Checks state IDs, labels and the initial state; returns the normalized config."""
    states = _validated_state_ids(switch_config)
    too_long = long_state_labels(switch_config.get("state_labels"))
    if too_long:
        raise HTTPException(
            status_code=400,
            detail=f"Switch state labels must be at most {STATE_LABEL_MAX} characters: {', '.join(too_long)}.",
        )
    initial_state = str(switch_config.get("initial_state") or "").strip().upper()
    if not initial_state:
        raise HTTPException(
            status_code=400, detail="An initial state must be defined for the switch."
        )
    if initial_state not in states:
        raise HTTPException(
            status_code=400,
            detail=f"Initial state '{initial_state}' is not one of the switch states: {', '.join(states)}.",
        )
    labels = normalize_state_labels(states, switch_config.get("state_labels"))
    return {
        **switch_config,
        "states": states,
        "state_labels": labels,
        "initial_state": initial_state,
    }


def _merged_switch(metadata_json: dict[str, Any], payload: EntityUpdateRequest) -> dict[str, Any]:
    switch_config = metadata_json.get("switch")
    switch_config = dict(switch_config) if isinstance(switch_config, dict) else {}
    for field, key in (
        ("switch_states", "states"),
        ("switch_state_labels", "state_labels"),
        ("switch_initial_state", "initial_state"),
        ("switch_transitions", "transitions"),
    ):
        if given(payload, field):
            switch_config[key] = getattr(payload, field)
    for field in ("on_success_script", "on_failure_script"):
        if given(payload, field):
            script = (getattr(payload, field) or "").strip()
            switch_config[field] = script
            metadata_json[field] = script
    return switch_config


def update_switch(
    metadata_json: dict[str, Any], payload: EntityUpdateRequest, active: bool
) -> None:
    if not active:
        _drop(metadata_json, ("switch", *_SWITCH_FLAT_KEYS))
        return
    if any(given(payload, f) for f in _SWITCH_FIELDS):
        metadata_json["switch"] = validated_switch(_merged_switch(metadata_json, payload))
    # Clean up flat switch keys that were previously written as pollution
    _drop(metadata_json, _SWITCH_FLAT_KEYS)


def _weapon_error(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def _clean_weapon_effects(raw: list[dict[str, Any]]) -> list[dict[str, str]]:
    effects = normalize_effects(raw)
    if len(effects) != len(raw):
        raise _weapon_error(
            "weapon_effects: every effect needs target, stat and an amount like -1d4."
        )
    if len(effects) > MAX_WEAPON_EFFECTS:
        raise _weapon_error(f"weapon_effects: at most {MAX_WEAPON_EFFECTS} effects.")
    return effects


def _choice(allowed: tuple[str, ...], field: str, transform: Callable[[str], str]):
    def clean(value: Any) -> str:
        text = transform(str(value or "").strip())
        if text not in allowed:
            raise _weapon_error(f"{field} must be one of {', '.join(allowed)}.")
        return text

    return clean


def _clean_dice(value: Any) -> str:
    dice = str(value or "").replace(" ", "").lower()
    if not WEAPON_DICE_RX.match(dice):
        raise _weapon_error("damage_dice must look like 1d8, 2d6 or 1d10+2.")
    return dice


# Payload field -> validator returning the value stored in metadata_json.
_WEAPON_CLEANERS: dict[str, Callable[[Any], Any]] = {
    "damage_dice": _clean_dice,
    "weapon_cost_type": _choice(("stamina", "mana"), "weapon_cost_type", str.lower),
    "weapon_cost_value": lambda value: max(0, int(value or 0)),
    "weapon_category": _choice(WEAPON_CATEGORIES, "weapon_category", str.upper),
    "weapon_hit_stat": _choice(SUCCESS_STATS, "weapon_hit_stat", str.lower),
    "weapon_effects": lambda value: _clean_weapon_effects(value or []),
}


def update_weapon(
    metadata_json: dict[str, Any], payload: EntityUpdateRequest, active: bool
) -> None:
    """Damage, cost, attack-roll stat, category and on-hit effects of a WEAPON item."""
    if not active:
        _drop(metadata_json, _WEAPON_KEYS)
        return
    for field, clean in _WEAPON_CLEANERS.items():
        if given(payload, field):
            metadata_json[field] = clean(getattr(payload, field))


def update_consumable(
    metadata_json: dict[str, Any], payload: EntityUpdateRequest, active: bool
) -> None:
    if not active:
        metadata_json.pop("effects", None)
    elif given(payload, "effects"):
        metadata_json["effects"] = payload.effects
