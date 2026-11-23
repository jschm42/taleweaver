"""Helpers for dynamic scene challenges: NPC cloning, enemy loot/keys, climax bosses, and puzzle scripts."""

from __future__ import annotations

import random
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.dynamic_cluster_context import normalize_match_token
from backend.api.routes.adventures.dynamic_scene_media import (
    extract_tone_text,
    generate_dynamic_object_image,
)
from backend.engine.party.party_state import read_party
from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.engine.world.dynamic_required_entities import npcs_to_persist, objects_to_persist
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedNpc,
    DynamicGeneratedObject,
    DynamicGeneratedScenePayload,
)
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity

_ROLE_HP_FACTORS: dict[str, float] = {
    "minion": 0.18,
    "standard": 0.35,
    "elite": 0.55,
    "boss": 0.85,
}
_DANGER_HP_MULT: dict[str, float] = {
    "peaceful": 0.7,
    "low": 0.8,
    "medium": 1.0,
    "high": 1.15,
    "deadly": 1.3,
}
_SCALED_DICE_RX = re.compile(r"^(\d+)d(\d*)([+-]\d+)?$", re.IGNORECASE)
_WEARABLE_MOD_ATTRS: tuple[str, ...] = (
    "stat_modifier_strength",
    "stat_modifier_dexterity",
    "stat_modifier_intelligence",
    "stat_modifier_wisdom",
    "stat_modifier_charisma",
    "stat_modifier_armor_class",
)
_ROLE_DMG_FACTORS: dict[str, float] = {
    "minion": 0.06,
    "standard": 0.10,
    "elite": 0.14,
    "boss": 0.18,
}
_DICE_TIERS: tuple[tuple[float, int, int], ...] = (
    (4.0, 1, 6),
    (6.5, 1, 8),
    (11.0, 2, 6),
    (15.0, 2, 8),
    (21.0, 3, 8),
    (29.0, 4, 8),
)


def average_dice_value(expr: str | None) -> float:
    """Return average roll value for dice strings such as '2d6+2', '1d8', or '1d+2'."""
    match = _SCALED_DICE_RX.match(str(expr or "").strip().replace(" ", ""))
    if not match:
        return 0.0
    count = max(1, min(20, int(match.group(1))))
    sides = max(2, int(match.group(2) or 6))
    bonus = int(match.group(3) or 0)
    return count * (sides + 1) / 2.0 + bonus


def dice_for_target_average(target_avg: float) -> str:
    """Build a standard RPG dice string ('NdM' or 'NdM+K') matching ``target_avg``."""
    target = max(3.5, float(target_avg))
    num_dice, sides = 5, 10
    for threshold, dice_count, die_sides in _DICE_TIERS:
        if target <= threshold:
            num_dice, sides = dice_count, die_sides
            break
    base = num_dice * (sides + 1) / 2.0
    bonus = max(0, int(round(target - base)))
    return f"{num_dice}d{sides}+{bonus}" if bonus > 0 else f"{num_dice}d{sides}"


def _effective_enemy_hp_reference(
    party_hp: int,
    enemy_hps: list[int],
    danger: str,
) -> float:
    base_enemy_hp = float(scale_enemy_hp("standard", party_hp, danger=danger))
    valid_hps = [h for h in enemy_hps if h > 0]
    if not valid_hps:
        return base_enemy_hp
    mean_hp = sum(valid_hps) / len(valid_hps)
    clamped = max(base_enemy_hp * 0.65, min(base_enemy_hp * 1.65, mean_hp))
    return 0.5 * base_enemy_hp + 0.5 * clamped


def _scale_weapon_object(
    obj: Any,
    ref_enemy_hp: float,
    is_climax: bool,
    instructions: str = "",
) -> None:
    raw_dice = str(obj.damage_dice or "").strip().lower()
    if raw_dice and raw_dice in instructions.lower():
        return
    target_avg = max(4.5, min(42.0, ref_enemy_hp * (0.30 if is_climax else 0.25)))
    min_avg = max(4.0, round(target_avg * 0.62, 1))
    max_avg = max(min_avg + 3.0, round(target_avg * 1.38, 1))
    current_avg = average_dice_value(obj.damage_dice)
    if current_avg < min_avg or current_avg > max_avg:
        obj.damage_dice = dice_for_target_average(target_avg)


