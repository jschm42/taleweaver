"""Adventure editor router.

The endpoints live in :mod:`backend.api.routes.adventures.editing`; this module
combines their routers (in the original registration order) and re-exports the
helpers other modules import from here.
"""

from fastapi import APIRouter

from backend.api.routes.adventures.editing import (
    ai_fix_apply,
    ai_fix_suggest,
    generation,
    payload,
    script_assist,
    story_crud,
    validation,
    world_builder_instruct,
    world_crud,
)
from backend.api.routes.adventures.editing.ai_fix_context import _format_focused_world_block
from backend.api.routes.adventures.editing.common import (
    _get_owned_adventure_or_404,
    _get_template_avatar,
    _sanitize_editor_id,
    _sanitize_object_id,
)
from backend.api.routes.adventures.editing.entity_update import routes as entity_update
from backend.api.routes.adventures.editing.image_clone import _clone_entity_image
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.api.routes.adventures.editing.validation import (
    _finding_signature,
    _summarize_for_ai,
)
from backend.core.llm_router import GameMasterLLM

router = APIRouter(tags=["Editor"])
for _module in (
    payload,
    validation,
    ai_fix_suggest,
    ai_fix_apply,
    world_builder_instruct,
    script_assist,
    world_crud,
    story_crud,
    entity_update,
    generation,
):
    router.include_router(_module.router)

__all__ = [
    "GameMasterLLM",
    "_build_adventure_editor_assets",
    "_clone_entity_image",
    "_finding_signature",
    "_format_focused_world_block",
    "_get_owned_adventure_or_404",
    "_get_template_avatar",
    "_sanitize_editor_id",
    "_sanitize_object_id",
    "_summarize_for_ai",
    "router",
]
