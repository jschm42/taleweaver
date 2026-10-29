"""Per-user import of the bundled default adventures (``adventures/default``).

Every user receives the bundles on first login. The ``has_imported_defaults`` flag is
claimed atomically, so parallel requests (several Gunicorn workers) import only once,
and it is released again when an import fails, so the next login retries instead of
leaving the user without the default adventures forever.
"""

import logging
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import PROJECT_ROOT
from backend.engine.adventures.adventure_importer import (
    AdventureConflictError,
    AdventureTemplateImporter,
)
from backend.models.user import User

logger = logging.getLogger(__name__)

# Anchored to the project root so the import does not depend on the working directory.
DEFAULT_ADVENTURES_DIR = PROJECT_ROOT / "adventures" / "default"
_ADVENTURE_SUFFIXES = (".adz", ".adv")


def default_adventure_files() -> list[Path]:
    """Return the bundled default adventure files, sorted by name."""
    if not DEFAULT_ADVENTURES_DIR.is_dir():
        return []
    return sorted(p for p in DEFAULT_ADVENTURES_DIR.iterdir() if p.suffix in _ADVENTURE_SUFFIXES)


async def _import_one(db: AsyncSession, path: Path, owner_id: str, overwrite: bool) -> bool:
    """Import one bundle; True when the adventure is present afterwards."""
    try:
        imported = await AdventureTemplateImporter.import_file(
            db, str(path), owner_id=owner_id, allow_session=False, overwrite=overwrite
        )
    except AdventureConflictError:
        logger.info("Default adventure '%s' already present; skipping.", path.name)
        return True
    except Exception:
        logger.exception("Default adventure import crashed for '%s'.", path.name)
        await db.rollback()
        return False
    if not imported:
        logger.error("Default adventure '%s' could not be imported.", path.name)
    return imported


async def import_default_adventures(
    db: AsyncSession, owner_id: str, overwrite: bool = False
) -> bool:
    """Import every bundled default adventure; True when all of them are present."""
    files = default_adventure_files()
    if not files:
        logger.error("No default adventures found in %s.", DEFAULT_ADVENTURES_DIR)
        return False
    results = [await _import_one(db, path, owner_id, overwrite) for path in files]
    return all(results)


async def _set_flag(db: AsyncSession, user_id: str, value: bool) -> bool:
    """Flip ``has_imported_defaults``; True when this call changed it."""
    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.has_imported_defaults.is_(not value))
        .values(has_imported_defaults=value)
    )
    await db.commit()
    return result.rowcount == 1


async def ensure_default_adventures(db: AsyncSession, user: User) -> bool:
    """Import the default adventures once per user; True when this call imported them."""
    if user.has_imported_defaults:
        return False
    if not await _set_flag(db, user.id, True):
        return False
    logger.info("First login for user '%s'. Importing default adventures...", user.username)
    if await import_default_adventures(db, user.id):
        return True
    await _set_flag(db, user.id, False)
    return False