def _scale_consumable_object(
    obj: Any,
    party_hp: int,
    ref_enemy_hp: float,
    is_climax: bool,
) -> None:
    hp_pool = 0.65 * max(40, party_hp) + 0.70 * ref_enemy_hp
    target_heal = max(10, min(200, int(round(hp_pool * (0.35 if is_climax else 0.28)))))
    min_heal = max(8, int(round(target_heal * 0.65)))
    max_heal = max(min_heal + 10, min(250, int(round(target_heal * 1.45))))

    if obj.hp_change == 0 and obj.stamina_change == 0 and obj.mana_change == 0:
        obj.hp_change = target_heal
    elif obj.hp_change > 0:
        obj.hp_change = max(min_heal, min(max_heal, int(obj.hp_change)))
    elif obj.hp_change < 0:
        min_dmg = max(5, int(round(target_heal * 0.35)))
        max_dmg = max(min_dmg + 5, int(round(target_heal * 0.90)))
        obj.hp_change = -max(min_dmg, min(max_dmg, abs(int(obj.hp_change))))

    for attr in ("stamina_change", "mana_change"):
        val = int(getattr(obj, attr, 0) or 0)
        if val > 0:
            setattr(obj, attr, max(15, min(45, val)))
        elif val < 0:
            setattr(obj, attr, -max(10, min(35, abs(val))))


def _scale_wearable_object(
    obj: Any,
    party_hp: int,
    is_climax: bool,
) -> None:
    max_single = 3 if (is_climax or party_hp >= 160) else 2
    for attr in _WEARABLE_MOD_ATTRS:
        val = int(getattr(obj, attr, 0) or 0)
        if val > max_single:
            setattr(obj, attr, max_single)
        elif val < -2:
            setattr(obj, attr, -2)


def scale_dynamic_object_stats(
    obj: Any,
    *,
    party_hp: int,
    enemy_hps: list[int],
    danger: str = "medium",
    is_climax: bool = False,
    instructions: str = "",
) -> None:
    """Scale dynamic weapon damage, potion healing, and wearable bonuses to party and enemy HP."""
    ref_enemy_hp = _effective_enemy_hp_reference(party_hp, enemy_hps, danger)
    if obj.item_type == "WEAPON":
        _scale_weapon_object(obj, ref_enemy_hp, is_climax, instructions=instructions)
    elif obj.item_type == "CONSUMABLE":
        _scale_consumable_object(obj, party_hp, ref_enemy_hp, is_climax)
    elif obj.item_type == "WEARABLE":
        _scale_wearable_object(obj, party_hp, is_climax)


def scale_enemy_hp(
    combat_role: str,
    party_hp: int,
    *,
    danger: str = "medium",
    clone_count: int = 1,
) -> int:
    """Scale hostile NPC HP fairly against protagonist + active companion HP."""
    role_factor = _ROLE_HP_FACTORS.get(str(combat_role or "").lower(), 0.30)
    danger_mult = _DANGER_HP_MULT.get(str(danger or "medium").lower(), 1.0)
    count = max(1, int(clone_count or 1))
    pack_factor = max(0.4, 1.0 / (count**0.65)) if count > 1 else 1.0
    return max(12, int(round(max(40, party_hp) * role_factor * danger_mult * pack_factor)))


async def compute_party_hp_budget(db: AsyncSession, state: SessionState) -> int:
    """Return combined max HP of the protagonist and active party companion."""
    prot_hp = 100
    if getattr(state, "avatar_id", None):
        avatar = (
            await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
        ).scalar_one_or_none()
        if avatar is not None:
            prot_hp = max(20, int(avatar.max_hp or avatar.hp or 100))

    comp_hp = 0
    party = read_party(state.entity_states)
    if party.active_id:
        comp = (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == state.session_id,
                    WorldEntity.id == party.active_id,
                )
            )
        ).scalar_one_or_none()
        if comp is not None:
            comp_hp = max(0, int(comp.max_hp or comp.hp or 0))
    return max(40, min(400, prot_hp + comp_hp))


_QUOTED_TOKEN_RE = re.compile(r"(['\"])([A-Za-z0-9_]+)\1")


def _safe_slug(raw: str, max_len: int = 24) -> str:
    cleaned = re.sub(r"[^A-Z0-9]+", "_", str(raw or "").upper()).strip("_")
    return (cleaned or "ITEM")[:max_len]


