import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.core.security import encryption_util
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _enable_tts_for_test_user(api_key: str = "test-api-key", **overrides: object) -> None:
    """Enable TTS for the seeded test user with valid settings (Gemini unless overridden)."""
    async with TestSessionLocal() as session:
        user = (
            (await session.execute(select(User).where(User.username == "test_user")))
            .scalars()
            .first()
        )
        assert user is not None
        user.tts_settings = {
            "enabled": True,
            "provider": "google",
            "selected_model": "gemini-3.8-flash-tts",
            "selected_voice": "Puck",
            "use_vocal_tags": True,
            "speech_rate": 1.0,
            "elevenlabs_voice_id": "",
            **overrides,
        }
        provider = str(user.tts_settings["provider"])
        user.encrypted_api_keys = {provider: encryption_util.encrypt_key(api_key)}
        await session.commit()


async def _create_template_avatar_and_session(
    template_id: str = "test-tpl-1",
    avatar_id: str = "test-avatar-1",
    session_id: str = "test-session-1",
) -> None:
    """Seed a minimal adventure template, avatar, and active game session."""
    async with TestSessionLocal() as session:
        user = (
            (await session.execute(select(User).where(User.username == "test_user")))
            .scalars()
            .first()
        )
        assert user is not None

        template = (
            (
                await session.execute(
                    select(AdventureTemplate).where(AdventureTemplate.id == template_id)
                )
            )
            .scalars()
            .first()
        )
        if template is None:
            template = AdventureTemplate(
                id=template_id,
                owner_id=user.id,
                title="Test Adventure",
                language="en",
                is_ready=True,
            )
            session.add(template)

        avatar = (
            (await session.execute(select(Avatar).where(Avatar.id == avatar_id))).scalars().first()
        )
        if avatar is None:
            avatar = Avatar(
                id=avatar_id,
                template_id=template_id,
                user_id=user.id,
                name="Tester",
                role="Hero",
                description="Test avatar",
            )
            session.add(avatar)

        game_session = (
            (await session.execute(select(GameSession).where(GameSession.id == session_id)))
            .scalars()
            .first()
        )
        if game_session is None:
            game_session = GameSession(
                id=session_id,
                user_id=user.id,
                avatar_id=avatar_id,
                template_id=template_id,
                status="active",
            )
            session.add(game_session)

        await session.commit()


def _build_fake_httpx_response(
    audio_payload: bytes, mime_type: str = "audio/L16;rate=24000"
) -> MagicMock:
    """Create a fake httpx response that returns raw PCM audio for the TTS engine."""
    import base64

    encoded = base64.b64encode(audio_payload).decode("ascii")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": mime_type,
                                        "data": encoded,
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    return FakeResponse()


@pytest.mark.asyncio
async def test_generate_tts_accepts_non_uuid_ids(auth_client: AsyncClient, monkeypatch):
    """TTS generation must accept legacy/non-UUID session and adventure ids."""
    await _enable_tts_for_test_user()

    async def fake_generate_speech(**kwargs):
        return "/data/audio/test.wav"

    monkeypatch.setattr(
        "backend.api.routes.tts_api.TTSEngine.generate_speech", fake_generate_speech
    )

    payload = {
        "text": "Hello from TaleWeaver.",
        "session_id": "session-1",
        "adventure_id": "adv-legacy",
    }

    resp = await auth_client.post("/api/tts/generate", json=payload)

    assert resp.status_code == 200
    assert resp.json().get("audio_url") == "/data/audio/test.wav"


@pytest.mark.asyncio
async def test_tts_writes_audio_under_session_folder_when_session_id_present(
    auth_client: AsyncClient, tmp_path, monkeypatch
):
    """Session-bound TTS must persist the file under
    ``<DATA_DIR>/adventures/sessions/<session_id>/tts/`` and expose a matching URL.
    """
    from backend.core.config import settings
    from backend.engine.tts_engine import TTSEngine

    await _enable_tts_for_test_user()
    await _create_template_avatar_and_session(
        template_id="route-tpl",
        avatar_id="route-avatar",
        session_id="route-session-uuid-001",
    )

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    async def fake_post(_url, json, timeout=None):
        return _build_fake_httpx_response(b"\x00\x00\x10\x00")

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = fake_post
        mock_client_cls.return_value = instance

        audio_url = await TTSEngine.generate_speech(
            text="Test line",
            voice="Puck",
            api_key="test-api-key",
            model_name="gemini-3.8-flash-tts",
            adventure_id="route-tpl",
            session_id="route-session-uuid-001",
        )

    assert audio_url is not None
    assert audio_url.startswith("/data/adventures/sessions/route-session-uuid-001/tts/")
    assert audio_url.endswith(".wav")

    relative_path = audio_url.replace("/data/", "", 1)
    written_file = os.path.join(str(tmp_path), relative_path.replace("/", os.sep))
    assert os.path.isfile(written_file), f"Expected file at {written_file}"

    session_audio_dir = tmp_path / "adventures" / "sessions" / "route-session-uuid-001" / "tts"
    assert session_audio_dir.is_dir()
    # The global /data/audio/ fallback must NOT receive this file.
    global_audio_dir = tmp_path / "audio"
    assert not (global_audio_dir / os.path.basename(written_file)).exists()


