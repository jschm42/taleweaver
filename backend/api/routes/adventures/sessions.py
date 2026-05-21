import logging
import os
from copy import deepcopy
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import GameSessionResponse
from backend.schemas.session import GameSessionUpdate
from backend.engine.session_exporter import SessionExporter
from backend.engine.session_importer import SessionImporter
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from sqlalchemy import delete
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.game_state import GameState
from backend.models.world_map import WorldMap
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


def _reconstruct_item_dict_from_entity(entity: WorldEntity) -> dict:
    from backend.engine.item_logic import get_item_slot
    guessed_slot = get_item_slot(entity.name, entity.item_type or "PICKABLE")
    slots = entity.wearable_slots
    if isinstance(slots, list) and len(slots) > 0:
        item_slot = slots[0]
    elif isinstance(slots, str):
        item_slot = slots
    else:
        item_slot = guessed_slot

    metadata = entity.metadata_json or {}
    effects = metadata.get("effects") if isinstance(metadata.get("effects"), dict) else {}

    def get_val(*candidates):
        for candidate in candidates:
            val = _to_int_or_none(candidate)
            if val is not None:
                return val
        return None

    return {
        "id": entity.id,
        "name": entity.name,
        "description": entity.description,
        "image_url": entity.image_url,
        "item_type": entity.item_type or "PICKABLE",
        "slot": item_slot,
        "stat_modifier_strength": get_val(entity.stat_modifier_strength, metadata.get("stat_modifier_strength")),
        "stat_modifier_dexterity": get_val(entity.stat_modifier_dexterity, metadata.get("stat_modifier_dexterity"), metadata.get("stat_modifier_agility")),
        "stat_modifier_intelligence": get_val(entity.stat_modifier_intelligence, metadata.get("stat_modifier_intelligence")),
        "stat_modifier_wisdom": get_val(entity.stat_modifier_wisdom, metadata.get("stat_modifier_wisdom")),
        "stat_modifier_charisma": get_val(entity.stat_modifier_charisma, metadata.get("stat_modifier_charisma")),
        "stat_modifier_armor_class": get_val(entity.stat_modifier_armor_class, metadata.get("stat_modifier_armor_class")),
        "hp_change": get_val(metadata.get("hp_change"), metadata.get("health_change"), effects.get("hp"), effects.get("health")),
        "stamina_change": get_val(metadata.get("stamina_change"), effects.get("stamina"), effects.get("energy")),
        "mana_change": get_val(metadata.get("mana_change"), effects.get("mana")),
    }


def _backfill_avatar_items_from_template_entities(avatar: Avatar, entities_by_id: dict[str, WorldEntity]) -> None:
    inventory = []
    for item in (avatar.inventory or []):
        if isinstance(item, str) and item in entities_by_id:
            inventory.append(_reconstruct_item_dict_from_entity(entities_by_id[item]))
        elif isinstance(item, dict) and item.get("id") in entities_by_id:
            inventory.append(_backfill_item_from_entity(item, entities_by_id[item["id"]]))
        else:
            inventory.append(item)
    avatar.inventory = inventory

    equipment = {}
    for slot, item in (avatar.equipment or {}).items():
        if isinstance(item, str) and item in entities_by_id:
            equipment[slot] = _reconstruct_item_dict_from_entity(entities_by_id[item])
        elif isinstance(item, dict) and item.get("id") in entities_by_id:
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

