"""Slide images of the cut-scenes a manifest brought (World-Builder, blueprint).

Drawn after the world is persisted when scene images are on: every slide without an image gets
one from its ``image_prompt`` (or its text), in the cut-scene's own ``image_style`` when set,
else the adventure's style. A failed image leaves the slide without one (it then shows on the
theme's veil) and counts as a failed image of the generation summary.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.engine.cutscenes.images import default_slide_prompt, style_instruction
from backend.engine.cutscenes.library import normalize_cutscenes
from backend.engine.manifest_apply.context import ApplyContext
from backend.engine.manifest_apply.visuals import publish_status, t2i_config

logger = logging.getLogger(__name__)


async def _draw(ctx: ApplyContext, cutscene: dict[str, Any], slide: dict[str, Any]) -> None:
    from backend.engine.media.media_engine import MediaEngine

    adventure = ctx.adventure
    title = str(getattr(adventure, "title", "") or "")
    prompt = slide["image_prompt"] or default_slide_prompt(title, cutscene["title"], slide["text"])
    catalog = getattr(ctx.user, "image_styles_catalog", None)
    style = style_instruction(
        cutscene["image_style"], getattr(adventure, "selected_image_styles", None), catalog
    )
    config, keys = t2i_config(ctx)
    ctx.image_counters["attempts"] += 1
    try:
        url = await MediaEngine.generate_scene_image(
            prompt, ctx.template_id, config, keys, style_instruction=style or None
        )
    except Exception as exc:  # one failed slide must not fail the generation
        logger.warning("Cut-scene image failed (%s): %s", cutscene["id"], exc)
        return
    if url:
        slide["image_url"] = url
        ctx.image_counters["successes"] += 1


async def draw_cutscene_images(ctx: ApplyContext) -> None:
    """Draws the missing slide images of all cut-scenes and stores them on the template."""
    adventure = ctx.adventure
    if not (ctx.gen_scenes and ctx.user and adventure):
        return
    cutscenes = normalize_cutscenes(adventure.cutscenes)
    missing = [(c, s) for c in cutscenes for s in c["slides"] if not s["image_url"]]
    if not missing:
        return
    for index, (cutscene, slide) in enumerate(missing, start=1):
        await publish_status(ctx, f"Drawing cut-scene images ({index}/{len(missing)})...")
        await _draw(ctx, cutscene, slide)
    adventure.cutscenes = cutscenes  # type: ignore[assignment]
    await ctx.db.commit()
