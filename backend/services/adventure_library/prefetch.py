"""Optional first-boot prefetch of the adventure library (spec section 8.5).

Enabled with ``TALEWEAVER_PREFETCH_ADVENTURES=1`` for Docker/CI images that should come
up with the published adventures already installed. It only runs on a first boot (no
``AdventureTemplate`` row yet) and installs into the first admin's library, because a
download job always needs an owner and a prefetched bundle is meant to be shared.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

import backend.core.database as core_database
from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.services.adventure_library.catalog import CatalogService
from backend.services.adventure_library.downloader import DownloadError
from backend.services.adventure_library.jobs import JobError, JobManager, job_manager
from backend.services.adventure_library.models import CatalogEntry, is_version_at_least

logger = logging.getLogger(__name__)


async def _first_admin_id() -> str | None:
    """Return the prefetch owner, or ``None`` when this is not a first boot / no admin."""
    async with core_database.AsyncSessionLocal() as db:
        has_template = await db.scalar(select(AdventureTemplate.id).limit(1))
        if has_template is not None:
            logger.info("Adventure prefetch skipped: adventures are already installed.")
            return None
        admin_id = await db.scalar(
            select(User.id).where(User.role == "admin").order_by(User.created_at).limit(1)
        )
    if admin_id is None:
        logger.warning("Adventure prefetch skipped: no admin user exists yet.")
    return admin_id


async def _start_job(manager: JobManager, entry: CatalogEntry, owner_id: str) -> bool:
    """Start one download; a failure skips this entry instead of the whole prefetch."""
    try:
        job = await manager.start(entry, owner_id)
    except (JobError, DownloadError) as exc:
        logger.warning("Adventure prefetch could not start %s: %s", entry.slug, exc)
        return False
    logger.info("Adventure prefetch started %s %s (job %s)", entry.slug, entry.version, job.job_id)
    return True


async def prefetch_adventures(
    catalog_service: CatalogService | None = None,
    manager: JobManager | None = None,
) -> int:
    """Start a download job for every compatible catalog entry; return how many started.

    Never raises: the prefetch is a convenience and must not affect the server.
    """
    if not settings.TALEWEAVER_PREFETCH_ADVENTURES:
        return 0
    try:
        owner_id = await _first_admin_id()
        if owner_id is None:
            return 0
        catalog = await (catalog_service or CatalogService()).get_catalog()
        compatible = [
            entry
            for entry in catalog.adventures
            if is_version_at_least(settings.APP_VERSION, entry.min_app_version)
        ]
        started = 0
        for entry in compatible:
            started += await _start_job(manager or job_manager, entry, owner_id)
    except Exception:
        logger.exception("Adventure prefetch failed")
        return 0
    logger.info(
        "Adventure prefetch started %d of %d catalog entries (%d compatible).",
        started,
        len(catalog.adventures),
        len(compatible),
    )
    return started


def schedule_prefetch() -> asyncio.Task[int] | None:
    """Run :func:`prefetch_adventures` in the background; ``None`` when disabled.

    The caller keeps the returned task so it is not garbage-collected mid-run.
    """
    if not settings.TALEWEAVER_PREFETCH_ADVENTURES:
        return None
    return asyncio.create_task(prefetch_adventures(), name="adventure-prefetch")
