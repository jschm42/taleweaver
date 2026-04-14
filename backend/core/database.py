import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Create the async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} # Needed for SQLite
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Dependency to get session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def apply_sqlite_compat_migrations() -> None:
    """
    Applies lightweight, idempotent schema fixes for local SQLite databases.

    SQLAlchemy `create_all()` does not alter existing tables. This helper adds
    columns introduced after initial schema creation so older local DB files
    continue to work without manual resets.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    async with engine.begin() as conn:
        # Ensure tables exist first
        await conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS adventures (id TEXT PRIMARY KEY)")
        await conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS game_states (id TEXT PRIMARY KEY)")

        adventure_cols_result = await conn.exec_driver_sql("PRAGMA table_info(adventures)")
        adventure_cols = {row[1] for row in adventure_cols_result.fetchall()}

        if "heartbeat_enabled" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN heartbeat_enabled BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added adventures.heartbeat_enabled")

        if "heartbeat_interval" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN heartbeat_interval INTEGER NOT NULL DEFAULT 10"
            )
            logger.info("SQLite migration: added adventures.heartbeat_interval")

        if "game_over_rules" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN game_over_rules TEXT"
            )
            logger.info("SQLite migration: added adventures.game_over_rules")

        game_state_cols_result = await conn.exec_driver_sql("PRAGMA table_info(game_states)")
        game_state_cols = {row[1] for row in game_state_cols_result.fetchall()}

        if "is_paused" not in game_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE game_states ADD COLUMN is_paused BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added game_states.is_paused")

        user_cols_result = await conn.exec_driver_sql("PRAGMA table_info(users)")
        user_cols = {row[1] for row in user_cols_result.fetchall()}
        if "llm_settings" not in user_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN llm_settings TEXT"
            )
            logger.info("SQLite migration: added users.llm_settings")

        if "t2i_settings" not in user_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN t2i_settings TEXT"
            )
            logger.info("SQLite migration: added users.t2i_settings")

        entity_cols_result = await conn.exec_driver_sql("PRAGMA table_info(world_entities)")
        entity_cols = {row[1] for row in entity_cols_result.fetchall()}
        if "image_url" not in entity_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE world_entities ADD COLUMN image_url TEXT"
            )
            logger.info("SQLite migration: added world_entities.image_url")

        # Async Generation Status
        if "is_ready" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN is_ready BOOLEAN NOT NULL DEFAULT 1"
            )
            logger.info("SQLite migration: added adventures.is_ready")
        
        if "creation_status" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN creation_status TEXT"
            )
            logger.info("SQLite migration: added adventures.creation_status")

        if "creation_error" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN creation_error TEXT"
            )
            logger.info("SQLite migration: added adventures.creation_error")

        if "generate_scene_images" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN generate_scene_images BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added adventures.generate_scene_images")

        if "generate_npc_images" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN generate_npc_images BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added adventures.generate_npc_images")

        if "generate_item_images" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN generate_item_images BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added adventures.generate_item_images")

        # Avatar link for cleanup
        avatar_cols_result = await conn.exec_driver_sql("PRAGMA table_info(avatars)")
        avatar_cols = {row[1] for row in avatar_cols_result.fetchall()}
        if "adventure_id" not in avatar_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE avatars ADD COLUMN adventure_id TEXT"
            )
            logger.info("SQLite migration: added avatars.adventure_id")

        if "role" not in avatar_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE avatars ADD COLUMN role TEXT"
            )
            logger.info("SQLite migration: added avatars.role")

        if "description" not in avatar_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE avatars ADD COLUMN description TEXT"
            )
            logger.info("SQLite migration: added avatars.description")

        if "profile_image" not in avatar_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE avatars ADD COLUMN profile_image TEXT"
            )
            logger.info("SQLite migration: added avatars.profile_image")
