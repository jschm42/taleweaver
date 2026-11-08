"""OpenAI-compatible TTS provider: local servers and hosted gateways via ``/audio/speech``."""

import json

import httpx
import pytest
from httpx import AsyncClient

from backend.api.routes.settings_normalization import normalize_tts_settings
from backend.core.config import settings
from backend.core.security import encryption_util
from backend.engine.audio import openai_compatible_tts as compat
from backend.engine.audio.openai_compatible_tts import (
    OPENAI_DEFAULT_VOICES,
    SpeechEndpoint,
    checked_base_url,
    list_speech_models,
    list_speech_voices,
    resolve_speech_api_key,
    synthesize_speech,
)
from backend.engine.audio.tts_engine import TTSEngine
from backend.engine.audio.tts_helpers import TTSProviderError
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings

pytestmark = pytest.mark.asyncio

LOCAL = "http://127.0.0.1:8880/v1"


@pytest.fixture
def local_policy(monkeypatch):
    """Explicit private-network opt-in, as the OpenAI-compatible LLM provider requires."""
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_MODELS", True)
    monkeypatch.setattr(
        settings,
        "__pydantic_fields_set__",
        settings.model_fields_set | {"ALLOW_PRIVATE_NETWORK_MODELS"},
    )


def _mock_http(monkeypatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []
    real_client = httpx.AsyncClient

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(record)
    monkeypatch.setattr(
        compat.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs)
    )
    return seen


def _endpoint(**overrides) -> SpeechEndpoint:
    values = {"base_url": LOCAL, "model": "kokoro", "voice": "af_heart", **overrides}
    return SpeechEndpoint(**values)


async def _enable_compatible_tts(keys: dict | None = None, **overrides: object) -> None:
    async with TestSessionLocal() as session:
        await seed_server_settings(
            session,
            tts_settings={
                "enabled": True,
                "provider": "custom_openai",
                "selected_model": "kokoro",
                "custom_openai_url": LOCAL,
                "custom_openai_voice": "bm_george",
                **overrides,
            },
            encrypted_api_keys=keys or {},
        )
        await session.commit()


async def test_local_server_gets_openai_speech_request_without_key(monkeypatch, local_policy):
    # Arrange
    seen = _mock_http(monkeypatch, lambda _r: httpx.Response(200, content=b"ID3-audio"))

    # Act
    audio, ext = await synthesize_speech("Hello there.", _endpoint())

    # Assert
    request = seen[0]
    body = json.loads(request.content)
    assert (audio, ext) == (b"ID3-audio", "mp3")
    assert str(request.url) == f"{LOCAL}/audio/speech"
    assert body == {
        "model": "kokoro",
        "input": "Hello there.",
        "voice": "af_heart",
        "response_format": "mp3",
    }
    assert "authorization" not in request.headers


async def test_key_and_instructions_are_sent_when_configured(monkeypatch, local_policy):
    seen = _mock_http(monkeypatch, lambda _r: httpx.Response(200, content=b"audio"))

    await synthesize_speech(
        "Hi", _endpoint(api_key="sk-test", instructions="Speak like an old bard.")
    )

    assert seen[0].headers["authorization"] == "Bearer sk-test"
    assert json.loads(seen[0].content)["instructions"] == "Speak like an old bard."


def _wav_sample_rate(wav: bytes) -> int:
    return int.from_bytes(wav[24:28], "little")


async def test_pcm_is_wrapped_as_wav_with_default_rate(monkeypatch, local_policy):
    _mock_http(monkeypatch, lambda _r: httpx.Response(200, content=b"\x00\x01" * 10))

    audio, ext = await synthesize_speech("Hi", _endpoint(response_format="pcm"))

    assert ext == "wav"
    assert audio.startswith(b"RIFF")
    assert _wav_sample_rate(audio) == 24000


async def test_pcm_uses_the_rate_from_the_content_type(monkeypatch, local_policy):
    # Fish Audio via OpenRouter answers "audio/pcm;rate=44100;channels=1".
    _mock_http(
        monkeypatch,
        lambda _r: httpx.Response(
            200,
            content=b"\x00\x01" * 10,
            headers={"content-type": "audio/pcm;rate=44100;channels=1"},
        ),
    )

    audio, _ext = await synthesize_speech("Hi", _endpoint(response_format="pcm"))

    assert _wav_sample_rate(audio) == 44100


async def test_empty_voice_is_omitted_for_the_model_default(monkeypatch, local_policy):
    seen = _mock_http(monkeypatch, lambda _r: httpx.Response(200, content=b"audio"))

    await synthesize_speech("Hi", _endpoint(model="fish-audio/drama-3", voice=""))

    assert "voice" not in json.loads(seen[0].content)


