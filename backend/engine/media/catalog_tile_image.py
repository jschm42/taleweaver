"""Prompt, model and provider options for the preview images of the admin style and tone catalogs.

Previews are 2:3 portraits so the catalog tiles show the whole picture. A style preview
renders one neutral sample motif with the style's own instruction, so the tile shows what
the style produces; a tone preview shows a mood scene for the tone. The admin picks the
simple (LQ) or advanced (HQ) image model per generation.
"""

from typing import Any, Literal, Optional

CATALOG_TILE_ASPECT_RATIO = "2:3"

TileQuality = Literal["simple", "advanced"]

_STYLE_SAMPLE_MOTIF = (
    "a lone traveler standing at the edge of an abandoned settlement at dusk, "
    "a path leading into the distance"
)

CATALOG_PROMPT_SUGGESTION_SYSTEM_PROMPT = (
    "You write prompts for text-to-image models. The image is the preview tile of a catalog "
    "entry in a text adventure tool: an image style or a narrative tone. Write ONE prompt in "
    "English, 40 to 80 words, as comma-separated descriptive phrases. Describe one concrete, "
    "evocative scene that shows the entry at its best, then the medium, technique, palette, "
    "lighting and composition. Vertical 2:3 portrait composition, a single image. Never "
    "mention text, letters, logos, artist names or studio names. Answer with the prompt only."
)


def catalog_tile_prompt(
    catalog_type: str,
    name: str,
    description: Optional[str] = None,
    instruction: Optional[str] = None,
) -> str:
    """Builds the default preview prompt for a catalog tile."""
    if catalog_type == "styles":
        look = (instruction or "").strip() or (description or "").strip() or name
        return (
            f"Style sample for the image style '{name}': {_STYLE_SAMPLE_MOTIF}. "
            f"Rendered as: {look}. Vertical portrait composition, single image, no text."
        )
    mood = (description or "").strip() or name
    return (
        f"Atmospheric key art that conveys the narrative tone '{name}': {mood}. "
        "One evocative scene, vertical portrait composition, single image, no text."
    )


def catalog_prompt_suggestion_request(
    catalog_type: str,
    name: str,
    description: Optional[str] = None,
    instruction: Optional[str] = None,
) -> str:
    """User prompt for the LLM that writes a preview prompt for a catalog entry."""
    kind = "image style" if catalog_type == "styles" else "narrative tone"
    lines = [f"Catalog entry type: {kind}", f"Name: {name}"]
    if (description or "").strip():
        lines.append(f"Description: {description.strip()}")
    if (instruction or "").strip():
        label = (
            "Style instruction (must define the look)"
            if catalog_type == "styles"
            else "Tone instruction"
        )
        lines.append(f"{label}: {instruction.strip()}")
    return "\n".join(lines)


def catalog_tile_model(t2i: dict[str, Any], quality: TileQuality) -> tuple[str, Optional[str]]:
    """Image provider and model for the chosen quality."""
    prefix = "advanced" if quality == "advanced" else "simple"
    provider = (t2i.get(f"{prefix}_model_provider") or t2i.get("provider") or "openai").lower()
    return provider, t2i.get(f"{prefix}_model")


def catalog_tile_options(
    t2i: dict[str, Any], provider: str, quality: TileQuality = "simple"
) -> dict[str, Any]:
    """Provider options for a 2:3 preview with the simple or advanced model."""
    from backend.engine.media.image_generation_support import local_image_edge
    from backend.engine.media.media_engine import MediaEngine

    prefix = "advanced" if quality == "advanced" else "simple"
    options = dict(t2i)
    options["comfyui_profile"] = prefix
    options["aspect_ratio"] = CATALOG_TILE_ASPECT_RATIO
    for key in ("steps", "cfg_scale", "sampler_name", "scheduler"):
        options[key] = t2i.get(f"{prefix}_{key}")
    if provider in ("stable_diffusion", "ollama", "comfyui"):
        edge = local_image_edge(provider, options, t2i.get(f"{prefix}_min_long_edge"))
        width, height = MediaEngine._resolve_sd_dimensions("COVER", edge)
        options["width"] = width
        options["height"] = height
    return options
