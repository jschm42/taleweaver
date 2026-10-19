"""Portal adventure creation: template, protagonist, first session and background generation."""

import logging
import os
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import CreateAdventureTemplatePayload
from backend.api.routes.adventures.session_materializer import (
    copy_data_asset_to_session,
    materialize_initial_session_from_template,
)
from backend.core.config import settings
from backend.engine.world_generator import WorldGenerator, is_image_moderation_error
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from backend.utils.text_utils import generate_adventure_id, generate_session_id

logger = logging.getLogger(__name__)

_IMAGE_MODERATION_NOTICE = (
    "Notice: One or more images were blocked by safety filters and replaced with placeholders. "
    "You can regenerate them later in the editor."
)
_UNLOCK_KEYS = ("code_to_unlock", "item_to_unlock", "rule_to_unlock")


@dataclass
class CoverSource:
    template: Optional[AdventureTemplate] = None
    manifest: Optional[dict[str, Any]] = None
    name: Optional[str] = None

    @property
    def adventure_id(self) -> Optional[str]:
        return self.template.id if self.template else None


@dataclass
class CreatedAdventure:
    template: AdventureTemplate
    avatar: Avatar
    session: GameSession
    cover: CoverSource = field(default_factory=CoverSource)


def is_chat_mode(payload: CreateAdventureTemplatePayload) -> bool:
    return (payload.rule_enforcement_mode or "rpg") == "chat"


def _similarity_percent(payload: CreateAdventureTemplatePayload) -> int:
    return max(0, min(100, int(payload.cover_similarity_percent or 0)))


async def ensure_no_active_generation(db: AsyncSession, user_id: str) -> None:
    """Allow only one active portal generation per user at a time."""
    active = await db.execute(
        select(AdventureTemplate.id)
        .where(AdventureTemplate.owner_id == user_id)
        .where(AdventureTemplate.is_ready.is_(False))
        .where(
            or_(
                AdventureTemplate.creation_status.is_(None),
                AdventureTemplate.creation_status.notin_(["Failed", "Cancelled"]),
            )
        )
        .limit(1)
    )
    if active.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Adventure generation already running for this user. Please wait until it finishes or cancel it.",
        )


async def resolve_cover_source(
    db: AsyncSession, payload: CreateAdventureTemplatePayload, user_id: str
) -> CoverSource:
    if not payload.cover_source_adventure_id:
        return CoverSource(name=payload.cover_source_adventure_name)

    source_res = await db.execute(
        select(AdventureTemplate).where(
            AdventureTemplate.id == payload.cover_source_adventure_id,
            AdventureTemplate.owner_id == user_id,
        )
    )
    source = source_res.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Cover source adventure not found.")
    return CoverSource(
        template=source,
        manifest=deepcopy(source.original_manifest or {}),
        name=payload.cover_source_adventure_name or source.title,
    )


def _pacing_minutes(payload: CreateAdventureTemplatePayload) -> Optional[int]:
    """Backward compatibility for older pacing configs."""
    pacing_minutes = payload.pacing_minutes or payload.time_per_turn
    if payload.pacing and isinstance(payload.pacing, dict):
        return payload.pacing.get("minutes_per_turn", pacing_minutes)
    return pacing_minutes