async def test_server_error_detail_becomes_provider_error(monkeypatch, local_policy):
    _mock_http(
        monkeypatch,
        lambda _r: httpx.Response(400, json={"detail": {"message": "Voice 'xx' not found"}}),
    )

    with pytest.raises(TTSProviderError, match="Voice 'xx' not found"):
        await synthesize_speech("Hi", _endpoint(voice="xx"))


async def test_unreachable_server_becomes_provider_error(monkeypatch, local_policy):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    _mock_http(monkeypatch, refuse)

    with pytest.raises(TTSProviderError, match="not reachable"):
        await synthesize_speech("Hi", _endpoint())


async def test_missing_model_fails_before_any_request(monkeypatch, local_policy):
    seen = _mock_http(monkeypatch, lambda _r: httpx.Response(200, content=b"audio"))

    with pytest.raises(TTSProviderError, match="model"):
        await synthesize_speech("Hi", _endpoint(model=""))
    assert seen == []


@pytest.mark.parametrize("url", ["", "http://127.0.0.1:8880", "file:///etc/passwd"])
async def test_invalid_base_urls_are_rejected(url, local_policy):
    with pytest.raises(TTSProviderError):
        checked_base_url(url)


async def test_private_server_needs_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(
        settings,
        "__pydantic_fields_set__",
        settings.model_fields_set - {"ALLOW_PRIVATE_NETWORK_MODELS"},
    )

    with pytest.raises(TTSProviderError, match="rejected"):
        checked_base_url(LOCAL)


async def test_key_rules_follow_the_llm_provider():
    own = {"custom_openai": encryption_util.encrypt_key("own-key")}
    router_only = {"openrouter": encryption_util.encrypt_key("or-key")}

    assert resolve_speech_api_key(own, "https://openrouter.ai/api/v1") == "own-key"
    assert resolve_speech_api_key(router_only, "https://openrouter.ai/api/v1") == "or-key"
    assert resolve_speech_api_key(router_only, LOCAL) is None
    # A URL that only contains the name never receives the OpenRouter key.
    assert resolve_speech_api_key(router_only, "https://evil.example/openrouter.ai/v1") is None


async def test_models_keep_only_speech_entries_when_the_server_marks_them(
    monkeypatch, local_policy
):
    payload = {
        "data": [
            {"id": "openai/gpt-4o-mini-tts", "architecture": {"output_modalities": ["speech"]}},
            {"id": "openai/gpt-5", "architecture": {"output_modalities": ["text"]}},
            {"id": "kokoro"},
        ]
    }
    seen = _mock_http(monkeypatch, lambda _r: httpx.Response(200, json=payload))

    models = await list_speech_models(LOCAL, None)

    assert models == ["kokoro", "openai/gpt-4o-mini-tts"]
    assert seen[0].url.params["output_modalities"] == "speech"


async def test_voices_from_server_list(monkeypatch, local_policy):
    _mock_http(
        monkeypatch,
        lambda _r: httpx.Response(200, json={"voices": ["bm_george", "af_heart", "af_heart"]}),
    )

    assert await list_speech_voices(LOCAL, None) == (["af_heart", "bm_george"], "server")


async def test_voices_from_model_entry_when_server_has_no_voice_route(monkeypatch, local_policy):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/audio/voices"):
            return httpx.Response(404)
        entry = {"id": "microsoft/mai-voice", "supported_voices": [{"id": "en-US-Harper"}]}
        return httpx.Response(200, json={"data": [entry]})

    _mock_http(monkeypatch, handler)

    voices = await list_speech_voices(LOCAL, None, "microsoft/mai-voice")

    assert voices == (["en-US-Harper"], "model")


@pytest.mark.parametrize("model", ["tts-1", "gpt-4o-mini-tts", "openai/gpt-4o-mini-tts-2025-12-15"])
async def test_openai_voice_names_are_suggested_for_openai_models(monkeypatch, local_policy, model):
    _mock_http(monkeypatch, lambda _r: httpx.Response(404))

    voices, source = await list_speech_voices(LOCAL, None, model)

    assert source == "suggested"
    assert voices == list(OPENAI_DEFAULT_VOICES)


async def test_other_models_get_no_openai_voice_names(monkeypatch, local_policy):
    # Fish Audio rejects "cedar" & co. with HTTP 400; its model entry lists no voices.
    _mock_http(
        monkeypatch,
        lambda r: (
            httpx.Response(404)
            if r.url.path.endswith("/audio/voices")
            else httpx.Response(200, json={"data": [{"id": "fish-audio/drama-3"}]})
        ),
    )

    assert await list_speech_voices(LOCAL, None, "fish-audio/drama-3") == ([], "none")


