"""Key tables that map blueprint ``key: value`` lines onto manifest schema fields.

Each tag kind owns a table of accepted keys. A key resolves to a ``FieldSpec``
whose ``target`` is the manifest field name. Dotted targets (``attack_trigger.guard_expression``)
address nested dicts, and the target ``*`` spreads a converter's dict result over
several fields.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from backend.engine.blueprint.converters import (
    STAT_ALIASES,
    ability_cost,
    ability_damage,
    boolean,
    choice,
    ident,
    ident_list,
    integer,
    movement,
    one_way,
    stat_bonus,
    switch_outcome,
    switch_transition,
    text,
    text_list,
    weapon_cost,
)

FieldRole = Literal["text", "script", "expr", "ref", "refs", "transition", "outcome"]


@dataclass(frozen=True)
class FieldSpec:
    target: str
    convert: Callable[[str], Any] = text
    role: FieldRole = "text"
    repeat: bool = False


def _script(target: str) -> FieldSpec:
    return FieldSpec(target, text, "script")


def _expr(target: str) -> FieldSpec:
    return FieldSpec(target, text, "expr")


def _ref(target: str) -> FieldSpec:
    return FieldSpec(target, ident, "ref")


def _refs(target: str) -> FieldSpec:
    return FieldSpec(target, ident_list, "refs")


def _hook(table: dict[str, FieldSpec], key: str, target: str) -> None:
    """Register ``key`` (script) and ``key_text`` (text) for an ``on_*_script/_text`` pair."""
    table[key] = _script(f"{target}_script")
    table[f"{key}_text"] = FieldSpec(f"{target}_text")


WORLD_KEYS: dict[str, FieldSpec] = {
    "language": FieldSpec("language"),
    "plot": FieldSpec("plot"),
    "rules": FieldSpec("rules"),
    "intro": FieldSpec("intro_text"),
    "teaser": FieldSpec("teaser"),
    "cover": FieldSpec("cover_appearance"),
    "win": FieldSpec("completed_condition"),
    "lose": FieldSpec("gameover_condition"),
    "win_guard": _expr("completed_guard_expression"),
    "lose_guard": _expr("gameover_guard_expression"),
    "init_script": _script("init_script"),
}

PROTAGONIST_KEYS: dict[str, FieldSpec] = {
    "role": FieldSpec("role"),
    "goal": FieldSpec("goal"),
    "character": FieldSpec("character"),
    "appearance": FieldSpec("appearance"),
    "hp": FieldSpec("hp", integer),
    "mana": FieldSpec("mana", integer),
    "stamina": FieldSpec("stamina", integer),
    "inventory": _refs("starting_inventory"),
    "weapon": _ref("starting_equipment.MainHand"),
    "offhand": _ref("starting_equipment.OffHand"),
    "armor": _ref("starting_equipment.Chest"),
}
for _alias, _stat in STAT_ALIASES.items():
    PROTAGONIST_KEYS[_alias] = FieldSpec(_stat, integer)
_hook(PROTAGONIST_KEYS, "on_hp_change", "on_hp_change")
_hook(PROTAGONIST_KEYS, "on_status_change", "on_status_change")

SCENE_KEYS: dict[str, FieldSpec] = {
    "decor": FieldSpec("decorative_objects", text_list),
}
_hook(SCENE_KEYS, "on_enter", "on_enter_scene")
_hook(SCENE_KEYS, "on_leave", "on_leave_scene")

EXIT_KEYS: dict[str, FieldSpec] = {
    "via": FieldSpec("label"),
    "label": FieldSpec("label"),
    "locked": FieldSpec("is_locked", boolean),
    "lock": FieldSpec("lock_description"),
    "code": FieldSpec("code_to_unlock"),
    "key_item": _ref("item_to_unlock"),
    "rule": FieldSpec("rule_to_unlock"),
    "guard": _expr("unlock_expression"),
    "bidirectional": FieldSpec("is_bidirectional", boolean),
    "one_way": FieldSpec("is_bidirectional", one_way),
}
_hook(EXIT_KEYS, "on_unlock", "on_unlock_success")
_hook(EXIT_KEYS, "on_unlock_fail", "on_unlock_failure")
_hook(EXIT_KEYS, "on_open", "on_open_exit")
_hook(EXIT_KEYS, "on_use", "on_exit_used")

NPC_KEYS: dict[str, FieldSpec] = {
    "in": _ref("start_scene_id"),
    "position": FieldSpec("spatial_position"),
    "type": FieldSpec("npc_type", choice("HUMANOID", "ANIMAL", "MONSTER", "BEING")),
    "goal": FieldSpec("goal"),
    "character": FieldSpec("character"),
    "appearance": FieldSpec("appearance"),
    "notes": FieldSpec("notes"),
    "hp": FieldSpec("hp", integer),
    "mana": FieldSpec("mana", integer),
    "stamina": FieldSpec("stamina", integer),
    "moves": FieldSpec("*", movement),
    "allowed_scenes": _refs("allowed_scenes"),
    "attackable": FieldSpec("is_attackable", boolean),
    "killable": FieldSpec("is_killable", boolean),
    "hidden": FieldSpec("is_hidden", boolean),
    "reveal": FieldSpec("reveal_rule"),
    "inventory": _refs("inventory"),
    "weapon": _ref("equipped_weapon_id"),
    "armor": _ref("equipped_armor_id"),
    "attack": FieldSpec(
        "attack_mode",
        choice("PASSIVE", "ATTACK_ON_SIGHT", aliases={"on_sight": "ATTACK_ON_SIGHT"}),
    ),
    "attack_when_holding": _ref("attack_trigger.required_item_id"),
    "attack_after_scene": _ref("attack_trigger.required_scene_id"),
    "attack_after_defeat": _ref("attack_trigger.required_defeated_npc_id"),
    "attack_guard": _expr("attack_trigger.guard_expression"),
    "special_chance": FieldSpec("special_chance", integer),
}
_hook(NPC_KEYS, "on_defeat", "on_defeat")
_hook(NPC_KEYS, "on_meet", "on_protagonist_enters_scene")
_hook(NPC_KEYS, "on_interact", "on_interact")

ITEM_TYPES = (
    "CONSUMABLE",
    "WEARABLE",
    "STATIC",
    "CONSTRUCTABLE",
    "PICKABLE",
    "WEAPON",
    "TOOL",
    "KEY",
    "READABLE",
    "CONTAINER",
    "SWITCH",
)
ITEM_KEYS: dict[str, FieldSpec] = {
    "in": _ref("start_scene_id"),
    "position": FieldSpec("spatial_position"),
    "type": FieldSpec("item_type", choice(*ITEM_TYPES)),
    "appearance": FieldSpec("appearance"),
    "slots": FieldSpec("wearable_slots", text_list),
    "hidden": FieldSpec("is_hidden", boolean),
    "reveal": FieldSpec("reveal_rule"),
    "portable": FieldSpec("is_portable", boolean),
    "code": FieldSpec("code_to_unlock"),
    "unlock_item": _ref("item_to_unlock"),
    "unlock_rule": FieldSpec("rule_to_unlock"),
    "unlock_guard": _expr("unlock_expression"),
    "contains": _refs("inventory"),
    "combine": _refs("combination_ingredients"),
    "craft_guard": _expr("craft_guard_expression"),
    "reveals": _ref("reveals_item_id"),
    "bonus": FieldSpec("*", stat_bonus),
    "heal": FieldSpec("hp_change", integer),
    "stamina": FieldSpec("stamina_change", integer),
    "mana": FieldSpec("mana_change", integer),
    "damage": FieldSpec("damage_dice"),
    "cost": FieldSpec("*", weapon_cost),
    "text": FieldSpec("text_log_content"),
    "format": FieldSpec("text_log_format", choice("DOCUMENT", "SCROLL", "BOOK", "SIGN")),
    "states": FieldSpec("switch_states", lambda raw: [s.upper() for s in text_list(raw)]),
    "initial": FieldSpec("switch_initial_state", lambda raw: raw.strip().upper()),
    "transition": FieldSpec("switch_transitions", switch_transition, "transition", repeat=True),
    "outcome": FieldSpec("switch_outcomes", switch_outcome, "outcome", repeat=True),
}
for _key, _target in (
    ("on_pickup", "on_pickup"),
    ("on_drop", "on_drop"),
    ("on_equip", "on_equip"),
    ("on_unequip", "on_unequip"),
    ("on_interact", "on_interact"),
    ("on_use", "on_interact"),
    ("on_unlock", "on_unlock_success"),
    ("on_unlock_fail", "on_unlock_failure"),
    ("on_read", "on_read"),
    ("on_craft", "on_craft_success"),
    ("on_craft_fail", "on_craft_failure"),
):
    _hook(ITEM_KEYS, _key, _target)

_GOAL_KEYS: dict[str, FieldSpec] = {
    "goal_item": _ref("required_item_id"),
    "goal_scene": _ref("required_scene_id"),
    "defeat": _ref("required_defeated_npc_id"),
    "guard": _expr("guard_expression"),
    "xp": FieldSpec("exp_reward", integer),
}

SEQUENCE_KEYS: dict[str, FieldSpec] = {
    **_GOAL_KEYS,
    "end": FieldSpec("end_condition"),
    "walkthrough": FieldSpec("walkthrough"),
}
# Legacy line prefixes understood by the original sequence parser.
for _alias in ("required_item", "required_item_id", "key_item", "item", "item_id"):
    SEQUENCE_KEYS[_alias] = _GOAL_KEYS["goal_item"]
for _alias in ("required_scene", "required_scene_id", "target_scene", "scene", "scene_id"):
    SEQUENCE_KEYS[_alias] = _GOAL_KEYS["goal_scene"]
for _alias in (
    "required_defeated_npc",
    "required_defeated_npc_id",
    "defeated_npc",
    "defeated_npc_id",
    "defeat_npc",
    "defeat_npc_id",
    "npc_to_defeat",
):
    SEQUENCE_KEYS[_alias] = _GOAL_KEYS["defeat"]
for _alias in ("end_condition", "completion_condition", "condition"):
    SEQUENCE_KEYS[_alias] = SEQUENCE_KEYS["end"]
_hook(SEQUENCE_KEYS, "on_start", "on_start_sequence")
_hook(SEQUENCE_KEYS, "on_end", "on_end_sequence")

RULE_KEYS: dict[str, FieldSpec] = {
    "when": FieldSpec("condition"),
    "guard": _expr("guard_expression"),
    "max": FieldSpec("max_triggers", integer),
    "script": _script("script"),
    "text": FieldSpec("text"),
}

SCRIPT_TRIGGERS = (
    "on_init",
    "on_enter_scene",
    "on_interact",
    "on_turn_start",
    "on_turn_end",
    "on_logic_pass_done",
    "on_narration_done",
)
SCRIPT_KEYS: dict[str, FieldSpec] = {
    "trigger": FieldSpec("trigger", choice(*SCRIPT_TRIGGERS)),
    "target": _ref("target_id"),
    "code": _script("code"),
}

SIDEQUEST_KEYS: dict[str, FieldSpec] = {
    **_GOAL_KEYS,
    "goal": FieldSpec("goal"),
    "impact": FieldSpec("impact"),
}

AWARD_KEYS: dict[str, FieldSpec] = {
    **{key: spec for key, spec in _GOAL_KEYS.items() if key != "xp"},
    "tier": FieldSpec("tier", choice("bronze", "silver", "gold", "negative")),
    "requires": FieldSpec("requirement"),
}

ABILITY_KEYS: dict[str, FieldSpec] = {
    "kind": FieldSpec("action_type", choice("ATTACK", "HEAL", "UTILITY")),
    "category": FieldSpec("category", choice("MAGIC", "MELEE", "RANGED", "SOCIAL", "OTHER")),
    "cost": FieldSpec("*", ability_cost),
    "stat": FieldSpec(
        "success_stat", choice("strength", "dexterity", "intelligence", "wisdom", "charisma")
    ),
    "dc": FieldSpec("difficulty", integer),
    "damage": FieldSpec("*", ability_damage),
    "outcome": FieldSpec("outcome_description"),
    "locked": FieldSpec("is_locked", boolean),
    "unlock_item": _ref("unlock_required_item_id"),
    "unlock_scene": _ref("unlock_required_scene_id"),
    "unlock_defeat": _ref("unlock_required_defeated_npc_id"),
    "unlock_guard": _expr("unlock_guard_expression"),
    "unlock_text": FieldSpec("unlock_text"),
}
_hook(ABILITY_KEYS, "on_success", "on_success")
_hook(ABILITY_KEYS, "on_fail", "on_failure")

KEY_TABLES: dict[str, dict[str, FieldSpec]] = {
    "world": WORLD_KEYS,
    "protagonist": PROTAGONIST_KEYS,
    "scene": SCENE_KEYS,
    "exit": EXIT_KEYS,
    "npc": NPC_KEYS,
    "item": ITEM_KEYS,
    "sequence": SEQUENCE_KEYS,
    "rule": RULE_KEYS,
    "script": SCRIPT_KEYS,
    "sidequest": SIDEQUEST_KEYS,
    "award": AWARD_KEYS,
    "ability": ABILITY_KEYS,
}


def normalize_key(raw: str) -> str:
    return re.sub(r"[\s\-]+", "_", raw.strip().lower())
