"""LLM-based enhancement and optimization for user-provided image prompts."""

import logging
from typing import Optional

from backend.core import prompts
from backend.core.llm_router import GameMasterLLM
from backend.models.user import User

logger = logging.getLogger(__name__)


async def enhance_image_prompt(
    current_user: User,
    prompt: str,
    target_type: Optional[str] = None,
    appearance: Optional[str] = None,
) -> str:
    """Enhance and optimize a user-provided image generation prompt."""
    raw = (prompt or "").strip()
    if not raw:
        return ""

    llm_settings = current_user.llm_settings or {}
    provider = (
        llm_settings.get("small_model_provider")
        or llm_settings.get("complex_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    model = llm_settings.get("small_model") or "gpt-4o-mini"

    context_lines = []
    if target_type:
        context_lines.append(f"Asset Type: {target_type.upper()}")
    if appearance and appearance.strip():
        context_lines.append(f"Visual Appearance Keywords: {appearance.strip()}")
    context_block = ("\n".join(context_lines) + "\n") if context_lines else ""

    user_prompt = prompts.IMAGE_PROMPT_ENHANCEMENT_USER_PROMPT_TEMPLATE.format(
        context_block=context_block,
        prompt=raw,
    )

    try:
        llm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
        enhanced = await llm.aexecute_simple_task(
            system_prompt=prompts.IMAGE_PROMPT_ENHANCEMENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=model,
        )
        cleaned = enhanced.strip().strip('"').strip("'")
        return cleaned or raw
    except Exception as exc:
        logger.warning("Prompt enhancement LLM call failed, returning original prompt: %s", exc)
        return raw