def sanitize_dynamic_script(
    raw_script: Optional[str],
    raw_id_to_entity: dict[str, WorldEntity],
) -> Optional[str]:
    """Rewrite local entity IDs to persisted IDs and validate against the script sandbox."""
    code = str(raw_script or "").strip()
    if not code:
        return None

    def _replace_token(match: re.Match[str]) -> str:
        quote, token = match.group(1), match.group(2)
        entity = raw_id_to_entity.get(normalize_match_token(token))
        return f"{quote}{entity.id}{quote}" if entity is not None else match.group(0)

    rewritten = _QUOTED_TOKEN_RE.sub(_replace_token, code)
    if SafeAstInterpreter.check_syntax(rewritten):
        return None
    return rewritten


def build_dynamic_npc_clones(
    *,
    session_id: str,
    target_id: str,
    npc: DynamicGeneratedNpc,
    image_url: Optional[str],
    state: SessionState,
    existing_ids: Optional[set[str]] = None,
    party_hp: int = 100,
    danger: str = "medium",
) -> list[tuple[WorldEntity, bool]]:
    """Build 1..clone_count WorldEntity instances for a dynamic NPC."""
    is_hostile = npc.attitude == "hostile"
    raw_count = int(getattr(npc, "clone_count", 1) or 1) if is_hostile else 1
    count = max(1, min(5, raw_count))
    npc_type = str(getattr(npc, "npc_type", "HUMANOID") or "HUMANOID").upper()
    dialogue_style = str(npc.dialogue_style or "").strip()
    if npc_type in {"HUMANOID", "BEING"} and "full sentences" not in dialogue_style.lower():
        speech_note = "Speaks in plain, intelligible full sentences."
        dialogue_style = f"{dialogue_style} ({speech_note})" if dialogue_style else speech_note

    hp_val = (
        scale_enemy_hp(npc.combat_role, party_hp, danger=danger, clone_count=count)
        if is_hostile
        else 100
    )
    base_slug = _safe_slug(npc.id, 14)
    results: list[tuple[WorldEntity, bool]] = []
    entity_states = dict(state.entity_states or {})

    raw_attack_mode = str(getattr(npc, "attack_mode", "PASSIVE") or "PASSIVE").upper()
    if is_hostile and raw_attack_mode != "ATTACK_ON_SIGHT" and random.random() < 0.3:
        raw_attack_mode = "ATTACK_ON_SIGHT"
    attack_mode = raw_attack_mode if is_hostile else "PASSIVE"

    make_companion = (
        not is_hostile
        and npc_type in {"HUMANOID", "BEING", "ANIMAL"}
        and (bool(getattr(npc, "is_recruitable_companion", False)) or random.random() < 0.25)
    )

    for idx in range(count):
        suffix = f"_{idx + 1}" if idx > 0 else ""
        entity_id = f"{target_id}_{base_slug}{suffix}"[:50]
        if existing_ids is not None and entity_id in existing_ids:
            continue
        if existing_ids is not None:
            existing_ids.add(entity_id)

        display_name = f"{npc.name[:94]} #{idx + 1}" if count > 1 else npc.name[:100]
        meta: dict[str, Any] = {
            "dynamic_generated": True,
            "attitude": npc.attitude,
            "combat_role": npc.combat_role,
            "attack_mode": attack_mode,
        }
        if make_companion and idx == 0:
            safe_name = display_name.replace("'", "")
            meta["companion"] = {
                "recruitable": True,
                "starts_in_party": False,
                "tactics": str(getattr(npc, "companion_tactics", "BALANCED") or "BALANCED"),
                "banter": str(getattr(npc, "companion_banter", "NORMAL") or "NORMAL"),
                "downed_recovery": 0.25,
                # The player recruits it with the Recruit action (frame + tag in the play view).
                "recruit_mode": "INSTANT",
            }
            meta["on_recruit_success_text"] = f"{safe_name} eagerly joins your party!"
            comp_dice = "1d6" if party_hp <= 110 else dice_for_target_average(party_hp * 0.08)
            meta["main_attack"] = {
                "name": "Strike",
                "category": "MELEE",
                "damage_dice": comp_dice,
                "hit_stat": "dexterity",
            }
            meta["on_interact_script"] = (
                f"if tw.party.is_member('{entity_id}'):\n"
                f"    tw.party.dismiss('{entity_id}')\n"
                f"    tw.story.narrate('{safe_name} steps back from your party.')"
            )
        elif is_hostile:
            role_dmg = _ROLE_DMG_FACTORS.get(str(npc.combat_role or "").lower(), 0.09)
            danger_mult = _DANGER_HP_MULT.get(str(danger or "medium").lower(), 1.0)
            pack_mult = max(0.55, 1.0 / (count**0.5)) if count > 1 else 1.0
            target_dmg = max(3.5, max(40, party_hp) * role_dmg * danger_mult * pack_mult)
            meta["main_attack"] = {
                "name": "Attack",
                "category": "MELEE",
                "damage_dice": dice_for_target_average(target_dmg),
                "hit_stat": "strength",
            }

        entity = WorldEntity(
            id=entity_id,
            template_id=None,
            session_id=session_id,
            entity_type="NPC",
            name=display_name,
            description=npc.description[:1000],
            appearance=npc.visual_description[:100] if npc.visual_description else None,
            current_scene_id=target_id,
            image_url=image_url,
            npc_type=npc_type,
            movement_type="STATIONARY",
            moveable=False,
            goal=npc.role[:1000] if npc.role else None,
            character=dialogue_style[:1000] if dialogue_style else None,
            hp=hp_val,
            max_hp=hp_val,
            mana=100,
            max_mana=100,
            stamina=100,
            max_stamina=100,
            is_attackable=is_hostile,
            is_killable=is_hostile,
            inventory=[],
            metadata_json=meta,
        )
        if is_hostile:
            entity_states[entity_id] = {"hp": hp_val, "max_hp": hp_val, "attitude": "hostile"}
        results.append((entity, idx == 0))

    if is_hostile and results:
        state.entity_states = entity_states
        flag_modified(state, "entity_states")
    return results


