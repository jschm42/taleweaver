from fastapi import APIRouter

from backend.api.routes.adventures.agent_routes import router as agent_router
from backend.api.routes.adventures.assets import router as assets_router
from backend.api.routes.adventures.cloning import router as cloning_router
from backend.api.routes.adventures.editor import router as editor_router
from backend.api.routes.adventures.editor_entity_transfer import (
    router as editor_entity_transfer_router,
)
from backend.api.routes.adventures.editor_npc_combat import router as editor_npc_combat_router
from backend.api.routes.adventures.editor_special_actions import (
    router as editor_special_actions_router,
)
from backend.api.routes.adventures.gameplay import router as gameplay_router
from backend.api.routes.adventures.imports import router as imports_router
from backend.api.routes.adventures.sessions import router as sessions_router
from backend.api.routes.adventures.templates import router as templates_router

router = APIRouter(prefix="/adventures")

# Include sub-routers in order of specificity.
# 1. Imports (static paths like /import, /check-defaults)
router.include_router(imports_router)

# 2. Assets (specific paths like /{template_id}/visuals/...)
router.include_router(assets_router)

# 3. Sessions (specific paths like /sessions)
router.include_router(sessions_router)

# 4. Editor (specific paths like /{template_id}/editor/...)
router.include_router(editor_router)
router.include_router(editor_special_actions_router)
router.include_router(editor_npc_combat_router)
router.include_router(editor_entity_transfer_router)

# 5. Cloning (specific paths like /{template_id}/duplicate and /{template_id}/copy)
router.include_router(cloning_router)

# 6. Templates (parameterized paths like /{template_id})
router.include_router(templates_router)

# 7. Gameplay (parameterized paths like /{game_id}/chat)
router.include_router(gameplay_router)
router.include_router(agent_router)
