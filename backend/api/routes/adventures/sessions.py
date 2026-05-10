import logging
import os
from typing import Any, Dict, List, Optional
from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.api.routes.adventures.schemas import GameSessionResponse
from backend.api.routes.adventures.logic import AdventureLogic
from backend.utils.text_utils import generate_session_id

router = APIRouter(tags=["Sessions"])
logger = logging.getLogger(__name__)

ITEM_INTEGRITY_FIELDS = [
    "stat_modifier_strength",
    "stat_modifier_dexterity",
    "stat_modifier_intelligence",
    "stat_modifier_wisdom",
    "stat_modifier_charisma",
    "stat_modifier_armor_class",
    "hp_change",
    "stamina_change",
    "mana_change",
]


def _to_int_or_none(value):
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _backfill_item_from_entity(item: dict, entity: WorldEntity) -> dict:
    merged = dict(item)
    metadata = entity.metadata_json or {}

    def fill(key: str, *candidates):
        if merged.get(key) is not None:
            return
        for candidate in candidates:
            val = _to_int_or_none(candidate)
            if val is not None:
                merged[key] = val
                return

    fill("stat_modifier_strength", entity.stat_modifier_strength, metadata.get("stat_modifier_strength"))
    fill("stat_modifier_dexterity", entity.stat_modifier_dexterity, metadata.get("stat_modifier_dexterity"), metadata.get("stat_modifier_agility"))
    fill("stat_modifier_intelligence", entity.stat_modifier_intelligence, metadata.get("stat_modifier_intelligence"))
    fill("stat_modifier_wisdom", entity.stat_modifier_wisdom, metadata.get("stat_modifier_wisdom"))
    fill("stat_modifier_charisma", entity.stat_modifier_charisma, metadata.get("stat_modifier_charisma"))
    fill("stat_modifier_armor_class", entity.stat_modifier_armor_class, metadata.get("stat_modifier_armor_class"))

    effects = metadata.get("effects") if isinstance(metadata.get("effects"), dict) else {}
    fill("hp_change", metadata.get("hp_change"), metadata.get("health_change"), effects.get("hp"), effects.get("health"))
    fill("stamina_change", metadata.get("stamina_change"), effects.get("stamina"), effects.get("energy"))
    fill("mana_change", metadata.get("mana_change"), effects.get("mana"))

    return merged


def _backfill_avatar_items_from_template_entities(avatar: Avatar, entities_by_id: dict[str, WorldEntity]) -> None:
    inventory = []
    for item in (avatar.inventory or []):
        if isinstance(item, dict) and item.get("id") in entities_by_id:
            inventory.append(_backfill_item_from_entity(item, entities_by_id[item["id"]]))
        else:
            inventory.append(item)
    avatar.inventory = inventory

    equipment = {}
    for slot, item in (avatar.equipment or {}).items():
        if isinstance(item, dict) and item.get("id") in entities_by_id:
            equipment[slot] = _backfill_item_from_entity(item, entities_by_id[item["id"]])
        else:
            equipment[slot] = item
    avatar.equipment = equipment


def _iter_avatar_items(avatar: Avatar):
    for index, item in enumerate(avatar.inventory or []):
        if isinstance(item, dict):
            yield (f"inventory[{index}]", item)

    for slot, item in (avatar.equipment or {}).items():
        if isinstance(item, dict):
            yield (f"equipment.{slot}", item)

async def _resolve_session_asset(state: SessionState, key: str, fallback: Optional[str] = None) -> Optional[str]:
    # Placeholder or import from logic if needed
    return AdventureLogic.resolve_session_asset(state, key, fallback)

