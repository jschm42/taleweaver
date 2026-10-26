"""Adventure cloning engine.

Provides modular duplication of adventure blueprints, world content (scenes, exits,
entities, maps, avatars), and associated disk assets.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from copy import deepcopy
from typing import Any, Optional

import uuid6
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.adventure_identity import new_origin_id
from backend.core.config import settings
from backend.engine.media_engine import MediaEngine
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.world_map import WorldMap
from backend.utils.path_security import ensure_within_data_dir
from backend.utils.text_utils import generate_short_id, slugify

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 50
MAX_SLUG_PREFIX_LENGTH = 25


def generate_cloned_title(original_title: str, existing_titles: set[str] | None = None) -> str:
    """Generate a clean numbered copy title fitting within MAX_TITLE_LENGTH."""
    base = (original_title or "Untitled Adventure").strip()
    match = re.match(
        r"^(.*?)(?:\s*\((?:Copy|Kopie)(?:\s+(\d+))?\))?$",
        base,
        flags=re.IGNORECASE,
    )
    core_title = match.group(1).strip() if match else base

    for counter in range(1, 1000):
        suffix = " (Copy)" if counter == 1 else f" (Copy {counter})"
        max_core = MAX_TITLE_LENGTH - len(suffix)
        candidate_core = core_title[:max_core].rstrip()
        candidate = f"{candidate_core}{suffix}"
        if existing_titles is None or candidate not in existing_titles:
            return candidate

    return f"{core_title[:43]} (Copy)"


def generate_cloned_adventure_id(title: str) -> str:
    """Generate a unique ID that is guaranteed to fit within 36 chars."""
    slug = slugify(title)[:MAX_SLUG_PREFIX_LENGTH].rstrip("-")
    if not slug:
        slug = "adv"
    short_id = generate_short_id(8)
    return f"{slug}-{short_id}"


def rewrite_asset_url(
    url: Optional[str], old_template_id: str, new_template_id: str
) -> Optional[str]:
    """Rewrite template library URLs to point to the cloned adventure's directory."""
    if not url or not isinstance(url, str):
        return url

    library_prefix = f"/data/adventures/library/{old_template_id}/"
    if library_prefix in url:
        return url.replace(library_prefix, f"/data/adventures/library/{new_template_id}/")

    legacy_prefix = f"/data/adventures/{old_template_id}/"
    if legacy_prefix in url:
        return url.replace(legacy_prefix, f"/data/adventures/library/{new_template_id}/")

    return url


def clone_disk_assets(old_template_id: str, new_template_id: str) -> None:
    """Copy media assets directory from the original adventure to the clone."""
    new_dir = ensure_within_data_dir(
        os.path.join(settings.DATA_DIR, "adventures", "library", new_template_id)
    )

    orig_dir = os.path.join(settings.DATA_DIR, "adventures", "library", old_template_id)
    legacy_dir = os.path.join(settings.DATA_DIR, "adventures", old_template_id)

    source_dir: Optional[str] = None
    if os.path.isdir(orig_dir):
        source_dir = orig_dir
    elif os.path.isdir(legacy_dir):
        source_dir = legacy_dir

    if not source_dir:
        os.makedirs(new_dir, exist_ok=True)
        return

    try:
        source_resolved = ensure_within_data_dir(source_dir)
        shutil.copytree(source_resolved, new_dir, dirs_exist_ok=True)
        logger.info(
            "Copied assets for adventure clone: %s -> %s",
            old_template_id,
            new_template_id,
        )
    except Exception as exc:
        logger.warning("Failed copying assets during clone from %s: %s", source_dir, exc)
        os.makedirs(new_dir, exist_ok=True)


def clone_manifest_data(
    original_manifest: Optional[dict[str, Any]],
    new_title: str,
    old_id: str,
    new_id: str,
) -> Optional[dict[str, Any]]:
    """Deep-copy and rewrite URLs in the original adventure manifest."""
    if not original_manifest or not isinstance(original_manifest, dict):
        return None

    manifest = deepcopy(original_manifest)
    adv_dict = manifest.get("adventure")
    if isinstance(adv_dict, dict):
        adv_dict["title"] = new_title
        adv_dict["image_url"] = rewrite_asset_url(adv_dict.get("image_url"), old_id, new_id)

    protagonist = manifest.get("protagonist")
    if isinstance(protagonist, dict):
        protagonist["profile_image"] = rewrite_asset_url(
            protagonist.get("profile_image"), old_id, new_id
        )

    for key in ("scenes", "npcs", "objects"):
        items = manifest.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and "image_url" in item:
                item["image_url"] = rewrite_asset_url(item.get("image_url"), old_id, new_id)

    return manifest


