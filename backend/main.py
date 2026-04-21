from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.core.database import engine, apply_sqlite_compat_migrations
from backend.models.base import Base

# Import all models so SQLAlchemy metadata registers them before create_all
import backend.models.user
import backend.models.avatar
import backend.models.adventure
import backend.models.game_state
import backend.models.chat
import backend.models.world_map

from backend.api.routes import config_api, adventures, avatars, data, characters, map_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown lifecycle."""
    # Startup: create DB tables and launch background heartbeat
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await apply_sqlite_compat_migrations()

    yield


app = FastAPI(
    title="TaleWeaver",
    description="Backend API for the TaleWeaver text-adventure engine.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the Vue.js frontend (dev server on port 5173) to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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

from backend.core.config import settings

# Ensure storage directories exist
os.makedirs(os.path.join(settings.DATA_DIR, "characters"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "adventures"), exist_ok=True)
os.makedirs(os.path.join(settings.DATA_DIR, "logs"), exist_ok=True)

app.mount("/data", StaticFiles(directory=settings.DATA_DIR), name="data")
app.mount("/assets", StaticFiles(directory="backend/static/assets"), name="assets")
# Keep /uploads mount temporarily for backward compatibility if needed, 
# but the plan said rename folder and I'll update the URLs.
# app.mount("/uploads", StaticFiles(directory=settings.DATA_DIR), name="uploads")

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Returns a simple liveness signal for load-balancer health checks."""
    return {"status": "ok"}