def link_dynamic_npc_inventories(
    npc_entries: list[tuple[DynamicGeneratedNpc, WorldEntity, bool]],
    raw_id_to_entity: dict[str, WorldEntity],
) -> None:
    """Attach carried loot/keys to primary NPC entities and move them off the scene floor."""
    for npc_spec, npc_entity, is_primary in npc_entries:
        if not is_primary or not npc_spec.inventory:
            continue
        resolved: list[str] = list(npc_entity.inventory or [])
        for token in npc_spec.inventory:
            item_ent = raw_id_to_entity.get(normalize_match_token(token))
            if item_ent is None or item_ent.entity_type != "OBJECT":
                continue
            if item_ent.id not in resolved:
                resolved.append(item_ent.id)
            item_ent.current_scene_id = "INVENTORY"
        npc_entity.inventory = resolved


def apply_dynamic_scripts_and_locks(
    objects: list[DynamicGeneratedObject],
    npc_entries: list[tuple[DynamicGeneratedNpc, WorldEntity, bool]],
    raw_id_to_entity: dict[str, WorldEntity],
) -> None:
    """Validate and wire optional puzzle scripts and local key-lock references."""
    for obj in objects:
        obj_entity = raw_id_to_entity.get(normalize_match_token(obj.id))
        if obj_entity is None:
            continue
        meta = dict(obj_entity.metadata_json or {})
        if obj.item_to_unlock:
            key_ent = raw_id_to_entity.get(normalize_match_token(obj.item_to_unlock))
            if key_ent is not None:
                meta["item_to_unlock"] = key_ent.id
        script = sanitize_dynamic_script(obj.on_interact_script, raw_id_to_entity)
        if script:
            meta["on_interact_script"] = script
        obj_entity.metadata_json = meta

    for npc_spec, npc_entity, is_primary in npc_entries:
        if not is_primary or not npc_spec.on_defeat_script:
            continue
        script = sanitize_dynamic_script(npc_spec.on_defeat_script, raw_id_to_entity)
        if script:
            meta = dict(npc_entity.metadata_json or {})
            meta["on_defeat_script"] = script
            npc_entity.metadata_json = meta


def _is_key_item(entity: WorldEntity) -> bool:
    meta = entity.metadata_json if isinstance(entity.metadata_json, dict) else {}
    if meta.get("is_zone_key") or meta.get("dynamic_zone_key_for"):
        return True
    haystack = f"{entity.id} {entity.name}".lower()
    return "key" in haystack or "schlüssel" in haystack or "schluessel" in haystack


