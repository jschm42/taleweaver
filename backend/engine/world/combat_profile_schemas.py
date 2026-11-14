"""Manifest schemas for the NPC main attack and the protagonist's non-combat talents."""

from typing import Literal, Optional

from pydantic import Field

from backend.engine.world.schema_base import WorldBaseSchema

StatName = Literal["strength", "dexterity", "intelligence", "wisdom", "charisma"]
MAX_TALENTS = 8


class AttackEffectSchema(WorldBaseSchema):
    target: Literal["target", "self"] = Field(
        ..., description="'target' = the victim of the hit, 'self' = the attacking NPC."
    )
    stat: str = Field(..., description="hp, mana, stamina or a stat like strength.")
    amount: str = Field(..., description="Signed amount, fixed or rolled, e.g. '-1d4' or '+2'.")

    model_config = {"extra": "forbid"}


class NpcMainAttackSchema(WorldBaseSchema):
    name: str = Field(
        ..., description="Name of the attack shown in the combat log, e.g. 'Longsword', 'Bite'."
    )
    category: Optional[Literal["MELEE", "RANGED", "MAGIC"]] = Field(
        None, description="Flavour of the attack (default MELEE)."
    )
    damage_dice: str = Field("1d6", description="Damage rolled on a hit, e.g. '1d8+2'.")
    hit_stat: Optional[StatName] = Field(
        None, description="Stat added to the d20 attack roll (default dexterity)."
    )
    cost_type: Optional[Literal["stamina", "mana"]] = Field(
        None, description="Resource paid per attack (default stamina)."
    )
    cost: Optional[int] = Field(
        None, ge=0, le=999, description="Resource cost per attack. 0 or omitted = free."
    )
    effects: list[AttackEffectSchema] = Field(
        default=[], description="Optional extra effects applied on a hit. Max 4."
    )

    model_config = {"extra": "forbid"}


class TalentSchema(WorldBaseSchema):
    id: str = Field(..., description="Unique slug for the talent, e.g. MIND_READING")
    name: str = Field(..., description="Human-readable name the player types, e.g. 'Mind Reading'")
    description: str = Field(..., description="Short explanation of what the talent does.")
    target_type: Optional[Literal["NONE", "NPC", "ITEM", "ANY"]] = Field(
        None,
        description=(
            "What the talent is used on: NONE (no target, default), NPC, ITEM "
            "(scene or inventory item) or ANY."
        ),
    )
    cost_type: Optional[Literal["mana", "stamina"]] = Field(
        None, description="Resource paid on every use (default mana)."
    )
    cost: Optional[int] = Field(None, ge=0, le=999, description="Resource cost per use. 0 = free.")
    max_uses: Optional[int] = Field(
        None, ge=1, le=99, description="Uses per adventure. Omit for unlimited uses."
    )
    gm_hint: Optional[str] = Field(
        default="",
        description=(
            "Instruction for the Game Master on how to narrate the effect, e.g. "
            "'Reveal the target's true thoughts in italics.'"
        ),
    )
    on_use_script: Optional[str] = Field(
        default="",
        description=(
            "Optional sandboxed script run on every successful use. A `talent` dict is in scope "
            "(id, name, target_id, target_name, target_type, uses, uses_left). Use '' for none."
        ),
    )
    on_use_text: Optional[str] = Field(
        default="", description="Optional system text shown on every successful use."
    )
    is_locked: bool = Field(default=False, description="Whether the talent starts locked.")
    unlock_required_item_id: Optional[str] = Field(
        None, description="Locked talent unlocks once the protagonist holds this object ID."
    )
    unlock_required_scene_id: Optional[str] = Field(
        None, description="Locked talent unlocks on entering this scene ID."
    )
    unlock_required_defeated_npc_id: Optional[str] = Field(
        None, description="Locked talent unlocks once this NPC ID is defeated."
    )
    unlock_guard_expression: Optional[str] = Field(
        None,
        description=(
            "Optional sandboxed boolean expression that must also be True, e.g. "
            "\"tw.vars.get('met_the_oracle') == True\"."
        ),
    )
    unlock_text: Optional[str] = Field(
        None, description="Optional flavor text appended to the 'talent unlocked' message."
    )

    model_config = {"extra": "forbid"}


class SpecialEffectSchema(WorldBaseSchema):
    target: Literal["target", "self", "ally"] = Field(
        "target",
        description=(
            "'target' affects the attacked combatant, 'self' the caster, 'ally' the caster's "
            "party partner (the companion for the protagonist, the protagonist for a companion)."
        ),
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


class WeaponEffectSchema(SpecialEffectSchema):
    """Weapon on-hit effects: only the hit enemy or the wielder, never an ally."""

    target: Literal["target", "self"] = Field(
        "target", description="'target' affects the hit combatant, 'self' the wielder."
    )
