"""Tests for tw.image / tw.media (in-game image generation) in the scripting sandbox."""

from types import SimpleNamespace

import pytest

from backend.api.routes.adventures import script_image
from backend.api.routes.adventures.script_image import _tier_options, make_script_image_generator
from backend.engine.scripting import GameContext, ScriptRunner
from backend.engine.scripting.image_proxy import (
    MAX_CAPTION_CHARS,
    MAX_IMAGES_PER_CONTEXT,
    MAX_PROMPT_CHARS,
    ImageProxy,
    MediaProxy,
    image_markdown,
    normalize_model_tier,
)
from backend.engine.scripting.sandbox import SafeAstInterpreter

IMAGE_URL = "/data/adventures/sessions/g1/script_images/script_1.png"


class FakeGenerator:
    def __init__(self, url=IMAGE_URL, error=None):
        self.url = url
        self.error = error
        self.calls: list[tuple[str, str, bool]] = []

    def __call__(self, prompt, tier, apply_style):
        self.calls.append((prompt, tier, apply_style))
        if self.error:
            raise self.error
        return self.url


def _run(code: str, generator=None, debug: bool = False) -> GameContext:
    context = GameContext(image_generator=generator, is_debug_enabled=debug)
    SafeAstInterpreter().execute(code, {"tw": context})
    return context


# --- Model selection -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "tier"),
    [("simple", "simple"), ("hq", "hq"), ("advanced", "hq"), (" HQ ", "hq"), ("", "simple")],
)
def test_normalize_model_tier_maps_aliases(model, tier):
    # Act / Assert
    assert normalize_model_tier(model, "caller") == tier


def test_normalize_model_tier_rejects_unknown_values():
    # Act / Assert
    with pytest.raises(ValueError, match="model must be 'simple', 'hq' or 'advanced'"):
        normalize_model_tier("huge", "tw.image.generate")


def test_generate_defaults_to_simple_model_with_style_and_shows_in_chat():
    # Arrange
    generator = FakeGenerator()

    # Act
    context = _run(
        "url = tw.image.generate('A raven on a skull')\ntw.vars.set('u', url)", generator
    )

    # Assert
    assert generator.calls == [("A raven on a skull", "simple", True)]
    assert context.changeset.var_updates["u"] == IMAGE_URL
    assert context.changeset.narrative_messages == [f"![]({IMAGE_URL})"]


@pytest.mark.parametrize("model", ["hq", "advanced"])
def test_generate_passes_hq_tier(model):
    # Arrange
    generator = FakeGenerator()

    # Act
    _run(f"tw.image.generate('Castle', model='{model}')", generator)

    # Assert
    assert generator.calls[0][1] == "hq"


def test_generate_simple_and_generate_hq_shortcuts():
    # Arrange
    generator = FakeGenerator()

    # Act
    _run("tw.image.generate_simple('a')\ntw.image.generate_hq('b')", generator)

    # Assert
    assert [(p, t) for p, t, _ in generator.calls] == [("a", "simple"), ("b", "hq")]


def test_unknown_model_tier_is_a_script_error():
    # Arrange
    generator = FakeGenerator()
    context = GameContext(image_generator=generator)

    # Act
    ScriptRunner().execute_code("tw.image.generate('Hi', model='huge')", {"tw": context})

    # Assert
    errors = [m for m in context.changeset.system_messages if m.startswith("Script error")]
    assert errors and "model must be 'simple', 'hq' or 'advanced'" in errors[0]
    assert generator.calls == []


# --- apply_style / show_in_chat / caption ----------------------------------------------------


def test_apply_style_false_is_passed_to_generator():
    # Arrange
    generator = FakeGenerator()

    # Act
    _run("tw.image.generate('A document', apply_style=False)", generator)

    # Assert
    assert generator.calls == [("A document", "simple", False)]


def test_show_in_chat_false_returns_url_without_posting():
    # Arrange
    generator = FakeGenerator()

    # Act
    context = _run("tw.vars.set('u', tw.image.generate('Sketch', show_in_chat=False))", generator)

    # Assert
    assert context.changeset.var_updates["u"] == IMAGE_URL
    assert context.changeset.narrative_messages == []


def test_caption_is_rendered_and_sanitized():
    # Arrange
    generator = FakeGenerator()

    # Act
    context = _run("tw.image.generate('Map', caption='The [old] map (torn)\\nback')", generator)

    # Assert
    assert context.changeset.narrative_messages == [f"![The old map torn back]({IMAGE_URL})"]


def test_image_markdown_truncates_long_captions():
    # Act
    line = image_markdown(IMAGE_URL, "x" * (MAX_CAPTION_CHARS + 50))

    # Assert
    assert line == f"![{'x' * MAX_CAPTION_CHARS}]({IMAGE_URL})"


def test_long_prompts_are_truncated():
    # Arrange
    generator = FakeGenerator()
    proxy = ImageProxy(generator, GameContext().changeset)

    # Act
    proxy.generate("p" * (MAX_PROMPT_CHARS + 100))

    # Assert
    assert len(generator.calls[0][0]) == MAX_PROMPT_CHARS


