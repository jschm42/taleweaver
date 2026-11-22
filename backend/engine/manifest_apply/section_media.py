"""Images of a generated region: drawn while its scenes, characters and items are persisted.

The Region Builder's media options switch the ``ApplyContext`` image flags of the merge, in
the adventure's image style. When image generation is not set up the region is still built,
without images, and the reason becomes a generation note; image failures and safety blocks
become notes too. Spec: docs/specs/region_builder.md (7.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.style_catalog import resolve_style_instruction
from backend.engine.manifest_apply.context import ApplyContext, generator_module


@dataclass
class RegionMedia:
    scenes: bool = False
    npcs: bool = False
    items: bool = False

    @property
    def any(self) -> bool:
        return self.scenes or self.npcs or self.items

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> RegionMedia:
        return cls(
            scenes=bool(options.get("generate_scene_images")),
            npcs=bool(options.get("generate_npc_images")),
            items=bool(options.get("generate_item_images")),
        )


def enable_images(ctx: ApplyContext, media: RegionMedia) -> list[str]:
    """Sets the image flags of ``ctx``; returns a note when images have to be skipped."""
    if not media.any or ctx.user is None:
        return []
    try:
        generator_module()._validate_t2i_prerequisites(
            ctx.user,
            need_scene_images=media.scenes,
            need_npc_images=media.npcs,
            need_item_images=media.items,
            need_protagonist_image=False,
        )
    except ValueError as exc:  # also PersonalKeyRequiredError
        return [f"Images skipped: {exc}"]
    ctx.gen_scenes, ctx.gen_npc, ctx.gen_items = media.scenes, media.npcs, media.items
    styles = getattr(ctx.adventure, "selected_image_styles", None)
    ctx.style_instruction = resolve_style_instruction(styles, ctx.user.image_styles_catalog)
    return []


def image_notes(ctx: ApplyContext) -> list[str]:
    """Notes about images that were blocked or failed (placeholders were used)."""
    counters = ctx.image_counters
    notes: list[str] = []
    if counters["moderation"]:
        notes.append(
            f"{counters['moderation']} image(s) were blocked by safety filters; regenerate them "
            "in the editor with adjusted descriptions."
        )
    failed = counters["attempts"] - counters["successes"] - counters["moderation"]
    if ctx.any_image_generation and failed > 0:
        notes.append(f"{failed} image(s) could not be generated; placeholders were used.")
    return notes
