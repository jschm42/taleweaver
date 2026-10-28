"""
Pydantic schemas for structured LLM output in the world generation pipeline.

These models define the expected JSON structure returned by the LLM during
adventure/world creation. They are validated by the LLM router before being
passed to the manifest applier.
"""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_serializer, model_validator

_EMPTY_VALUES: tuple[Any, ...] = (None, "", [], {})


def _drop_empty_unknown_keys(model: type[BaseModel], data: dict[str, Any]) -> dict[str, Any]:
    """Remove keys the model does not declare when their value carries no content.

    LLMs pattern-complete field names (e.g. ``on_success_script_text`` next to the
    ``on_*_script`` / ``on_*_text`` pairs) and emit them as null. Under
    ``extra="forbid"`` one such empty key would fail the whole manifest, so it is
    dropped here; unknown keys that carry content still fail validation.
    """
    known = set(model.model_fields)
    known.update(f.alias for f in model.model_fields.values() if f.alias)
    return {k: v for k, v in data.items() if k in known or v not in _EMPTY_VALUES}


class WorldBaseSchema(BaseModel):
    """Base schema for world generation models that normalizes null LLM outputs."""

    @model_validator(mode="before")
    @classmethod
    def normalize_null_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if cls.model_config.get("extra") == "forbid":
            data = _drop_empty_unknown_keys(cls, data)
        for field_name, field_info in cls.model_fields.items():
            key = field_info.alias if field_info.alias and field_info.alias in data else field_name
            if key not in data or data[key] is not None:
                continue
            if field_info.default == "":
                data[key] = ""
                continue
            if field_info.default_factory is list or field_info.default == []:
                data[key] = []
        return data


class WorldSceneSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the scene, e.g., CASTLE_GATES")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(
        ..., description="Atmospheric and detailed description of the location."
    )
    source_asset_id: Optional[str] = Field(
        None, description="Optional source scene ID to reuse an old cover asset image."
    )
    decorative_objects: list[str] = Field(
        default=[],
        description="A list of up to 7 simple, non-interactable decorative objects, furniture, or background features present in the scene (e.g. ['metal table', 'faint light fixture']). These are not interactable entities and won't have images/stats, but describe the room better.",
    )
    on_enter_scene_script: Optional[str] = Field(
        default="",
        description="Optional script executed when the protagonist enters the scene. Use empty string for none.",
    )
    on_enter_scene_text: Optional[str] = Field(
        default="",
        description="Optional text output when the protagonist enters the scene. Use empty string for none.",
    )
    on_leave_scene_script: Optional[str] = Field(
        default="",
        description="Optional script executed when the protagonist leaves the scene. Use empty string for none.",
    )
    on_leave_scene_text: Optional[str] = Field(
        default="",
        description="Optional text output when the protagonist leaves the scene. Use empty string for none.",
    )

    model_config = {"extra": "forbid"}


class WorldExitSchema(WorldBaseSchema):
    from_scene_id: str = Field(..., description="The ID of the source scene.")
    to_scene_id: str = Field(..., description="The ID of the destination scene.")
    label: str = Field(
        ..., description="How to describe the transition, e.g., 'a narrow stone staircase'"
    )
    is_bidirectional: bool = Field(
        True,
        description=(
            "Whether the player can traverse this exit in BOTH directions. "
            "Set True for normal passages (doors, corridors, stairs) — the engine will automatically "
            "create the reverse exit. "
            "Set False ONLY for genuinely one-way paths (a collapsing bridge, a drop, a gate that slams shut)."
        ),
    )
    is_locked: bool = Field(..., description="Whether the path is initially blocked.")
    lock_description: Optional[str] = Field(
        default="",
        description="If locked, why? e.g. 'a heavy iron padlock'. Use empty string if not locked.",
    )
    code_to_unlock: Optional[str] = Field(
        default="",
        description="Deterministic access code for the lock, e.g. 4711. Keep empty if no code is required.",
    )
    item_to_unlock: Optional[str] = Field(
        default="",
        description="The ID of the item needed to unlock this path, e.g. IRON_KEY. Keep empty if no item is required.",
    )
    rule_to_unlock: Optional[str] = Field(
        default="",
        description="A soft narrative rule for unlocking, e.g. 'Protagonist overpersuades NPC_1 to open the door'. Keep empty if no soft rule is required.",
    )
    on_open_exit_script: Optional[str] = Field(
        default="",
        description="Optional script executed when this exit is opened/traversed. Use empty string for none.",
    )
    on_open_exit_text: Optional[str] = Field(
        default="",
        description="Optional text output when this exit is opened/traversed. Use empty string for none.",
    )
    on_exit_used_script: Optional[str] = Field(
        default="",
        description="Optional script executed when this exit is used/traversed. Use empty string for none.",
    )
    on_exit_used_text: Optional[str] = Field(
        default="",
        description="Optional text output when this exit is used/traversed. Use empty string for none.",
    )
    unlock_expression: Optional[str] = Field(
        default="",
        description="Deterministic script guard expression evaluated to allow unlocking the exit (e.g. tw.vars.get('puzzle_solved') == True). Keep empty if none.",
    )
    on_unlock_success_script: Optional[str] = Field(
        default="",
        description="Optional script executed when unlocking this exit succeeds. Use empty string for none.",
    )
    on_unlock_success_text: Optional[str] = Field(
        default="",
        description="Optional text output when unlocking this exit succeeds. Use empty string for none.",
    )
    on_unlock_failure_script: Optional[str] = Field(
        default="",
        description="Optional script executed when unlocking this exit fails. Use empty string for none.",
    )
    on_unlock_failure_text: Optional[str] = Field(
        default="",
        description="Optional text output when unlocking this exit fails. Use empty string for none.",
    )

    model_config = {"extra": "forbid"}


