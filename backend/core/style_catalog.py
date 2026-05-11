from typing import Any, Optional, Union

from backend.core.catalog_defaults import DEFAULT_IMAGE_STYLES


def default_image_styles_catalog() -> list[dict[str, Any]]:
    """Return a copy of default image styles to avoid accidental mutation."""
    return [dict(item) for item in DEFAULT_IMAGE_STYLES]


def resolve_style_instruction(
    selected_image_styles: Optional[list[Any]],
    user_catalog: list[dict[str, Optional[Any]]],
) -> str:
    """Resolve style instruction from selected style, then user catalog, then default catalog."""
    if not selected_image_styles:
        return ""

    first_style = selected_image_styles[0]
    style_id = None

    if isinstance(first_style, dict):
        direct_instruction = (first_style.get("instruction") or "").strip()
        if direct_instruction:
            return direct_instruction
        style_id = first_style.get("id") or first_style.get("name")
    elif isinstance(first_style, str):
        style_id = first_style

    if not style_id:
        return ""

    for catalog in (user_catalog or [], default_image_styles_catalog()):
        for entry in catalog:
            if entry.get("id") == style_id or entry.get("name") == style_id:
                return (entry.get("instruction") or "").strip()

    return ""

