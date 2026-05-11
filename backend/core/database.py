import logging

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Create the async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30} # Needed for SQLite
)


if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        """Reduce lock contention for concurrent background writes + status polling."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()

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
        table_rows = await conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {row[0] for row in table_rows.fetchall()}

        # Ensure tables exist first
        await conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS adventures (id TEXT PRIMARY KEY)")
        await conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS game_states (id TEXT PRIMARY KEY)")

        adventure_cols_result = await conn.exec_driver_sql("PRAGMA table_info(adventures)")
        adventure_cols = {row[1] for row in adventure_cols_result.fetchall()}
 
        # Cleanup legacy columns from 'adventures' table if they still exist
        if "heartbeat_enabled" in adventure_cols:
            try:
                await conn.exec_driver_sql("ALTER TABLE adventures DROP COLUMN heartbeat_enabled")
                logger.info("SQLite migration: dropped adventures.heartbeat_enabled")
            except Exception as e:
                logger.debug(f"Could not drop heartbeat_enabled from adventures: {e}")

        if "heartbeat_interval" in adventure_cols:
            try:
                await conn.exec_driver_sql("ALTER TABLE adventures DROP COLUMN heartbeat_interval")
                logger.info("SQLite migration: dropped adventures.heartbeat_interval")
            except Exception as e:
                logger.debug(f"Could not drop heartbeat_interval from adventures: {e}")

        if "game_over_rules" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN game_over_rules TEXT"
            )
            logger.info("SQLite migration: added adventures.game_over_rules")

        if "rule_enforcement_mode" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN rule_enforcement_mode TEXT NOT NULL DEFAULT 'strict'"
            )
            logger.info("SQLite migration: added adventures.rule_enforcement_mode")

        if "pacing_minutes" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN pacing_minutes INTEGER NOT NULL DEFAULT 5"
            )
            logger.info("SQLite migration: added adventures.pacing_minutes")

        if "clock_enabled" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN clock_enabled BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added adventures.clock_enabled")

        if "selected_image_styles" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN selected_image_styles TEXT"
            )
            logger.info("SQLite migration: added adventures.selected_image_styles")

        if "selected_tone" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN selected_tone TEXT"
            )
            logger.info("SQLite migration: added adventures.selected_tone")

        game_state_cols_result = await conn.exec_driver_sql("PRAGMA table_info(game_states)")
        game_state_cols = {row[1] for row in game_state_cols_result.fetchall()}

        if "is_debug_enabled" not in game_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE game_states ADD COLUMN is_debug_enabled BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added game_states.is_debug_enabled")

        user_cols_result = await conn.exec_driver_sql("PRAGMA table_info(users)")
        user_cols = {row[1] for row in user_cols_result.fetchall()}

        if "profile_image_url" not in user_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN profile_image_url TEXT"
            )
            logger.info("SQLite migration: added users.profile_image_url")

        if "bio" not in user_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN bio TEXT"
            )
            logger.info("SQLite migration: added users.bio")

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

        if "image_styles_catalog" not in user_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN image_styles_catalog TEXT"
            )
            logger.info("SQLite migration: added users.image_styles_catalog")

        if "tone_catalog" not in user_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN tone_catalog TEXT"
            )
            logger.info("SQLite migration: added users.tone_catalog")

        if "game_settings" not in user_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN game_settings TEXT"
            )
            logger.info("SQLite migration: added users.game_settings")

        entity_cols_result = await conn.exec_driver_sql("PRAGMA table_info(world_entities)")
        entity_cols = {row[1] for row in entity_cols_result.fetchall()}
        if "image_url" not in entity_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE world_entities ADD COLUMN image_url TEXT"
            )
            logger.info("SQLite migration: added world_entities.image_url")

        if "npc_type" not in entity_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE world_entities ADD COLUMN npc_type TEXT"
            )
            logger.info("SQLite migration: added world_entities.npc_type")

        if "movement_type" not in entity_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE world_entities ADD COLUMN movement_type TEXT"
            )
            logger.info("SQLite migration: added world_entities.movement_type")

        if "hp" not in entity_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE world_entities ADD COLUMN hp INTEGER"
            )
            logger.info("SQLite migration: added world_entities.hp")

        if "mana" not in entity_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE world_entities ADD COLUMN mana INTEGER"
            )
            logger.info("SQLite migration: added world_entities.mana")

        if "stamina" not in entity_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE world_entities ADD COLUMN stamina INTEGER"
            )
            logger.info("SQLite migration: added world_entities.stamina")

        scene_cols_result = await conn.exec_driver_sql("PRAGMA table_info(world_scenes)")
        scene_cols = {row[1] for row in scene_cols_result.fetchall()}
        if "image_url" not in scene_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE world_scenes ADD COLUMN image_url TEXT"
            )
            logger.info("SQLite migration: added world_scenes.image_url")

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

        if "quests" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN quests TEXT"
            )
            logger.info("SQLite migration: added adventures.quests")

        if "is_completed" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN is_completed BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added adventures.is_completed")

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

        if "awards" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN awards TEXT"
            )
            logger.info("SQLite migration: added adventures.awards")

        if "award_generation_enabled" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN award_generation_enabled BOOLEAN NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added adventures.award_generation_enabled")

        if "min_awards" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN min_awards INTEGER NOT NULL DEFAULT 3"
            )
            logger.info("SQLite migration: added adventures.min_awards")

        if "max_awards" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN max_awards INTEGER NOT NULL DEFAULT 8"
            )
            logger.info("SQLite migration: added adventures.max_awards")

        if "original_manifest" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN original_manifest TEXT"
            )
            logger.info("SQLite migration: added adventures.original_manifest")

        if "min_scenes" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN min_scenes INTEGER NOT NULL DEFAULT 1"
            )
            logger.info("SQLite migration: added adventures.min_scenes")

        if "max_scenes" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN max_scenes INTEGER NOT NULL DEFAULT 5"
            )
            logger.info("SQLite migration: added adventures.max_scenes")

        if "owner_id" not in adventure_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE adventures ADD COLUMN owner_id TEXT"
            )
            logger.info("SQLite migration: added adventures.owner_id")

        # game_sessions fields introduced after early local schemas
        if "game_sessions" in table_names:
            game_session_cols_result = await conn.exec_driver_sql("PRAGMA table_info(game_sessions)")
            game_session_cols = {row[1] for row in game_session_cols_result.fetchall()}

            if "adventure_title" not in game_session_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE game_sessions ADD COLUMN adventure_title TEXT"
                )
                logger.info("SQLite migration: added game_sessions.adventure_title")

            if "adventure_image_url" not in game_session_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE game_sessions ADD COLUMN adventure_image_url TEXT"
                )
                logger.info("SQLite migration: added game_sessions.adventure_image_url")

            if "status_note" not in game_session_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE game_sessions ADD COLUMN status_note TEXT"
                )
                logger.info("SQLite migration: added game_sessions.status_note")

        # New split model uses adventure_templates; backfill columns that older local DBs may miss.
        if "adventure_templates" in table_names:
            template_cols_result = await conn.exec_driver_sql("PRAGMA table_info(adventure_templates)")
            template_cols = {row[1] for row in template_cols_result.fetchall()}

            # Cleanup: Drop deprecated heartbeat columns from adventure_templates (using the new table name)
            if "heartbeat_enabled" in template_cols:
                try:
                    await conn.exec_driver_sql("ALTER TABLE adventure_templates DROP COLUMN heartbeat_enabled")
                    logger.info("SQLite migration: dropped adventure_templates.heartbeat_enabled")
                except Exception as e:
                    logger.warning(f"Could not drop heartbeat_enabled: {e}")

            if "heartbeat_interval" in template_cols:
                try:
                    await conn.exec_driver_sql("ALTER TABLE adventure_templates DROP COLUMN heartbeat_interval")
                    logger.info("SQLite migration: dropped adventure_templates.heartbeat_interval")
                except Exception as e:
                    logger.warning(f"Could not drop heartbeat_interval: {e}")

            if "quests" not in template_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE adventure_templates ADD COLUMN quests TEXT"
                )
                logger.info("SQLite migration: added adventure_templates.quests")

            if "is_completed" not in template_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE adventure_templates ADD COLUMN is_completed BOOLEAN NOT NULL DEFAULT 0"
                )
                logger.info("SQLite migration: added adventure_templates.is_completed")

            if "teaser" not in template_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE adventure_templates ADD COLUMN teaser TEXT"
                )
                logger.info("SQLite migration: added adventure_templates.teaser")

            if "intro_text" not in template_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE adventure_templates ADD COLUMN intro_text TEXT"
                )
                logger.info("SQLite migration: added adventure_templates.intro_text")

            if "is_adventure_generator" not in template_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE adventure_templates ADD COLUMN is_adventure_generator BOOLEAN NOT NULL DEFAULT 0"
                )
                logger.info("SQLite migration: added adventure_templates.is_adventure_generator")

            if "starting_timestamp" not in template_cols:
                await conn.exec_driver_sql(
                    "ALTER TABLE adventure_templates ADD COLUMN starting_timestamp INTEGER NOT NULL DEFAULT 0"
                )
                logger.info("SQLite migration: added adventure_templates.starting_timestamp")

        # Avatar link for cleanup
        avatar_cols_result = await conn.exec_driver_sql("PRAGMA table_info(avatars)")
        avatar_cols = {row[1] for row in avatar_cols_result.fetchall()}
        if "adventure_id" not in avatar_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE avatars ADD COLUMN adventure_id TEXT"
            )
            logger.info("SQLite migration: added avatars.adventure_id")

        # Cleanup: Drop is_paused from session_states
        session_state_cols_result = await conn.exec_driver_sql("PRAGMA table_info(session_states)")
        session_state_cols = {row[1] for row in session_state_cols_result.fetchall()}

        if "time_system" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN time_system TEXT NOT NULL DEFAULT 'calendar'"
            )
            logger.info("SQLite migration: added session_states.time_system")

        if "time_config" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN time_config TEXT"
            )
            logger.info("SQLite migration: added session_states.time_config")

        if "quests" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN quests TEXT"
            )
            logger.info("SQLite migration: added session_states.quests")

        if "start_datetime" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN start_datetime TEXT"
            )
            logger.info("SQLite migration: added session_states.start_datetime")

        if "plot" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN plot TEXT"
            )
            logger.info("SQLite migration: added session_states.plot")

        if "rules" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN rules TEXT"
            )
            logger.info("SQLite migration: added session_states.rules")

        if "walkthrough" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN walkthrough TEXT"
            )
            logger.info("SQLite migration: added session_states.walkthrough")

        if "completed_condition" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN completed_condition TEXT"
            )
            logger.info("SQLite migration: added session_states.completed_condition")

        if "gameover_condition" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN gameover_condition TEXT"
            )
            logger.info("SQLite migration: added session_states.gameover_condition")

        if "selected_image_styles" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN selected_image_styles TEXT"
            )
            logger.info("SQLite migration: added session_states.selected_image_styles")

        if "selected_tone" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN selected_tone TEXT"
            )
            logger.info("SQLite migration: added session_states.selected_tone")

        if "is_walkthrough_revealed" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN is_walkthrough_revealed BOOLEAN DEFAULT 0"
            )
            logger.info("SQLite migration: added session_states.is_walkthrough_revealed")

        if "allow_dynamic_items" not in session_state_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE session_states ADD COLUMN allow_dynamic_items BOOLEAN NOT NULL DEFAULT 1"
            )
            logger.info("SQLite migration: added session_states.allow_dynamic_items")

        if "is_paused" in session_state_cols:
            try:
                await conn.exec_driver_sql("ALTER TABLE session_states DROP COLUMN is_paused")
                logger.info("SQLite migration: dropped session_states.is_paused")
            except Exception as e:
                logger.warning(f"Could not drop is_paused: {e}")

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

        if "exp" not in avatar_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE avatars ADD COLUMN exp INTEGER NOT NULL DEFAULT 0"
            )
            logger.info("SQLite migration: added avatars.exp")

        # User Awards System
        user_cols_result = await conn.exec_driver_sql("PRAGMA table_info(users)")
        user_cols = {row[1] for row in user_cols_result.fetchall()}
        
        if "earned_awards" not in user_cols:
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN earned_awards TEXT"
            )
            logger.info("SQLite migration: added users.earned_awards")