class SpecialEffectSchema(WorldBaseSchema):
    target: Literal["target", "self"] = Field(
        "target", description="'target' affects the attacked combatant, 'self' the caster."
    )
    stat: Literal[
        "hp",
        "mana",
        "stamina",
        "strength",
        "dexterity",
        "intelligence",
        "wisdom",
        "charisma",
        "armor_class",
    ] = Field(..., description="Stat changed by the effect. Attribute changes last for the fight.")
    amount: str = Field(
        ..., description="Signed amount, fixed or dice, e.g. '-2d6', '+5', '-3', '+1d4+1'."
    )

    model_config = {"extra": "forbid"}


class NpcAttackTriggerSchema(WorldBaseSchema):
    required_item_id: Optional[str] = Field(
        None,
        description="NPC attacks once the protagonist holds this object ID (e.g. a stolen idol).",
    )
    required_scene_id: Optional[str] = Field(
        None, description="Only fire once the protagonist has reached this scene ID."
    )
    required_defeated_npc_id: Optional[str] = Field(
        None, description="Only fire once this NPC ID has been defeated."
    )
    guard_expression: Optional[str] = Field(
        None, description="Optional sandboxed Python boolean expression that must also be True."
    )

    model_config = {"extra": "forbid"}


class SpecialActionSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the special action, e.g., HEAL_SPELL")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Short explanation of the action")
    action_type: Literal["ATTACK", "HEAL", "UTILITY"] = Field(
        ..., description="Type of special action"
    )
    category: Optional[Literal["MAGIC", "MELEE", "RANGED", "SOCIAL", "OTHER"]] = Field(
        None,
        description="Flavor of the attack: MAGIC spell, MELEE move, RANGED shot, SOCIAL (e.g. insult) or OTHER.",
    )
    cost_type: Optional[Literal["mana", "stamina"]] = Field(
        None, description="Resource paid to use the action (default mana)."
    )
    cost: Optional[int] = Field(
        None, description="Resource cost. Falls back to mana_cost when omitted."
    )
    success_stat: Optional[
        Literal["strength", "dexterity", "intelligence", "wisdom", "charisma"]
    ] = Field(None, description="Stat added to the d20 success roll (default by category).")
    difficulty: Optional[int] = Field(
        None,
        description="Fixed difficulty class for the success roll. Omit to roll against the target's AC.",
    )
    effects: list[SpecialEffectSchema] = Field(
        default=[],
        description="Stat effects applied on success. Omit to derive them from damage_type/damage_value.",
    )
    mana_cost: int = Field(default=0, description="Mana cost to perform this action")
    damage_type: Optional[Literal["FIXED", "ROLLED"]] = Field(
        None, description="Damage type (FIXED or ROLLED)"
    )
    damage_value: Optional[str] = Field(
        None, description="Damage or healing value, e.g. '15' (fixed) or '2d8+3' (rolled)"
    )
    outcome_description: Optional[str] = Field(
        default="",
        description="Narrative description of what happens, especially for UTILITY actions.",
    )
    is_locked: bool = Field(
        default=False, description="Whether the action starts locked and must be unlocked."
    )
    unlock_condition_type: Optional[Literal["READ_ITEM", "FIND_ITEM"]] = Field(
        None, description="Type of condition to unlock."
    )
    unlock_condition_target: Optional[str] = Field(
        None, description="Item ID that triggers the unlock."
    )
    unlock_required_item_id: Optional[str] = Field(
        None,
        description="Protagonist only: locked action unlocks once the protagonist holds this object ID.",
    )
    unlock_required_scene_id: Optional[str] = Field(
        None, description="Protagonist only: locked action unlocks on entering this scene ID."
    )
    unlock_required_defeated_npc_id: Optional[str] = Field(
        None, description="Protagonist only: locked action unlocks once this NPC ID is defeated."
    )
    unlock_guard_expression: Optional[str] = Field(
        None,
        description=(
            "Protagonist only: optional sandboxed Python boolean expression that must also be True, "
            "e.g. \"tw.vars.get('trained_with_master') == True\". All configured unlock rules must hold."
        ),
    )
    unlock_text: Optional[str] = Field(
        None,
        description="Optional flavor text appended to the 'special attack unlocked' system message.",
    )
    on_success_script: Optional[str] = Field(
        default="",
        description=(
            "Optional sandboxed script run when the action succeeds. A `special` dict is available "
            "(id, name, caster, target, success, crit, fumble, roll, dc) besides `tw`. Use empty string for none."
        ),
    )
    on_success_text: Optional[str] = Field(
        default="", description="Optional system text shown when the action succeeds."
    )
    on_failure_script: Optional[str] = Field(
        default="",
        description="Optional sandboxed script run when the success roll fails. Use empty string for none.",
    )
    on_failure_text: Optional[str] = Field(
        default="", description="Optional system text shown when the action fails."
    )

    model_config = {"extra": "forbid"}


class WorldNPCSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the NPC, e.g., MAD_ALCHEMIST")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(
        ..., description="Appearance and demeanor or physical characteristics, max 400 characters."
    )
    goal: str = Field(
        ...,
        description="Concise description of the NPC's primary motivation or intention, max 200 characters.",
    )
    character: str = Field(
        ...,
        description="Concise description of the NPC's personality, demeanor, or character traits, max 200 characters.",
    )
    appearance: str = Field(
        default="",
        description="Comma-separated English visual keywords for the image generator (build, face, hair, clothing, distinctive marks), max 100 characters.",
    )
    start_scene_id: str = Field(..., description="The ID of the scene where the NPC starts.")
    spatial_position: str = Field(
        ...,
        description="Precise micro-location in the scene, e.g., 'sitting in the armchair', 'hidden in a drawer'",
    )

    npc_type: str = Field(..., description="One of: HUMANOID, ANIMAL, MONSTER, BEING")
    movement_type: str = Field(default="STATIONARY", description="One of: STATIONARY, MOVABLE")
    moveable: bool = Field(default=False, description="Whether this NPC can move between scenes.")
    allowed_scenes: list[str] = Field(
        default=[],
        description="List of scene IDs this NPC is allowed to move between. If empty, can move through all scenes.",
    )
    notes: Optional[str] = Field(
        default=None, description="Dynamic state/status notes or conditions regarding the NPC."
    )
    hp: int = Field(..., description="Hitpoints (range 10-100)")
    mana: int = Field(..., description="Mana (range 0-999)")
    stamina: int = Field(..., description="Stamina (range 50-100)")
    is_attackable: bool = Field(
        ..., description="If False, the player cannot start a fight with this NPC."
    )
    is_killable: bool = Field(
        ..., description="If False, this NPC can be defeated but cannot be permanently killed."
    )
    is_hidden: bool = Field(..., description="If True, the NPC is initially concealed.")
    source_asset_id: Optional[str] = Field(
        None, description="Optional source NPC ID to reuse an old portrait image."
    )
    reveal_rule: Optional[str] = Field(
        default="",
        description=(
            "If is_hidden=True: the condition that reveals this NPC. "
            "E.g. 'If the prot searches under the table', 'If the prot picks up BRASS_KEY', or 'If the NPC speaks'. "
            "Use empty string if not hidden."
        ),
    )
    inventory: list[str] = Field(
        default_factory=list,
        description="List of object IDs in this NPC's inventory. Use [] if empty.",
    )
    equipped_weapon_id: Optional[str] = Field(
        None,
        description="Optional ID of the equipped weapon object. Must exist in the objects list.",
    )
    equipped_armor_id: Optional[str] = Field(
        None,
        description="Optional ID of the equipped armor object. Must exist in the objects list.",
    )
    special_actions: list[SpecialActionSchema] = Field(
        default=[],
        description=(
            "Up to 5 special attacks this NPC uses at random during fights (magic, melee moves, ranged "
            "shots or absurd social attacks like insults). NPCs never use unlock_* fields. Max 5."
        ),
    )
    attack_mode: Literal["PASSIVE", "ATTACK_ON_SIGHT"] = Field(
        "PASSIVE",
        description="If ATTACK_ON_SIGHT, the NPC attacks as soon as the protagonist enters the scene.",
    )
    attack_trigger: Optional[NpcAttackTriggerSchema] = Field(
        None,
        description=(
            "Optional: the NPC attacks once when all configured conditions are met while the protagonist "
            "is in its scene (e.g. required_item_id of a guarded treasure). Use null for none."
        ),
    )
    special_chance: Optional[int] = Field(
        None,
        description="Percent chance (0-100) per combat turn that the NPC uses one of its special_actions. Default 40.",
    )
    on_defeat_script: Optional[str] = Field(
        default="",
        description="Optional script executed when the NPC is defeated. Use empty string for none.",
    )
    on_defeat_text: Optional[str] = Field(
        default="",
        description="Optional text the NPC says when defeated. Use empty string for none.",
    )
    on_protagonist_enters_scene_script: Optional[str] = Field(
        default="",
        description="Optional script executed when the protagonist enters the NPC's scene. Use empty string for none.",
    )
    on_protagonist_enters_scene_text: Optional[str] = Field(
        default="",
        description="Optional text the NPC says when the protagonist enters the scene. Use empty string for none.",
    )
    on_interact_script: Optional[str] = Field(
        default="",
        description="Optional script executed whenever the protagonist interacts with this NPC (talks to, inspects, uses an item on it). Use empty string for none.",
    )
    on_interact_text: Optional[str] = Field(
        default="",
        description="Optional text output whenever the protagonist interacts with this NPC. Use empty string for none.",
    )

    model_config = {"extra": "forbid"}


