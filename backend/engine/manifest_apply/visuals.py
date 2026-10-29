"""Image selection and generation shared by every entity kind."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Optional

from backend.engine.manifest_apply.assets import is_usable_image_url, resolve_source_asset_image
from backend.engine.manifest_apply.context import ApplyContext, generator_module

logger = logging.getLogger(__name__)

ImageFactory = Callable[[], Awaitable[Optional[str]]]


async def publish_status(ctx: ApplyContext, message: str) -> None:
    await generator_module()._publish_generation_status_with_callback(
        ctx.db, ctx.adventure, message, status_callback=ctx.status_callback
    )


async def pick_existing_image(
    ctx: ApplyContext,
    *,
    kind: str,
    label: str,
    source_asset_id: Optional[str],
    before: list[Optional[str]],
    after: list[Optional[str]],
) -> Optional[str]:
    """Returns the first usable image: ``before`` candidates, a reused source asset, then ``after``."""
    reused = resolve_source_asset_image(ctx.source_assets, ctx.template_id, kind, source_asset_id)
    url = next((c for c in [*before, reused, *after] if c), None)
    if not is_usable_image_url(url):
        return None
    if url and url == reused:
        await generator_module()._log_reused_asset(ctx.db, ctx.adventure, label, url)
    return url


async def generate_image(
    ctx: ApplyContext,
    *,
    status: str,
    prompt: str,
    factory: ImageFactory,
    timeout: float,
    failure_label: str,
) -> Optional[str]:
    """Publishes progress, calls the image model and keeps the success/moderation counters."""
    wg = generator_module()
    await publish_status(ctx, status)
    ctx.image_counters["attempts"] += 1
    try:
        image_url = await asyncio.wait_for(factory(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("%s timed out after %ss", failure_label, timeout)
        return None
    except Exception as exc:
        if wg.is_image_moderation_error(exc):
            ctx.image_counters["moderation"] += 1
        logger.warning("%s failed: %s", failure_label, exc)
        return None
    if image_url:
        ctx.image_counters["successes"] += 1
        await wg._log_image_generation(ctx.db, ctx.adventure, prompt, image_url)
    return image_url


async def placeholder_image(
    ctx: ApplyContext, entity_id: str, category: str, subdir: str = ""
) -> Optional[str]:
    from backend.engine.media.media_engine import MediaEngine

    target_dir = os.path.join(ctx.library_dir, subdir) if subdir else ctx.library_dir
    return await MediaEngine.generate_placeholder(
        ctx.template_id, entity_id, target_dir, category=category
    )


def t2i_config(ctx: ApplyContext) -> tuple[dict, dict]:
    """Returns the (user_config, api_keys) pair every MediaEngine call expects."""
    user = ctx.user
    return {"t2i_settings": user.t2i_settings if user else None}, dict(
        (user.encrypted_api_keys if user else None) or {}
    )


def uses_advanced_model(ctx: ApplyContext, setting: str, default: str) -> bool:
    t2i = (ctx.user.t2i_settings if ctx.user else None) or {}
    return t2i.get(setting, default) == "advanced"