@router.get("/sessions", response_model=list[GameSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Returns all game sessions for the current user."""
    result = await db.execute(
        select(GameSession, SessionState, AdventureTemplate, WorldScene.label, Avatar.profile_image)
        .outerjoin(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(AdventureTemplate, GameSession.template_id == AdventureTemplate.id)
        .outerjoin(Avatar, Avatar.id == SessionState.avatar_id)
        .outerjoin(
            WorldScene,
            (WorldScene.id == SessionState.current_scene_id)
            & (WorldScene.session_id == GameSession.id),
        )
        .where(GameSession.user_id == current_user.id)
        .distinct()
    )
    rows = result.all()
    user_earned_awards = current_user.earned_awards or []
    
    return [
        GameSessionResponse(
            game_id=g.id, template_id=g.template_id, adventure_id=g.template_id, avatar_id=g.avatar_id,
            profile_image=AdventureLogic.resolve_session_asset(s, "protagonist", avatar_profile_image),
            adventure_title=a.title if a else (g.adventure_title or "Unknown"),
            adventure_version=a.version if a else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get("version"),
            image_url=AdventureLogic.resolve_session_asset(s, "cover", a.image_url if a else g.adventure_image_url),
            scene_id=s.current_scene_id if s else "START", 
            current_scene_name=scene_label or ("Exploring..." if s else "Archived"),
            in_game_time=s.in_game_time if s else 0,
            is_ready=a.is_ready if a else True, creation_status=a.creation_status if a else "Ready",
            creation_error=a.creation_error if a else None, selected_tone=a.selected_tone if a else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get("selected_tone"),
            progress=AdventureLogic.calculate_quest_progress(s.quests if s else (a.quests if a else None)),
            quest_count=len((s.quests if s else (a.quests if a else None)) or []),
            completed_quest_count=len([q for q in ((s.quests if s else (a.quests if a else None)) or []) if q.get("status") == "completed"]),
            award_count=len((a.awards if a else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get("awards")) or []),
            earned_award_count=len([aw for aw in ((a.awards if a else None) or []) if any(ea.get("key") == aw.get("key") and ea.get("template_id") == a.id for ea in user_earned_awards)]),
            created_at=g.created_at,
            status=g.status,
            status_note=g.status_note,
            copied_from_id=g.copied_from_id,
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
    av_res = await db.execute(
        select(Avatar)
        .where(Avatar.template_id == template_id)
        .order_by(Avatar.created_at.asc())
        .limit(1)
    )
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
            WorldEntity.session_id.is_(None),
            WorldEntity.entity_type == "OBJECT",
        )
    )
    entities_by_id = {ent.id: ent for ent in entity_rows.scalars().all() if ent.id}
    if entities_by_id:
        _backfill_avatar_items_from_template_entities(avatar, entities_by_id)
    
    db.add(avatar)
    await db.flush()

    scene_res = await db.execute(
        select(WorldScene.id)
        .where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
        .order_by(WorldScene.id.asc())
        .limit(1)
    )
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

    # Create SessionState with narrative and asset snapshot
    manifest_snapshot = AdventureLogic.build_session_manifest_snapshot(adventure)

    # Build entity image mapping from template entities for asset snapshot
    ent_rows = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
        )
    )
    template_entities = ent_rows.scalars().all()
    entity_images = {e.id: e.image_url for e in template_entities if getattr(e, "id", None)}

    asset_snapshot = {
        "cover": adventure.image_url,
        "protagonist": avatar.profile_image,
        "entity_images": entity_images,
    }

    initial_entity_states = {
        AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: manifest_snapshot,
        "__asset_snapshot__": asset_snapshot,
    }
    for ent in template_entities:
        if str(getattr(ent, "entity_type", "") or "").upper() != "OBJECT":
            continue
        metadata_json = dict(getattr(ent, "metadata_json", None) or {})
        locked = metadata_json.get("locked")
        if isinstance(locked, bool):
            initial_entity_states[ent.id] = {"locked": locked}

    new_state = SessionState(
        session_id=new_session.id, user_id=current_user.id, template_id=template_id, avatar_id=avatar.id,
        current_scene_id=first_scene_id, in_game_time=0, quests=deepcopy(adventure.quests or []),
        entity_states=initial_entity_states,
        start_datetime=AdventureLogic.resolve_start_datetime(adventure.original_manifest),
        plot=adventure.plot,
        rules=adventure.rules,
        walkthrough=adventure.walkthrough,
        completed_condition=adventure.completed_condition,
        gameover_condition=adventure.gameover_condition,
        tts_director_notes=adventure.tts_director_notes,
        selected_image_styles=deepcopy(adventure.selected_image_styles),
        selected_tone=deepcopy(adventure.selected_tone)
    )
    db.add(new_state)

    intro_text = (adventure.intro_text or "").strip()
    if intro_text:
        db.add(ChatMessage(session_id=new_session.id, role="system", content=intro_text))
    
    # --- DEEP CLONE WORLD DATA ---
    # 1. Clone Scenes
    scenes_res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
    )
    scenes = scenes_res.scalars().all()
    for s in scenes:
        new_s = WorldScene(
            id=s.id, session_id=new_session.id, template_id=None,
            label=s.label, description=s.description, image_url=s.image_url
        )
        db.add(new_s)
    
    # 2. Clone Exits
    exits_res = await db.execute(
        select(WorldExit).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
        )
    )
    exits = exits_res.scalars().all()
    for e in exits:
        new_e = WorldExit(
            session_id=new_session.id, template_id=None,
            from_scene_id=e.from_scene_id, to_scene_id=e.to_scene_id,
            label=e.label, is_locked=e.is_locked, lock_description=e.lock_description
        )
        db.add(new_e)
        
    # 3. Clone Entities
    entities_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
        )
    )
    entities = entities_res.scalars().all()
    for ent in entities:
        new_ent = WorldEntity(
            id=ent.id, session_id=new_session.id, template_id=None,
            entity_type=ent.entity_type, name=ent.name, description=ent.description,
            current_scene_id=ent.current_scene_id, spatial_position=ent.spatial_position,
            image_url=ent.image_url, item_type=ent.item_type, wearable_slots=ent.wearable_slots,
            is_in_inventory=ent.is_in_inventory, is_hidden=ent.is_hidden, unlock_rule=ent.unlock_rule, is_portable=ent.is_portable,
            combination_ingredients=ent.combination_ingredients, reveals_item_id=ent.reveals_item_id,
            is_final_state=ent.is_final_state, state_comment=ent.state_comment,
            npc_type=ent.npc_type, movement_type=ent.movement_type,
            hp=ent.hp, max_hp=ent.max_hp, mana=ent.mana, max_mana=ent.max_mana, stamina=ent.stamina, max_stamina=ent.max_stamina,
            stat_modifier_strength=ent.stat_modifier_strength, stat_modifier_dexterity=ent.stat_modifier_dexterity,
            stat_modifier_intelligence=ent.stat_modifier_intelligence, stat_modifier_wisdom=ent.stat_modifier_wisdom,
            stat_modifier_charisma=ent.stat_modifier_charisma, stat_modifier_armor_class=ent.stat_modifier_armor_class,
            is_attackable=ent.is_attackable,
            is_killable=ent.is_killable,
            inventory=deepcopy(ent.inventory), metadata_json=deepcopy(ent.metadata_json)
        )
        db.add(new_ent)

    await db.commit()
    return {"game_id": new_session.id, "template_id": template_id, "avatar_id": avatar.id}


@router.post("/{template_id}/reset")
async def reset_adventure(template_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Resets a template into a fresh state while preserving any already-generated image URLs on the template/world data."""
    # Verify ownership
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found.")

    # Remove session-bound rows and leave template-level images intact.
    # Only delete rows that belong to active sessions (session_id IS NOT NULL).
    await db.execute(delete(GameSession).where(GameSession.template_id == template_id))
    await db.execute(delete(SessionState).where(SessionState.template_id == template_id))
    await db.execute(delete(WorldEntity).where((WorldEntity.template_id == template_id) & (WorldEntity.session_id != None)))
    await db.execute(delete(WorldScene).where((WorldScene.template_id == template_id) & (WorldScene.session_id != None)))
    await db.execute(delete(WorldExit).where((WorldExit.template_id == template_id) & (WorldExit.session_id != None)))
    await db.commit()
    return {"status": "success"}

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
    await db.execute(delete(WorldMap).where(WorldMap.session_id == game_id))

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


@router.delete("/sessions/{game_id}/messages/{message_id}", status_code=200)
async def delete_chat_message(
    game_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a single chat message from the session history in debug mode."""
    session_res = await db.execute(
        select(GameSession).where((GameSession.id == game_id) & (GameSession.user_id == current_user.id))
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    state_res = await db.execute(
        select(SessionState).where(SessionState.session_id == game_id)
    )
    state = state_res.scalars().first()
    is_debug = settings.TALEWEAVER_DEBUG_ENABLED or (state and state.is_debug_enabled)
    if not is_debug:
        raise HTTPException(status_code=403, detail="Not in debug mode.")

    msg_res = await db.execute(
        select(ChatMessage).where((ChatMessage.id == message_id) & (ChatMessage.session_id == game_id))
    )
    message = msg_res.scalars().first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found.")

    await db.delete(message)
    await db.commit()
    return {"status": "deleted", "message_id": message_id}


@router.get("/sessions/{game_id}/integrity/items", status_code=200)
async def check_session_item_integrity(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
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

    issues: list[dict[str, Any]] = []
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


@router.post("/sessions/{game_id}/copy", status_code=201)
async def copy_session(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Creates a full duplicate/copy of an existing session."""
    # 1. Fetch original session
    session_res = await db.execute(
        select(GameSession).where((GameSession.id == game_id) & (GameSession.user_id == current_user.id))
    )
    original_session = session_res.scalars().first()
    if not original_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # 2. Fetch original avatar
    avatar_res = await db.execute(select(Avatar).where(Avatar.id == original_session.avatar_id))
    original_avatar = avatar_res.scalars().first()
    if not original_avatar:
        raise HTTPException(status_code=404, detail="Session avatar not found.")

    # 3. Clone Avatar
    cloned_avatar = Avatar(
        user_id=current_user.id,
        template_id=original_avatar.template_id,
        name=original_avatar.name,
        role=original_avatar.role,
        description=original_avatar.description,
        profile_image=original_avatar.profile_image,
        hp=original_avatar.hp,
        max_hp=original_avatar.max_hp,
        stamina=original_avatar.stamina,
        max_stamina=original_avatar.max_stamina,
        mana=original_avatar.mana,
        max_mana=original_avatar.max_mana,
        strength=original_avatar.strength,
        dexterity=original_avatar.dexterity,
        intelligence=original_avatar.intelligence,
        wisdom=original_avatar.wisdom,
        charisma=original_avatar.charisma,
        armor_class=original_avatar.armor_class,
        stats=deepcopy(original_avatar.stats or {}),
        inventory=deepcopy(original_avatar.inventory or []),
        equipment=deepcopy(original_avatar.equipment or {}),
        status_effects=deepcopy(original_avatar.status_effects or []),
    )
    db.add(cloned_avatar)
    await db.flush()

    # 4. Create cloned GameSession
    orig_title = original_session.adventure_title or "Unknown Adventure"
    if orig_title.startswith("Kopie von "):
        new_title = orig_title
    else:
        new_title = f"Kopie von {orig_title}"

    copied_session = GameSession(
        id=generate_session_id(original_session.adventure_title or original_session.template_id or "copy"),
        user_id=current_user.id,
        avatar_id=cloned_avatar.id,
        template_id=original_session.template_id,
        adventure_title=new_title,
        adventure_image_url=original_session.adventure_image_url,
        status=original_session.status,
        status_note=original_session.status_note,
        copied_from_id=original_session.id,
    )
    db.add(copied_session)
    await db.flush()

    # Create session-bound folder
    os.makedirs(os.path.join(settings.DATA_DIR, "adventures", "sessions", copied_session.id), exist_ok=True)

    # 5. Clone SessionState
    state_res = await db.execute(select(SessionState).where(SessionState.session_id == original_session.id))
    original_state = state_res.scalars().first()
    if original_state:
        cloned_state = SessionState(
            session_id=copied_session.id,
            user_id=current_user.id,
            template_id=original_state.template_id,
            avatar_id=cloned_avatar.id,
            current_scene_id=original_state.current_scene_id,
            in_game_time=original_state.in_game_time,
            time_system=original_state.time_system,
            time_config=deepcopy(original_state.time_config),
            inventory=deepcopy(original_state.inventory),
            entity_states=deepcopy(original_state.entity_states),
            exit_states=deepcopy(original_state.exit_states),
            discovered_scenes=deepcopy(original_state.discovered_scenes),
            quests=deepcopy(original_state.quests),
            start_datetime=original_state.start_datetime,
            plot=original_state.plot,
            rules=original_state.rules,
            walkthrough=original_state.walkthrough,
            completed_condition=original_state.completed_condition,
            gameover_condition=original_state.gameover_condition,
            tts_director_notes=original_state.tts_director_notes,
            selected_image_styles=deepcopy(original_state.selected_image_styles),
            selected_tone=deepcopy(original_state.selected_tone),
            is_completed=original_state.is_completed,
            is_debug_enabled=original_state.is_debug_enabled,
            is_walkthrough_revealed=original_state.is_walkthrough_revealed,
            allow_dynamic_items=original_state.allow_dynamic_items,
        )
        db.add(cloned_state)

    # 6. Clone ChatMessage
    messages_res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == original_session.id))
    original_messages = messages_res.scalars().all()
    for msg in original_messages:
        cloned_msg = ChatMessage(
            session_id=copied_session.id,
            role=msg.role,
            content=msg.content
        )
        db.add(cloned_msg)

    # 7. Clone WorldScene
    scenes_res = await db.execute(select(WorldScene).where(WorldScene.session_id == original_session.id))
    original_scenes = scenes_res.scalars().all()
    for s in original_scenes:
        cloned_scene = WorldScene(
            id=s.id,
            session_id=copied_session.id,
            template_id=None,
            label=s.label,
            description=s.description,
            image_url=s.image_url
        )
        db.add(cloned_scene)

    # 8. Clone WorldExit
    exits_res = await db.execute(select(WorldExit).where(WorldExit.session_id == original_session.id))
    original_exits = exits_res.scalars().all()
    for e in original_exits:
        cloned_exit = WorldExit(
            session_id=copied_session.id,
            template_id=None,
            from_scene_id=e.from_scene_id,
            to_scene_id=e.to_scene_id,
            label=e.label,
            is_locked=e.is_locked,
            lock_description=e.lock_description
        )
        db.add(cloned_exit)

    # 9. Clone WorldEntity
    entities_res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == original_session.id))
    original_entities = entities_res.scalars().all()
    for ent in original_entities:
        cloned_ent = WorldEntity(
            id=ent.id,
            session_id=copied_session.id,
            template_id=None,
            entity_type=ent.entity_type,
            name=ent.name,
            description=ent.description,
            current_scene_id=ent.current_scene_id,
            spatial_position=ent.spatial_position,
            image_url=ent.image_url,
            item_type=ent.item_type,
            wearable_slots=ent.wearable_slots,
            is_in_inventory=ent.is_in_inventory,
            is_hidden=ent.is_hidden,
            unlock_rule=ent.unlock_rule,
            is_portable=ent.is_portable,
            combination_ingredients=ent.combination_ingredients,
            reveals_item_id=ent.reveals_item_id,
            is_final_state=ent.is_final_state,
            state_comment=ent.state_comment,
            npc_type=ent.npc_type,
            movement_type=ent.movement_type,
            hp=ent.hp,
            max_hp=ent.max_hp,
            mana=ent.mana,
            max_mana=ent.max_mana,
            stamina=ent.stamina,
            max_stamina=ent.max_stamina,
            stat_modifier_strength=ent.stat_modifier_strength,
            stat_modifier_dexterity=ent.stat_modifier_dexterity,
            stat_modifier_intelligence=ent.stat_modifier_intelligence,
            stat_modifier_wisdom=ent.stat_modifier_wisdom,
            stat_modifier_charisma=ent.stat_modifier_charisma,
            stat_modifier_armor_class=ent.stat_modifier_armor_class,
            is_attackable=ent.is_attackable,
            is_killable=ent.is_killable,
            inventory=deepcopy(ent.inventory),
            metadata_json=deepcopy(ent.metadata_json),
            voice=ent.voice
        )
        db.add(cloned_ent)

    # 10. Clone WorldMap
    map_res = await db.execute(select(WorldMap).where(WorldMap.session_id == original_session.id))
    original_map = map_res.scalars().first()
    if original_map:
        cloned_map = WorldMap(
            template_id=original_map.template_id,
            session_id=copied_session.id,
            nodes=deepcopy(original_map.nodes),
            edges=deepcopy(original_map.edges),
            current_scene_id=original_map.current_scene_id
        )
        db.add(cloned_map)

    await db.commit()
    return {"game_id": copied_session.id, "template_id": copied_session.template_id, "avatar_id": cloned_avatar.id}