def _build_fallback_key_appearance(zone: dict[str, Any], adventure: Any, user: Any = None) -> str:
    """Compose an image appearance prompt from the adventure's tone, cover appearance, and zone theme."""
    tone_text = extract_tone_text(adventure, user) if adventure is not None else ""
    zone_theme = str(zone.get("root_theme") or zone.get("theme") or "").strip()
    cover_app = str(getattr(adventure, "cover_appearance", "") or "").strip() if adventure else ""
    parts = [
        "key item that unlocks a locked container",
        zone_theme[:160],
        tone_text[:160],
        cover_app[:100],
    ]
    return ", ".join(part for part in parts if part)


async def _find_cluster_key(
    db: AsyncSession,
    session_id: str,
    zone_id: str,
    local_objects: list[WorldEntity],
) -> Optional[WorldEntity]:
    for obj in local_objects:
        if _is_key_item(obj):
            return obj

    rows = (
        (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == session_id,
                    WorldEntity.entity_type == "OBJECT",
                )
            )
        )
        .scalars()
        .all()
    )
    target_zone = str(zone_id or "").strip().lower()
    for ent in rows:
        meta = ent.metadata_json if isinstance(ent.metadata_json, dict) else {}
        if str(meta.get("dynamic_zone_key_for") or "").strip().lower() == target_zone:
            return ent
    return None


def _promote_climax_boss(
    hostile_npcs: list[WorldEntity],
    danger: str,
    state: SessionState,
    party_hp: int,
) -> None:
    if not hostile_npcs:
        return
    boss_role = "elite" if danger == "low" else "boss"
    has_boss = any(
        (n.metadata_json or {}).get("combat_role") in {"elite", "boss"} for n in hostile_npcs
    )
    if has_boss:
        return

    leader = hostile_npcs[0]
    boss_hp = scale_enemy_hp(boss_role, party_hp, danger=danger, clone_count=1)
    leader.hp = boss_hp
    leader.max_hp = boss_hp
    meta = dict(leader.metadata_json or {})
    meta["combat_role"] = boss_role
    leader.metadata_json = meta
    states = dict(state.entity_states or {})
    states[leader.id] = {"hp": boss_hp, "max_hp": boss_hp, "attitude": "hostile"}
    state.entity_states = states
    flag_modified(state, "entity_states")


_DEFAULT_ZONE_KEY_NAME = "Zone Key"
_DEFAULT_ZONE_KEY_DESC = "A distinctive key recovered from a guardian of this area, made to unlock a sealed container nearby."


async def resolve_fallback_zone_key_prompt(
    *,
    db: AsyncSession,
    session_id: str,
    zone: dict[str, Any],
    payload: DynamicGeneratedScenePayload,
    max_npcs: int,
    adventure: Any = None,
    user: Any = None,
) -> Optional[tuple[str, str, str]]:
    """Return ``(name, desc, appearance)`` if this scene needs a fallback Zone Key artwork task."""
    danger = str(zone.get("danger_level") or "medium").strip().lower()
    if danger == "peaceful":
        return None
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    if depth >= max_depth and bool(zone.get("cul_de_sac_on_max_depth", True)):
        return None
    if not any(npc.attitude == "hostile" for npc in npcs_to_persist(payload, max_npcs)):
        return None
    for obj in objects_to_persist(payload):
        haystack = f"{obj.id} {obj.name}".lower()
        if getattr(obj, "is_zone_key", False) or any(
            tok in haystack for tok in ("key", "schlüssel", "schluessel")
        ):
            return None
    existing_key = await _find_cluster_key(db, session_id, str(zone.get("zone_id") or ""), [])
    if existing_key is not None:
        return None
    return (
        _DEFAULT_ZONE_KEY_NAME,
        _DEFAULT_ZONE_KEY_DESC,
        _build_fallback_key_appearance(zone, adventure, user),
    )


