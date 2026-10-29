from __future__ import annotations

import logging
from copy import deepcopy
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.adventure_creation import (
    GenerationJob,
    create_adventure_records,
    run_background_generation,
)
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.manifest_export import (
    backfill_item_start_scenes,
    backfill_manifest_metadata,
    normalize_protagonist_items,
    serialize_exit,
)
from backend.api.routes.adventures.schemas import (
    AdventureTemplateResponse,
    AdventureTemplateSummaryResponse,
    AdventureTemplateUpdate,
    CreateAdventureTemplatePayload,
    StoryIdeaSuggestionRequest,
    StoryIdeaSuggestionResponse,
    TemplateFieldGenerationRequest,
    TemplateFieldGenerationResponse,
)
from backend.api.routes.adventures.template_reset import rebuild_template_world
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import (
    STORY_IDEA_GENERATION_SYSTEM_PROMPT,
    STORY_IDEA_GENERATION_USER_PROMPT_TEMPLATE,
    TEMPLATE_FIELD_GENERATION_SYSTEM_PROMPT,
    TEMPLATE_FIELD_GENERATION_USER_PROMPT_TEMPLATE,
)
from backend.engine.item_logic import normalize_equipment_keys
from backend.engine.world_generator import WorldGenerator
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.schemas.adventure import (
    GeneratorSurprisePresetRequest,
    GeneratorSurprisePresetResponse,
)
from backend.utils.download_headers import attachment_disposition

# WorldGenerator is re-exported so tests can patch ``templates.WorldGenerator.generate_world``.
__all__ = ["WorldGenerator", "router"]

router = APIRouter(tags=["Adventures"])
logger = logging.getLogger(__name__)


