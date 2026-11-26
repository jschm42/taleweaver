"""Preview images of the admin style and tone catalogs: prompt and 2:3 provider options."""

from backend.core.style_catalog import default_image_styles_catalog, default_tones_catalog
from backend.engine.media.catalog_tile_image import (
    catalog_tile_model,
    catalog_tile_options,
    catalog_tile_prompt,
)


def test_style_preview_prompt_renders_the_style_instruction():
    prompt = catalog_tile_prompt(
        "styles", "Survival Realism", "Documentary look.", "35mm lens, mud"
    )

    assert "Survival Realism" in prompt
    assert "35mm lens, mud" in prompt
    assert "no text" in prompt


def test_style_preview_prompt_falls_back_to_the_description():
    prompt = catalog_tile_prompt("styles", "Chalk", "chalk on slate", None)

    assert "chalk on slate" in prompt


def test_tone_preview_prompt_uses_the_mood():
    prompt = catalog_tile_prompt("tones", "Horror", "Dread and pressure.", "ignored")

    assert "Dread and pressure." in prompt
    assert "ignored" not in prompt


def test_preview_options_request_a_2_3_portrait():
    options = catalog_tile_options({"simple_model": "m"}, "openai")

    assert options["aspect_ratio"] == "2:3"
    assert "width" not in options


def test_local_preview_options_get_portrait_dimensions():
    options = catalog_tile_options({"simple_min_long_edge": 1200}, "comfyui")

    assert options["height"] > options["width"]


def test_default_catalogs_have_unique_ids_and_full_entries():
    for catalog in (default_image_styles_catalog(), default_tones_catalog()):
        ids = [item["id"] for item in catalog]
        assert len(ids) == len(set(ids))
        for item in catalog:
            assert item["name"] and item["description"] and item["instruction"]


def test_default_styles_include_the_survival_styles():
    ids = {item["id"] for item in default_image_styles_catalog()}

    assert {"survival-science-fiction", "survival-rpg", "survival-realism"} <= ids


def test_tile_model_follows_the_chosen_quality():
    t2i = {
        "simple_model_provider": "openai",
        "simple_model": "lq",
        "advanced_model_provider": "OpenRouter",
        "advanced_model": "hq",
    }

    assert catalog_tile_model(t2i, "simple") == ("openai", "lq")
    assert catalog_tile_model(t2i, "advanced") == ("openrouter", "hq")


def test_hq_options_use_the_advanced_profile():
    options = catalog_tile_options({"advanced_steps": 40}, "openai", "advanced")

    assert options["comfyui_profile"] == "advanced"
    assert options["steps"] == 40