# ---------------------------------------------------------------------------
# /{template_id}/state  (adventure-scoped convenience routes used by the UI)
# ---------------------------------------------------------------------------

@router.get("/{template_id}/state")
async def get_adventure_state(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Returns a lightweight snapshot of the most-recent active session state for a template."""
    state_res = await db.execute(
        select(SessionState)
        .join(GameSession, GameSession.id == SessionState.session_id)
        .where(
            GameSession.template_id == template_id,
            GameSession.user_id == current_user.id,
            GameSession.status == "active",
        )
        .order_by(GameSession.created_at.desc())
        .limit(1)
    )
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="No active session found for this adventure.")

    return {
        "scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time or 0,
        "is_paused": False,
        "session_id": state.session_id,
    }


@router.patch("/{template_id}/state")
async def update_adventure_state(
    template_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Patches the most-recent active session state for a template (e.g. scene_id, in_game_time)."""
    state_res = await db.execute(
        select(SessionState)
        .join(GameSession, GameSession.id == SessionState.session_id)
        .where(
            GameSession.template_id == template_id,
            GameSession.user_id == current_user.id,
            GameSession.status == "active",
        )
        .order_by(GameSession.created_at.desc())
        .limit(1)
    )
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="No active session found for this adventure.")

    if "scene_id" in payload:
        state.current_scene_id = payload["scene_id"]
    if "in_game_time" in payload:
        state.in_game_time = payload["in_game_time"]

    await db.commit()
    await db.refresh(state)

    game_session_res = await db.execute(
        select(GameSession).where(GameSession.id == state.session_id)
    )
    game_session = game_session_res.scalars().first()

    return {
        "scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time or 0,
        "is_paused": bool(game_session and game_session.status == "paused"),
        "session_id": state.session_id,
    }