@router.post("/story-idea/suggest", response_model=StoryIdeaSuggestionResponse)
async def suggest_story_idea(
    payload: StoryIdeaSuggestionRequest,
    current_user: User = Depends(get_current_user),
):
    """Generates or improves an adventure title/story idea using the configured small model."""
    llm_settings = current_user.llm_settings or {}
    provider = (
        llm_settings.get("small_model_provider")
        or llm_settings.get("complex_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    model = llm_settings.get("small_model") or "gpt-4o-mini"

    selected_tone = payload.selected_tone or {}
    tone_label = ""
    if isinstance(selected_tone, dict):
        tone_label = str(selected_tone.get("name") or selected_tone.get("id") or "").strip()

    title = (payload.title or "").strip()
    story_idea = (payload.story_idea or "").strip()
    has_existing_input = bool(title or story_idea)

    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    user_prompt = STORY_IDEA_GENERATION_USER_PROMPT_TEMPLATE.format(
        selected_tone=tone_label or "Neutral",
        rule_enforcement_mode=(payload.rule_enforcement_mode or "story").upper(),
        language=payload.language or "Default",
        has_existing_input="yes" if has_existing_input else "no",
        title=title or "(empty)",
        story_idea=story_idea or "(empty)",
    )

    try:
        suggestion = await gm.aexecute_complex_task(
            system_prompt=STORY_IDEA_GENERATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=StoryIdeaSuggestionResponse,
            model=model,
        )
    except Exception as exc:
        logger.error("Failed to suggest story idea: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to generate story idea.") from exc

    final_title = suggestion.title.strip()[:50]
    if has_existing_input and title:
        final_title = title[:50]

    return StoryIdeaSuggestionResponse(
        title=final_title,
        story_idea=suggestion.story_idea.strip(),
    )


def _generate_fallback_surprise_preset(
    available_tones: list[str],
    available_styles: list[str],
    language: str = "English",
) -> GeneratorSurprisePresetResponse:
    import random

    archetypes = [
        {
            "title": "Orbital Void: Protocol Omega",
            "story_idea": (
                "Deep within the derelict orbital spire Aegis-7, an ancient quarantined AI has reawakened. "
                "You are an atmospheric scavenger dispatched to recover the core mainframe before automated security glass cleanses the station."
            ),
            "tone_candidates": ["Sci-Fi", "Cyberpunk", "Mystery", "Grimdark"],
            "style_candidates": ["cinematic-realism", "pixel-art", "dark-fantasy"],
            "rule_enforcement_mode": "story",
            "time_system": "calendar",
            "day_label": "Sol",
            "initial_day": 42,
            "start_time": "06:30",
            "time_format": "24h",
            "pacing_minutes": 5,
        },
        {
            "title": "Whispers of the Sunken Hollow",
            "story_idea": (
                "Beneath the mist-choked marshes of Oakhaven, a submerged cathedral rings its drowned bells. "
                "Strange glowing ichor seeps through ancient masonry as local villagers begin sleepwalking into the dark waters."
            ),
            "tone_candidates": ["Horror", "Mystery", "Grimdark"],
            "style_candidates": ["dark-fantasy", "watercolor", "vintage-comic"],
            "rule_enforcement_mode": "rpg",
            "time_system": "calendar",
            "day_label": "Day",
            "initial_day": 1,
            "start_time": "21:00",
            "time_format": "24h",
            "pacing_minutes": 10,
        },
        {
            "title": "Chronos Drift: The Broken Horizon",
            "story_idea": (
                "A localized temporal storm has fractured the frontier mining settlement of New Caelum into overlapping epochs. "
                "To restore chronological coherence, you must navigate shifting paradox corridors and locate the harmonic dampeners."
            ),
            "tone_candidates": ["Sci-Fi", "Mystery", "Heroic"],
            "style_candidates": ["anime", "cinematic-realism", "vintage-comic"],
            "rule_enforcement_mode": "story",
            "time_system": "units",
            "unit_name": "Cycles",
            "initial_units": 0,
            "units_per_turn": 1,
        },
        {
            "title": "The Gilded Bazaar of Never-Was",
            "story_idea": (
                "Hidden in an alleyway that only appears at twilight, the Bazaar of Never-Was trades in forgotten memories and bottled desires. "
                "A mischievous collector has stolen your true name, and you have until dawn to bargain it back before it is sold at auction."
            ),
            "tone_candidates": ["Whimsical", "Mystery", "Heroic", "Satirical"],
            "style_candidates": ["watercolor", "anime", "vintage-comic"],
            "rule_enforcement_mode": "chat",
            "time_system": "calendar",
            "day_label": "Night",
            "initial_day": 1,
            "start_time": "19:45",
            "time_format": "12h",
            "pacing_minutes": 15,
        },
    ]

    choice = random.choice(archetypes)
    matched_tone = next(
        (t for t in choice["tone_candidates"] if t in available_tones),
        available_tones[0] if available_tones else "Mystery",
    )
    matched_style = next(
        (s for s in choice["style_candidates"] if s in available_styles),
        available_styles[0] if available_styles else "dark-fantasy",
    )

    return GeneratorSurprisePresetResponse(
        title=choice["title"],
        story_idea=choice["story_idea"],
        selected_tone=matched_tone,
        selected_style=matched_style,
        rule_enforcement_mode=choice.get("rule_enforcement_mode", "story"),
        generate_scene_images=True,
        generate_npc_images=True,
        generate_item_images=True,
        clock_enabled=True,
        time_system=choice.get("time_system", "calendar"),
        day_label=choice.get("day_label", "Day"),
        initial_day=choice.get("initial_day", 1),
        start_time=choice.get("start_time", "08:00"),
        time_format=choice.get("time_format", "24h"),
        pacing_minutes=choice.get("pacing_minutes", 5),
        unit_name=choice.get("unit_name", "Units"),
        initial_units=choice.get("initial_units", 0),
        units_per_turn=choice.get("units_per_turn", 1),
        min_scenes=3,
        max_scenes=6,
        min_quests=2,
        max_quests=4,
    )


@router.post("/generator/surprise-me", response_model=GeneratorSurprisePresetResponse)
async def generate_surprise_preset(
    payload: Optional[GeneratorSurprisePresetRequest] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Generates a coherent, creative, and completely randomized adventure preset
    using the world-generation LLM (model_category="generator").
    """
    req = payload or GeneratorSurprisePresetRequest()
    llm_settings = current_user.llm_settings or {}
    provider = (
        llm_settings.get("generator_model_provider")
        or llm_settings.get("complex_model_provider")
        or llm_settings.get("small_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    model = (
        llm_settings.get("generator_model")
        or llm_settings.get("complex_model")
        or llm_settings.get("small_model")
        or "gpt-4o"
    )

    available_tones = req.available_tones or [
        "Heroic",
        "Grimdark",
        "Whimsical",
        "Mystery",
        "Cyberpunk",
        "Horror",
        "Sci-Fi",
        "Satirical",
    ]
    available_styles = req.available_styles or [
        "cinematic-realism",
        "dark-fantasy",
        "anime",
        "pixel-art",
        "vintage-comic",
        "watercolor",
    ]
    language = req.language or current_user.default_language or "English"

    system_prompt = (
        "You are the Master Reality Architect of TaleWeaver, an advanced AI interactive fiction engine. "
        "Your role is to design an evocative, original, and deeply atmospheric adventure blueprint that pre-fills "
        "the world generator parameters. Create an inventive story vision across any genre (fantasy, sci-fi, horror, "
        "cyberpunk, mystery, surrealism, solarpunk, etc.). Specify the title (max 50 chars), a 2-4 sentence story idea, "
        "the best matching tone, visual art style, rule mode (rpg, story, or chat), and a thematic in-game time system."
    )

    user_prompt = (
        f"Design a surprising and inspiring new adventure concept.\n"
        f"- Target Language: {language}\n"
        f"- Available Tones: {', '.join(available_tones)}\n"
        f"- Available Visual Art Styles: {', '.join(available_styles)}\n\n"
        f"Requirements:\n"
        f"1. Choose the single most fitting Tone from the available list (exact ID or name).\n"
        f"2. Choose the single most fitting Visual Style from the available list (exact ID or name).\n"
        f"3. Select rule_enforcement_mode: 'rpg' (strict checks/combat), 'story' (balanced narrative priority), or 'chat' (casual roleplay).\n"
        f"4. Decide time_system: 'calendar' (day & clock time) or 'units' (abstract units like Cycles, Hours, Lightyears, Sol, etc.).\n"
        f"   - If 'calendar': provide thematic day_label (e.g. Day, Sol, Cycle, Shift), initial_day, start_time (HH:MM), and pacing_minutes (1-60).\n"
        f"   - If 'units': provide unit_name (e.g. Hours, Cycles, Jumps, Lightyears), initial_units, and units_per_turn (1-10).\n"
        f"5. Set generate_scene_images, generate_npc_images, generate_item_images (typically true).\n"
        f"6. Optionally set min_scenes (3-6), max_scenes (5-10), min_quests (2-4), max_quests (3-6)."
    )

    gm = GameMasterLLM(user=current_user, provider=provider, model_category="generator")

    try:
        preset = await gm.aexecute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=GeneratorSurprisePresetResponse,
            model=model,
        )
        # Normalize title length
        preset.title = preset.title.strip()[:50]
        # Match selected_tone to available_tones if possible
        if preset.selected_tone and available_tones:
            lower_tones = {t.lower(): t for t in available_tones}
            if preset.selected_tone.lower() in lower_tones:
                preset.selected_tone = lower_tones[preset.selected_tone.lower()]
        # Match selected_style to available_styles if possible
        if preset.selected_style and available_styles:
            lower_styles = {s.lower(): s for s in available_styles}
            if preset.selected_style.lower() in lower_styles:
                preset.selected_style = lower_styles[preset.selected_style.lower()]

        return preset
    except Exception as exc:
        logger.warning(
            "World-gen LLM surprise preset generation failed, using diverse archetype fallback: %s",
            exc,
        )
        return _generate_fallback_surprise_preset(available_tones, available_styles, language)


_GENERATABLE_FIELD_LIMITS = {
    "plot": 5000,
    "rules": 5000,
    "intro_text": 20000,
    "completed_condition": 2000,
    "gameover_condition": 2000,
    "tts_director_notes": 5000,
}
_GENERATABLE_FIELD_LABELS = {
    "plot": "Adventure Plot (Secret)",
    "rules": "Adventure Rules / Mechanics",
    "intro_text": "Session Intro Text",
    "completed_condition": "Win Conditions",
    "gameover_condition": "Loss Conditions",
    "tts_director_notes": "Director's TTS Notes",
}
_FIELD_CONTEXT_KEYS = (
    "original_prompt",
    "plot",
    "rules",
    "intro_text",
    "completed_condition",
    "gameover_condition",
    "completed_guard_expression",
    "gameover_guard_expression",
    "tts_director_notes",
)


def _small_model_choice(user: User) -> tuple[str, str]:
    llm_settings = user.llm_settings or {}
    provider = (
        llm_settings.get("small_model_provider")
        or llm_settings.get("complex_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    return provider, llm_settings.get("small_model") or "gpt-4o-mini"


def _field_generation_context(
    payload: TemplateFieldGenerationRequest, adv: AdventureTemplate
) -> dict[str, str]:
    context = {"title": payload.title or adv.title}
    for key in _FIELD_CONTEXT_KEYS:
        context[key] = getattr(payload, key, None) or getattr(adv, key, None) or ""
    return context


def _other_fields_block(context: dict[str, str], target_field: str) -> str:
    """Bullet list of the other filled-in fields, used as generation context."""
    lines = []
    for key, value in context.items():
        if key == target_field or key in ("title", "original_prompt"):
            continue
        text = value.strip() if value else ""
        if text:
            label = _GENERATABLE_FIELD_LABELS.get(key, key.replace("_", " ").title())
            lines.append(f"- {label}: {text}\n\n")
    return "".join(lines)


def _tone_name(adv: AdventureTemplate) -> str:
    tone = adv.selected_tone
    if not isinstance(tone, dict):
        return "Neutral"
    return tone.get("name") or tone.get("id") or "Neutral"


def _clean_generated_field_text(text: str, label: str, max_len: int) -> str:
    """Strip an echoed "<label>:" prefix and code fences, then enforce the DB length."""
    cleaned = text.strip()
    prefix = f"{label}:"
    if cleaned.lower().startswith(prefix.lower()):
        cleaned = cleaned[len(prefix) :].strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned[:max_len]


@router.post("/{template_id}/generate-field", response_model=TemplateFieldGenerationResponse)
async def generate_template_field(
    template_id: str,
    payload: TemplateFieldGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a template field using the configured small/simple model, given the other fields as context."""
    # 1. Fetch template and check ownership
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    # 2. Get user's LLM settings for small model
    provider, model = _small_model_choice(current_user)

    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")

    # 3. Determine the target field and limits
    target_field = payload.field
    if target_field not in _GENERATABLE_FIELD_LIMITS:
        raise HTTPException(status_code=400, detail="Invalid field name for generation.")

    max_len = _GENERATABLE_FIELD_LIMITS[target_field]
    label = _GENERATABLE_FIELD_LABELS[target_field]

    # 4. Construct the prompt context, preferring payload values over saved ones.
    context_data = _field_generation_context(payload, adv)

    # Remove the target field from context so it's not self-referential
    context_data[target_field] = ""

    other_fields_block = _other_fields_block(context_data, target_field)
    system_prompt = TEMPLATE_FIELD_GENERATION_SYSTEM_PROMPT.format(
        language=adv.language or "English",
        tone=_tone_name(adv),
        label=label,
    )

    user_prompt = TEMPLATE_FIELD_GENERATION_USER_PROMPT_TEMPLATE.format(
        label=label,
        title=context_data["title"],
        original_prompt=context_data["original_prompt"],
        other_fields_block=other_fields_block or "- No other fields are defined yet.",
        max_len=max_len,
    )

    try:
        generated_text = await gm.aexecute_simple_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
        )
    except Exception as exc:
        logger.error("Failed to generate template field %s: %s", target_field, exc)
        raise HTTPException(status_code=500, detail=f"Failed to generate {label}.") from exc

    return TemplateFieldGenerationResponse(
        generated_text=_clean_generated_field_text(generated_text, label, max_len)
    )


@router.get("/templates", response_model=list[AdventureTemplateSummaryResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Returns all adventure templates and optional active session metadata."""
    template_rows = await db.execute(
        select(AdventureTemplate).where(AdventureTemplate.owner_id == current_user.id)
    )
    templates = template_rows.scalars().all()

    session_rows = await db.execute(
        select(GameSession, SessionState, WorldScene.label)
        .join(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(
            WorldScene,
            (WorldScene.template_id == GameSession.template_id)
            & (WorldScene.id == SessionState.current_scene_id),
        )
        .where((GameSession.user_id == current_user.id) & (GameSession.status == "active"))
        .order_by(func.coalesce(GameSession.last_played_at, GameSession.created_at).desc())
    )
    # First row per template wins, so active_game_id points at the most recently played session.
    latest_by_template = {}
    for game_session, state, scene_label in session_rows.all():
        if game_session.template_id not in latest_by_template:
            latest_by_template[game_session.template_id] = (
                game_session,
                state,
                scene_label,
            )

    from backend.engine.adventure_updates import (
        check_template_update,
        scan_available_adventure_files,
    )

    available_files = scan_available_adventure_files()

    response = []
    for template in templates:
        latest = latest_by_template.get(template.id)
        game_session, state, scene_label = latest if latest else (None, None, None)
        update_info = check_template_update(template, available_files)
        response.append(
            AdventureTemplateSummaryResponse(
                template_id=template.id,
                title=template.title,
                teaser=template.teaser,
                version=template.version,
                creator=template.creator,
                copyright=template.copyright,
                license=template.license,
                license_url=template.license_url,
                image_url=template.image_url,
                is_ready=template.is_ready,
                creation_status=template.creation_status,
                creation_error=template.creation_error,
                selected_tone=template.selected_tone,
                progress=AdventureLogic.calculate_quest_progress(template.quests),
                quest_count=len(template.quests or []),
                completed_quest_count=len(
                    [q for q in (template.quests or []) if q.get("status") == "completed"]
                ),
                active_game_id=(game_session.id if game_session else None),
                has_active_session=(game_session is not None),
                last_played_at=(game_session.last_played_at if game_session else None),
                scene_id=(state.current_scene_id if state else None),
                current_scene_name=(scene_label if scene_label else None),
                origin_id=template.origin_id,
                is_adventure_generator=template.is_adventure_generator,
                cover_source_adventure_id=template.cover_source_adventure_id,
                cover_source_adventure_name=template.cover_source_adventure_name,
                has_update=update_info["has_update"],
                available_version=update_info["available_version"],
                has_sequences=update_info["has_sequences"],
                is_legacy_format=update_info["is_legacy_format"],
                is_deprecated=update_info["is_deprecated"],
                can_start=update_info["can_start"],
                rule_enforcement_mode=template.rule_enforcement_mode or "rpg",
                selected_image_styles=template.selected_image_styles,
            )
        )
    return response


@router.post("/templates/update-all")
@router.post("/update-all")
async def update_all_adventure_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates all adventure templates for the user that have newer versions in /adventures."""
    from backend.engine.adventure_updates import update_all_adventures

    try:
        return await update_all_adventures(
            db=db,
            user_id=current_user.id,
        )
    except Exception as e:
        logger.exception("Failed to update all adventure templates")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/templates/{template_id}/update")
@router.post("/{template_id}/update")
async def update_adventure_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates an individual adventure template from its matching file in /adventures."""
    from backend.engine.adventure_updates import update_single_adventure

    try:
        return await update_single_adventure(
            db=db,
            template_id=template_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to update adventure template %s", template_id)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/templates/{template_id}/migrate")
@router.post("/{template_id}/migrate")
async def migrate_adventure_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Migrates a legacy adventure template to the current sequence-supported format."""
    from backend.engine.adventure_updates import migrate_single_adventure

    try:
        return await migrate_single_adventure(
            db=db,
            template_id=template_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to migrate adventure template %s", template_id)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{template_id}", response_model=AdventureTemplateResponse)
async def get_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the details of a single adventure by its ID."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    user_earned_keys = {
        ea.get("key")
        for ea in (current_user.earned_awards or [])
        if ea.get("template_id") == adv.id or ea.get("adventure_id") == adv.id
    }
    enriched_awards = [
        {**aw, "is_earned": aw.get("key") in user_earned_keys} for aw in (adv.awards or [])
    ]

    if (
        not adv.sequences
        and isinstance(adv.original_manifest, dict)
        and adv.original_manifest.get("sequences")
    ):
        adv.sequences = adv.original_manifest.get("sequences")

    response_data = AdventureTemplateResponse.model_validate(adv).model_dump()
    response_data["awards"] = enriched_awards
    return response_data


@router.post("/", status_code=201)
async def create_adventure(
    payload: CreateAdventureTemplatePayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new adventure template, initializes the protagonist avatar and first game session,
    and starts the background world generation task.
    """
    created = await create_adventure_records(db, payload, current_user)
    if not payload.skip_generation:
        background_tasks.add_task(
            run_background_generation,
            GenerationJob(
                payload=payload,
                user_id=current_user.id,
                template_id=created.template.id,
                session_id=created.session.id,
                selected_image_styles=created.template.selected_image_styles,
                cover=created.cover,
            ),
        )

    return {
        "game_id": created.session.id,
        "adventure_id": created.template.id,
        "avatar_id": created.avatar.id,
    }


@router.post("/{template_id}/reset")
async def reset_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rebuilds the template world data from original_manifest, preserving existing image URLs."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
    if not adv.original_manifest:
        raise HTTPException(status_code=400, detail="No original manifest to reset from.")

    await rebuild_template_world(db, adv)
    await db.commit()
    return {"status": "reset", "template_id": template_id}


_SESSION_SYNCED_NARRATIVE_FIELDS = (
    "plot",
    "rules",
    "completed_condition",
    "gameover_condition",
    "completed_guard_expression",
    "gameover_guard_expression",
    "tts_director_notes",
)
_SESSION_SYNC_TRIGGER_TIME_FIELDS = (
    "time_system",
    "time_config",
    "clock_enabled",
    "pacing_minutes",
    "time_per_turn",
    "max_time_per_turn",
)
_SESSION_SYNCED_TIME_FIELDS = ("time_system", "time_config")


def _apply_sequences_update(adv: AdventureTemplate, sequences: Optional[list]) -> None:
    """Store sequences on the template and mirror them into the original manifest."""
    from sqlalchemy.orm.attributes import flag_modified

    adv.sequences = list(sequences or [])
    flag_modified(adv, "sequences")
    manifest = deepcopy(adv.original_manifest or {})
    manifest["sequences"] = adv.sequences
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


async def _sync_updates_to_sessions(db: AsyncSession, template_id: str, update_data: dict) -> None:
    """Propagate narrative and time settings changes to the template's sessions."""
    triggers = (*_SESSION_SYNCED_NARRATIVE_FIELDS, *_SESSION_SYNC_TRIGGER_TIME_FIELDS)
    if not any(f in update_data for f in triggers):
        return
    synced = [
        f
        for f in (*_SESSION_SYNCED_NARRATIVE_FIELDS, *_SESSION_SYNCED_TIME_FIELDS)
        if f in update_data
    ]
    session_res = await db.execute(
        select(SessionState).where(SessionState.template_id == template_id)
    )
    for state in session_res.scalars().all():
        for f in synced:
            setattr(state, f, update_data[f])


@router.patch("/{template_id}", response_model=AdventureTemplateResponse)
async def update_adventure(
    template_id: str,
    payload: AdventureTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partially updates an adventure template's metadata, narrative fields, or configuration."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("max_containers") is not None:
        update_data["max_containers"] = max(0, min(30, int(update_data["max_containers"])))

    for field, value in update_data.items():
        setattr(adv, field, value)

    # Sync strict_rules internally if mode changed (but not if strict_rules was patched directly)
    if "rule_enforcement_mode" in update_data and "strict_rules" not in update_data:
        adv.strict_rules = update_data["rule_enforcement_mode"] != "chat"

    if "sequences" in update_data:
        _apply_sequences_update(adv, update_data["sequences"])

    await _sync_updates_to_sessions(db, template_id, update_data)

    await db.commit()
    await db.refresh(adv)

    # Enrich awards for response
    user_earned_keys = {
        ea.get("key")
        for ea in (current_user.earned_awards or [])
        if ea.get("template_id") == adv.id or ea.get("adventure_id") == adv.id
    }
    enriched_awards = [
        {**aw, "is_earned": aw.get("key") in user_earned_keys} for aw in (adv.awards or [])
    ]

    response_data = AdventureTemplateResponse.model_validate(adv).model_dump()
    response_data["awards"] = enriched_awards
    return response_data


@router.get("/{template_id}/status")
async def get_adventure_status(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.models.avatar import Avatar
    from backend.models.world_entity import WorldEntity, WorldScene

    """Retrieves the generation status and potential errors for an adventure."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    stats = None
    if adv.is_ready:
        avatar = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
        avatar = avatar.scalars().first()

        scenes = await db.execute(
            select(WorldScene).where(
                WorldScene.template_id == template_id, WorldScene.session_id.is_(None)
            )
        )
        scenes = scenes.scalars().all()

        entities = await db.execute(
            select(WorldEntity).where(
                WorldEntity.template_id == template_id, WorldEntity.session_id.is_(None)
            )
        )
        entities = entities.scalars().all()

        stats = {
            "cover": {
                "generated": 1 if not adv.cover_source_adventure_id else 0,
                "reused": 1 if adv.cover_source_adventure_id else 0,
            },
            "protagonist": {
                "generated": 1 if avatar and not getattr(avatar, "source_asset_id", None) else 0,
                "reused": 1 if avatar and getattr(avatar, "source_asset_id", None) else 0,
            },
            "scene": {
                "generated": len([s for s in scenes if not getattr(s, "source_asset_id", None)]),
                "reused": len([s for s in scenes if getattr(s, "source_asset_id", None)]),
            },
            "npc": {
                "generated": len(
                    [
                        e
                        for e in entities
                        if e.entity_type == "NPC" and not getattr(e, "source_asset_id", None)
                    ]
                ),
                "reused": len(
                    [
                        e
                        for e in entities
                        if e.entity_type == "NPC" and getattr(e, "source_asset_id", None)
                    ]
                ),
            },
            "item": {
                "generated": len(
                    [
                        e
                        for e in entities
                        if e.entity_type == "OBJECT" and not getattr(e, "source_asset_id", None)
                    ]
                ),
                "reused": len(
                    [
                        e
                        for e in entities
                        if e.entity_type == "OBJECT" and getattr(e, "source_asset_id", None)
                    ]
                ),
            },
        }

    return {
        "status": adv.creation_status or "Unknown",
        "is_ready": adv.is_ready,
        "error": adv.creation_error,
        "stats": stats,
    }


@router.get("/{template_id}/state")
async def get_adventure_state(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the current runtime state for the latest session of this template for the user."""
    state = await AdventureLogic.resolve_session_state(db, template_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")

    is_paused = False
    if state.session and getattr(state.session, "status", None):
        is_paused = state.session.status == "paused"

    return {
        "scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time,
        "is_paused": is_paused,
    }


@router.patch("/{template_id}/state")
async def patch_adventure_state(
    template_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Patch mutable fields on the active session state (e.g. scene_id)."""
    state = await AdventureLogic.resolve_session_state(db, template_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")

    updated = False
    if "scene_id" in payload:
        state.current_scene_id = payload.get("scene_id")
        updated = True
    if "in_game_time" in payload:
        try:
            state.in_game_time = int(payload.get("in_game_time"))
            updated = True
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid in_game_time %r", payload.get("in_game_time"))

    if updated:
        await db.commit()

    return {
        "scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time,
    }


@router.post("/{template_id}/pause")
async def pause_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause the most recent session for this user/template."""
    res = await db.execute(
        select(GameSession)
        .where(GameSession.template_id == template_id)
        .order_by(GameSession.updated_at.desc())
    )
    session = next(iter(res.scalars().all()), None)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")

    session.status = "paused"
    await db.commit()
    return {"status": "paused"}


@router.post("/{template_id}/resume")
async def resume_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused session for this user/template."""
    res = await db.execute(
        select(GameSession)
        .where(GameSession.template_id == template_id)
        .order_by(GameSession.updated_at.desc())
    )
    session = next(iter(res.scalars().all()), None)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")

    session.status = "active"
    await db.commit()
    return {"status": "active"}


@router.post("/{template_id}/cancel")
async def cancel_adventure_generation(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Signals a background generation task to stop by updating the template status."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    if adv.is_ready:
        raise HTTPException(status_code=400, detail="Generation already finished.")

    adv.creation_status = "Cancelled"
    await db.commit()
    return {"status": "Cancelled"}


@router.post("/{template_id}/cancel")
async def cancel_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancels an active adventure generation."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    if not adv.is_ready:
        adv.creation_status = "Cancelled"
        await db.commit()

    return {"status": "cancelled"}


@router.delete("/{template_id}", status_code=200)
async def delete_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an adventure template and all associated scenes, entities, maps, etc."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    await AdventureLogic.delete_adventure(db, template_id)
    return {"status": "deleted", "template_id": template_id}


@router.get("/{template_id}/export/manifest")
async def export_adventure_manifest(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the raw/original manifest stored in the template with minor backfills if needed."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adventure = result.scalars().first()
    if not adventure or not adventure.original_manifest:
        raise HTTPException(status_code=404, detail="Original manifest not found.")

    manifest = deepcopy(adventure.original_manifest)
    backfill_manifest_metadata(manifest, adventure)
    normalize_protagonist_items(manifest)

    entity_res = await db.execute(
        select(WorldEntity.id, WorldEntity.current_scene_id).where(
            WorldEntity.template_id == template_id
        )
    )
    backfill_item_start_scenes(
        manifest, {row.id: row.current_scene_id for row in entity_res.all() if row.id}
    )

    # Sync exits from world_exits table to reflect world editor updates
    exit_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id))
    db_exits = exit_res.scalars().all()
    if db_exits:
        manifest["exits"] = [serialize_exit(x) for x in db_exits]

    return manifest


@router.get("/{template_id}/export/adv")
async def export_adventure_adv(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the adventure as a pure .adv JSON manifest."""
    from backend.engine.adventure_exporter import AdventureExporter

    try:
        manifest = await AdventureExporter.build_full_manifest(db, template_id)
        return manifest
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{template_id}/export/adz")
async def export_adventure_adz(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the adventure as a portable .adz (ZIP) bundle including assets."""
    import io

    from backend.engine.adventure_exporter import AdventureExporter

    try:
        zip_data = await AdventureExporter.export_adz(db, template_id)
        return StreamingResponse(
            io.BytesIO(zip_data),
            media_type="application/zip",
            headers={"Content-Disposition": attachment_disposition(f"adventure_{template_id}.adz")},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("ADZ Export failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{template_id}/export/session")
async def export_adventure_session(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports a minimal session payload for the template (useful for import/preview)."""
    # Find template-level avatar if present
    av_res = await db.execute(
        select(Avatar)
        .where(Avatar.template_id == template_id)
        .order_by(Avatar.created_at.asc(), Avatar.id.asc())
        .limit(1)
    )
    avatar = av_res.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found for template.")

    avatar_payload = {
        "name": avatar.name,
        "role": avatar.role,
        "description": avatar.description,
        "profile_image": avatar.profile_image,
        "hp": avatar.hp,
        "stamina": avatar.stamina,
        "mana": avatar.mana,
        "inventory": avatar.inventory or [],
        "equipment": normalize_equipment_keys(avatar.equipment),
    }

    return {"avatar": avatar_payload}


@router.get("/{template_id}/generation-logs")
async def get_adventure_generation_logs(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves the live detailed generation logs (history) for an adventure template."""
    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    return {"logs": adv.generation_logs or []}
