"""World generation schema for cut-scenes (slide shows at chapter starts or played by scripts).

The manifest applier reads these fields (``engine/cutscenes/library.py``, ``transfer.py``); the
schemas use ``extra="forbid"`` like every world schema, so every field the applier reads must
exist here. Slide images are drawn during the apply (``manifest_apply/cutscene_media.py``).
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from backend.engine.world.schema_base import WorldBaseSchema


class CutsceneSlideSchema(WorldBaseSchema):
    text: str = Field(
        ...,
        description="What the narrator says on this slide (1-3 sentences, max 400 characters).",
    )
    passages: list[str] = Field(
        default=[],
        description=(
            "Optional further passages shown one after another over the same picture "
            "(e.g. a dialogue exchange). Use [] for none."
        ),
    )
    image_prompt: str = Field(
        default="",
        description=(
            "English prompt for the slide image: subject, setting, light, composition. No text, "
            "lettering or captions in the image. Max 400 characters."
        ),
    )

    model_config = {"extra": "forbid"}


class CutsceneSchema(WorldBaseSchema):
    id: str = Field(..., description="Uppercase slug, e.g. INTRO_CRIMSON_DEBT.")
    title: str = Field(default="", description="Short title shown over the first slide.")
    image_style: str = Field(
        default="",
        description=(
            "Optional image style for these slides only (e.g. 'comic book', 'loose watercolor'); "
            "empty = the adventure's image style."
        ),
    )
    audio_track_id: Optional[str] = Field(
        default=None, description="Optional id of a track of `audio_tracks` to play during it."
    )
    slides: list[CutsceneSlideSchema] = Field(..., description="2-4 slides in order.")

    model_config = {"extra": "forbid"}
