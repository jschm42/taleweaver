from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.core.database import engine, Base
from backend.engine.heartbeat import heartbeat_daemon

# Import all models so metadata knows them
import backend.models.user
import backend.models.avatar
import backend.models.adventure
import backend.models.game_state
import backend.models.chat

from backend.api.routes import config_api, adventures, ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    heartbeat_daemon.start()
    
    yield
    # Shutdown actions
    await heartbeat_daemon.stop()

app = FastAPI(
    title="TaleWeaver",
    description="Backend API for TaleWeaver",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(config_api.router, prefix="/api")
app.include_router(adventures.router, prefix="/api")
app.include_router(ws.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
