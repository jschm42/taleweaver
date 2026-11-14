"""World-generation schema for objects (items, containers, switches, recipes)."""

from typing import Literal, Optional

from pydantic import Field

from backend.engine.world.combat_profile_schemas import WeaponEffectSchema
from backend.engine.world.schema_base import WorldBaseSchema
from backend.engine.world.switch_schemas import (
    SwitchOutcomeSchema,
    SwitchStateLabelSchema,
    SwitchTransitionSchema,
)


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
        description="One of: CONSUMABLE, WEARABLE, STATIC, CONSTRUCTABLE, PICKABLE, WEAPON, TOOL, KEY, READABLE, CONTAINER, SWITCH, CONTAINER_SWITCH (one appliance that is both a container and a switch, e.g. a microwave, vending machine or fuse box)",
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
            "Use 'script' if only a script, crafting or reveals_item_id may reveal it. "
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
    locked: Optional[bool] = Field(
        default=None,
        description=(
            "Optional explicit lock flag. CONTAINER/CONTAINER_SWITCH: true = must be unlocked before it "
            "opens (normally derived from the unlock fields, so leave null). Any other item type: "
            "true = TAKE-LOCKED, visible and inspectable but cannot be picked up until a script "
            "(tw.objects.unlock) or a switch outcome (unlock_item) releases it. Use null if not needed."
        ),
    )
    min_items: Optional[int] = Field(
        default=None,
        description="Only for CONTAINER/CONTAINER_SWITCH: minimum number of stored items the puzzle expects (e.g. 3 fuses in a fuse box); scripts read it via .has_min_items. Use null if none.",
    )
    max_items: Optional[int] = Field(
        default=None,
        description="Only for CONTAINER/CONTAINER_SWITCH: maximum number of items the container accepts (e.g. 1 for a microwave). Use null for unlimited.",
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
        description="Only for SWITCH and CONTAINER_SWITCH objects: ordered state IDs used by scripts and transitions, e.g. ['OFF','ON']. Each ID: 1-15 characters, upper-case letters, digits, '_' or '-'.",
    )
    switch_state_labels: list[SwitchStateLabelSchema] = Field(
        default_factory=list,
        description="Only for SWITCH and CONTAINER_SWITCH objects: optional in-game text per state ID (max 20 characters each). States without a label show their ID. Use [] if the IDs read well.",
    )
    switch_initial_state: Optional[str] = Field(
        default="", description="Only for SWITCH and CONTAINER_SWITCH objects: initial state value."
    )
    switch_disabled_states: list[str] = Field(
        default_factory=list,
        description="Only for SWITCH and CONTAINER_SWITCH objects: state IDs that start disabled (shown locked, not clickable) until a script calls tw.switches.enable_state(id, state). Use [] if all states are available.",
    )
    switch_status_text: Optional[str] = Field(
        default="",
        description="Only for SWITCH and CONTAINER_SWITCH objects: optional hint shown inside the switch panel, e.g. 'No power. Insert a fuse first.' Scripts update it via set_status_text/clear_status_text. Use empty string for none.",
    )
    switch_transitions: list[SwitchTransitionSchema] = Field(
        default_factory=list,
        description="Only for SWITCH and CONTAINER_SWITCH objects: deterministic transitions with optional gates and fail_message.",
    )
    switch_outcomes: list[SwitchOutcomeSchema] = Field(
        default_factory=list,
        description="Only for SWITCH and CONTAINER_SWITCH objects: state-based effects (unlock_exit, unlock_container, unlock_item, lock_item, story_flag).",
    )
    on_success_script: Optional[str] = Field(
        default="",
        description="Only for SWITCH and CONTAINER_SWITCH objects: optional script executed when a transition succeeds. Use empty string for none.",
    )
    on_failure_script: Optional[str] = Field(
        default="",
        description="Only for SWITCH and CONTAINER_SWITCH objects: optional script executed when a transition fails. Use empty string for none.",
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
    weapon_category: Optional[Literal["MELEE", "RANGED", "MAGIC"]] = Field(
        None, description="Only for WEAPON items: MELEE (default), RANGED or MAGIC."
    )
    weapon_hit_stat: Optional[
        Literal["strength", "dexterity", "intelligence", "wisdom", "charisma"]
    ] = Field(
        None,
        description="Only for WEAPON items: stat added to the d20 attack roll (default dexterity).",
    )
    weapon_effects: list[WeaponEffectSchema] = Field(
        default=[],
        description=(
            "Only for WEAPON items: up to 4 extra effects applied on a hit, e.g. "
            "[{target:'target', stat:'stamina', amount:'-1d4'}] (poison) or "
            "[{target:'self', stat:'hp', amount:'+2'}] (life drain)."
        ),
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
        description="Optional script executed when container (or container-switch) unlocking succeeds. Use empty string for none.",
    )
    on_unlock_success_text: Optional[str] = Field(
        default="",
        description="Optional text output when container (or container-switch) unlocking succeeds. Use empty string for none.",
    )
    on_unlock_failure_script: Optional[str] = Field(
        default="",
        description="Optional script executed when container (or container-switch) unlocking fails. Use empty string for none.",
    )
    on_unlock_failure_text: Optional[str] = Field(
        default="",
        description="Optional text output when container (or container-switch) unlocking fails. Use empty string for none.",
    )
    on_items_added_script: Optional[str] = Field(
        default="",
        description="Optional script executed after the player put items into this container (added_items, added_item_ids in scope). Use empty string for none.",
    )
    on_items_added_text: Optional[str] = Field(
        default="",
        description="Optional text output after the player put items into this container. Use empty string for none.",
    )
    on_items_removed_script: Optional[str] = Field(
        default="",
        description="Optional script executed after the player took or dropped items out of this container (removed_items, removed_item_ids in scope). Use empty string for none.",
    )
    on_items_removed_text: Optional[str] = Field(
        default="",
        description="Optional text output after the player took items out of this container. Use empty string for none.",
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
