from fastapi import APIRouter
from backend.api.routes.adventures.templates import router as templates_router
from backend.api.routes.adventures.sessions import router as sessions_router
from backend.api.routes.adventures.gameplay import router as gameplay_router
from backend.api.routes.adventures.assets import router as assets_router
from backend.api.routes.adventures.editor import router as editor_router

router = APIRouter(prefix="/adventures", redirect_slashes=False)

# Include sub-routers in order of specificity.
# Routes with static paths (like /sessions) must come BEFORE 
# routers that have greedy parameterized paths (like /{template_id}).
router.include_router(assets_router)
router.include_router(sessions_router)
router.include_router(editor_router)
router.include_router(templates_router)
router.include_router(gameplay_router)
