"""LLM-backed text generation endpoints for the editor."""

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.schemas import (
    BiographyGenerationRequest,
    BiographyGenerationResponse,
    DecorativeItemsGenerationRequest,
    DecorativeItemsGenerationResponse,
    QuestDescriptionGenerationRequest,
    QuestDescriptionGenerationResponse,
    QuestGenerationRequest,
    QuestGenerationResponse,
    SceneDescriptionGenerationRequest,
    SceneDescriptionGenerationResponse,
    TraitGenerationRequest,
    TraitGenerationResponse,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import (
    BIOGRAPHY_GENERATION_SYSTEM_PROMPT,
    BIOGRAPHY_GENERATION_USER_PROMPT_TEMPLATE,
    DECORATIVE_ITEMS_GENERATION_SYSTEM_PROMPT,
    DECORATIVE_ITEMS_GENERATION_USER_PROMPT_TEMPLATE,
    QUEST_DESCRIPTION_GENERATION_SYSTEM_PROMPT,
    QUEST_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE,
    QUEST_GENERATION_SYSTEM_PROMPT,
    QUEST_GENERATION_USER_PROMPT_TEMPLATE,
    SCENE_DESCRIPTION_GENERATION_SYSTEM_PROMPT,
    SCENE_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE,
    TRAIT_GENERATION_SYSTEM_PROMPT,
    TRAIT_GENERATION_USER_PROMPT_TEMPLATE,
)
from backend.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

_MAX_TEXT_LENGTH = 1000
_MAX_DECORATIVE_ITEMS = 7
_MAX_DECORATIVE_ITEM_LENGTH = 100
_DEFAULT_THEME = "Fantasy Adventure"
_TRAIT_FOCUS = {
    "goal": "IMPORTANT: Focus specifically on generating a compelling Goal/Motivation.",
    "character": "IMPORTANT: Focus specifically on generating evocative Personality/Traits.",
}


def _small_llm(current_user: User) -> tuple[GameMasterLLM, str]:
    """The user's configured small model, used for all editor text helpers."""
    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    return GameMasterLLM(user=current_user, provider=provider, model_category="small"), model


async def _run_structured(
    current_user: User, system_prompt: str, user_prompt: str, response_model: type, label: str
) -> Any:
    gm, model = _small_llm(current_user)
    try:
        return await gm.aexecute_complex_task(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            model=model,
        )
    except Exception as e:
        logger.error(f"Failed to generate {label}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _run_text(current_user: User, system_prompt: str, user_prompt: str, label: str) -> str:
    gm, model = _small_llm(current_user)
    try:
        return await gm.aexecute_simple_task(
            system_prompt=system_prompt, user_prompt=user_prompt, model=model
        )
    except Exception as e:
        logger.error(f"Failed to generate {label}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


def _clean_generated_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1].strip()
    return cleaned[:_MAX_TEXT_LENGTH]


def _format_other_quests(other_quests: list[dict[str, Any]] | None) -> str:
    """List existing quests so the model does not generate duplicates."""
    if not other_quests:
        return "No other quests defined yet."
    lines = []
    for q in other_quests:
        q_title = q.get("title") or "Unnamed Quest"
        q_desc = q.get("description") or "No description."
        q_type = "Main" if q.get("is_main") else "Side"
        lines.append(f"- [{q_type}] {q_title}: {q_desc}")
    return "\n".join(lines)


@router.post("/{template_id}/editor/generate-traits", response_model=TraitGenerationResponse)
async def generate_entity_traits(
    template_id: str,
    payload: TraitGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates NPC/Protagonist goal and character traits based on description/bio."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    base_prompt = TRAIT_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        description=payload.description,
        adventure_theme=payload.adventure_theme or adv.original_prompt or _DEFAULT_THEME,
    )
    user_prompt = f"{base_prompt}\n{_TRAIT_FOCUS.get(payload.target_field or '', '')}"
    return await _run_structured(
        current_user,
        TRAIT_GENERATION_SYSTEM_PROMPT,
        user_prompt,
        TraitGenerationResponse,
        "traits",
    )


@router.post(
    "/{template_id}/editor/generate-quest-description",
    response_model=QuestDescriptionGenerationResponse,
)
async def generate_quest_description(
    template_id: str,
    payload: QuestDescriptionGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    user_prompt = QUEST_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE.format(
        title=payload.title,
        quest_type="Main" if payload.is_main else "Side",
        adventure_title=adv.title or "Untitled Adventure",
        adventure_plot=adv.plot or adv.original_prompt or "No description provided.",
        adventure_tone=adv.selected_tone or "Standard",
        other_quests_text=_format_other_quests(payload.other_quests),
    )
    return await _run_structured(
        current_user,
        QUEST_DESCRIPTION_GENERATION_SYSTEM_PROMPT,
        user_prompt,
        QuestDescriptionGenerationResponse,
        "quest description",
    )


@router.post("/{template_id}/editor/generate-new-quest", response_model=QuestGenerationResponse)
async def generate_new_quest(
    template_id: str,
    payload: QuestGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    user_prompt = QUEST_GENERATION_USER_PROMPT_TEMPLATE.format(
        quest_type="Main" if payload.is_main else "Side",
        adventure_title=adv.title or "Untitled Adventure",
        adventure_plot=adv.plot or adv.original_prompt or "No description provided.",
        adventure_tone=adv.selected_tone or "Standard",
        other_quests_text=_format_other_quests(payload.other_quests),
    )
    return await _run_structured(
        current_user,
        QUEST_GENERATION_SYSTEM_PROMPT,
        user_prompt,
        QuestGenerationResponse,
        "new quest",
    )


@router.post("/{template_id}/editor/generate-biography", response_model=BiographyGenerationResponse)
async def generate_entity_biography(
    template_id: str,
    payload: BiographyGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates NPC/Protagonist description/biography based on name, goal, and character traits."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    user_prompt = BIOGRAPHY_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        goal=payload.goal,
        character=payload.character,
        theme=payload.adventure_theme or adv.original_prompt or _DEFAULT_THEME,
    )
    text = await _run_text(
        current_user, BIOGRAPHY_GENERATION_SYSTEM_PROMPT, user_prompt, "biography"
    )
    return BiographyGenerationResponse(description=_clean_generated_text(text))


@router.post(
    "/{template_id}/editor/generate-scene-description",
    response_model=SceneDescriptionGenerationResponse,
)
async def generate_scene_description(
    template_id: str,
    payload: SceneDescriptionGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a scene description based on scene name and adventure theme context."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    user_prompt = SCENE_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        theme=payload.adventure_theme or adv.original_prompt or _DEFAULT_THEME,
    )
    text = await _run_text(
        current_user, SCENE_DESCRIPTION_GENERATION_SYSTEM_PROMPT, user_prompt, "scene description"
    )
    return SceneDescriptionGenerationResponse(description=_clean_generated_text(text))


def _decorative_items_array(text: str) -> Any:
    """The ``items`` list of the answer. Models sometimes add stray characters after the JSON
    (e.g. ``{"items": [...]} "}"``) or return a bare array, so on invalid JSON only the
    array itself is decoded and anything around it is ignored."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        key_at = text.find('"items"')
        start = text.find("[", max(key_at, 0))
        if start == -1:
            raise
        data, _end = json.JSONDecoder().raw_decode(text, start)
    return data.get("items") if isinstance(data, dict) else data


def _parse_decorative_items(
    generated_text: str, existing_lower: set[str], max_new: int
) -> list[str]:
    """Parse the ``{"items": [...]}`` answer into new, de-duplicated, lowercase noun phrases."""
    cleaned = generated_text.strip()
    # Strip optional code fences the model sometimes wraps the JSON in.
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    raw_items = _decorative_items_array(cleaned)
    if not isinstance(raw_items, list):
        raise ValueError("LLM response did not contain an 'items' array.")

    seen = set(existing_lower)
    parsed: list[str] = []
    for raw in raw_items:
        value = raw.strip().rstrip(",.;:!?").strip().lower() if isinstance(raw, str) else ""
        value = value[:_MAX_DECORATIVE_ITEM_LENGTH]
        if not value or value in seen:
            continue
        seen.add(value)
        parsed.append(value)
        if len(parsed) >= max_new:
            break
    return parsed


@router.post(
    "/{template_id}/editor/generate-decorative-items",
    response_model=DecorativeItemsGenerationResponse,
)
async def generate_decorative_items(
    template_id: str,
    payload: DecorativeItemsGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a list of decorative background details fitting a scene using the Simple LLM.

    The result is a JSON array of short noun-phrase strings (e.g. "metal table", "flickering torch").
    Existing items in `payload.existing_items` are excluded from the result and the total is capped
    so the merged list does not exceed 7 entries.
    """
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    existing = [
        str(item).strip() for item in (payload.existing_items or []) if str(item or "").strip()
    ]
    max_new = max(0, _MAX_DECORATIVE_ITEMS - len(existing))
    if max_new == 0:
        return DecorativeItemsGenerationResponse(items=[])

    user_prompt = DECORATIVE_ITEMS_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        theme=payload.adventure_theme or adv.original_prompt or _DEFAULT_THEME,
        description=payload.description or "(no description available)",
        existing_block="\n".join(f"- {item}" for item in existing) or "- (none)",
        max_new=max_new,
    )
    generated_text = await _run_text(
        current_user, DECORATIVE_ITEMS_GENERATION_SYSTEM_PROMPT, user_prompt, "decorative items"
    )
    try:
        items = _parse_decorative_items(
            generated_text, {item.lower() for item in existing}, max_new
        )
    except Exception as e:
        logger.error(f"Failed to parse decorative items response: {e}; raw=%r", generated_text)
        raise HTTPException(
            status_code=500, detail="LLM returned an invalid response for decorative items."
        ) from e
    return DecorativeItemsGenerationResponse(items=items)
