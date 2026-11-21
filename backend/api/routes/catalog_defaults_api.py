"""Admin helpers for the style and tone catalogs.

* Built-in defaults for "Restore defaults"; the stored catalogs live in ``server_settings``
  and are saved through ``POST /settings/image-styles`` and ``/settings/tones``.
* A suggested image prompt for a catalog tile, written by the small LLM, with the built-in
  preview prompt as fallback when the model is unavailable or answers with nothing.
"""

import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.core.auth import get_current_admin
from backend.core.llm_router import GameMasterLLM
from backend.core.style_catalog import default_image_styles_catalog, default_tones_catalog
from backend.engine.media.catalog_tile_image import (
    CATALOG_PROMPT_SUGGESTION_SYSTEM_PROMPT,
    catalog_prompt_suggestion_request,
    catalog_tile_prompt,
)
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])

CatalogType = Literal["styles", "tones"]


class CatalogPromptRequest(BaseModel):
    catalog_type: CatalogType
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    instruction: Optional[str] = Field(default=None, max_length=2000)


@router.get("/catalog-defaults/{catalog_type}")
async def get_catalog_defaults(
    catalog_type: CatalogType,
    _admin: User = Depends(get_current_admin),
) -> dict[str, list[dict[str, Any]]]:
    """Returns a copy of the built-in styles or tones."""
    items = default_image_styles_catalog() if catalog_type == "styles" else default_tones_catalog()
    return {"items": items}


async def _llm_prompt(user: User, payload: CatalogPromptRequest) -> str:
    llm_settings = user.llm_settings or {}
    provider = (
        llm_settings.get("small_model_provider")
        or llm_settings.get("complex_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    llm = GameMasterLLM(user=user, provider=provider, model_category="small")
    answer = await llm.aexecute_simple_task(
        system_prompt=CATALOG_PROMPT_SUGGESTION_SYSTEM_PROMPT,
        user_prompt=catalog_prompt_suggestion_request(
            payload.catalog_type, payload.name, payload.description, payload.instruction
        ),
        model=model,
        operation="catalog_prompt_suggestion",
    )
    return (answer or "").strip().strip('"').strip()


@router.post("/catalog/suggest-prompt")
async def suggest_catalog_prompt(
    payload: CatalogPromptRequest,
    admin: User = Depends(get_current_admin),
) -> dict[str, str]:
    """Suggests an image prompt for a catalog tile; `source` says who wrote it."""
    try:
        suggested = await _llm_prompt(admin, payload)
    except Exception as exc:  # Any provider failure falls back to the template prompt.
        logger.warning("Catalog prompt suggestion failed, using the template: %s", exc)
        suggested = ""
    if suggested:
        return {"prompt": suggested, "source": "llm"}
    fallback = catalog_tile_prompt(
        payload.catalog_type, payload.name, payload.description, payload.instruction
    )
    return {"prompt": fallback, "source": "template"}