@pytest.mark.asyncio
async def test_tts_falls_back_to_global_audio_folder_without_session_id(tmp_path, monkeypatch):
    """Legacy callers (connection test, manual TTS) without a session id must still
    persist into the global ``<DATA_DIR>/audio/`` folder.
    """
    from backend.core.config import settings
    from backend.engine.tts_engine import TTSEngine

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    async def fake_post(_url, json, timeout=None):
        return _build_fake_httpx_response(b"\x00\x00\x10\x00")

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = fake_post
        mock_client_cls.return_value = instance

        audio_url = await TTSEngine.generate_speech(
            text="Test line",
            voice="Puck",
            api_key="test-api-key",
            model_name="gemini-3.8-flash-tts",
        )

    assert audio_url is not None
    assert audio_url.startswith("/data/audio/")
    assert audio_url.endswith(".wav")

    written_file = os.path.join(str(tmp_path), "audio", os.path.basename(audio_url))
    assert os.path.isfile(written_file), f"Expected file at {written_file}"


@pytest.mark.asyncio
async def test_tts_invalid_session_id_falls_back_to_global_audio_folder(tmp_path, monkeypatch):
    """An unsafe/invalid session id must not crash the engine and must fall back
    to the global ``/data/audio/`` folder, never writing outside ``DATA_DIR``.
    """
    from backend.core.config import settings
    from backend.engine.tts_engine import TTSEngine

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    async def fake_post(_url, json, timeout=None):
        return _build_fake_httpx_response(b"\x00\x00\x10\x00")

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = fake_post
        mock_client_cls.return_value = instance

        audio_url = await TTSEngine.generate_speech(
            text="Test line",
            voice="Puck",
            api_key="test-api-key",
            model_name="gemini-3.8-flash-tts",
            adventure_id="some-adv",
            session_id="../etc/passwd",
        )

    assert audio_url is not None
    assert audio_url.startswith("/data/audio/")
    assert audio_url.endswith(".wav")

    written_file = os.path.join(str(tmp_path), "audio", os.path.basename(audio_url))
    assert os.path.isfile(written_file), f"Expected file at {written_file}"
    # No traversal artifacts should be created under DATA_DIR.
    assert not (tmp_path / "etc").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("voice_override", ["Kore", "Unknown Speaker", None])
async def test_gemini_always_uses_the_narrator_voice(
    auth_client: AsyncClient, monkeypatch, voice_override
):
    """Per-character voices are an ElevenLabs feature; Gemini ignores NPC voice overrides."""
    # Arrange
    await _enable_tts_for_test_user()
    captured: dict = {}

    async def fake_generate_speech(**kwargs):
        captured.update(kwargs)
        return "/data/audio/test.wav"

    monkeypatch.setattr(
        "backend.api.routes.tts_api.TTSEngine.generate_speech", fake_generate_speech
    )

    # Act
    resp = await auth_client.post(
        "/api/tts/generate", json={"text": "Halt!", "voice_override": voice_override}
    )

    # Assert
    assert resp.status_code == 200
    assert captured["voice"] == "Puck"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("voice_override", "expected_voice_id"),
    [("M" * 20, "M" * 20), ("Unknown Speaker", "N" * 20), (None, "N" * 20)],
)
async def test_elevenlabs_applies_npc_voice_ids(
    auth_client: AsyncClient, monkeypatch, voice_override, expected_voice_id
):
    """ElevenLabs gets the NPC voice id; speaker names fall back to the narrator voice."""
    # Arrange
    await _enable_tts_for_test_user(
        provider="elevenlabs", elevenlabs_voice_id="N" * 20, selected_model="eleven_v4"
    )
    captured: dict = {}

    async def fake_generate_speech(**kwargs):
        captured.update(kwargs)
        return "/data/audio/test.mp3"

    monkeypatch.setattr(
        "backend.api.routes.tts_api.TTSEngine.generate_speech", fake_generate_speech
    )

    # Act
    resp = await auth_client.post(
        "/api/tts/generate", json={"text": "Halt!", "voice_override": voice_override}
    )

    # Assert
    assert resp.status_code == 200
    assert captured["elevenlabs_voice_id"] == expected_voice_id