def _create_cloned_template_entity(
    original: AdventureTemplate,
    new_id: str,
    new_title: str,
    user_id: str,
    username: str,
    cloned_manifest: Optional[dict[str, Any]],
) -> AdventureTemplate:
    """Build the new AdventureTemplate model instance from the original."""
    return AdventureTemplate(
        id=new_id,
        owner_id=user_id,
        title=new_title,
        teaser=original.teaser,
        cover_appearance=original.cover_appearance,
        version=original.version or "1.0.0",
        language=original.language,
        origin_id=new_origin_id(),
        cover_source_adventure_id=original.cover_source_adventure_id,
        cover_source_adventure_name=original.cover_source_adventure_name,
        cover_similarity_percent=original.cover_similarity_percent,
        allow_reuse_source_assets=original.allow_reuse_source_assets,
        image_url=rewrite_asset_url(original.image_url, original.id, new_id),
        strict_rules=original.strict_rules,
        rule_enforcement_mode=original.rule_enforcement_mode,
        time_per_turn=original.time_per_turn,
        pacing_minutes=original.pacing_minutes,
        max_time_per_turn=original.max_time_per_turn,
        clock_enabled=original.clock_enabled,
        max_memory_turns=original.max_memory_turns,
        time_system=original.time_system,
        time_config=(deepcopy(original.time_config) if original.time_config else None),
        generate_scene_images=original.generate_scene_images,
        generate_npc_images=original.generate_npc_images,
        generate_item_images=original.generate_item_images,
        selected_image_styles=(
            deepcopy(original.selected_image_styles) if original.selected_image_styles else None
        ),
        selected_tone=(deepcopy(original.selected_tone) if original.selected_tone else None),
        ui_theme=(deepcopy(original.ui_theme) if original.ui_theme else None),
        game_over_rules=(deepcopy(original.game_over_rules) if original.game_over_rules else None),
        quests=deepcopy(original.quests) if original.quests else None,
        is_completed=False,
        is_ready=original.is_ready,
        creation_status=("Ready" if original.is_ready else original.creation_status),
        creation_error=None,
        generation_logs=None,
        original_manifest=cloned_manifest,
        min_scenes=original.min_scenes,
        max_scenes=original.max_scenes,
        container_generation_enabled=original.container_generation_enabled,
        scripts_generation_enabled=original.scripts_generation_enabled,
        min_containers=original.min_containers,
        max_containers=original.max_containers,
        min_items=original.min_items,
        max_items=original.max_items,
        text_log_generation_enabled=original.text_log_generation_enabled,
        min_text_logs=original.min_text_logs,
        max_text_logs=original.max_text_logs,
        plot=original.plot,
        rules=original.rules,
        intro_text=original.intro_text,
        completed_condition=original.completed_condition,
        gameover_condition=original.gameover_condition,
        completed_guard_expression=original.completed_guard_expression,
        gameover_guard_expression=original.gameover_guard_expression,
        tts_director_notes=original.tts_director_notes,
        original_prompt=original.original_prompt,
        starting_timestamp=original.starting_timestamp,
        allow_dynamic_items=original.allow_dynamic_items,
        can_damage_npcs=original.can_damage_npcs,
        npcs_can_damage_protagonist=original.npcs_can_damage_protagonist,
        awards=deepcopy(original.awards) if original.awards else None,
        award_generation_enabled=original.award_generation_enabled,
        min_awards=original.min_awards,
        max_awards=original.max_awards,
        quest_generation_enabled=original.quest_generation_enabled,
        min_quests=original.min_quests,
        max_quests=original.max_quests,
        is_adventure_generator=original.is_adventure_generator,
        sequences=(deepcopy(original.sequences) if original.sequences else None),
        generation_strictness=original.generation_strictness,
        creator=original.creator or username,
        copyright=original.copyright,
        license=original.license,
        license_url=original.license_url,
    )


