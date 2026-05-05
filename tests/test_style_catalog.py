from backend.core.style_catalog import default_image_styles_catalog, resolve_style_instruction


def test_resolve_style_instruction_uses_default_catalog_when_user_catalog_empty():
    selected = [{"id": "science-fiction"}]
    instruction = resolve_style_instruction(selected, user_catalog=[])
    assert "science fiction" in instruction


def test_resolve_style_instruction_prefers_embedded_instruction():
    selected = [{"id": "science-fiction", "instruction": "custom style prompt"}]
    instruction = resolve_style_instruction(selected, user_catalog=[])
    assert instruction == "custom style prompt"


def test_default_image_styles_catalog_is_copy():
    first = default_image_styles_catalog()
    second = default_image_styles_catalog()
    first[0]["id"] = "mutated"
    assert second[0]["id"] != "mutated"
