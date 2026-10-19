"""Type-specific ``metadata_json`` updates for items (container, readable, switch, ...).

Each section writes its fields when the item has that type and removes them otherwise,
so a type change never leaves stale configuration behind.
"""

from typing import Any

from fastapi import HTTPException

from backend.api.routes.adventures.editing.common import _normalize_lock_fields
from backend.api.routes.adventures.editing.entity_update.fields import given, put_metadata
from backend.api.routes.adventures.editing.schemas import EntityUpdateRequest
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
)
_SWITCH_FLAT_KEYS = ("switch_states", "switch_initial_state", "switch_transitions")
_SWITCH_FIELDS = (
    "switch_states",
    "switch_initial_state",
    "switch_transitions",
    "on_success_script",
    "on_failure_script",
)
_PICKUP_TRIGGER_MODES = {"silent", "narration", "turn"}


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
    if active:
        put_metadata(metadata_json, payload, _CRAFT_FIELDS, empty_as_none=True)


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


def _validated_switch(switch_config: dict[str, Any]) -> dict[str, Any]:
    states = [str(s).strip().upper() for s in switch_config.get("states") or [] if str(s).strip()]
    if len(states) < 2:
        raise HTTPException(status_code=400, detail="A switch must have at least 2 states.")
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
    return {**switch_config, "states": states, "initial_state": initial_state}


def _merged_switch(metadata_json: dict[str, Any], payload: EntityUpdateRequest) -> dict[str, Any]:
    switch_config = metadata_json.get("switch")
    switch_config = dict(switch_config) if isinstance(switch_config, dict) else {}
    for field, key in (
        ("switch_states", "states"),
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
        metadata_json["switch"] = _validated_switch(_merged_switch(metadata_json, payload))
    # Clean up flat switch keys that were previously written as pollution
    _drop(metadata_json, _SWITCH_FLAT_KEYS)


def update_consumable(
    metadata_json: dict[str, Any], payload: EntityUpdateRequest, active: bool
) -> None:
    if not active:
        metadata_json.pop("effects", None)
    elif given(payload, "effects"):
        metadata_json["effects"] = payload.effects
