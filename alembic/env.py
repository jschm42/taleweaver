from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.core.config import settings
from backend.models.base import Base

# Import all models so metadata is fully registered for autogenerate.
import backend.models.user  # noqa: F401
import backend.models.avatar  # noqa: F401
import backend.models.character  # noqa: F401
import backend.models.adventure  # noqa: F401
import backend.models.game_state  # noqa: F401
import backend.models.chat  # noqa: F401
import backend.models.world_entity  # noqa: F401
import backend.models.world_map  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_database_url(url: str) -> str:
    """Converts async SQLAlchemy URLs to sync URLs for Alembic operations."""
    return url.replace("+aiosqlite", "")


config.set_main_option("sqlalchemy.url", _sync_database_url(settings.DATABASE_URL))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