async def _clone_avatars(db: AsyncSession, old_id: str, new_id: str, user_id: str) -> None:
    avatars_query = select(Avatar).where(Avatar.template_id == old_id)
    avatars = (await db.scalars(avatars_query)).all()
    for orig in avatars:
        cloned = Avatar(
            user_id=user_id,
            template_id=new_id,
            name=orig.name,
            role=orig.role,
            description=orig.description,
            character=orig.character,
            appearance=orig.appearance,
            voice=orig.voice,
            goal=orig.goal,
            profile_image=rewrite_asset_url(orig.profile_image, old_id, new_id),
            hp=orig.hp,
            max_hp=orig.max_hp,
            stamina=orig.stamina,
            max_stamina=orig.max_stamina,
            mana=orig.mana,
            max_mana=orig.max_mana,
            exp=orig.exp,
            strength=orig.strength,
            dexterity=orig.dexterity,
            intelligence=orig.intelligence,
            wisdom=orig.wisdom,
            charisma=orig.charisma,
            armor_class=orig.armor_class,
            stats=deepcopy(orig.stats) if orig.stats else {},
            inventory=deepcopy(orig.inventory) if orig.inventory else [],
            equipment=deepcopy(orig.equipment) if orig.equipment else {},
            status_effects=(deepcopy(orig.status_effects) if orig.status_effects else []),
        )
        db.add(cloned)


async def _clone_scenes(db: AsyncSession, old_id: str, new_id: str) -> None:
    scenes_query = select(WorldScene).where(
        WorldScene.template_id == old_id,
        WorldScene.session_id.is_(None),
    )
    scenes = (await db.scalars(scenes_query)).all()
    for s in scenes:
        cloned = WorldScene(
            id=s.id,
            template_id=new_id,
            session_id=None,
            label=s.label,
            description=s.description,
            image_url=rewrite_asset_url(s.image_url, old_id, new_id),
            decorative_objects=(deepcopy(s.decorative_objects) if s.decorative_objects else None),
            on_enter_scene_script=s.on_enter_scene_script,
            on_enter_scene_text=s.on_enter_scene_text,
            on_leave_scene_script=s.on_leave_scene_script,
            on_leave_scene_text=s.on_leave_scene_text,
        )
        db.add(cloned)


async def _clone_exits(db: AsyncSession, old_id: str, new_id: str) -> None:
    exits_query = select(WorldExit).where(
        WorldExit.template_id == old_id,
        WorldExit.session_id.is_(None),
    )
    exits = (await db.scalars(exits_query)).all()
    for e in exits:
        cloned = WorldExit(
            id=str(uuid6.uuid7()),
            template_id=new_id,
            session_id=None,
            from_scene_id=e.from_scene_id,
            to_scene_id=e.to_scene_id,
            label=e.label,
            exit_type=e.exit_type,
            is_locked=e.is_locked,
            lock_description=e.lock_description,
            code_to_unlock=e.code_to_unlock,
            item_to_unlock=e.item_to_unlock,
            rule_to_unlock=e.rule_to_unlock,
            unlock_expression=e.unlock_expression,
            on_open_exit_script=e.on_open_exit_script,
            on_open_exit_text=e.on_open_exit_text,
            on_exit_used_script=e.on_exit_used_script,
            on_exit_used_text=e.on_exit_used_text,
            on_unlock_success_script=e.on_unlock_success_script,
            on_unlock_success_text=e.on_unlock_success_text,
            on_unlock_failure_script=e.on_unlock_failure_script,
            on_unlock_failure_text=e.on_unlock_failure_text,
        )
        db.add(cloned)


async def _clone_entities(db: AsyncSession, old_id: str, new_id: str) -> None:
    entities_query = select(WorldEntity).where(
        WorldEntity.template_id == old_id,
        WorldEntity.session_id.is_(None),
    )
    entities = (await db.scalars(entities_query)).all()
    for ent in entities:
        cloned = WorldEntity(
            id=ent.id,
            template_id=new_id,
            session_id=None,
            entity_type=ent.entity_type,
            name=ent.name,
            description=ent.description,
            current_scene_id=ent.current_scene_id,
            spatial_position=ent.spatial_position,
            image_url=rewrite_asset_url(ent.image_url, old_id, new_id),
            item_type=ent.item_type,
            wearable_slots=(deepcopy(ent.wearable_slots) if ent.wearable_slots else None),
            is_in_inventory=ent.is_in_inventory,
            is_hidden=ent.is_hidden,
            reveal_rule=ent.reveal_rule,
            unlock_rule=ent.unlock_rule,
            is_portable=ent.is_portable,
            combination_ingredients=(
                deepcopy(ent.combination_ingredients) if ent.combination_ingredients else None
            ),
            reveals_item_id=ent.reveals_item_id,
            is_final_state=ent.is_final_state,
            state_comment=ent.state_comment,
            npc_type=ent.npc_type,
            movement_type=ent.movement_type,
            moveable=ent.moveable,
            allowed_scenes=(deepcopy(ent.allowed_scenes) if ent.allowed_scenes else []),
            notes=ent.notes,
            goal=ent.goal,
            character=ent.character,
            appearance=ent.appearance,
            hp=ent.hp,
            max_hp=ent.max_hp,
            mana=ent.mana,
            max_mana=ent.max_mana,
            stamina=ent.stamina,
            max_stamina=ent.max_stamina,
            voice=ent.voice,
            stat_modifier_strength=ent.stat_modifier_strength,
            stat_modifier_dexterity=ent.stat_modifier_dexterity,
            stat_modifier_intelligence=ent.stat_modifier_intelligence,
            stat_modifier_wisdom=ent.stat_modifier_wisdom,
            stat_modifier_charisma=ent.stat_modifier_charisma,
            stat_modifier_armor_class=ent.stat_modifier_armor_class,
            is_attackable=ent.is_attackable,
            is_killable=ent.is_killable,
            inventory=deepcopy(ent.inventory) if ent.inventory else [],
            metadata_json=(deepcopy(ent.metadata_json) if ent.metadata_json else {}),
        )
        db.add(cloned)


