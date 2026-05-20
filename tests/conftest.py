"""
Shared pytest fixtures for TaleWeaver backend tests.

Uses an in-memory SQLite database so tests are fully isolated and
never touch the production database. All LLM calls are mocked to
avoid API costs and network latency.
"""
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import backend.core.database as core_database
from backend.core.auth import create_access_token, get_password_hash
from backend.core.database import get_db
from backend.main import app
from backend.models.base import Base
from backend.models.user import User

# ---------------------------------------------------------------------------
# In-memory test database
# ---------------------------------------------------------------------------

from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    """FastAPI dependency override that yields a test DB session."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Creates all tables before each test and drops them afterwards."""
    original_session_local = core_database.AsyncSessionLocal
    core_database.AsyncSessionLocal = TestSessionLocal
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    core_database.AsyncSessionLocal = original_session_local


@pytest_asyncio.fixture
async def client():
    """
    Provides an AsyncClient wired to the FastAPI app with the test DB
    and the heartbeat daemon disabled (lifespan is skipped via transport).
    """
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Provides an authenticated client bound to a seeded test user."""
    username = "test_user"

    async with TestSessionLocal() as session:
        user = User(
            username=username,
            hashed_password=get_password_hash("test_password"),
            role="admin",
            llm_settings={
                "small_model": "llama3.2",
                "small_model_provider": "ollama",
                "complex_model": "qwen2.5",
                "complex_model_provider": "ollama",
                "generator_model": "qwen2.5",
                "generator_model_provider": "ollama",
                "preferred_provider": "ollama",
                "ollama_url": "http://localhost:11434",
            },
            t2i_settings={
                "simple_model": "sdxl",
                "simple_model_provider": "local",
                "advanced_model": "sdxl",
                "advanced_model_provider": "local",
            }
        )
        session.add(user)
        await session.commit()

    token = create_access_token({"sub": username})
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Yields a database session from the test engine."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
def _patch_external_generation_and_media(monkeypatch):
    """Autouse fixture to stub external LLM/world generation and media generation.

    Many tests assume generation happens in background; to keep tests deterministic
    when no local Ollama or image backend is running we stub the heavy calls.
    Individual tests may still monkeypatch these targets for custom behavior.
    """

    async def _fake_generate_world(*args, **kwargs):
        return None

    async def _fake_generate_entity_image(*args, **kwargs):
        return "/data/adventures/test/protagonist.png"

    async def _fake_generate_scene_image(*args, **kwargs):
        return "/data/adventures/test/scene.png"

    async def _fake_generate_adventure_cover(*args, **kwargs):
        return "/data/adventures/test/cover.png"

    # Patch both the engine class and the reference used by the templates/routes module.
    monkeypatch.setattr(
        "backend.engine.world_generator.WorldGenerator.generate_world",
        _fake_generate_world,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.api.routes.adventures.templates.WorldGenerator.generate_world",
        _fake_generate_world,
        raising=False,
    )

    monkeypatch.setattr(
        "backend.engine.media_engine.MediaEngine.generate_entity_image",
        _fake_generate_entity_image,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.engine.media_engine.MediaEngine.generate_scene_image",
        _fake_generate_scene_image,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.engine.media_engine.MediaEngine.generate_adventure_cover",
        _fake_generate_adventure_cover,
        raising=False,
    )

    yield