@router.get("/sessions", response_model=List[GameSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Returns all game sessions for the current user."""
    result = await db.execute(
        select(GameSession, SessionState, AdventureTemplate, WorldScene.label, Avatar.profile_image)
        .join(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(AdventureTemplate, GameSession.template_id == AdventureTemplate.id)
        .outerjoin(Avatar, Avatar.id == SessionState.avatar_id)
        .outerjoin(WorldScene, (WorldScene.template_id == GameSession.template_id) & (WorldScene.id == SessionState.current_scene_id))
        .where(GameSession.user_id == current_user.id)
    )
    rows = result.all()
    user_earned_awards = current_user.earned_awards or []
    
    return [
        GameSessionResponse(
            game_id=g.id, template_id=g.template_id, adventure_id=g.template_id, avatar_id=g.avatar_id,
            profile_image=AdventureLogic.resolve_session_asset(s, "protagonist", avatar_profile_image),
            adventure_title=a.title if a else (g.adventure_title or "Unknown"),
            adventure_version=a.version if a else None,
            image_url=AdventureLogic.resolve_session_asset(s, "cover", a.image_url if a else g.adventure_image_url),
            scene_id=s.current_scene_id, current_scene_name=scene_label or "Exploring...",
            in_game_time=s.in_game_time,
            is_ready=a.is_ready if a else True, creation_status=a.creation_status if a else "Ready",
            creation_error=a.creation_error if a else None, selected_tone=a.selected_tone if a else None,
            progress=AdventureLogic.calculate_quest_progress(s.quests if s else (a.quests if a else None)),
            quest_count=len((s.quests if s else (a.quests if a else None)) or []),
            completed_quest_count=len([q for q in ((s.quests if s else (a.quests if a else None)) or []) if q.get("status") == "completed"]),
            award_count=len((a.awards if a else None) or []),
            earned_award_count=len([aw for aw in ((a.awards if a else None) or []) if any(ea.get("key") == aw.get("key") and ea.get("template_id") == a.id for ea in user_earned_awards)]),
            created_at=g.created_at,
            status=g.status,
            status_note=g.status_note,
        )
        for g, s, a, scene_label, avatar_profile_image in rows
    ]

@router.post("/{template_id}/sessions/start", status_code=201)
async def start_session_for_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates a new active session for a template and returns its identifiers."""
    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    # Allow if user is owner OR if adventure is ready (public-ready)
    if adventure.owner_id != current_user.id and not adventure.is_ready:
        raise HTTPException(status_code=403, detail="You do not have access to this adventure yet.")

    # 1. Resolve Avatar (Template-based or fresh manifest-based)
    av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
    template_avatar = av_res.scalars().first()
    
    if template_avatar:
        # Clone template avatar for this session
        avatar = Avatar(
            user_id=current_user.id,
            template_id=template_id,
            name=template_avatar.name,
            role=template_avatar.role,
            description=template_avatar.description,
            profile_image=template_avatar.profile_image,
            hp=template_avatar.hp,
            max_hp=template_avatar.max_hp,
            stamina=template_avatar.stamina,
            max_stamina=template_avatar.max_stamina,
            mana=template_avatar.mana,
            max_mana=template_avatar.max_mana,
            strength=template_avatar.strength,
            dexterity=template_avatar.dexterity,
            intelligence=template_avatar.intelligence,
            wisdom=template_avatar.wisdom,
            charisma=template_avatar.charisma,
            armor_class=template_avatar.armor_class,
            stats=deepcopy(template_avatar.stats or {}),
            inventory=deepcopy(template_avatar.inventory or []),
            equipment=deepcopy(template_avatar.equipment or {
                "Head": None, "Chest": None, "Arms": None, "Legs": None, 
                "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, 
                "Neck": None, "MainHand": None, "OffHand": None
            }),
            status_effects=deepcopy(template_avatar.status_effects or []),
        )
    else:
        # Fallback: Create from manifest if no template avatar exists (legacy/import)
        prot = (adventure.original_manifest or {}).get("protagonist", {})
        avatar = Avatar(
            user_id=current_user.id, 
            template_id=template_id, 
            name=prot.get("name", "You"),
            role=prot.get("role"), 
            description=prot.get("description"), 
            profile_image=prot.get("profile_image"),
            hp=prot.get("hp", 200), 
            max_hp=prot.get("hp", 200), 
            stamina=prot.get("stamina", 200), 
            max_stamina=prot.get("stamina", 200), 
            mana=prot.get("mana", 200), 
            max_mana=prot.get("mana", 200),
            strength=prot.get("strength", 10),
            dexterity=prot.get("dexterity", 10),
            intelligence=prot.get("intelligence", 10),
            wisdom=prot.get("wisdom", 10),
            charisma=prot.get("charisma", 10),
            armor_class=prot.get("armor_class", 10),
            stats=prot.get("stats", {}), 
            inventory=deepcopy(prot.get("starting_inventory") or prot.get("inventory", [])),
            equipment=deepcopy(prot.get("starting_equipment") or {
                "Head": None, "Chest": None, "Arms": None, "Legs": None, 
                "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, 
                "Neck": None, "MainHand": None, "OffHand": None
            }),
            status_effects=deepcopy(prot.get("status_effects", [])),
        )

    # Repair legacy imported avatars: backfill missing item effects/stats from template entities.
    entity_rows = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.entity_type == "OBJECT",
        )
    )
    entities_by_id = {ent.id: ent for ent in entity_rows.scalars().all() if ent.id}
    if entities_by_id:
        _backfill_avatar_items_from_template_entities(avatar, entities_by_id)
    
    db.add(avatar)
    await db.flush()

    scene_res = await db.execute(select(WorldScene.id).where(WorldScene.template_id == template_id).order_by(WorldScene.id.asc()).limit(1))
    first_scene_id = scene_res.scalar_one_or_none() or "START"

    new_session = GameSession(
        id=generate_session_id(adventure.title or template_id),
        user_id=current_user.id,
        avatar_id=avatar.id,
        template_id=template_id,
        adventure_title=adventure.title,
        adventure_image_url=adventure.image_url,
        status="active"
    )
    db.add(new_session)
    await db.flush()

    # Ensure a concrete session filesystem root exists for session-bound artifacts (e.g. TTS).
    os.makedirs(os.path.join(settings.DATA_DIR, "adventures", "sessions", new_session.id), exist_ok=True)

    # Create SessionState with narrative snapshot
    new_state = SessionState(
        session_id=new_session.id, user_id=current_user.id, template_id=template_id, avatar_id=avatar.id,
        current_scene_id=first_scene_id, in_game_time=0, quests=deepcopy(adventure.quests or []),
        start_datetime=AdventureLogic.resolve_start_datetime(adventure.original_manifest),
        plot=adventure.plot,
        rules=adventure.rules,
        walkthrough=adventure.walkthrough,
        completed_condition=adventure.completed_condition,
        gameover_condition=adventure.gameover_condition,
        tts_director_notes=adventure.tts_director_notes
    )
    db.add(new_state)

    intro_text = (adventure.intro_text or "").strip()
    if intro_text:
        db.add(ChatMessage(session_id=new_session.id, role="system", content=intro_text))
    
    # --- DEEP CLONE WORLD DATA ---
    # 1. Clone Scenes
    scenes_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
    scenes = scenes_res.scalars().all()
    for s in scenes:
        new_s = WorldScene(
            id=s.id, session_id=new_session.id, template_id=None,
            label=s.label, description=s.description, image_url=s.image_url
        )
        db.add(new_s)
    
    # 2. Clone Exits
    exits_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id))
    exits = exits_res.scalars().all()
    for e in exits:
        new_e = WorldExit(
            session_id=new_session.id, template_id=None,
            from_scene_id=e.from_scene_id, to_scene_id=e.to_scene_id,
            label=e.label, is_locked=e.is_locked, lock_description=e.lock_description
        )
        db.add(new_e)
        
    # 3. Clone Entities
    entities_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id))
    entities = entities_res.scalars().all()
    for ent in entities:
        new_ent = WorldEntity(
            id=ent.id, session_id=new_session.id, template_id=None,
            entity_type=ent.entity_type, name=ent.name, description=ent.description,
            current_scene_id=ent.current_scene_id, spatial_position=ent.spatial_position,
            image_url=ent.image_url, item_type=ent.item_type, wearable_slots=ent.wearable_slots,
            is_in_inventory=ent.is_in_inventory, is_hidden=ent.is_hidden, is_portable=ent.is_portable,
            combination_ingredients=ent.combination_ingredients, reveals_item_id=ent.reveals_item_id,
            is_final_state=ent.is_final_state, state_comment=ent.state_comment,
            npc_type=ent.npc_type, movement_type=ent.movement_type,
            hp=ent.hp, max_hp=ent.max_hp, mana=ent.mana, max_mana=ent.max_mana, stamina=ent.stamina, max_stamina=ent.max_stamina,
            stat_modifier_strength=ent.stat_modifier_strength, stat_modifier_dexterity=ent.stat_modifier_dexterity,
            stat_modifier_intelligence=ent.stat_modifier_intelligence, stat_modifier_wisdom=ent.stat_modifier_wisdom,
            stat_modifier_charisma=ent.stat_modifier_charisma, stat_modifier_armor_class=ent.stat_modifier_armor_class,
            inventory=deepcopy(ent.inventory), metadata_json=deepcopy(ent.metadata_json)
        )
        db.add(new_ent)

    await db.commit()
    return {"game_id": new_session.id, "template_id": template_id, "avatar_id": avatar.id}

