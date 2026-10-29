from backend.engine.media.image_prompt_context import (
    MAX_APPEARANCE_LENGTH,
    MAX_PLOT_CONTEXT_LENGTH,
    build_npc_image_prompt,
    build_object_image_prompt,
    build_protagonist_image_prompt,
    build_scene_image_prompt,
    clean_appearance,
    protagonist_context,
    scene_context,
)


def test_scene_prompt_includes_decorations_only():
    # Act
    prompt = build_scene_image_prompt(
        "Library", "Dusty shelves.", decorative_objects=["candelabra", "globe"]
    )

    # Assert
    assert prompt.startswith("Background scene: Library. Dusty shelves. ")
    assert "candelabra, globe" in prompt
    assert "Characters present" not in prompt
    assert "3:2 aspect ratio" in prompt


def test_scene_prompt_without_context_keeps_base_template():
    # Act
    prompt = build_scene_image_prompt("Cave", "Dark and damp.")

    # Assert
    assert prompt.startswith("Background scene: Cave. Dark and damp. 3:2 aspect ratio")


def test_scene_context_skips_blank_decorations():
    # Act
    context = scene_context(["  ", "lantern"])

    # Assert
    assert context == "Visible details in the environment: lantern."
    assert scene_context(None) == ""


def test_protagonist_prompt_includes_clipped_plot():
    # Arrange
    plot = "A steampunk heist in Victorian London. " * 100

    # Act
    prompt = build_protagonist_image_prompt("Ada", "Thief", "Wiry and quick.", plot=plot)
    context = protagonist_context(plot)

    # Assert
    assert prompt.startswith("Portrait of character Ada, Thief. Wiry and quick. Adventure setting")
    assert "steampunk heist" in prompt
    assert context.endswith("...")
    assert len(context) < MAX_PLOT_CONTEXT_LENGTH + 200


def test_protagonist_prompt_without_plot_has_no_context():
    # Act
    prompt = build_protagonist_image_prompt("Ada", "Thief", "Wiry and quick.", plot="  ")

    # Assert
    assert "Adventure setting" not in prompt
    assert "Wiry and quick. Game attribute art style." in prompt


def test_clean_appearance_collapses_whitespace_and_clips():
    # Act
    cleaned = clean_appearance("  tall,\n  scarred   face " + "x" * 200)

    # Assert
    assert cleaned is not None
    assert cleaned.startswith("tall, scarred face x")
    assert len(cleaned) == MAX_APPEARANCE_LENGTH
    assert clean_appearance("   ") is None
    assert clean_appearance(None) is None


def test_npc_and_object_prompts_include_appearance():
    # Act
    npc_prompt = build_npc_image_prompt("Guard", "A bored guard.", "burly, chainmail, red cape")
    object_prompt = build_object_image_prompt("Key", "A key.", "brass, ornate bow")
    plain_prompt = build_npc_image_prompt("Guard", "A bored guard.")

    # Assert
    assert "A bored guard. Visual keywords: burly, chainmail, red cape. Game" in npc_prompt
    assert "A key. Visual keywords: brass, ornate bow. Centered" in object_prompt
    assert "Visual keywords" not in plain_prompt


def test_protagonist_prompt_puts_appearance_before_plot():
    # Act
    prompt = build_protagonist_image_prompt(
        "Ada", "Thief", "Wiry.", plot="Heist in London.", appearance="red hair, goggles"
    )

    # Assert
    assert prompt.index("Visual keywords: red hair, goggles.") < prompt.index("Adventure setting")
