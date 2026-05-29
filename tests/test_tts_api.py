import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.core.security import encryption_util
from tests.conftest import TestSessionLocal
from backend.models.user import User

pytestmark = pytest.mark.asyncio


@pytest.mark.asyncio
async def test_generate_tts_accepts_non_uuid_ids(auth_client: AsyncClient, monkeypatch):
    """TTS generation must accept legacy/non-UUID session and adventure ids."""
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.username == "test_user"))).scalars().first()
        assert user is not None
        user.tts_settings = {
            "enabled": True,
            "provider": "google",
            "selected_model": "gemini-2.5-flash-preview-tts",
            "selected_voice": "Puck",
            "use_vocal_tags": True,
            "speech_rate": 1.0,
            "elevenlabs_voice_id": "",
        }
        user.encrypted_api_keys = {"google": encryption_util.encrypt_key("test-api-key")}
        await session.commit()

    async def fake_generate_speech(**kwargs):
        return "/data/audio/test.wav"

    monkeypatch.setattr("backend.api.routes.tts_api.TTSEngine.generate_speech", fake_generate_speech)

    payload = {
        "text": "Hello from TaleWeaver.",
        "session_id": "session-1",
        "adventure_id": "adv-legacy",
    }

    resp = await auth_client.post("/api/tts/generate", json=payload)

    assert resp.status_code == 200
    assert resp.json().get("audio_url") == "/data/audio/test.wav"
