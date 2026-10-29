"""Context enrichment for image generation prompts.

Protagonist, NPC, item and cover prompts carry the optional ``appearance`` keywords
(max 100 chars). Scene images are described by their description and decorative
objects only; protagonist portraits borrow setting and mood from the plot.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Optional

from backend.core import prompts

MAX_APPEARANCE_LENGTH = 100
MAX_SCENE_DECORATIONS = 7
MAX_PLOT_CONTEXT_LENGTH = 1000


def _clip(text: Any, limit: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def clean_appearance(value: Any) -> Optional[str]:
    """Normalizes appearance keywords to a single line of at most 100 characters (None if empty)."""
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())[:MAX_APPEARANCE_LENGTH].strip()
    return text or None


def appearance_context(appearance: Any) -> str:
    keywords = clean_appearance(appearance)
    if not keywords:
        return ""
    return prompts.IMAGE_APPEARANCE_TEMPLATE.format(appearance=keywords.rstrip("."))


def scene_context(decorative_objects: Optional[Iterable[Any]] = None) -> str:
    """Returns visual details for a scene prompt, or an empty string when there are none."""
    items = [_clip(d, 100) for d in decorative_objects or [] if isinstance(d, str) and d.strip()]
    if not items:
        return ""
    return prompts.SCENE_IMAGE_DECORATIONS_TEMPLATE.format(
        items=", ".join(items[:MAX_SCENE_DECORATIONS])
    )


def protagonist_context(plot: Optional[str], appearance: Any = None) -> str:
    """Returns appearance keywords plus the plot-derived setting hint for a protagonist portrait."""
    parts = [appearance_context(appearance)]
    excerpt = _clip(plot, MAX_PLOT_CONTEXT_LENGTH)
    if excerpt:
        parts.append(prompts.PROTAGONIST_IMAGE_PLOT_TEMPLATE.format(plot=excerpt))
    return " ".join(part for part in parts if part)


def with_context(context: str) -> str:
    """Formats an optional context sentence for the ``{context}`` template slot."""
    return f"{context} " if context else ""


def _sentence_body(text: Optional[str]) -> str:
    """Drops trailing periods because the templates add their own."""
    return (text or "").strip().rstrip(".").rstrip()


def build_scene_image_prompt(
    name: str,
    description: str,
    decorative_objects: Optional[Iterable[Any]] = None,
) -> str:
    return prompts.SCENE_IMAGE_PROMPT_TEMPLATE.format(
        name=name,
        description=_sentence_body(description),
        context=with_context(scene_context(decorative_objects)),
    )


def build_protagonist_image_prompt(
    name: str,
    role: str,
    description: str,
    plot: Optional[str] = None,
    appearance: Any = None,
) -> str:
    return prompts.PROTAGONIST_IMAGE_PROMPT_TEMPLATE.format(
        name=name,
        role=role,
        description=_sentence_body(description),
        context=with_context(protagonist_context(plot, appearance)),
    )


def build_npc_image_prompt(name: str, description: str, appearance: Any = None) -> str:
    return prompts.NPC_IMAGE_PROMPT_TEMPLATE.format(
        name=name,
        description=_sentence_body(description),
        context=with_context(appearance_context(appearance)),
    )


def build_object_image_prompt(name: str, description: str, appearance: Any = None) -> str:
    return prompts.OBJECT_IMAGE_PROMPT_TEMPLATE.format(
        name=name,
        description=_sentence_body(description),
        context=with_context(appearance_context(appearance)),
    )
