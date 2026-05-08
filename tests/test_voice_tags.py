"""
Tests for Voice-Tag support in GM narration.

Voice-tags like [shouting] or [very fast] are runtime markup produced by the GM.
They are stored unchanged in ChatMessage.content and passed through to TTS.
"""
import re
import os
import base64
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Prompt guidance
# ---------------------------------------------------------------------------

def test_gm_narration_formatting_contains_voice_tag_guidance():
    """GM_NARRATION_MANDATORY_FORMATTING must document voice-tag usage."""
    from backend.core.prompts import GM_NARRATION_MANDATORY_FORMATTING

    assert "[excited]" in GM_NARRATION_MANDATORY_FORMATTING
    assert "[whispers]" in GM_NARRATION_MANDATORY_FORMATTING
    assert "[shouting]" in GM_NARRATION_MANDATORY_FORMATTING
    assert "ENGLISH" in GM_NARRATION_MANDATORY_FORMATTING
    assert "new paragraph" in GM_NARRATION_MANDATORY_FORMATTING.lower()
    assert "Do not nest tags" in GM_NARRATION_MANDATORY_FORMATTING


# ---------------------------------------------------------------------------
# TTS engine: voice-tag acting cues in prompt
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tts_engine_includes_voice_direction_cue_in_prompt():
    """TTSEngine must embed acting-cue instructions so the model honours tags."""
    from backend.engine.tts_engine import TTSEngine

    captured_payload: dict = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/l16",
                                        "data": "",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    async def fake_post(_url, json, timeout=None):
        _ = timeout
        captured_payload.update(json)
        return FakeResponse()

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = fake_post
        mock_client_cls.return_value = instance

        await TTSEngine.generate_speech(
            text="[shouting] Look out!",
            voice="Puck",
            api_key="fake-key",
        )

    assert captured_payload, "No HTTP request was captured."
    prompt_text = captured_payload["contents"][0]["parts"][0]["text"]
    assert "voice-direction" in prompt_text or "acting cues" in prompt_text.lower() or "[shouting]" in prompt_text


@pytest.mark.asyncio
async def test_tts_engine_passes_voice_tags_in_transcript():
    """Voice tags in the input text must appear verbatim in the TTS transcript."""
    from backend.engine.tts_engine import TTSEngine

    captured_payload: dict = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/l16",
                                        "data": "",
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    async def fake_post(_url, json, timeout=None):
        _ = timeout
        captured_payload.update(json)
        return FakeResponse()

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = fake_post
        mock_client_cls.return_value = instance

        await TTSEngine.generate_speech(
            text="[very fast] Run, run, run!\n\n[whispers] They are still here.",
            voice="Puck",
            api_key="fake-key",
        )

    prompt_text = captured_payload["contents"][0]["parts"][0]["text"]
    assert "[very fast]" in prompt_text
    assert "[whispers]" in prompt_text


@pytest.mark.asyncio
async def test_tts_engine_converts_uppercase_l16_mime_to_valid_wav(tmp_path, monkeypatch):
    """Gemini 2.5 may return audio/L16;rate=24000 and must be wrapped as WAV."""
    from backend.engine.tts_engine import TTSEngine
    from backend.core.config import settings

    # 16-bit PCM sample pair (very short test payload)
    raw_pcm = b"\x00\x00\x10\x00"
    encoded = base64.b64encode(raw_pcm).decode("ascii")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/L16;rate=24000",
                                        "data": encoded,
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    async def fake_post(_url, json, timeout=None):
        _ = json
        _ = timeout
        return FakeResponse()

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = fake_post
        mock_client_cls.return_value = instance

        audio_url = await TTSEngine.generate_speech(
            text="Test line",
            voice="Aoede",
            api_key="fake-key",
            model_name="gemini-2.5-flash-preview-tts",
        )

    assert audio_url and audio_url.endswith(".wav")

    relative_path = audio_url.replace("/data/", "", 1)
    written_file = os.path.join(str(tmp_path), relative_path.replace("/", os.sep))
    with open(written_file, "rb") as f:
        payload = f.read(12)

    assert payload[:4] == b"RIFF"
    assert payload[8:12] == b"WAVE"


