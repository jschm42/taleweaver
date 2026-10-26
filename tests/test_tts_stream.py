"""Tests for ElevenLabs streaming speech (two-step token flow and upstream relay)."""

import httpx
import pytest
from httpx import AsyncClient

from backend.engine import elevenlabs_stream
from backend.engine.tts_helpers import TTSProviderError, TTSRateLimitError
from tests.test_tts_api import _enable_tts_for_test_user

VOICE = "N" * 20


def _mock_elevenlabs(monkeypatch, handler):
    """Routes the stream client's requests to ``handler`` instead of ElevenLabs."""
    real_client = httpx.AsyncClient
    seen: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(
        elevenlabs_stream.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(recording), **kwargs),
    )
    return seen


@pytest.mark.asyncio
async def test_open_stream_relays_audio_chunks(monkeypatch):
    # Arrange
    seen = _mock_elevenlabs(monkeypatch, lambda _r: httpx.Response(200, content=b"ID3audio"))

    # Act
    chunks = await elevenlabs_stream.open_elevenlabs_stream(
        "[sighs] Hi.", VOICE, "key", "eleven_v4"
    )
    audio = b"".join([chunk async for chunk in chunks])

    # Assert
    assert audio == b"ID3audio"
    assert seen[0].url.path == f"/v1/text-to-speech/{VOICE}/stream"
    assert seen[0].url.params["output_format"] == "mp3_44100_128"
    assert seen[0].headers["xi-api-key"] == "key"


@pytest.mark.asyncio
async def test_open_stream_raises_before_relaying_on_rate_limit(monkeypatch):
    # Arrange
    _mock_elevenlabs(monkeypatch, lambda _r: httpx.Response(429, headers={"Retry-After": "3"}))

    # Act / Assert
    with pytest.raises(TTSRateLimitError):
        await elevenlabs_stream.open_elevenlabs_stream("Hi.", VOICE, "key")


@pytest.mark.asyncio
async def test_open_stream_reports_provider_errors(monkeypatch):
    # Arrange
    _mock_elevenlabs(
        monkeypatch,
        lambda _r: httpx.Response(400, json={"detail": {"message": "voice_not_found"}}),
    )

    # Act / Assert
    with pytest.raises(TTSProviderError, match="voice_not_found"):
        await elevenlabs_stream.open_elevenlabs_stream("Hi.", VOICE, "key")


@pytest.mark.asyncio
async def test_stream_token_flow_relays_audio_once(auth_client: AsyncClient, monkeypatch):
    # Arrange
    await _enable_tts_for_test_user(
        provider="elevenlabs", elevenlabs_voice_id=VOICE, selected_model="eleven_v4"
    )
    seen = _mock_elevenlabs(monkeypatch, lambda _r: httpx.Response(200, content=b"mp3-bytes"))

    # Act
    prepared = await auth_client.post(
        "/api/tts/stream", json={"text": "<sigh> Hello there.", "voice_override": "M" * 20}
    )
    token = prepared.json()["token"]
    first = await auth_client.get(f"/api/tts/stream/{token}")
    second = await auth_client.get(f"/api/tts/stream/{token}")

    # Assert
    assert prepared.status_code == 200
    assert first.status_code == 200
    assert first.headers["content-type"] == "audio/mpeg"
    assert first.content == b"mp3-bytes"
    assert second.status_code == 404
    body = seen[0].read().decode()
    assert "[sighs] Hello there." in body
    assert seen[0].url.path.endswith(f"/{'M' * 20}/stream")


@pytest.mark.asyncio
async def test_stream_is_refused_for_gemini(auth_client: AsyncClient):
    # Arrange
    await _enable_tts_for_test_user()

    # Act
    resp = await auth_client.post("/api/tts/stream", json={"text": "Hello."})

    # Assert
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_unknown_stream_token_is_rejected(auth_client: AsyncClient):
    # Arrange / Act
    resp = await auth_client.get("/api/tts/stream/not-a-token")

    # Assert
    assert resp.status_code == 404
