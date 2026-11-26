"""Slide images of cut-scenes: default prompt and the image style that applies.

A cut-scene may override the adventure's image style (``image_style``: a catalog id or name,
or a free description), e.g. a comic or watercolor cut-scene in a painterly fantasy adventure.
Used by the editor (``editing/cutscene_image_routes.py``) and the manifest apply
(``manifest_apply/cutscene_media.py``).
"""

from __future__ import annotations

from typing import Any, Optional

from backend.core.style_catalog import resolve_style_instruction

MAX_PROMPT_TEXT = 600


def style_instruction(
    image_style: Optional[str], adventure_styles: Any, catalog: Optional[list[dict[str, Any]]]
) -> str:
    """The cut-scene's own style when set, else the adventure's style."""
    override = str(image_style or "").strip()
    styles = [override] if override else adventure_styles
    return resolve_style_instruction(styles, catalog or [])


def default_slide_prompt(adventure_title: str, cutscene_title: str, slide_text: str) -> str:
    """A prompt for one slide image from the slide's text."""
    text = " ".join(str(slide_text or "").split())[:MAX_PROMPT_TEXT]
    title = str(cutscene_title or "").strip()
    frame = (
        f"Cinematic story illustration for the cut-scene '{title}'"
        if title
        else ("Cinematic story illustration")
    )
    story = f" of the adventure '{adventure_title}'" if adventure_title else ""
    scene = f": {text}" if text else "."
    return f"{frame}{story}{scene} Wide 16:9 composition, no text, no lettering, no captions."