# --- show() ----------------------------------------------------------------------------------


@pytest.mark.parametrize("url", ["/data/img/a.png", "https://example.com/a.webp", "HTTP://x.io/a"])
def test_show_accepts_data_and_http_urls(url):
    # Act
    context = _run(f"tw.image.show('{url}', 'Cap')")

    # Assert
    assert context.changeset.narrative_messages == [f"![Cap]({url})"]


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "/etc/passwd",
        "/data/a b.png",
        "/data/a).png",
        "",
    ],
)
def test_show_rejects_unsupported_urls_with_debug_note(url):
    # Act
    context = _run(f"tw.image.show({url!r})", debug=True)

    # Assert
    assert context.changeset.narrative_messages == []
    assert any("tw.image.show skipped" in m for m in context.changeset.system_messages)


def test_show_works_without_generator_and_has_no_limit():
    # Act
    context = _run("for i in range(5):\n    tw.image.show('/data/a.png')\n")

    # Assert
    assert len(context.changeset.narrative_messages) == 5


# --- Aliases and shortcuts -------------------------------------------------------------------


def test_media_is_alias_of_image():
    # Arrange
    context = GameContext()

    # Assert
    assert MediaProxy is ImageProxy
    assert context.media is context.image


def test_root_and_story_shortcuts_share_the_proxy_and_limit():
    # Arrange
    generator = FakeGenerator()

    # Act
    context = _run(
        "tw.generate_image('a')\n"
        "tw.story.generate_image('b', model='hq')\n"
        "tw.media.generate('c')\n"
        "tw.show_image('/data/x.png', 'X')\n"
        "tw.story.show_image('/data/y.png')\n",
        generator,
    )

    # Assert
    assert [(p, t) for p, t, _ in generator.calls] == [("a", "simple"), ("b", "hq")]
    assert context.changeset.narrative_messages[-2:] == ["![X](/data/x.png)", "![](/data/y.png)"]


def test_story_proxy_without_image_proxy_falls_back_to_unavailable():
    # Arrange
    from backend.engine.scripting.context import StoryProxy

    changeset = GameContext().changeset

    # Act
    url = StoryProxy(changeset).generate_image("a")

    # Assert
    assert url == ""


# --- Limits, availability and error handling -------------------------------------------------


def test_calls_are_capped_per_context_with_debug_note():
    # Arrange
    generator = FakeGenerator()

    # Act
    context = _run("for i in range(5):\n    tw.image.generate('q' + str(i))\n", generator, True)

    # Assert
    assert len(generator.calls) == MAX_IMAGES_PER_CONTEXT
    assert len(context.changeset.narrative_messages) == MAX_IMAGES_PER_CONTEXT
    assert any("limit of" in m for m in context.changeset.system_messages)


def test_empty_prompt_does_not_call_or_count():
    # Arrange
    generator = FakeGenerator()

    # Act
    _run("tw.image.generate('   ')\ntw.image.generate('a')\ntw.image.generate('b')", generator)

    # Assert
    assert [p for p, _, _ in generator.calls] == ["a", "b"]


def test_missing_generator_returns_empty_string_and_is_unavailable():
    # Act
    context = _run(
        "tw.vars.set('a', tw.image.generate('Hi') or 'fallback')\n"
        "tw.vars.set('ok', tw.image.available)",
        debug=True,
    )

    # Assert
    assert context.changeset.var_updates == {"a": "fallback", "ok": False}
    assert context.changeset.narrative_messages == []
    assert any(
        "not available in this script context" in m for m in context.changeset.system_messages
    )


def test_available_is_true_with_generator():
    # Act
    context = _run("tw.vars.set('ok', tw.image.available)", FakeGenerator())

    # Assert
    assert context.changeset.var_updates["ok"] is True


def test_provider_error_returns_empty_string_and_posts_nothing():
    # Arrange
    failing = FakeGenerator(error=RuntimeError("provider down"))

    # Act
    context = _run("tw.vars.set('a', tw.image.generate('Hi') or 'fallback')", failing, True)

    # Assert
    assert context.changeset.var_updates["a"] == "fallback"
    assert context.changeset.narrative_messages == []
    assert len(failing.calls) == 1
    assert any("failed: provider down" in m for m in context.changeset.system_messages)


def test_errors_are_silent_outside_debug_mode():
    # Act
    context = _run("tw.image.generate('Hi')", FakeGenerator(error=RuntimeError("down")))

    # Assert
    assert context.changeset.system_messages == []


def test_generator_returning_empty_url_shows_nothing():
    # Act
    context = _run("tw.image.generate('Hi')", FakeGenerator(url=None))

    # Assert
    assert context.changeset.narrative_messages == []


def test_guard_expressions_never_generate_images():
    # Arrange
    generator = FakeGenerator()
    context = GameContext(image_generator=generator)

    # Act
    result = SafeAstInterpreter().evaluate_expression(
        "tw.image.generate('Door?') == '' and not tw.image.available", {"tw": context}
    )

    # Assert
    assert result is True
    assert generator.calls == []