async def _clone_maps(db: AsyncSession, old_id: str, new_id: str) -> None:
    maps_query = select(WorldMap).where(
        WorldMap.template_id == old_id,
        WorldMap.session_id.is_(None),
    )
    maps = (await db.scalars(maps_query)).all()
    for wm in maps:
        cloned = WorldMap(
            id=str(uuid6.uuid7()),
            template_id=new_id,
            session_id=None,
            nodes=deepcopy(wm.nodes) if wm.nodes else {},
            edges=deepcopy(wm.edges) if wm.edges else [],
            current_scene_id=wm.current_scene_id,
        )
        db.add(cloned)


async def _resolve_unique_template_id(db: AsyncSession, title: str) -> str:
    while True:
        candidate_id = generate_cloned_adventure_id(title)
        collision = await db.scalar(
            select(AdventureTemplate.id).where(AdventureTemplate.id == candidate_id)
        )
        if not collision:
            return candidate_id


async def _resolve_cloned_title(
    db: AsyncSession,
    original_title: str,
    user_id: str,
    custom_title: Optional[str] = None,
) -> str:
    if custom_title and custom_title.strip():
        return custom_title.strip()[:MAX_TITLE_LENGTH]

    existing_titles_res = await db.execute(
        select(AdventureTemplate.title).where(AdventureTemplate.owner_id == user_id)
    )
    existing_titles = set(existing_titles_res.scalars().all())
    return generate_cloned_title(original_title, existing_titles)


class AdventureCloner:
    """Service responsible for cloning adventures and all nested world content."""

    @staticmethod
    async def clone_adventure(
        db: AsyncSession,
        template_id: str,
        current_user: User,
        custom_title: Optional[str] = None,
    ) -> AdventureTemplate:
        """Create a full clone of an adventure blueprint and its world contents."""
        is_admin = getattr(current_user, "role", "user") == "admin"
        query = select(AdventureTemplate).where(AdventureTemplate.id == template_id)
        if not is_admin:
            query = query.where(
                or_(
                    AdventureTemplate.owner_id == current_user.id,
                    AdventureTemplate.owner_id.is_(None),
                )
            )

        result = await db.execute(query)
        original = result.scalars().first()
        if not original:
            raise HTTPException(status_code=404, detail="Adventure template not found.")

        new_title = await _resolve_cloned_title(db, original.title, current_user.id, custom_title)
        new_id = await _resolve_unique_template_id(db, new_title)

        clone_disk_assets(original.id, new_id)

        cloned_manifest = clone_manifest_data(
            original.original_manifest, new_title, original.id, new_id
        )

        cloned_template = _create_cloned_template_entity(
            original,
            new_id,
            new_title,
            current_user.id,
            current_user.username,
            cloned_manifest,
        )
        db.add(cloned_template)
        await db.flush()

        await _clone_avatars(db, original.id, new_id, current_user.id)
        await _clone_scenes(db, original.id, new_id)
        await _clone_exits(db, original.id, new_id)
        await _clone_entities(db, original.id, new_id)
        await _clone_maps(db, original.id, new_id)

        await db.commit()
        await db.refresh(cloned_template)

        try:
            await MediaEngine.ensure_thumbnails(new_id)
        except Exception as exc:
            logger.warning("Failed ensuring thumbnails for clone %s: %s", new_id, exc)

        logger.info(
            "Successfully duplicated adventure %s to %s ('%s')",
            original.id,
            new_id,
            new_title,
        )
        return cloned_template
