from typing import Any, Optional

from backend.core.catalog_defaults import DEFAULT_IMAGE_STYLES, DEFAULT_TONES

MAX_CUSTOM_LABEL_LEN = 40


def default_image_styles_catalog() -> list[dict[str, Any]]:
    """Return a copy of default image styles to avoid accidental mutation."""
    return [dict(item) for item in DEFAULT_IMAGE_STYLES]


def default_tones_catalog() -> list[dict[str, Any]]:
    """Return a copy of default tones to avoid accidental mutation."""
    return [dict(item) for item in DEFAULT_TONES]


def match_catalog_entry(
    raw: str,
    catalogs: tuple[list[dict[str, Optional[Any]]], ...],
) -> Optional[dict[str, Any]]:
    """Find a catalog item by id or name (case-insensitive)."""
    needle = raw.strip().lower()
    if not needle:
        return None
    for catalog in catalogs:
        for entry in catalog or []:
            entry_id = str(entry.get("id") or "").strip().lower()
            entry_name = str(entry.get("name") or "").strip().lower()
            if needle in (entry_id, entry_name):
                return dict(entry)
    return None


def _custom_catalog_entry(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    name = (
        cleaned
        if len(cleaned) <= MAX_CUSTOM_LABEL_LEN
        else f"{cleaned[: MAX_CUSTOM_LABEL_LEN - 3].rstrip()}..."
    )
    return {
        "id": cleaned,
        "name": name,
        "description": cleaned,
        "instruction": cleaned,
    }


def build_blueprint_image_styles(
    raw: str,
    user_catalog: Optional[list[dict[str, Optional[Any]]]] = None,
) -> list[dict[str, Any]]:
    """Turn a blueprint ``image_style``/``style`` value into ``selected_image_styles``."""
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("expected an image style name or description")
    matched = match_catalog_entry(cleaned, (user_catalog or [], default_image_styles_catalog()))
    return [matched] if matched else [_custom_catalog_entry(cleaned)]


def build_blueprint_tone(
    raw: str,
    user_catalog: Optional[list[dict[str, Optional[Any]]]] = None,
) -> dict[str, Any]:
    """Turn a blueprint ``tone`` value into ``selected_tone``."""
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("expected a narrative tone name or description")
    matched = match_catalog_entry(cleaned, (user_catalog or [], default_tones_catalog()))
    return matched if matched else _custom_catalog_entry(cleaned)


def resolve_style_instruction(
    selected_image_styles: Optional[list[Any]],
    user_catalog: list[dict[str, Optional[Any]]],
) -> str:
    """Resolve style instruction from selected style, then user catalog, then default catalog."""
    if not selected_image_styles:
        return ""

    first_style = selected_image_styles[0]
    style_id = None
    direct_instruction = ""

    if isinstance(first_style, dict):
        direct_instruction = (first_style.get("instruction") or "").strip()
        style_id = first_style.get("id") or first_style.get("name")
        if direct_instruction and direct_instruction != style_id:
            return direct_instruction
    elif isinstance(first_style, str):
        style_id = first_style

    if not style_id:
        return direct_instruction

    matched = match_catalog_entry(
        str(style_id), (user_catalog or [], default_image_styles_catalog())
    )
    if matched:
        return str(matched.get("instruction") or "").strip()

    return direct_instruction or str(style_id)


def resolve_tone_instruction(
    selected_tone: Optional[str | dict[str, Any]],
    user_catalog: list[dict[str, Optional[Any]]],
) -> str:
    """Resolve tone instruction from selected tone, then user catalog, then default catalog."""
    if not selected_tone:
        return ""

    tone_id = None
    direct_instruction = ""

    if isinstance(selected_tone, dict):
        direct_instruction = (selected_tone.get("instruction") or "").strip()
        tone_id = selected_tone.get("id") or selected_tone.get("name")
        if direct_instruction and direct_instruction != tone_id:
            return direct_instruction
    elif isinstance(selected_tone, str):
        tone_id = selected_tone

    if not tone_id:
        return direct_instruction

    matched = match_catalog_entry(str(tone_id), (user_catalog or [], default_tones_catalog()))
    if matched:
        return str(matched.get("instruction") or "").strip()

    return direct_instruction or str(tone_id)
