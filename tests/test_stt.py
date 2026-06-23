import io
import wave
import numpy as np
import pytest
from httpx import AsyncClient

from backend.core.auth import create_access_token, get_password_hash
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


async def _create_test_user(*, username: str, role: str = "user") -> None:
    async with TestSessionLocal() as session:
        session.add(
            User(
                username=username,
                hashed_password=get_password_hash("pw"),
                role=role,
                game_settings={
                    "whisper_model": "tiny"
                }
            )
        )
        await session.commit()


def create_dummy_wav(sample_rate=16000, channels=1, sampwidth=2, duration_sec=1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        
        n_samples = int(sample_rate * duration_sec)
        samples = np.zeros(n_samples, dtype=np.int16)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


async def test_stt_transcribe_success(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    await _create_test_user(username="stt_user")

    captured_args = {}

    class MockWhisperModel:
        def transcribe(self, audio_data, **kwargs):
            captured_args["audio_data"] = audio_data
            return {"text": "Hello, world! This is a test."}

    def fake_load_model(model_name):
        captured_args["model_name"] = model_name
        return MockWhisperModel()

    monkeypatch.setattr(
        "backend.api.routes.stt_api.get_whisper_model",
        fake_load_model
    )

    wav_bytes = create_dummy_wav(sample_rate=16000, channels=1, sampwidth=2)
    files = {"file": ("test.wav", wav_bytes, "audio/wav")}
    
    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'stt_user'})}"}
    response = await client.post("/api/stt/transcribe", headers=headers, files=files)

    assert response.status_code == 200
    assert response.json()["text"] == "Hello, world! This is a test."
    assert captured_args["model_name"] == "tiny"
    assert isinstance(captured_args["audio_data"], np.ndarray)
    assert len(captured_args["audio_data"]) == 16000


async def test_stt_transcribe_invalid_samplerate(client: AsyncClient) -> None:
    await _create_test_user(username="stt_user_err")

    wav_bytes = create_dummy_wav(sample_rate=8000, channels=1, sampwidth=2)
    files = {"file": ("test.wav", wav_bytes, "audio/wav")}
    
    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'stt_user_err'})}"}
    response = await client.post("/api/stt/transcribe", headers=headers, files=files)

    assert response.status_code == 400
    assert "sample rate" in response.json()["detail"].lower()