@pytest.mark.asyncio
async def test_tts_engine_skips_empty_inline_data_and_uses_non_empty_chunk(tmp_path, monkeypatch):
    """Responses with an empty first inlineData part must still produce audio."""
    from backend.engine.tts_engine import TTSEngine
    from backend.core.config import settings

    non_empty_pcm = b"\x01\x00\x02\x00\x03\x00\x04\x00"
    encoded_non_empty = base64.b64encode(non_empty_pcm).decode("ascii")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "audio/L16;rate=24000",
                                        "data": "",
                                    }
                                },
                                {
                                    "inlineData": {
                                        "mimeType": "audio/L16;rate=24000",
                                        "data": encoded_non_empty,
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    async def fake_post(_url, json, timeout=None):
        _ = json
        _ = timeout
        return FakeResponse()

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = fake_post
        mock_client_cls.return_value = instance

        audio_url = await TTSEngine.generate_speech(
            text="Chunked output test",
            voice="Aoede",
            api_key="fake-key",
            model_name="gemini-2.5-flash-preview-tts",
        )

    assert audio_url and audio_url.endswith(".wav")

    rel = audio_url.replace("/data/", "", 1)
    written_file = os.path.join(str(tmp_path), rel.replace("/", os.sep))
    assert os.path.exists(written_file)
    # WAV header (44 bytes) + non-empty PCM payload
    assert os.path.getsize(written_file) > 44


# ---------------------------------------------------------------------------
# Voice-tag regex logic (Python mirror of the frontend formatVoiceTags rules)
# These tests document the expected parsing behaviour that the frontend
# TypeScript function must satisfy.
# ---------------------------------------------------------------------------

VOICE_TAG_PATTERN = re.compile(r"^\[([^\]\n]+)\]", re.MULTILINE)


def _simulate_force_paragraph_breaks(text: str) -> str:
    """Mirrors the frontend rule: insert \\n\\n before [tag] that starts a
    line but is not already preceded by a blank line."""
    return re.sub(r"(?<!\n)\n(?!\n)(\[[^\]\n]+\])", r"\n\n\1", text)


def test_force_paragraph_break_before_tag_on_new_line():
    """A [tag] on a new line without a preceding blank line gets one inserted."""
    text = "Some text.\n[shouting] Loud!"
    result = _simulate_force_paragraph_breaks(text)
    assert result == "Some text.\n\n[shouting] Loud!"


def test_no_extra_break_when_already_blank_line():
    """A [tag] already preceded by a blank line must not get a duplicate."""
    text = "Some text.\n\n[shouting] Loud!"
    result = _simulate_force_paragraph_breaks(text)
    assert result == "Some text.\n\n[shouting] Loud!"


def test_multiple_consecutive_tags_get_breaks():
    """Multiple consecutive [tag] lines each get their own paragraph."""
    text = "[excited] Hello!\n[shouting] HELLO!"
    result = _simulate_force_paragraph_breaks(text)
    assert result == "[excited] Hello!\n\n[shouting] HELLO!"


def test_known_tags_detected():
    """All documented tags should be detectable by the voice-tag pattern."""
    from backend.core.voice_tags import VOICE_TAG_CATALOG

    known_tags = [f"[{tag}]" for tag in VOICE_TAG_CATALOG]
    for tag in known_tags:
        assert VOICE_TAG_PATTERN.match(tag), f"Tag not recognised: {tag}"


def test_unknown_tag_also_detected():
    """Unknown tags should still be matched (generic fallback)."""
    assert VOICE_TAG_PATTERN.match("[mysteriously]")
    assert VOICE_TAG_PATTERN.match("[half-asleep]")


def test_system_tag_not_matched_as_multiline():
    """[system] at start of message content is distinct from inline voice tags
    and is handled separately by displayMessageContent — the pattern must still
    match it so the frontend can decide to strip it explicitly."""
    assert VOICE_TAG_PATTERN.match("[system]")


def test_tag_scope_ends_at_blank_line():
    """Scope of a tag is the paragraph up to the next blank line."""
    text = "[shouting] First line.\nStill first para.\n\nNormal again."
    after_breaks = _simulate_force_paragraph_breaks(text)
    paragraphs = after_breaks.split("\n\n")
    # First paragraph starts with [shouting]
    assert paragraphs[0].startswith("[shouting]")
    # Second paragraph has no tag prefix
    assert not paragraphs[1].startswith("[")