async def _ensure_non_climax_zone_key(
    *,
    db: AsyncSession,
    state: SessionState,
    zone: dict[str, Any],
    zone_id: str,
    target_id: str,
    hostile_npcs: list[WorldEntity],
    object_entities: list[WorldEntity],
    dyn_cfg: Optional[dict[str, Any]],
    user: Any,
    adventure: Any,
    pregenerated_key_image: Optional[str],
    key_image_pregenerated: bool,
) -> Optional[WorldEntity]:
    if not hostile_npcs:
        return None
    existing_key = await _find_cluster_key(db, state.session_id, zone_id, object_entities)
    if existing_key is not None:
        meta = dict(existing_key.metadata_json or {})
        meta["dynamic_zone_key_for"] = zone_id
        existing_key.metadata_json = meta
        return None

    key_appearance = _build_fallback_key_appearance(zone, adventure, user)
    key_image = (
        pregenerated_key_image
        if key_image_pregenerated
        else await generate_dynamic_object_image(
            name=_DEFAULT_ZONE_KEY_NAME,
            description=_DEFAULT_ZONE_KEY_DESC,
            appearance=key_appearance,
            dyn_cfg=dyn_cfg,
            user=user,
            adventure=adventure,
            session_id=state.session_id,
            prefix=f"{target_id}_zone_key",
        )
    )
    key_entity = WorldEntity(
        id=f"{target_id}_ZONE_KEY"[:50],
        template_id=None,
        session_id=state.session_id,
        entity_type="OBJECT",
        name=_DEFAULT_ZONE_KEY_NAME,
        description=_DEFAULT_ZONE_KEY_DESC,
        current_scene_id="INVENTORY",
        image_url=key_image,
        item_type="STANDARD",
        is_portable=True,
        inventory=[],
        metadata_json={
            "dynamic_generated": True,
            "is_zone_key": True,
            "dynamic_zone_key_for": zone_id,
        },
    )
    db.add(key_entity)
    carrier = hostile_npcs[0]
    carrier.inventory = [*list(carrier.inventory or []), key_entity.id]
    return key_entity


async def _lock_climax_chest(
    db: AsyncSession,
    session_id: str,
    zone_id: str,
    object_entities: list[WorldEntity],
) -> None:
    containers = [o for o in object_entities if o.item_type == "CONTAINER"]
    if not containers:
        return
    chest = containers[0]
    chest_meta = dict(chest.metadata_json or {})
    if chest_meta.get("locked") and chest_meta.get("item_to_unlock"):
        return
    cluster_key = await _find_cluster_key(db, session_id, zone_id, object_entities)
    if cluster_key is None:
        return
    chest_meta["locked"] = True
    chest_meta["item_to_unlock"] = cluster_key.id
    chest_meta["lock_description"] = (
        chest_meta.get("lock_description") or f"Locked. Requires {cluster_key.name}."
    )
    chest.metadata_json = chest_meta


async def apply_cluster_key_and_climax_progression(
    *,
    db: AsyncSession,
    state: SessionState,
    zone: dict[str, Any],
    target_id: str,
    npc_entities: list[WorldEntity],
    object_entities: list[WorldEntity],
    dyn_cfg: Optional[dict[str, Any]] = None,
    user: Any = None,
    adventure: Any = None,
    pregenerated_key_image: Optional[str] = None,
    key_image_pregenerated: bool = False,
) -> Optional[WorldEntity]:
    """Tag or spawn an enemy-held zone key on non-climax depth, and enforce boss + locked chest at climax."""
    danger = str(zone.get("danger_level") or "medium").strip().lower()
    if danger == "peaceful":
        return None

    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    is_climax = depth >= max_depth and bool(zone.get("cul_de_sac_on_max_depth", True))
    zone_id = str(zone.get("zone_id") or "")
    hostile_npcs = [n for n in npc_entities if n.is_attackable]

    if not is_climax:
        return await _ensure_non_climax_zone_key(
            db=db,
            state=state,
            zone=zone,
            zone_id=zone_id,
            target_id=target_id,
            hostile_npcs=hostile_npcs,
            object_entities=object_entities,
            dyn_cfg=dyn_cfg,
            user=user,
            adventure=adventure,
            pregenerated_key_image=pregenerated_key_image,
            key_image_pregenerated=key_image_pregenerated,
        )

    party_hp = await compute_party_hp_budget(db, state)
    _promote_climax_boss(hostile_npcs, danger, state, party_hp)
    await _lock_climax_chest(db, state.session_id, zone_id, object_entities)
    return None