def build_template(
    payload: CreateAdventureTemplatePayload, template_id: str, owner_id: str, cover: CoverSource
) -> AdventureTemplate:
    chat_mode = is_chat_mode(payload)
    return AdventureTemplate(
        id=template_id,
        owner_id=owner_id,
        title=payload.title,
        original_prompt=payload.original_prompt,
        strict_rules=payload.rule_enforcement_mode != "chat",
        rule_enforcement_mode=payload.rule_enforcement_mode or "rpg",
        generation_strictness=payload.generation_strictness or "creative",
        sequences=payload.sequences,
        time_per_turn=payload.time_per_turn,
        pacing_minutes=_pacing_minutes(payload),
        max_time_per_turn=payload.max_time_per_turn,
        max_memory_turns=payload.max_memory_turns if payload.max_memory_turns is not None else 10,
        clock_enabled=payload.clock_enabled or False,
        time_system=payload.time_system or "calendar",
        time_config=payload.time_config,
        generate_scene_images=payload.generate_scene_images,
        generate_npc_images=payload.generate_npc_images,
        generate_item_images=payload.generate_item_images,
        selected_image_styles=payload.selected_image_styles,
        selected_tone=payload.selected_tone,
        min_scenes=payload.min_scenes,
        max_scenes=payload.max_scenes,
        container_generation_enabled=payload.container_generation_enabled,
        scripts_generation_enabled=payload.scripts_generation_enabled,
        min_containers=payload.min_containers,
        max_containers=payload.max_containers,
        min_items=payload.min_items,
        max_items=payload.max_items,
        text_log_generation_enabled=payload.text_log_generation_enabled,
        min_text_logs=payload.min_text_logs,
        max_text_logs=payload.max_text_logs,
        award_generation_enabled=(False if chat_mode else payload.award_generation_enabled),
        min_awards=payload.min_awards,
        max_awards=payload.max_awards,
        can_damage_npcs=payload.can_damage_npcs,
        npcs_can_damage_protagonist=payload.npcs_can_damage_protagonist,
        is_ready=bool(payload.skip_generation),
        creation_status="Ready" if payload.skip_generation else "Initializing...",
        original_manifest=payload.original_manifest,
        teaser=payload.teaser,
        version=payload.version,
        language=payload.language,
        intro_text=payload.intro_text,
        is_adventure_generator=payload.is_adventure_generator,
        cover_source_adventure_id=cover.adventure_id,
        cover_source_adventure_name=cover.name,
        cover_similarity_percent=_similarity_percent(payload),
        allow_reuse_source_assets=bool(payload.allow_reuse_source_assets),
    )


def _initial_object_lock_states(template_entities: list[WorldEntity]) -> dict[str, dict[str, bool]]:
    """Objects with an unlock requirement start locked; otherwise honour an explicit flag."""
    states: dict[str, dict[str, bool]] = {}
    for ent in template_entities:
        if str(getattr(ent, "entity_type", "") or "").upper() != "OBJECT":
            continue
        metadata_json = dict(getattr(ent, "metadata_json", None) or {})
        if any(metadata_json.get(key) for key in _UNLOCK_KEYS):
            states[ent.id] = {"locked": True}
            continue
        locked = metadata_json.get("locked")
        if isinstance(locked, bool):
            states[ent.id] = {"locked": locked}
    return states


def _build_session_state(
    adv: AdventureTemplate,
    session: GameSession,
    avatar: Avatar,
    user_id: str,
    entity_states: dict[str, Any],
) -> SessionState:
    return SessionState(
        session_id=session.id,
        user_id=user_id,
        template_id=adv.id,
        avatar_id=avatar.id,
        current_scene_id="START",
        in_game_time=0,
        quests=deepcopy(adv.quests or []),
        entity_states=entity_states,
        start_datetime=AdventureLogic.resolve_start_datetime(
            adv.original_manifest, time_config=adv.time_config
        ),
        plot=adv.plot,
        rules=adv.rules,
        walkthrough=adv.walkthrough,
        completed_condition=adv.completed_condition,
        gameover_condition=adv.gameover_condition,
        completed_guard_expression=adv.completed_guard_expression,
        gameover_guard_expression=adv.gameover_guard_expression,
        tts_director_notes=adv.tts_director_notes,
        selected_image_styles=deepcopy(adv.selected_image_styles),
        selected_tone=deepcopy(adv.selected_tone),
    )


async def _create_initial_session_state(
    db: AsyncSession, adv: AdventureTemplate, session: GameSession, avatar: Avatar, user_id: str
) -> None:
    """Snapshot the template manifest and asset mapping for the newly created session."""
    asset_cache: dict[str, str] = {}
    copied_cover = copy_data_asset_to_session(session.id, "cover", adv.image_url, asset_cache)
    copied_protagonist = copy_data_asset_to_session(
        session.id, "protagonist", avatar.profile_image, asset_cache
    )
    session.adventure_image_url = copied_cover or adv.image_url
    avatar.profile_image = copied_protagonist or avatar.profile_image

    ent_rows = await db.execute(select(WorldEntity).where(WorldEntity.template_id == adv.id))
    template_entities = list(ent_rows.scalars().all())
    entity_states: dict[str, Any] = {
        AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: AdventureLogic.build_session_manifest_snapshot(
            adv
        ),
        "__asset_snapshot__": {
            "cover": session.adventure_image_url,
            "protagonist": avatar.profile_image,
            "entity_images": {
                e.id: e.image_url for e in template_entities if getattr(e, "id", None)
            },
        },
        **_initial_object_lock_states(template_entities),
    }
    db.add(_build_session_state(adv, session, avatar, user_id, entity_states))


