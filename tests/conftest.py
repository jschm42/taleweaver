"""
Shared pytest fixtures for TaleWeaver backend tests.

Uses an in-memory SQLite database so tests are fully isolated and
never touch the production database. All LLM calls are mocked to
avoid API costs and network latency.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.main import app
from backend.core.database import get_db
from backend.models.base import Base

# ---------------------------------------------------------------------------
# In-memory test database
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
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
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


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