def test_waiting_for_the_image_does_not_count_against_the_time_limit(monkeypatch):
    # Arrange: a fake clock that jumps past the 2 s budget while the image "renders".
    clock = [1000.0]
    monkeypatch.setattr("backend.engine.scripting.sandbox.time.monotonic", lambda: clock[0])

    def slow_generator(_prompt, _tier, _apply_style):
        clock[0] += 10
        return IMAGE_URL

    context = GameContext(image_generator=slow_generator)

    # Act
    ScriptRunner().execute_code(
        "x = tw.image.generate('slow')\ntotal = 0\nfor i in range(300):\n    total += i\n",
        {"tw": context},
    )

    # Assert
    assert not any("Script error" in m for m in context.changeset.system_messages)


# --- make_script_image_generator ------------------------------------------------------------


T2I = {
    "provider": "openai",
    "simple_model_provider": "ComfyUI",
    "simple_model": "sdxl-turbo",
    "simple_steps": 4,
    "advanced_model_provider": "openai",
    "advanced_model": "gpt-image-1",
    "advanced_steps": 30,
    "image_format": "png",
}


def test_tier_options_map_simple_and_hq_to_settings():
    # Act
    simple = _tier_options(T2I, "simple")
    hq = _tier_options(T2I, "hq")

    # Assert
    assert simple[:2] == ("comfyui", "sdxl-turbo")
    assert simple[2]["comfyui_profile"] == "simple" and simple[2]["steps"] == 4
    assert hq[:2] == ("openai", "gpt-image-1")
    assert hq[2]["comfyui_profile"] == "advanced" and hq[2]["steps"] == 30


def _user(t2i=None, keys=None):
    return SimpleNamespace(
        t2i_settings=T2I if t2i is None else t2i,
        encrypted_api_keys=keys or {},
        image_styles_catalog=[],
    )


@pytest.fixture
def media_calls(monkeypatch, tmp_path):
    calls: list[dict] = []

    async def fake_generate_image(**kwargs):
        calls.append(kwargs)
        return IMAGE_URL

    monkeypatch.setattr(
        script_image.MediaEngine, "generate_image", staticmethod(fake_generate_image)
    )
    monkeypatch.setattr(
        script_image.MediaEngine, "_resolve_api_key", staticmethod(lambda p, k: k.get(p))
    )
    monkeypatch.setattr(
        script_image, "safe_data_path", lambda *parts: str(tmp_path.joinpath(*parts))
    )
    monkeypatch.setattr(
        script_image,
        "resolve_style_instruction",
        lambda styles, _cat: "Ink style" if styles else "",
    )
    return calls


def test_generator_calls_media_engine_with_tier_settings_and_style(media_calls):
    # Arrange
    statuses: list[str] = []
    adventure = SimpleNamespace(id="adv1", selected_image_styles=["ink"])
    generate = make_script_image_generator(
        _user(keys={"openai": "sk"}), adventure, "g1", on_status=statuses.append
    )

    # Act
    url = generate("A raven", "hq", True)

    # Assert
    assert url == IMAGE_URL
    assert statuses == ["Generating image..."]
    call = media_calls[0]
    assert (call["provider"], call["model"], call["api_key"]) == ("openai", "gpt-image-1", "sk")
    assert call["adventure_id"] == "adv1"
    assert call["style_instruction"] == "Ink style"
    assert call["target_dir"].replace("\\", "/").endswith("adventures/sessions/g1/script_images")


def test_generator_skips_style_when_apply_style_is_false(media_calls):
    # Arrange
    adventure = SimpleNamespace(id="adv1", selected_image_styles=["ink"])
    generate = make_script_image_generator(_user(), adventure, "g1")

    # Act
    generate("A raven", "simple", False)

    # Assert
    assert media_calls[0]["style_instruction"] is None
    assert media_calls[0]["provider"] == "comfyui"
    assert media_calls[0]["api_key"] is None


def test_generator_raises_without_model(media_calls):
    # Arrange
    generate = make_script_image_generator(_user(t2i={}), SimpleNamespace(id="a"), "g1")

    # Act / Assert
    with pytest.raises(ValueError, match="No hq image model"):
        generate("A raven", "hq", True)
    assert media_calls == []


def test_generator_raises_without_api_key_for_cloud_provider(media_calls):
    # Arrange
    generate = make_script_image_generator(_user(), SimpleNamespace(id="a"), "g1")

    # Act / Assert
    with pytest.raises(ValueError, match="Missing API key for image provider 'openai'"):
        generate("A raven", "hq", True)
    assert media_calls == []


def test_generator_raises_without_game_id(media_calls):
    # Arrange
    generate = make_script_image_generator(_user(), SimpleNamespace(id="a"), "")

    # Act / Assert
    with pytest.raises(ValueError, match="Missing game session"):
        generate("A raven", "simple", True)


def test_generator_errors_become_empty_string_in_scripts(media_calls):
    # Arrange
    generate = make_script_image_generator(_user(), SimpleNamespace(id="a"), "g1")

    # Act
    context = _run("tw.vars.set('a', tw.image.generate_hq('A raven') or 'fallback')", generate)

    # Assert
    assert context.changeset.var_updates["a"] == "fallback"
    assert media_calls == []
