"""
Pydantic schemas for structured LLM output in the world generation pipeline.

These models define the expected JSON structure returned by the LLM during
adventure/world creation. They are validated by the LLM router before being
passed to the manifest applier.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_serializer


class WorldSceneSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the scene, e.g., CASTLE_GATES")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Atmospheric and detailed description of the location.")
    source_asset_id: Optional[str] = Field(None, description="Optional source scene ID to reuse an old cover asset image.")
    decorative_objects: list[str] = Field(
        default=[],
        description="A list of up to 7 simple, non-interactable decorative objects, furniture, or background features present in the scene (e.g. ['metal table', 'faint light fixture']). These are not interactable entities and won't have images/stats, but describe the room better."
    )

    model_config = {"extra": "forbid"}


class WorldExitSchema(BaseModel):
    from_scene_id: str = Field(..., description="The ID of the source scene.")
    to_scene_id: str = Field(..., description="The ID of the destination scene.")
    label: str = Field(..., description="How to describe the transition, e.g., 'a narrow stone staircase'")
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
    lock_description: str = Field(..., description="If locked, why? e.g. 'a heavy iron padlock'. Use empty string if not locked.")
    code_to_unlock: str = Field("", description="Deterministic access code for the lock, e.g. 4711. Keep empty if no code is required.")
    item_to_unlock: str = Field("", description="The ID of the item needed to unlock this path, e.g. IRON_KEY. Keep empty if no item is required.")
    rule_to_unlock: str = Field("", description="A soft narrative rule for unlocking, e.g. 'Protagonist overpersuades NPC_1 to open the door'. Keep empty if no soft rule is required.")

    model_config = {"extra": "forbid"}


class SpecialActionSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the special action, e.g., HEAL_SPELL")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Short explanation of the action")
    action_type: Literal["ATTACK", "HEAL", "UTILITY"] = Field(..., description="Type of special action")
    mana_cost: int = Field(default=0, description="Mana cost to perform this action")
    damage_type: Optional[Literal["FIXED", "ROLLED"]] = Field(None, description="Damage type (FIXED or ROLLED)")
    damage_value: Optional[str] = Field(None, description="Damage or healing value, e.g. '15' (fixed) or '2d8+3' (rolled)")
    outcome_description: str = Field(default="", description="Narrative description of what happens, especially for UTILITY actions.")
    is_locked: bool = Field(default=False, description="Whether the action starts locked and must be unlocked.")
    unlock_condition_type: Optional[Literal["READ_ITEM", "FIND_ITEM"]] = Field(None, description="Type of condition to unlock.")
    unlock_condition_target: Optional[str] = Field(None, description="Item ID that triggers the unlock.")

    model_config = {"extra": "forbid"}


class WorldNPCSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the NPC, e.g., MAD_ALCHEMIST")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Appearance and demeanor or physical characteristics, max 400 characters.")
    goal: str = Field(..., description="Concise description of the NPC's primary motivation or intention, max 200 characters.")
    character: str = Field(..., description="Concise description of the NPC's personality, demeanor, or character traits, max 200 characters.")
    start_scene_id: str = Field(..., description="The ID of the scene where the NPC starts.")
    spatial_position: str = Field(..., description="Precise micro-location in the scene, e.g., 'sitting in the armchair', 'hidden in a drawer'")

    npc_type: str = Field(..., description="One of: HUMANOID, ANIMAL, MONSTER, BEING")
    movement_type: str = Field(..., description="One of: STATIONARY, MOVABLE")
    hp: int = Field(..., description="Hitpoints (range 10-100)")
    mana: int = Field(..., description="Mana (range 0-999)")
    stamina: int = Field(..., description="Stamina (range 50-100)")
    is_attackable: bool = Field(..., description="If False, the player cannot start a fight with this NPC.")
    is_killable: bool = Field(..., description="If False, this NPC can be defeated but cannot be permanently killed.")
    is_hidden: bool = Field(..., description="If True, the NPC is initially concealed.")
    source_asset_id: Optional[str] = Field(None, description="Optional source NPC ID to reuse an old portrait image.")
    reveal_rule: str = Field(
        ...,
        description=(
            "If is_hidden=True: the condition that reveals this NPC. "
            "E.g. 'If the prot searches under the table', 'If the prot picks up BRASS_KEY', or 'If the NPC speaks'. "
            "Use empty string if not hidden."
        )
    )
    inventory: list[str] = Field(..., description="List of object IDs in this NPC's inventory. Use [] if empty.")
    equipped_weapon_id: Optional[str] = Field(None, description="Optional ID of the equipped weapon object. Must exist in the objects list.")
    equipped_armor_id: Optional[str] = Field(None, description="Optional ID of the equipped armor object. Must exist in the objects list.")
    special_actions: list[SpecialActionSchema] = Field(default=[], description="List of up to 5 special actions this NPC can perform. Max 5.")

    model_config = {"extra": "forbid"}


class SwitchGatesSchema(BaseModel):
    item: Optional[str] = Field(default="", description="The item ID needed to pass this transition.")
    code: Optional[str] = Field(default="", description="The code/password needed to pass this transition.")
    rule: Optional[str] = Field(default="", description="A soft narrative rule needed to pass this transition.")
    model_config = {"extra": "forbid"}


class SwitchTransitionSchema(BaseModel):
    from_state: str = Field(..., alias="from", description="The starting state of this transition.")
    to_state: str = Field(..., alias="to", description="The target state of this transition.")
    gates: Optional[SwitchGatesSchema] = Field(default=None, description="Optional lock gates required to allow the transition.")
    fail_message: Optional[str] = Field(default="", description="The failure message narrated if gates are not met.")
    
    @model_serializer
    def serialize_model(self) -> dict[str, Any]:
        return {
            "from": self.from_state,
            "to": self.to_state,
            "gates": self.gates.model_dump() if self.gates else None,
            "fail_message": self.fail_message,
        }

    model_config = {"populate_by_name": True, "extra": "forbid"}


class SwitchEffectSchema(BaseModel):
    type: str = Field(..., description="The effect type: unlock_exit, unlock_container, or story_flag.")
    target_id: Optional[str] = Field(default="", description="The ID of the target exit or container. Keep empty if not applicable.")
    key: Optional[str] = Field(default="", description="The story flag key. Keep empty if not applicable.")
    model_config = {"extra": "forbid"}


class SwitchOutcomeSchema(BaseModel):
    on_state: str = Field(..., description="The state trigger for these effects.")
    effects: list[SwitchEffectSchema] = Field(..., description="List of effects triggered when the state is entered.")
    model_config = {"extra": "forbid"}


class WorldObjectSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the object, e.g., GOLDEN_KEY")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Physical characteristics and details.")
    start_scene_id: str = Field(..., description="The ID of the scene where the object starts.")
    spatial_position: str = Field(..., description="Precise micro-location in the scene, e.g., 'on the dusty shelf', 'under the rug'")

    item_type: str = Field(..., description="One of: CONSUMABLE, WEARABLE, STATIC, COMBINABLE, PICKABLE, WEAPON, TOOL, KEY, READABLE, CONTAINER, SWITCH")
    wearable_slots: list[str] = Field(..., description="If WEARABLE, which slots? e.g. ['Head'], ['MainHand']. Use [] if none.")
    is_hidden: bool = Field(..., description="If True, the player must SEARCH or trigger an event to see this.")
    reveal_rule: str = Field(
        ...,
        description=(
            "If is_hidden=True: the condition that reveals this object. "
            "E.g. 'If the prot searches the desk', 'If the prot picks up IRON_KEY'. "
            "Use empty string if not hidden."
        )
    )
    is_portable: bool = Field(..., description="Whether the item can be picked up. False for STATIC objects.")
    code_to_unlock: str = Field("", description="Deterministic access code for locked containers, e.g. ALPHA or 4711. May be empty for open containers.")
    item_to_unlock: str = Field("", description="Deterministic item ID required to unlock this container. May be empty for open containers.")
    rule_to_unlock: str = Field("", description="A soft narrative rule for unlocking locked containers, e.g. 'Protagonist defeats NPC_2'. May be empty for open containers.")
    combination_ingredients: list[str] = Field(..., description="Item IDs required to trigger a combination. Use [] if none.")
    reveals_item_id: str = Field(..., description="Item slug revealed when combination occurs. Use empty string if none.")

    # Stat Modifiers
    stat_modifier_strength: int = Field(..., description="Strength bonus. Use 0 if none.")
    stat_modifier_dexterity: int = Field(..., description="Dexterity bonus. Use 0 if none.")
    stat_modifier_intelligence: int = Field(..., description="Intelligence bonus. Use 0 if none.")
    stat_modifier_wisdom: int = Field(..., description="Wisdom bonus. Use 0 if none.")
    stat_modifier_charisma: int = Field(..., description="Charisma bonus. Use 0 if none.")
    stat_modifier_armor_class: int = Field(..., description="Armor class bonus. Use 0 if none.")
    hp_change: int = Field(..., description="HP restoration or damage when consumed. Use 0 if none.")
    stamina_change: int = Field(..., description="Stamina restoration when consumed. Use 0 if none.")
    mana_change: int = Field(..., description="Mana restoration when consumed. Use 0 if none.")

    inventory: list[str] = Field(..., description="List of object IDs inside this container object. Use [] if empty.")
    text_log_content: str = Field("", description="Only for READABLE objects: visible text content, max 500 characters. Must be non-empty for READABLE objects. Paragraphs are allowed (use blank lines). Use empty string for non-readable items.")
    text_log_format: str = Field("", description="Only for READABLE objects: one of DOCUMENT, SCROLL, BOOK, SIGN. Use empty string for non-readable items.")
    switch_states: list[str] = Field(default_factory=list, description="Only for SWITCH objects: ordered states, e.g. ['OFF','ON'].")
    switch_initial_state: str = Field("", description="Only for SWITCH objects: initial state value.")
    switch_transitions: list[SwitchTransitionSchema] = Field(default_factory=list, description="Only for SWITCH objects: deterministic transitions with optional gates and fail_message.")
    switch_outcomes: list[SwitchOutcomeSchema] = Field(default_factory=list, description="Only for SWITCH objects: state-based effects (unlock_exit, unlock_container, story_flag).")
    source_asset_id: Optional[str] = Field(None, description="Optional source object ID to reuse an old item image.")
    damage_dice: Optional[str] = Field("1d8", description="Only for WEAPON items: damage formula (e.g. 1d8, 2d6, 1d10+1).")
    weapon_cost_type: Optional[Literal["stamina", "mana"]] = Field("stamina", description="Only for WEAPON items: resource type consumed on attack.")
    weapon_cost_value: Optional[int] = Field(20, description="Only for WEAPON items: amount of resource consumed on attack.")

    model_config = {"extra": "forbid"}


class QuestSchema(BaseModel):
    id: str = Field(..., description="Unique slug for the quest, e.g., FIND_GOLDEN_KEY")
    title: str = Field(..., description="Short, descriptive title")
    description: str = Field(..., description="Narrative description of what needs to be done")
    goal: str = Field(..., description="Technical condition for completion (for GM reference)")
    impact: str = Field(..., description="How this affects the world when completed. Use empty string for standard quests.")
    exp_reward: int = Field(..., description="EXP awarded for completion (e.g., 50, 100, 250)")
    is_main: bool = Field(..., description="True if this quest is required to finish the adventure")
    status: str = Field(..., description="Current state: open, completed, failed")

    model_config = {"extra": "forbid"}


class AwardTemplateSchema(BaseModel):
    key: str = Field(..., description="Unique identifier for the award, e.g., SLAYER_OF_RATS")
    title: str = Field(..., description="Visual name of the award")
    description: str = Field(..., description="Short description shown to the player")
    tier: Literal["bronze", "silver", "gold"] = Field(..., description="The rarity/tier of the award: bronze, silver, or gold")
    requirement: str = Field(..., description="The specific rule/condition when the GM should grant this award")

    model_config = {"extra": "forbid"}


class EquipmentSchema(BaseModel):
    Head: str = Field(..., description="Item ID for head slot or empty string")
    Chest: str = Field(..., description="Item ID for chest slot or empty string")
    Hands: str = Field(..., description="Item ID for hands slot or empty string")
    Legs: str = Field(..., description="Item ID for legs slot or empty string")
    Feet: str = Field(..., description="Item ID for feet slot or empty string")
    Neck: str = Field(..., description="Item ID for neck slot or empty string")
    Ring_1: str = Field(..., description="Item ID for ring 1 slot or empty string")
    Ring_2: str = Field(..., description="Item ID for ring 2 slot or empty string")
    MainHand: str = Field(..., description="Item ID for main hand slot or empty string")
    OffHand: str = Field(..., description="Item ID for off hand slot or empty string")

    model_config = {"extra": "forbid"}


class ProtagonistSchema(BaseModel):
    name: str = Field(..., description="The name of the player character.")
    role: str = Field(..., description="The professional or narrative role of the player.")
    description: str = Field(..., description="Narrative description of appearance and backstory.")
    goal: str = Field(..., description="The protagonist's primary motivation or personal driving goal, max 200 characters.")
    character: str = Field(..., description="Concise description of the protagonist's personality, quirks, and character traits, max 200 characters.")
    strength: int = Field(..., description="Base strength stat (1-99)")
    dexterity: int = Field(..., description="Base dexterity stat (1-99)")
    intelligence: int = Field(..., description="Base intelligence stat (1-99)")
    wisdom: int = Field(..., description="Base wisdom stat (1-99)")
    charisma: int = Field(..., description="Base charisma stat (1-99)")
    armor_class: int = Field(..., description="Base armor class stat (1-99)")
    starting_inventory: list[str] = Field(..., description="List of object IDs in player's pocket. Use [] if none.")
    starting_equipment: EquipmentSchema = Field(..., description="Initial equipment setup.")
    hp: int = Field(..., description="Base health points (60-120)")
    mana: int = Field(..., description="Base mana points (0-300)")
    stamina: int = Field(..., description="Base stamina points (60-100)")
    source_asset_id: Optional[str] = Field(None, description="Optional source protagonist ID to reuse an old portrait image.")
    special_actions: list[SpecialActionSchema] = Field(default=[], description="List of up to 5 special actions the protagonist has at the start. Max 5.")

    model_config = {"extra": "forbid"}


class WorldManifesto(BaseModel):
    """The complete blueprint of the generated world."""

    protagonist: ProtagonistSchema
    teaser: str = Field(..., description="A short, atmospheric teaser text for the adventure, max 100 characters.")
    language: str = Field(..., description="The target language for all generated content, e.g. 'English'.")
    origin_id: str = Field(..., description="Stable ID for the adventure. Use empty string if not provided.")
    plot: str = Field(..., description="The main plotline, goals, and narrative arc of the adventure.")
    rules: str = Field(..., description="Special rules or mechanics specific to this adventure world.")
    intro_text: str = Field(..., description="Optional intro text shown once when a new session starts. Use empty string if none.")
    walkthrough: str = Field(..., description="A secret GM walkthrough/solution for the adventure.")
    completed_condition: str = Field(..., description="Technical or narrative condition for winning the adventure.")
    gameover_condition: str = Field(..., description="Technical or narrative condition for losing the adventure.")
    tts_director_notes: str = Field(..., description="Style instructions for the Text-to-Speech engine (tone, pacing, emphasis).")
    can_damage_npcs: bool = Field(True, description="Global flag: whether the protagonist can damage NPCs.")
    npcs_can_damage_protagonist: bool = Field(True, description="Global flag: whether NPCs can damage the protagonist.")
    scenes: list[WorldSceneSchema]
    exits: list[WorldExitSchema]
    npcs: list[WorldNPCSchema]
    objects: list[WorldObjectSchema]
    quests: list[QuestSchema] = Field(..., description="List of 3-5 quests. Use [] if none.")
    awards: list[AwardTemplateSchema] = Field(..., description="List of 3-5 awards. Use [] if none.")
    cover_source_adventure_id: Optional[str] = None
    cover_source_adventure_name: Optional[str] = None
    cover_similarity_percent: int = 50
    allow_reuse_source_assets: bool = True
    cover_source_asset_id: Optional[str] = None

    model_config = {"extra": "forbid"}
