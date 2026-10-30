"""Request models for the adventure editor endpoints."""

import logging
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EntityUpdateRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist", "exit"]
    target_id: str
    new_id: Optional[str] = None
    name: Optional[str] = None
    teaser: Optional[str] = None
    description: Optional[str] = None
    hp: Optional[int] = None
    mana: Optional[int] = None
    stamina: Optional[int] = None
    goal: Optional[str] = None
    character: Optional[str] = None
    # NPC TTS voice; an empty string clears it so the voice is cast automatically.
    voice: Optional[str] = None
    # Visual keywords for image prompts; maps to ``cover_appearance`` for the cover.
    appearance: Optional[str] = Field(default=None, max_length=100)
    is_killable: Optional[bool] = None
    item_type: Optional[str] = None
    is_portable: Optional[bool] = None
    locked: Optional[bool] = None
    code_to_unlock: Optional[str] = None
    item_to_unlock: Optional[str] = None
    rule_to_unlock: Optional[str] = None
    inventory: Optional[list] = None
    is_in_inventory: Optional[bool] = None
    text_log_content: Optional[str] = None
    text_log_format: Optional[str] = None
    exit_type: Optional[str] = None
    wearable_slots: Optional[list[str]] = None
    combination_ingredients: Optional[list[str]] = None
    reveal_rule: Optional[str] = None
    is_hidden: Optional[bool] = None
    spatial_position: Optional[str] = None
    reveals_item_id: Optional[str] = None
    pickup_trigger_mode: Optional[str] = None
    pickup_trigger_cue: Optional[str] = None
    switch_states: Optional[list[str]] = None
    switch_state_labels: Optional[dict[str, str]] = None
    switch_initial_state: Optional[str] = None
    switch_transitions: Optional[list[dict[str, Any]]] = None
    on_success_script: Optional[str] = None
    on_failure_script: Optional[str] = None
    effects: Optional[dict[str, Any]] = None
    stat_modifier_strength: Optional[int] = None
    current_scene_id: Optional[str] = None
    strength: Optional[int] = None
    intelligence: Optional[int] = None
    wisdom: Optional[int] = None
    dexterity: Optional[int] = None
    charisma: Optional[int] = None
    armor_class: Optional[int] = None
    exp: Optional[int] = None
    equipment: Optional[dict[str, Any]] = None
    decorative_objects: Optional[list[str]] = None
    on_pickup_script: Optional[str] = None
    on_pickup_text: Optional[str] = None
    on_drop_script: Optional[str] = None
    on_drop_text: Optional[str] = None
    on_equip_script: Optional[str] = None
    on_equip_text: Optional[str] = None
    on_unequip_script: Optional[str] = None
    on_unequip_text: Optional[str] = None
    on_interact_script: Optional[str] = None
    on_interact_text: Optional[str] = None
    on_defeat_script: Optional[str] = None
    on_defeat_text: Optional[str] = None
    on_protagonist_enters_scene_script: Optional[str] = None
    on_protagonist_enters_scene_text: Optional[str] = None
    on_enter_scene_script: Optional[str] = None
    on_enter_scene_text: Optional[str] = None
    on_leave_scene_script: Optional[str] = None
    on_leave_scene_text: Optional[str] = None
    helpers_script: Optional[str] = None
    on_open_exit_script: Optional[str] = None
    on_open_exit_text: Optional[str] = None
    on_exit_used_script: Optional[str] = None
    on_exit_used_text: Optional[str] = None
    unlock_expression: Optional[str] = None
    on_unlock_success_script: Optional[str] = None
    on_unlock_success_text: Optional[str] = None
    on_unlock_failure_script: Optional[str] = None
    on_unlock_failure_text: Optional[str] = None
    on_read_script: Optional[str] = None
    on_read_text: Optional[str] = None
    result_item_ids: Optional[list[str]] = None
    kept_ingredients: Optional[list[str]] = None
    craft_guard_expression: Optional[str] = None
    on_craft_success_script: Optional[str] = None
    on_craft_success_text: Optional[str] = None
    on_craft_failure_script: Optional[str] = None
    on_craft_failure_text: Optional[str] = None
    # WEAPON items (see backend/engine/combat/weapons.py)
    damage_dice: Optional[str] = None
    weapon_cost_type: Optional[str] = None
    weapon_cost_value: Optional[int] = None
    weapon_category: Optional[str] = None
    weapon_hit_stat: Optional[str] = None
    weapon_effects: Optional[list[dict[str, Any]]] = None
    on_hp_change_script: Optional[str] = None
    on_hp_change_text: Optional[str] = None
    on_status_change_script: Optional[str] = None
    on_status_change_text: Optional[str] = None
    is_hidden: Optional[bool] = None
    reveal_rule: Optional[str] = None
    moveable: Optional[bool] = None
    allowed_scenes: Optional[list[str]] = None
    notes: Optional[str] = None


class StartSceneUpdateRequest(BaseModel):
    scene_id: str


class SceneCreateRequest(BaseModel):
    scene_id: str
    label: str
    description: str
    image_url: Optional[str] = None
    decorative_objects: Optional[list[str]] = None


class ExitCreateRequest(BaseModel):
    from_scene_id: str
    to_scene_id: str
    label: str
    exit_type: Literal["one_way", "bidirectional"] = "one_way"
    is_locked: bool = False
    lock_description: Optional[str] = None
    code_to_unlock: Optional[str] = None
    item_to_unlock: Optional[str] = None
    rule_to_unlock: Optional[str] = None


class EntityCreateRequest(BaseModel):
    entity_id: str
    entity_type: Literal["NPC", "OBJECT"]
    scene_id: str
    name: str
    description: str
    appearance: Optional[str] = Field(default=None, max_length=100)
    image_url: Optional[str] = None
    item_type: Optional[str] = None
    is_portable: Optional[bool] = None
    goal: Optional[str] = None
    character: Optional[str] = None
    hp: Optional[int] = None
    stamina: Optional[int] = None
    mana: Optional[int] = None
    is_killable: Optional[bool] = None
    metadata_json: Optional[dict[str, Any]] = None
    wearable_slots: Optional[list[str]] = None
    combination_ingredients: Optional[list[str]] = None
    result_item_ids: Optional[list[str]] = None
    kept_ingredients: Optional[list[str]] = None
    stat_modifier_strength: Optional[int] = None
    inventory: Optional[list] = None
    is_hidden: Optional[bool] = None
    reveal_rule: Optional[str] = None
    moveable: Optional[bool] = None
    allowed_scenes: Optional[list[str]] = None
    notes: Optional[str] = None


class QuestCreateRequest(BaseModel):
    id: str
    title: str
    description: str = ""
    goal: str = ""
    impact: str = ""
    exp_reward: int = 0
    is_main: bool = False


class AwardCreateRequest(BaseModel):
    key: str
    title: str
    description: str = ""
    tier: Literal["bronze", "silver", "gold", "negative"] = "bronze"
    requirement: str = ""
    is_earned: bool = False


class ScriptCreateRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    trigger: str = "on_turn_start"
    target: Optional[str] = None
    code: str = ""
    priority: int = 100
    is_active: bool = True