async def create_adventure_records(
    db: AsyncSession, payload: CreateAdventureTemplatePayload, user: User
) -> CreatedAdventure:
    """Create template, protagonist, first session and session state (committed)."""
    await ensure_no_active_generation(db, user.id)
    cover = await resolve_cover_source(db, payload, user.id)
    template_id = payload.id or generate_adventure_id(payload.title)

    adv = build_template(payload, template_id, user.id, cover)
    db.add(adv)

    avatar = Avatar(
        user_id=user.id,
        template_id=template_id,
        name=payload.avatar_name or f"Hero of {payload.title}",
        role="Protagonist",
        description="A mysterious wanderer...",
        hp=200,
        stamina=200,
        mana=200,
        exp=0,
        stats={"str": 10, "int": 10, "wis": 10, "dex": 10, "cha": 10, "ac": 10},
    )
    db.add(avatar)
    await db.flush()  # Ensure avatar.id is available

    session = GameSession(
        id=generate_session_id(payload.title),
        user_id=user.id,
        avatar_id=avatar.id,
        template_id=template_id,
        adventure_title=payload.title,
        status="active",
    )
    db.add(session)
    await db.flush()

    # Ensure a concrete session filesystem root exists for session-bound artifacts (e.g. TTS).
    os.makedirs(
        os.path.join(settings.DATA_DIR, "adventures", "sessions", session.id), exist_ok=True
    )

    await _create_initial_session_state(db, adv, session, avatar, user.id)
    await db.commit()
    return CreatedAdventure(template=adv, avatar=avatar, session=session, cover=cover)


# --- Background generation -------------------------------------------------


def _cover_bounds(src_count: int, hard_min: int) -> tuple[int, int]:
    """Return (min, max) that bracket src_count by ±1, clamped to hard_min."""
    lo = max(hard_min, src_count - 1)
    return lo, max(lo, src_count + 1)


def _count_objects_of_type(objects: list[Any], item_type: str) -> int:
    return sum(
        1
        for o in objects
        if isinstance(o, dict) and str(o.get("item_type", "")).upper() == item_type
    )


def effective_generation_bounds(
    payload: CreateAdventureTemplatePayload, cover_manifest: Optional[dict[str, Any]]
) -> dict[str, Optional[int]]:
    """Min/max bounds per category for the world generator.

    In cover mode, a category left on "auto" (min=None, max=None) gets tight
    bounds derived from the source manifest so the cover has approximately the
    same asset density as the original adventure.
    """
    categories = ("sequences", "scenes", "items", "containers", "text_logs", "quests", "awards")
    bounds = {
        f"{edge}_{cat}": getattr(payload, f"{edge}_{cat}")
        for cat in categories
        for edge in ("min", "max")
    }
    if not cover_manifest:
        return bounds

    objects = cover_manifest.get("objects") or []
    chat_mode = is_chat_mode(payload)
    # category -> (source count, hard minimum, category enabled)
    rules = {
        "scenes": (len(cover_manifest.get("scenes") or []), 1, True),
        "sequences": (len(cover_manifest.get("sequences") or []), 0, True),
        "items": (len(objects), 1, True),
        "containers": (
            _count_objects_of_type(objects, "CONTAINER"),
            0,
            bool(payload.container_generation_enabled),
        ),
        "text_logs": (
            _count_objects_of_type(objects, "READABLE"),
            0,
            bool(payload.text_log_generation_enabled),
        ),
        "quests": (
            len(cover_manifest.get("quests") or []),
            1,
            bool(payload.quest_generation_enabled) and not chat_mode,
        ),
        "awards": (
            len(cover_manifest.get("awards") or []),
            1,
            bool(payload.award_generation_enabled) and not chat_mode,
        ),
    }
    for cat, (src_count, hard_min, enabled) in rules.items():
        is_auto = bounds[f"min_{cat}"] is None and bounds[f"max_{cat}"] is None
        if enabled and is_auto and src_count > 0:
            bounds[f"min_{cat}"], bounds[f"max_{cat}"] = _cover_bounds(src_count, hard_min)
    return bounds


