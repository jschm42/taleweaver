from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import logging
from sqlalchemy import select
from backend.core.database import engine, apply_sqlite_compat_migrations
from backend.models.base import Base
from backend.core.config import settings

# Configure logging based on .env settings
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(levelname)s:     %(name)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Import all models so SQLAlchemy metadata registers them before create_all
import backend.models.user
import backend.models.avatar
import backend.models.adventure_template
import backend.models.game_session
import backend.models.session_state
import backend.models.chat
import backend.models.world_map

from backend.api.routes import config_api, adventures, avatars, data, characters, map_api, auth_api, users_api, tts_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown lifecycle."""
    # Startup: create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await apply_sqlite_compat_migrations()

    # Auto-import adventures
    from backend.core.database import AsyncSessionLocal
    from backend.engine.adventure_importer import AdventureTemplateImporter
    from backend.models.adventure_template import AdventureTemplate
    
    async with AsyncSessionLocal() as db:
        # Check if we have any admins in the database
        result = await db.execute(select(backend.models.user.User).where(backend.models.user.User.role == "admin").limit(1))
        has_admin = result.scalars().first() is not None

        if not has_admin:
            logger.info("No admin user found. Please use the setup flow or create a root user.")
            
        # We no longer auto-import adventures here. 
        # Default adventures are imported per-user on their first login.
        # Manual drops in DATA_DIR/imports/adventures are still processed for convenience.
        await AdventureTemplateImporter.import_from_directory(
            db,
            os.path.join(settings.DATA_DIR, "imports", "adventures"),
            delete_after=True,
        )

    yield


app = FastAPI(
    title="TaleWeaver",
    description="Backend API for the TaleWeaver text-adventure engine.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Allow the Vue.js frontend (dev server) to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.FRONTEND_PORT}",
        f"http://127.0.0.1:{settings.FRONTEND_PORT}"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_api.router, prefix="/api")
app.include_router(adventures.router, prefix="/api")
app.include_router(avatars.router, prefix="/api")
app.include_router(characters.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(map_api.router, prefix="/api")
app.include_router(auth_api.router, prefix="/api")
app.include_router(users_api.router, prefix="/api")
app.include_router(tts_api.router, prefix="/api")



# Ensure storage directories exist
os.makedirs(os.path.join(settings.DATA_DIR, "characters"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "adventures"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "adventures", "library"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "adventures", "sessions"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "users"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "audio"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "imports", "adventures"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "presets", "adventures"), exist_ok=True)
os.makedirs("adventures", exist_ok=True)

# Static data and assets
app.mount("/data", StaticFiles(directory=settings.DATA_DIR), name="data")

# Serve frontend if available (Production/Docker mode)
if os.path.exists("frontend_dist"):
    # First, define a route for assets that checks both backend and frontend folders
    @app.get("/assets/{path:path}")
    async def serve_assets(path: str):
        # 1. Try backend static assets (like catalog images)
        backend_asset = os.path.join("backend/static/assets", path)
        if os.path.isfile(backend_asset):
            return FileResponse(backend_asset)
        
        # 2. Try frontend built assets (JS, CSS)
        frontend_asset = os.path.join("frontend_dist/assets", path)
        if os.path.isfile(frontend_asset):
            return FileResponse(frontend_asset)
            
        return {"error": "Asset not found"}

    # Catch-all for SPA client-side routing
    @app.get("/{catchall:path}")
    async def serve_spa(catchall: str):
        # Check if the specific file exists in frontend_dist (e.g. favicon.ico)
        full_path = os.path.join("frontend_dist", catchall)
        if catchall and os.path.isfile(full_path):
            return FileResponse(full_path)
            
        # Otherwise serve the index.html for the SPA
        return FileResponse("frontend_dist/index.html")
else:
    # Standard mount for development
    app.mount("/assets", StaticFiles(directory="backend/static/assets"), name="assets")

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Returns a simple liveness signal for load-balancer health checks."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # On Windows, reload mode spawns a watchdog process and can produce noisy
    # KeyboardInterrupt traces on shutdown. Keep reload opt-in for local dev.
    reload_enabled = os.getenv("TALEWEAVER_RELOAD", "0").lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.BACKEND_PORT,
        reload=reload_enabled,
    )