class SwitchGatesSchema(WorldBaseSchema):
    item: Optional[str] = Field(
        default="", description="The item ID needed to pass this transition."
    )
    code: Optional[str] = Field(
        default="", description="The code/password needed to pass this transition."
    )
    rule: Optional[str] = Field(
        default="", description="A soft narrative rule needed to pass this transition."
    )
    expression: Optional[str] = Field(
        default="",
        description="A boolean Python expression evaluated against tw (e.g. tw.vars.get('flag') == True).",
    )
    condition: Optional[str] = Field(
        default="",
        description="Alias for expression.",
    )

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        expr = self.expression or self.condition or ""
        return {
            "item": self.item or "",
            "code": self.code or "",
            "rule": self.rule or "",
            "expression": expr,
            "condition": expr,
        }

    model_config = {"populate_by_name": True, "extra": "forbid"}


class SwitchTransitionSchema(WorldBaseSchema):
    from_state: Optional[str] = Field(
        default="",
        alias="from",
        description="The starting state of this transition. Omit or leave empty to apply to any current state.",
    )
    to_state: str = Field(..., alias="to", description="The target state of this transition.")
    gates: Optional[SwitchGatesSchema] = Field(
        default=None, description="Optional lock gates required to allow the transition."
    )
    fail_message: Optional[str] = Field(
        default="", description="The failure message narrated if gates are not met."
    )
    success_message: Optional[str] = Field(
        default="", description="Optional success message narrated when transition passes."
    )
    on_success_script: Optional[str] = Field(
        default="", description="Optional script executed when this transition succeeds."
    )
    on_failure_script: Optional[str] = Field(
        default="", description="Optional script executed when this transition fails."
    )

    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "to": self.to_state,
            "gates": self.gates.model_dump() if self.gates else None,
            "fail_message": self.fail_message or "",
        }
        if self.from_state:
            payload["from"] = self.from_state
        if self.success_message:
            payload["success_message"] = self.success_message
        if self.on_success_script:
            payload["on_success_script"] = self.on_success_script
        if self.on_failure_script:
            payload["on_failure_script"] = self.on_failure_script
        return payload

    model_config = {"populate_by_name": True, "extra": "forbid"}


class SwitchEffectSchema(WorldBaseSchema):
    type: str = Field(
        ..., description="The effect type: unlock_exit, unlock_container, or story_flag."
    )
    target_id: Optional[str] = Field(
        default="",
        description="The ID of the target exit or container. Keep empty if not applicable.",
    )
    key: Optional[str] = Field(
        default="", description="The story flag key. Keep empty if not applicable."
    )
    model_config = {"extra": "forbid"}


class SwitchOutcomeSchema(WorldBaseSchema):
    on_state: str = Field(..., description="The state trigger for these effects.")
    effects: list[SwitchEffectSchema] = Field(
        ..., description="List of effects triggered when the state is entered."
    )
    model_config = {"extra": "forbid"}


class WorldObjectSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the object, e.g., GOLDEN_KEY")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Physical characteristics and details.")
    appearance: str = Field(
        default="",
        description="Comma-separated English visual keywords for the image generator (material, shape, color, condition), max 100 characters.",
    )
    start_scene_id: str = Field(..., description="The ID of the scene where the object starts.")
    spatial_position: str = Field(
        ...,
        description="Precise micro-location in the scene, e.g., 'on the dusty shelf', 'under the rug'",
    )

    item_type: str = Field(
        ...,
        description="One of: CONSUMABLE, WEARABLE, STATIC, CONSTRUCTABLE, PICKABLE, WEAPON, TOOL, KEY, READABLE, CONTAINER, SWITCH",
    )
    wearable_slots: list[str] = Field(
        default_factory=list,
        description="If WEARABLE, which slots? e.g. ['Head'], ['MainHand']. Use [] if none.",
    )
    is_hidden: bool = Field(
        ..., description="If True, the player must SEARCH or trigger an event to see this."
    )
    reveal_rule: Optional[str] = Field(
        default="",
        description=(
            "If is_hidden=True: the condition that reveals this object. "
            "E.g. 'If the prot searches the desk', 'If the prot picks up IRON_KEY'. "
            "Use empty string if not hidden."
        ),
    )
    is_portable: bool = Field(
        ..., description="Whether the item can be picked up. False for STATIC objects."
    )
    code_to_unlock: Optional[str] = Field(
        default="",
        description="Deterministic access code for locked containers, e.g. ALPHA or 4711. May be empty for open containers.",
    )
    item_to_unlock: Optional[str] = Field(
        default="",
        description="Deterministic item ID required to unlock this container. May be empty for open containers.",
    )
    rule_to_unlock: Optional[str] = Field(
        default="",
        description="A soft narrative rule for unlocking locked containers, e.g. 'Protagonist defeats NPC_2'. May be empty for open containers.",
    )
    combination_ingredients: list[str] = Field(
        default_factory=list,
        description="Item IDs required to trigger a combination. For a CONSTRUCTABLE recipe, list ALL ingredient ids (minimum 2) that must be combined. Use [] if none.",
    )
    result_item_ids: list[str] = Field(
        default_factory=list,
        description="Only for CONSTRUCTABLE recipes: ids of the separate, regular items (any item type, is_hidden=True) that crafting reveals. Minimum 1 for a recipe; never a CONSTRUCTABLE or one of the recipe's ingredients. Use [] otherwise.",
    )
    kept_ingredients: list[str] = Field(
        default_factory=list,
        description="Only for CONSTRUCTABLE recipes: ingredient ids that are NOT consumed by crafting (e.g. a tool). Must be a subset of combination_ingredients. Use [] if all ingredients are consumed.",
    )
    reveals_item_id: Optional[str] = Field(
        default="",
        description="Item slug revealed when combination occurs. Not used by CONSTRUCTABLE recipes (use result_item_ids). Use empty string if none.",
    )

    # Stat Modifiers
    stat_modifier_strength: int = Field(0, description="Strength bonus. Use 0 if none.")
    stat_modifier_dexterity: int = Field(0, description="Dexterity bonus. Use 0 if none.")
    stat_modifier_intelligence: int = Field(0, description="Intelligence bonus. Use 0 if none.")
    stat_modifier_wisdom: int = Field(0, description="Wisdom bonus. Use 0 if none.")
    stat_modifier_charisma: int = Field(0, description="Charisma bonus. Use 0 if none.")
    stat_modifier_armor_class: int = Field(0, description="Armor class bonus. Use 0 if none.")
    hp_change: int = Field(0, description="HP restoration or damage when consumed. Use 0 if none.")
    stamina_change: int = Field(0, description="Stamina restoration when consumed. Use 0 if none.")
    mana_change: int = Field(0, description="Mana restoration when consumed. Use 0 if none.")

    inventory: list[str] = Field(
        default_factory=list,
        description="List of object IDs inside this container object. Use [] if empty.",
    )
    text_log_content: Optional[str] = Field(
        default="",
        description="Only for READABLE objects: visible text content, max 500 characters. Must be non-empty for READABLE objects. Paragraphs are allowed (use blank lines). Use empty string for non-readable items.",
    )
    text_log_format: Optional[str] = Field(
        default="",
        description="Only for READABLE objects: one of DOCUMENT, SCROLL, BOOK, SIGN. Use empty string for non-readable items.",
    )
    switch_states: list[str] = Field(
        default_factory=list,
        description="Only for SWITCH objects: ordered states, e.g. ['OFF','ON'].",
    )
    switch_initial_state: Optional[str] = Field(
        default="", description="Only for SWITCH objects: initial state value."
    )
    switch_transitions: list[SwitchTransitionSchema] = Field(
        default_factory=list,
        description="Only for SWITCH objects: deterministic transitions with optional gates and fail_message.",
    )
    switch_outcomes: list[SwitchOutcomeSchema] = Field(
        default_factory=list,
        description="Only for SWITCH objects: state-based effects (unlock_exit, unlock_container, story_flag).",
    )
    on_success_script: Optional[str] = Field(
        default="",
        description="Only for SWITCH objects: optional script executed when a transition succeeds. Use empty string for none.",
    )
    on_failure_script: Optional[str] = Field(
        default="",
        description="Only for SWITCH objects: optional script executed when a transition fails. Use empty string for none.",
    )
    source_asset_id: Optional[str] = Field(
        None, description="Optional source object ID to reuse an old item image."
    )
    damage_dice: Optional[str] = Field(
        "1d8", description="Only for WEAPON items: damage formula (e.g. 1d8, 2d6, 1d10+1)."
    )
    weapon_cost_type: Optional[Literal["stamina", "mana"]] = Field(
        "stamina", description="Only for WEAPON items: resource type consumed on attack."
    )
    weapon_cost_value: Optional[int] = Field(
        20, description="Only for WEAPON items: amount of resource consumed on attack."
    )
    on_pickup_script: Optional[str] = Field(
        default="",
        description="Optional script executed when the item is picked up. Use empty string for none.",
    )
    on_pickup_text: Optional[str] = Field(
        default="",
        description="Optional text output when the item is picked up. Use empty string for none.",
    )
    on_drop_script: Optional[str] = Field(
        default="",
        description="Optional script executed when the item is dropped. Use empty string for none.",
    )
    on_drop_text: Optional[str] = Field(
        default="",
        description="Optional text output when the item is dropped. Use empty string for none.",
    )
    on_equip_script: Optional[str] = Field(
        default="",
        description="Optional script executed when the item is equipped (only for equippables). Use empty string for none.",
    )
    on_equip_text: Optional[str] = Field(
        default="",
        description="Optional text output when the item is equipped. Use empty string for none.",
    )
    on_unequip_script: Optional[str] = Field(
        default="",
        description="Optional script executed when the item is unequipped. Use empty string for none.",
    )
    on_unequip_text: Optional[str] = Field(
        default="",
        description="Optional text output when the item is unequipped. Use empty string for none.",
    )
    on_interact_script: Optional[str] = Field(
        default="",
        description="Optional script executed whenever the protagonist interacts with this object (inspects, uses, pushes, tampers with it), also for objects that cannot be picked up. Use empty string for none.",
    )
    on_interact_text: Optional[str] = Field(
        default="",
        description="Optional text output whenever the protagonist interacts with this object. Use empty string for none.",
    )
    unlock_expression: Optional[str] = Field(
        default="",
        description="Deterministic script guard expression evaluated when unlocking this container. Keep empty if none.",
    )
    on_unlock_success_script: Optional[str] = Field(
        default="",
        description="Optional script executed when container unlocking succeeds. Use empty string for none.",
    )
    on_unlock_success_text: Optional[str] = Field(
        default="",
        description="Optional text output when container unlocking succeeds. Use empty string for none.",
    )
    on_unlock_failure_script: Optional[str] = Field(
        default="",
        description="Optional script executed when container unlocking fails. Use empty string for none.",
    )
    on_unlock_failure_text: Optional[str] = Field(
        default="",
        description="Optional text output when container unlocking fails. Use empty string for none.",
    )
    on_read_script: Optional[str] = Field(
        default="",
        description="Only for READABLE objects: optional script executed when read. Use empty string for none.",
    )
    on_read_text: Optional[str] = Field(
        default="",
        description="Only for READABLE objects: optional text output when read. Use empty string for none.",
    )
    craft_guard_expression: Optional[str] = Field(
        default="",
        description="Only for CONSTRUCTABLE recipes: optional script guard expression evaluated during crafting. Keep empty if none.",
    )
    on_craft_success_script: Optional[str] = Field(
        default="",
        description="Only for CONSTRUCTABLE recipes: optional script executed when crafting succeeds. Use empty string for none.",
    )
    on_craft_success_text: Optional[str] = Field(
        default="",
        description="Only for CONSTRUCTABLE recipes: optional text shown instead of the default message when crafting succeeds. Use empty string for none.",
    )
    on_craft_failure_script: Optional[str] = Field(
        default="",
        description="Only for CONSTRUCTABLE recipes: optional script executed when crafting fails. Use empty string for none.",
    )
    on_craft_failure_text: Optional[str] = Field(
        default="",
        description="Only for CONSTRUCTABLE recipes: optional text shown instead of the default message when the craft guard blocks. Use empty string for none.",
    )

    model_config = {"extra": "forbid"}


class SoftRuleSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the soft rule, e.g. BRENDA_FLIRT")
    condition: str = Field(
        ...,
        description="Narrative condition judged by the GM, e.g. 'Arthur flirts with Brenda'.",
    )
    script: Optional[str] = Field(
        default="",
        description="Script executed when the GM judges the condition fulfilled. Use empty string for none.",
    )
    text: Optional[str] = Field(
        default="",
        description="Optional text output when the rule fires. Use empty string for none.",
    )
    guard_expression: Optional[str] = Field(
        default="",
        description="Optional deterministic guard that must also hold, e.g. tw.vars.get('BRENDA_TRUST', 0) >= 0. Keep empty if none.",
    )
    max_triggers: Optional[int] = Field(
        default=None,
        description="How often the rule may fire per session (e.g. 1 for one-time rewards). Null for unlimited.",
    )

    model_config = {"extra": "ignore"}


class SequenceScriptSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the script, e.g. SCRIPT_BOMB_TAMPER")
    name: str = Field(default="", description="Human-readable title for the script")
    trigger: Literal[
        "on_enter_scene",
        "on_interact",
        "on_turn_start",
        "on_turn_end",
        "on_logic_pass_done",
        "on_narration_done",
    ] = Field(..., description="The game event trigger (on_init is not available here).")
    target_id: Optional[str] = Field(
        None,
        description="Optional entity_id or scene_id target, e.g. the entity ID for on_interact.",
    )
    code: str = Field(..., description="Safe Python script using the 'tw' API.")
    description: Optional[str] = Field(None, description="What this script does.")

    model_config = {"extra": "ignore"}


class SequenceSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the sequence, e.g., SEQ_1_DRAGON")
    order: int = Field(..., description="The sequence order (1, 2, 3...)")
    title: str = Field(..., description="Title of the section")
    description: Optional[str] = Field(
        default="", description="Narrative description for the AI Gamemaster"
    )
    walkthrough: Optional[str] = Field(
        default="", description="The dedicated walkthrough/solution for this sequence"
    )
    end_condition: Optional[str] = Field(
        default="", description="Condition that must be met to proceed to the next sequence"
    )
    required_item_id: Optional[str] = Field(
        default="",
        description="Optional hard rule: ID of the item the protagonist must obtain to complete the sequence",
    )
    required_scene_id: Optional[str] = Field(
        default="",
        description="Optional hard rule: ID of the scene the protagonist must enter to complete the sequence",
    )
    required_defeated_npc_id: Optional[str] = Field(
        default="",
        description="Optional hard rule: ID of the NPC the protagonist must defeat to complete the sequence",
    )
    guard_expression: Optional[str] = Field(
        default="",
        description="Optional deterministic script guard expression evaluated to complete the sequence (e.g. tw.vars.get('puzzle_solved') == True). Keep empty if none.",
    )
    completion_guard_expression: Optional[str] = Field(
        default="",
        description="Alias for guard_expression.",
    )
    exp_reward: int = Field(default=100, description="XP reward for completion")
    on_start_sequence_script: Optional[str] = Field(
        default="",
        description="Optional script executed when this sequence begins. Use empty string for none.",
    )
    on_start_sequence_text: Optional[str] = Field(
        default="",
        description="Optional text output when this sequence begins. Use empty string for none.",
    )
    on_end_sequence_script: Optional[str] = Field(
        default="",
        description="Optional script executed when this sequence ends/completes. Use empty string for none.",
    )
    on_end_sequence_text: Optional[str] = Field(
        default="",
        description="Optional text output when this sequence ends/completes. Use empty string for none.",
    )
    soft_rules: list[SoftRuleSchema] = Field(
        default_factory=list,
        description="Narrative rules only active during this sequence: the GM judges the condition, the engine runs the script. Use [] if none.",
    )
    scripts: list[SequenceScriptSchema] = Field(
        default_factory=list,
        description="Event scripts that only run while this sequence is active (same triggers as top-level scripts except on_init). Use [] if none.",
    )

    model_config = {"extra": "ignore"}


class QuestSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the quest, e.g., FIND_GOLDEN_KEY")
    title: str = Field(..., description="Short, descriptive title")
    description: str = Field(..., description="Narrative description of what needs to be done")
    goal: str = Field(..., description="Technical condition for completion (for GM reference)")
    impact: Optional[str] = Field(
        default="",
        description="How this affects the world when completed. Use empty string for standard quests.",
    )
    exp_reward: int = Field(..., description="EXP awarded for completion (e.g., 50, 100, 250)")
    status: str = Field(..., description="Current state: open, completed, failed")
    required_item_id: Optional[str] = Field(
        default="",
        description="Hard rule: Quest only completes once protagonist has this item ID in inventory. Use empty string for none.",
    )
    required_scene_id: Optional[str] = Field(
        default="",
        description="Hard rule: Quest only completes once protagonist enters this scene ID. Use empty string for none.",
    )
    required_defeated_npc_id: Optional[str] = Field(
        default="",
        description="Hard rule: Quest only completes once this NPC ID is defeated. Use empty string for none.",
    )
    guard_expression: Optional[str] = Field(
        default="",
        description="Deterministic Python boolean expression evaluated against tw context. Quest only completes when True.",
    )

    model_config = {"extra": "ignore"}


class AwardTemplateSchema(WorldBaseSchema):
    key: str = Field(..., description="Unique identifier for the award, e.g., SLAYER_OF_RATS")
    title: str = Field(..., description="Visual name of the award")
    description: str = Field(..., description="Short description shown to the player")
    tier: Literal["bronze", "silver", "gold", "negative"] = Field(
        ..., description="The rarity/tier of the award: bronze, silver, gold, or negative"
    )
    requirement: str = Field(
        ..., description="The specific rule/condition when the GM should grant this award"
    )
    required_item_id: Optional[str] = Field(
        default="",
        description="Hard rule: Award is granted once protagonist has this item ID in inventory. Use empty string for none.",
    )
    required_scene_id: Optional[str] = Field(
        default="",
        description="Hard rule: Award is granted once protagonist enters this scene ID. Use empty string for none.",
    )
    required_defeated_npc_id: Optional[str] = Field(
        default="",
        description="Hard rule: Award is granted once this NPC ID is defeated. Use empty string for none.",
    )
    guard_expression: Optional[str] = Field(
        default="",
        description="Deterministic Python boolean expression evaluated against tw context. Award is granted when True.",
    )

    model_config = {"extra": "ignore"}


class EquipmentSchema(WorldBaseSchema):
    Head: Optional[str] = Field(default="", description="Item ID for head slot or empty string")
    Chest: Optional[str] = Field(default="", description="Item ID for chest slot or empty string")
    Hands: Optional[str] = Field(default="", description="Item ID for hands slot or empty string")
    Legs: Optional[str] = Field(default="", description="Item ID for legs slot or empty string")
    Feet: Optional[str] = Field(default="", description="Item ID for feet slot or empty string")
    Neck: Optional[str] = Field(default="", description="Item ID for neck slot or empty string")
    Ring_1: Optional[str] = Field(default="", description="Item ID for ring 1 slot or empty string")
    Ring_2: Optional[str] = Field(default="", description="Item ID for ring 2 slot or empty string")
    MainHand: Optional[str] = Field(
        default="", description="Item ID for main hand slot or empty string"
    )
    OffHand: Optional[str] = Field(
        default="", description="Item ID for off hand slot or empty string"
    )

    model_config = {"extra": "forbid"}


class ProtagonistSchema(WorldBaseSchema):
    name: str = Field(..., description="The name of the player character.")
    role: str = Field(..., description="The professional or narrative role of the player.")
    description: str = Field(..., description="Narrative description of appearance and backstory.")
    goal: str = Field(
        ...,
        description="The protagonist's primary motivation or personal driving goal, max 200 characters.",
    )
    character: str = Field(
        ...,
        description="Concise description of the protagonist's personality, quirks, and character traits, max 200 characters.",
    )
    appearance: str = Field(
        default="",
        description="Comma-separated English visual keywords for the image generator (build, face, hair, clothing, gear), max 100 characters.",
    )
    strength: int = Field(10, description="Base strength stat (1-99)")
    dexterity: int = Field(10, description="Base dexterity stat (1-99)")
    intelligence: int = Field(10, description="Base intelligence stat (1-99)")
    wisdom: int = Field(10, description="Base wisdom stat (1-99)")
    charisma: int = Field(10, description="Base charisma stat (1-99)")
    armor_class: int = Field(10, description="Base armor class stat (1-99)")
    starting_inventory: list[str] = Field(
        default_factory=list, description="List of object IDs in player's pocket. Use [] if none."
    )
    starting_equipment: EquipmentSchema = Field(..., description="Initial equipment setup.")
    hp: int = Field(..., description="Base health points (60-120)")
    mana: int = Field(..., description="Base mana points (0-300)")
    stamina: int = Field(..., description="Base stamina points (60-100)")
    source_asset_id: Optional[str] = Field(
        None, description="Optional source protagonist ID to reuse an old portrait image."
    )
    special_actions: list[SpecialActionSchema] = Field(
        default=[],
        description="List of up to 5 special actions the protagonist has at the start. Max 5.",
    )
    on_hp_change_script: Optional[str] = Field(
        default="",
        description="Optional script executed when protagonist HP changes. Use empty string for none.",
    )
    on_hp_change_text: Optional[str] = Field(
        default="",
        description="Optional text output when protagonist HP changes. Use empty string for none.",
    )
    on_status_change_script: Optional[str] = Field(
        default="",
        description="Optional script executed when protagonist status or stats change. Use empty string for none.",
    )
    on_status_change_text: Optional[str] = Field(
        default="",
        description="Optional text output when protagonist status or stats change. Use empty string for none.",
    )

    model_config = {"extra": "forbid"}


class WorldScriptSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the script, e.g. SCRIPT_LEVER_PUZZLE")
    name: str = Field(..., description="Human-readable title for the script")
    trigger: Literal[
        "on_init",
        "on_enter_scene",
        "on_interact",
        "on_turn_start",
        "on_turn_end",
        "on_logic_pass_done",
        "on_narration_done",
    ] = Field(
        ...,
        description="The game event trigger: on_init, on_enter_scene, on_interact, on_turn_start, on_turn_end, on_logic_pass_done, on_narration_done",
    )
    target_id: Optional[str] = Field(
        None,
        description="Optional entity_id or scene_id target. E.g. scene ID for on_enter_scene, or entity ID for on_interact.",
    )
    target: Optional[str] = Field(None, description="Optional alias for target_id.")
    code: str = Field(..., description="Safe Python script using the 'tw' API.")
    description: Optional[str] = Field(None, description="What this script does.")

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def reconcile_target(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("target_id") and data.get("target"):
            data["target_id"] = data.get("target")
        return data


class WorldManifesto(WorldBaseSchema):
    """The complete blueprint of the generated world."""

    protagonist: ProtagonistSchema
    teaser: str = Field(
        ..., description="A short, atmospheric teaser text for the adventure, max 100 characters."
    )
    cover_appearance: str = Field(
        default="",
        description="Comma-separated English visual keywords for the cover image (key motif, setting, colors, mood), max 100 characters.",
    )
    language: str = Field(
        ..., description="The target language for all generated content, e.g. 'English'."
    )
    plot: str = Field(
        ..., description="The main plotline, goals, and narrative arc of the adventure."
    )
    rules: str = Field(
        ..., description="Special rules or mechanics specific to this adventure world."
    )
    intro_text: Optional[str] = Field(
        default="",
        description="Optional intro text shown once when a new session starts. Use empty string if none.",
    )
    completed_condition: Optional[str] = Field(
        default="",
        description="Technical or narrative soft rule condition for winning the adventure.",
    )
    gameover_condition: Optional[str] = Field(
        default="",
        description="Technical or narrative soft rule condition for losing the adventure.",
    )
    completed_guard_expression: Optional[str] = Field(
        default="",
        description="Deterministic Python boolean guard expression evaluated with tw for winning the adventure.",
    )
    gameover_guard_expression: Optional[str] = Field(
        default="",
        description="Deterministic Python boolean guard expression evaluated with tw for losing the adventure.",
    )
    can_damage_npcs: bool = Field(
        True, description="Global flag: whether the protagonist can damage NPCs."
    )
    npcs_can_damage_protagonist: bool = Field(
        True, description="Global flag: whether NPCs can damage the protagonist."
    )
    max_sequences: int = Field(15, description="Maximum number of allowed sequences.")
    scenes: list[WorldSceneSchema]
    exits: list[WorldExitSchema]
    npcs: list[WorldNPCSchema]
    objects: list[WorldObjectSchema]
    sequences: list[SequenceSchema] = Field(
        ...,
        description="List of sequences for the linear story. Must not be empty unless sequences are explicitly disabled.",
        max_length=15,
    )
    quests: list[QuestSchema] = Field(
        ..., description="List of 3-5 optional sidequests. Use [] if none."
    )
    awards: list[AwardTemplateSchema] = Field(
        ..., description="List of 3-5 awards. Use [] if none."
    )
    scripts: list[WorldScriptSchema] = Field(
        default_factory=list,
        description="List of 1-3 game logic event scripts when scripting is enabled (e.g. traps, puzzles, quest updates). Use [] ONLY if scripting is explicitly disabled.",
    )
    init_script: Optional[str] = Field(
        default=None,
        description="Optional initialization Python script executed at session creation and loaded into scope before event triggers. Define shared helper functions and every tw.dialog on_choice handler here.",
    )
    cover_source_adventure_id: Optional[str] = None
    cover_source_adventure_name: Optional[str] = None
    cover_similarity_percent: int = 50
    allow_reuse_source_assets: bool = True
    cover_source_asset_id: Optional[str] = None

    model_config = {"extra": "ignore"}