@pytest.mark.asyncio
async def test_voices_endpoint_lists_voice_list_only_for_elevenlabs(auth_client: AsyncClient):
    # Arrange
    await _enable_tts_for_test_user()

    # Act
    gemini = await auth_client.get("/api/tts/voices")
    eleven = await auth_client.get("/api/tts/voices", params={"provider": "elevenlabs"})

    # Assert
    assert gemini.json() == {"provider": "google", "supports_npc_voices": False, "voices": []}
    assert eleven.json()["supports_npc_voices"] is True
    assert eleven.json()["voices"]


@pytest.mark.asyncio
async def test_gemini_api_key_is_sent_as_header_not_in_url(tmp_path, monkeypatch):
    """The Google API key must never be embedded in the request URL (it leaks into logs)."""
    # Arrange
    from backend.core.config import settings
    from backend.engine.tts_engine import TTSEngine

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    captured_urls: list[str] = []

    async def fake_post(url, json, timeout=None):
        captured_urls.append(url)
        return _build_fake_httpx_response(b"\x00\x00\x10\x00")

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = fake_post
        mock_client_cls.return_value = instance

        # Act
        audio_url = await TTSEngine.generate_speech(
            text="Test line", voice="Puck", api_key="secret-key-123"
        )

    # Assert
    assert audio_url is not None
    assert captured_urls and all("secret-key-123" not in url for url in captured_urls)
    assert mock_client_cls.call_args.kwargs["headers"] == {"x-goog-api-key": "secret-key-123"}


@pytest.mark.asyncio
async def test_elevenlabs_rate_limit_raises_rate_limit_error(monkeypatch):
    """ElevenLabs 429 responses must surface as TTSRateLimitError (HTTP 429), not a 500."""
    # Arrange
    import httpx

    from backend.engine.tts_engine import TTSEngine, TTSRateLimitError

    monkeypatch.setattr(
        "backend.engine.tts_engine._wait_for_tts_request_slot", AsyncMock(return_value=None)
    )
    rate_limited = httpx.Response(429, headers={"Retry-After": "3"})

    with patch("httpx.AsyncClient") as mock_client_cls:
        instance = MagicMock()
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        instance.post = AsyncMock(return_value=rate_limited)
        mock_client_cls.return_value = instance

        # Act / Assert
        with pytest.raises(TTSRateLimitError):
            await TTSEngine.generate_speech(
                text="Hello",
                provider="elevenlabs",
                elevenlabs_voice_id="voice-1",
                api_key="el-key",
            )


@pytest.mark.asyncio
async def test_google_payload_does_not_use_system_instruction():
    """Gemini TTS endpoints reject systemInstruction with 400; ensure it is never set."""
    from backend.engine.tts_engine import TTSEngine

    payload = TTSEngine._build_google_payload("Guten Morgen", voice="Puck", language="de")
    assert "systemInstruction" not in payload
    assert payload["contents"][0]["parts"][0]["text"] == "Guten Morgen"


@pytest.mark.asyncio
async def test_tts_provider_error_propagates_to_http_502(auth_client: AsyncClient, monkeypatch):
    """When the upstream TTS provider returns an error, the endpoint should return 502 with the message."""
    from backend.engine.tts_engine import TTSProviderError

    await _enable_tts_for_test_user()

    async def fake_generate_speech(**kwargs):
        raise TTSProviderError("Google TTS error: Developer instruction is not enabled")

    monkeypatch.setattr(
        "backend.api.routes.tts_api.TTSEngine.generate_speech", fake_generate_speech
    )

    resp = await auth_client.post("/api/tts/generate", json={"text": "Fail test", "language": "de"})
    assert resp.status_code == 502
    assert "Google TTS error" in resp.json()["detail"]