async def test_engine_strips_vocal_tags_and_stores_the_clip(monkeypatch):
    # Arrange
    calls: dict = {}

    async def fake_synthesize(text, endpoint):
        calls.update(text=text, endpoint=endpoint)
        return b"mp3", "mp3"

    monkeypatch.setattr("backend.engine.audio.tts_engine.synthesize_speech", fake_synthesize)
    monkeypatch.setattr(
        "backend.engine.audio.tts_engine._write_audio_file",
        lambda audio, adventure_id, session_id, ext: f"/data/audio/clip.{ext}",
    )

    # Act
    url = await TTSEngine.generate_speech(
        text="[whispering] The door creaks open.",
        provider="custom_openai",
        api_key=None,
        speech_endpoint=_endpoint(),
    )

    # Assert
    assert url == "/data/audio/clip.mp3"
    assert "[" not in calls["text"]
    assert "The door creaks open." in calls["text"]


async def test_settings_normalization_keeps_compatible_fields():
    normalized = normalize_tts_settings(
        {
            "provider": "custom_openai",
            "selected_model": "openai/gpt-4o-mini-tts",
            "custom_openai_url": " https://openrouter.ai/api/v1 ",
            "custom_openai_voice": "alloy",
            "custom_openai_format": "OGG",
        }
    )

    assert normalized["selected_model"] == "openai/gpt-4o-mini-tts"
    assert normalized["custom_openai_url"] == "https://openrouter.ai/api/v1"
    assert normalized["custom_openai_voice"] == "alloy"
    assert normalized["custom_openai_format"] == "mp3"


async def test_generate_endpoint_works_without_any_key(auth_client: AsyncClient, monkeypatch):
    # Arrange
    await _enable_compatible_tts()
    captured: dict = {}

    async def fake_generate_speech(**kwargs):
        captured.update(kwargs)
        return "/data/audio/compat.mp3"

    monkeypatch.setattr(
        "backend.api.routes.tts_api.TTSEngine.generate_speech", fake_generate_speech
    )

    # Act
    resp = await auth_client.post("/api/tts/generate", json={"text": "Welcome, traveller."})

    # Assert
    endpoint = captured["speech_endpoint"]
    assert resp.status_code == 200
    assert captured["provider"] == "custom_openai"
    assert (endpoint.base_url, endpoint.model, endpoint.voice) == (LOCAL, "kokoro", "bm_george")
    assert endpoint.api_key is None


async def test_generate_endpoint_uses_the_vault_key(auth_client: AsyncClient, monkeypatch):
    await _enable_compatible_tts(keys={"custom_openai": encryption_util.encrypt_key("sk-x")})
    captured: dict = {}

    async def fake_generate_speech(**kwargs):
        captured.update(kwargs)
        return "/data/audio/compat.mp3"

    monkeypatch.setattr(
        "backend.api.routes.tts_api.TTSEngine.generate_speech", fake_generate_speech
    )

    resp = await auth_client.post("/api/tts/generate", json={"text": "Hi"})

    assert resp.status_code == 200
    assert captured["speech_endpoint"].api_key == "sk-x"


async def test_stream_endpoint_falls_back_to_whole_clips(auth_client: AsyncClient):
    await _enable_compatible_tts()

    resp = await auth_client.post("/api/tts/stream", json={"text": "Hello"})

    assert resp.status_code == 409


async def test_voice_discovery_endpoint_uses_saved_server(
    auth_client: AsyncClient, monkeypatch, local_policy
):
    # Arrange
    await _enable_compatible_tts()
    seen: dict = {}

    async def fake_list(base_url, api_key, model=""):
        seen.update(base_url=base_url, model=model)
        return ["af_heart"], "server"

    monkeypatch.setattr(
        "backend.api.routes.tts_openai_compatible_api.list_speech_voices", fake_list
    )

    # Act
    resp = await auth_client.get("/api/tts/openai-compatible/voices", params={"model": "kokoro"})

    # Assert
    assert resp.status_code == 200
    assert resp.json() == {"base_url": LOCAL, "source": "server", "voices": ["af_heart"]}
    assert seen == {"base_url": LOCAL, "model": "kokoro"}


async def test_model_discovery_endpoint_reports_server_errors(
    auth_client: AsyncClient, monkeypatch, local_policy
):
    async def failing(base_url, api_key):
        raise TTSProviderError(f"Could not load models from {base_url}.")

    monkeypatch.setattr("backend.api.routes.tts_openai_compatible_api.list_speech_models", failing)

    resp = await auth_client.get(
        "/api/tts/openai-compatible/models", params={"base_url": "http://127.0.0.1:9000/v1"}
    )

    assert resp.status_code == 502
    assert "127.0.0.1:9000" in resp.json()["detail"]


async def test_discovery_rejects_invalid_base_url(auth_client: AsyncClient, local_policy):
    resp = await auth_client.get(
        "/api/tts/openai-compatible/models", params={"base_url": "http://127.0.0.1:9000"}
    )

    assert resp.status_code == 400