@router.post("/{template_id}/pause")
async def pause_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Pauses the most-recent active session for a template."""
    session_res = await db.execute(
        select(GameSession).where(
            GameSession.template_id == template_id,
            GameSession.user_id == current_user.id,
            GameSession.status == "active",
        ).order_by(GameSession.created_at.desc()).limit(1)
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="No active session found for this adventure.")

    game_session.status = "paused"
    await db.commit()
    return {"status": "paused", "game_id": game_session.id}


@router.post("/{template_id}/resume")
async def resume_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resumes the most-recently paused session for a template."""
    session_res = await db.execute(
        select(GameSession).where(
            GameSession.template_id == template_id,
            GameSession.user_id == current_user.id,
            GameSession.status == "paused",
        ).order_by(GameSession.created_at.desc()).limit(1)
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="No paused session found for this adventure.")

    game_session.status = "active"
    await db.commit()
    return {"status": "active", "game_id": game_session.id}


async def _get_session_response(db: AsyncSession, game_id: str, current_user_id: str) -> GameSessionResponse:
    # Query single session with joins
    result = await db.execute(
        select(GameSession, SessionState, AdventureTemplate, WorldScene.label, Avatar.profile_image)
        .outerjoin(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(AdventureTemplate, GameSession.template_id == AdventureTemplate.id)
        .outerjoin(Avatar, Avatar.id == SessionState.avatar_id)
        .outerjoin(
            WorldScene,
            (WorldScene.id == SessionState.current_scene_id)
            & (WorldScene.session_id == GameSession.id),
        )
        .where((GameSession.id == game_id) & (GameSession.user_id == current_user_id))
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    g, s, a, scene_label, avatar_profile_image = row
    
    # We can fetch earned awards here
    user_res = await db.execute(select(User).where(User.id == current_user_id))
    current_user = user_res.scalar_one()
    user_earned_awards = current_user.earned_awards or []
    
    return GameSessionResponse(
        game_id=g.id,
        template_id=g.template_id,
        adventure_id=g.template_id,
        avatar_id=g.avatar_id,
        profile_image=AdventureLogic.resolve_session_asset(s, "protagonist", avatar_profile_image),
        adventure_title=a.title if a else (g.adventure_title or "Unknown"),
        adventure_version=a.version if a else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get("version"),
        image_url=AdventureLogic.resolve_session_asset(s, "cover", a.image_url if a else g.adventure_image_url),
        scene_id=s.current_scene_id if s else "START", 
        current_scene_name=scene_label or ("Exploring..." if s else "Archived"),
        in_game_time=s.in_game_time if s else 0,
        is_ready=a.is_ready if a else True,
        creation_status=a.creation_status if a else "Ready",
        creation_error=a.creation_error if a else None,
        selected_tone=a.selected_tone if a else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get("selected_tone"),
        progress=AdventureLogic.calculate_quest_progress(s.quests if s else (a.quests if a else None)),
        quest_count=len((s.quests if s else (a.quests if a else None)) or []),
        completed_quest_count=len([q for q in ((s.quests if s else (a.quests if a else None)) or []) if q.get("status") == "completed"]),
        award_count=len((a.awards if a else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get("awards")) or []),
        earned_award_count=len([aw for aw in ((a.awards if a else None) or []) if any(ea.get("key") == aw.get("key") and ea.get("template_id") == a.id for ea in user_earned_awards)]),
        created_at=g.created_at,
        status=g.status,
        status_note=g.status_note,
        copied_from_id=g.copied_from_id,
    )


@router.patch("/sessions/{game_id}", response_model=GameSessionResponse)
async def update_session(
    game_id: str,
    payload: GameSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(GameSession).where((GameSession.id == game_id) & (GameSession.user_id == current_user.id))
    )
    game_session = result.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if payload.status is not None:
        game_session.status = payload.status
    if payload.status_note is not None:
        game_session.status_note = payload.status_note

    await db.commit()

    return await _get_session_response(db, game_id, current_user.id)


@router.get("/sessions/{game_id}/export")
async def export_session_ads(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the session as a portable .ads (ZIP) bundle including assets."""
    import io
    try:
        # Verify ownership
        result = await db.execute(
            select(GameSession).where((GameSession.id == game_id) & (GameSession.user_id == current_user.id))
        )
        if not result.scalars().first():
            raise HTTPException(status_code=404, detail="Session not found.")
            
        zip_data = await SessionExporter.export_ads(db, game_id)
        return StreamingResponse(
            io.BytesIO(zip_data),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=session_{game_id}.ads"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("ADS Export failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/import")
async def import_session_ads(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a game session from a portable .ads (ZIP) file."""
    try:
        content = await file.read()
        new_session_id = await SessionImporter.import_ads(db, content, owner_id=current_user.id)
        if not new_session_id:
            raise HTTPException(status_code=400, detail="The ADS file is invalid or could not be processed.")
        return {"status": "success", "game_id": new_session_id, "message": "Session imported successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ADS Import failed")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