@router.delete("/sessions/{game_id}", status_code=200)
async def delete_session(game_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(GameSession).where((GameSession.id == game_id) & (GameSession.user_id == current_user.id)))
    game_session = result.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    avatar_id = game_session.avatar_id

    # Explicitly remove session-bound rows that may not be ORM-cascaded.
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == game_id))
    await db.execute(delete(SessionState).where(SessionState.session_id == game_id))
    await db.execute(delete(WorldEntity).where(WorldEntity.session_id == game_id))
    await db.execute(delete(WorldScene).where(WorldScene.session_id == game_id))
    await db.execute(delete(WorldExit).where(WorldExit.session_id == game_id))

    await db.delete(game_session)

    # Remove avatar only if no other session references it.
    other_session_res = await db.execute(
        select(GameSession.id).where(GameSession.avatar_id == avatar_id, GameSession.id != game_id).limit(1)
    )
    if not other_session_res.scalar_one_or_none():
        avatar_res = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
        avatar = avatar_res.scalars().first()
        if avatar:
            await db.delete(avatar)
        
    await db.commit()
    return {"status": "deleted", "game_id": game_id}


@router.get("/sessions/{game_id}/integrity/items", status_code=200)
async def check_session_item_integrity(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Checks if session avatar item modifiers/effects match available template object data."""
    session_res = await db.execute(
        select(GameSession).where((GameSession.id == game_id) & (GameSession.user_id == current_user.id))
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    avatar_res = await db.execute(select(Avatar).where(Avatar.id == game_session.avatar_id))
    avatar = avatar_res.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Session avatar not found.")

    template_entities_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == game_session.template_id,
            WorldEntity.entity_type == "OBJECT",
        )
    )
    entities_by_id = {ent.id: ent for ent in template_entities_res.scalars().all() if ent.id}

    issues: list[Dict[str, Any]] = []
    checked_items = 0

    for location, item in _iter_avatar_items(avatar):
        item_id = item.get("id")
        if not item_id:
            continue
        checked_items += 1

        entity = entities_by_id.get(item_id)
        if not entity:
            continue

        expected = _backfill_item_from_entity(item, entity)
        for field in ITEM_INTEGRITY_FIELDS:
            current_value = item.get(field)
            expected_value = expected.get(field)
            if current_value is None and expected_value is not None:
                issues.append(
                    {
                        "location": location,
                        "item_id": item_id,
                        "item_name": item.get("name") or entity.name,
                        "field": field,
                        "current": current_value,
                        "expected": expected_value,
                    }
                )

    return {
        "status": "ok",
        "game_id": game_id,
        "template_id": game_session.template_id,
        "checked_items": checked_items,
        "issue_count": len(issues),
        "issues": issues,
    }