@dataclass
class GenerationJob:
    payload: CreateAdventureTemplatePayload
    user_id: str
    template_id: str
    session_id: str
    selected_image_styles: Any
    cover: CoverSource


async def _load_template(db: AsyncSession, template_id: str) -> Optional[AdventureTemplate]:
    result = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    return result.scalars().first()


async def _generate_world(db: AsyncSession, user: Optional[User], job: GenerationJob) -> None:
    payload = job.payload
    chat_mode = is_chat_mode(payload)
    await WorldGenerator.generate_world(
        db=db,
        user=user,
        template_id=job.template_id,
        title=payload.title,
        original_prompt=payload.original_prompt or "",
        sequences=payload.sequences,
        generation_strictness=payload.generation_strictness or "creative",
        generate_scene_images=payload.generate_scene_images,
        generate_npc_images=payload.generate_npc_images,
        generate_item_images=payload.generate_item_images,
        automatic_npc_voice_assignment=payload.automatic_npc_voice_assignment,
        container_generation_enabled=payload.container_generation_enabled,
        scripts_generation_enabled=payload.scripts_generation_enabled,
        text_log_generation_enabled=bool(payload.text_log_generation_enabled),
        quest_generation_enabled=(not chat_mode) and bool(payload.quest_generation_enabled),
        award_generation_enabled=(False if chat_mode else payload.award_generation_enabled),
        can_damage_npcs=payload.can_damage_npcs,
        npcs_can_damage_protagonist=payload.npcs_can_damage_protagonist,
        selected_image_styles=job.selected_image_styles,
        language=payload.language,
        cover_source_manifest=job.cover.manifest,
        cover_source_adventure_id=job.cover.adventure_id,
        cover_source_adventure_name=(job.cover.name if job.cover.template else None),
        cover_similarity_percent=_similarity_percent(payload),
        allow_reuse_source_assets=bool(payload.allow_reuse_source_assets),
        **effective_generation_bounds(payload, job.cover.manifest),
    )


async def _record_generation_failure(db: AsyncSession, template_id: str, exc: Exception) -> None:
    adv = await _load_template(db, template_id)
    if not adv:
        return
    if is_image_moderation_error(exc):
        adv.is_ready = True
        adv.creation_status = "Ready"
        adv.creation_error = _IMAGE_MODERATION_NOTICE
    else:
        adv.creation_status = "Failed"
        adv.creation_error = str(exc)
    await db.commit()


async def _generate_and_finalize(db: AsyncSession, job: GenerationJob) -> None:
    user = (await db.execute(select(User).where(User.id == job.user_id))).scalars().first()

    adv = await _load_template(db, job.template_id)
    if adv:
        adv.creation_status = "Generating world structure"
        await db.commit()

    await _generate_world(db, user, job)

    if job.payload.auto_validate_and_fix:
        # Fixes must land on the template before the first session is built from it.
        from backend.api.routes.adventures.editing.auto_fix import run_auto_fix_pass_safely

        await run_auto_fix_pass_safely(db, job.template_id, user)

    await materialize_initial_session_from_template(
        db=db, template_id=job.template_id, session_id=job.session_id
    )

    adv = await _load_template(db, job.template_id)
    if adv:
        adv.is_ready = True
        adv.creation_status = "Ready"
        await db.commit()


async def run_background_generation(job: GenerationJob) -> None:
    """Background task: generate the world, then build the first session from it."""
    # A fresh DB session: the request session is closed once the response is sent.
    import backend.core.database as core_database

    async with core_database.AsyncSessionLocal() as db:
        try:
            await _generate_and_finalize(db, job)
        except Exception as exc:
            logger.exception("Background generation failed for %s: %s", job.template_id, exc)
            await _record_generation_failure(db, job.template_id, exc)
