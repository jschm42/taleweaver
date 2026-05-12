import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from backend.core.config import settings
from backend.core.database import engine
from backend.models.base import Base

# Configure logging based on .env settings
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(levelname)s:     %(name)s - %(message)s"
)

logger = logging.getLogger(__name__)


from typing import Optional
def _safe_join(base_dir: str, *parts: str) -> Optional[str]:
    """Safely join path parts and ensure result stays inside base_dir."""
    base_abs = os.path.abspath(base_dir)
    candidate = os.path.abspath(os.path.join(base_abs, *parts))
    try:
        if os.path.commonpath([candidate, base_abs]) != base_abs:
            return None
    except ValueError:
        return None
    return candidate

# Import all models so SQLAlchemy metadata registers them before create_all
import backend.models.adventure_template
import backend.models.avatar
import backend.models.chat
import backend.models.game_session
import backend.models.session_state
import backend.models.user
import backend.models.world_map
from backend.api.routes import (
    adventures,
    auth_api,
    avatars,
    characters,
    config_api,
    data,
    map_api,
    tts_api,
    users_api,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manages application startup and shutdown lifecycle."""
    # Startup: create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Note: We now use Alembic for all schema migrations. 
    # Manual apply_sqlite_compat_migrations() is deprecated and disabled to avoid conflicts.
    # await apply_sqlite_compat_migrations()

    # Auto-import adventures
    from backend.core.database import AsyncSessionLocal
    from backend.engine.adventure_importer import AdventureTemplateImporter
    
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

# Security: Allowed hosts (prevent Host Header Injection)
# In production, this should be set to the actual domain
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.localhost", "0.0.0.0", "test", "testserver"]
)

# Performance: Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Allow the Vue.js frontend (dev server) to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.FRONTEND_PORT}",
        f"http://127.0.0.1:{settings.FRONTEND_PORT}"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Security: HSTS (Strict-Transport-Security) - Disabled in dev/test to avoid 307 redirects
    # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: https:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com;"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

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
# Security: Do NOT mount the entire settings.DATA_DIR as it contains sensitive files like taleweaver.db
# Instead, mount only the public subdirectories.
public_data_dirs = ["characters", "adventures/library", "audio", "scratch/test_connection"]
for d in public_data_dirs:
    dir_path = os.path.join(settings.DATA_DIR, d)
    os.makedirs(dir_path, exist_ok=True)
    app.mount(f"/data/{d}", StaticFiles(directory=dir_path), name=f"data_{d.replace('/', '_')}")

# Serve frontend if available (Production/Docker mode)
if os.path.exists("frontend_dist"):
    # First, define a route for assets that checks both backend and frontend folders
    @app.get("/assets/{path:path}")
    async def serve_assets(path: str):
        # 1. Try backend static assets (like catalog images)
        backend_asset = _safe_join("backend/static/assets", path)
        if backend_asset and os.path.isfile(backend_asset):
            return FileResponse(backend_asset)
        
        # 2. Try frontend built assets (JS, CSS)
        frontend_asset = _safe_join("frontend_dist/assets", path)
        if frontend_asset and os.path.isfile(frontend_asset):
            return FileResponse(frontend_asset)
            
        return {"error": "Asset not found"}

    # Catch-all for SPA client-side routing
    @app.get("/{catchall:path}")
    async def serve_spa(catchall: str):
        # Check if the specific file exists in frontend_dist (e.g. favicon.ico)
        full_path = _safe_join("frontend_dist", catchall)
        if catchall and full_path and os.path.isfile(full_path):
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

@app.post("/api/ping")
async def ping():
    return {"message": "pong"}


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
