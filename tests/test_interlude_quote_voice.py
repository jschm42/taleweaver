"""The dynamic-scene transition quote is spoken in the NPC's cast TTS voice."""

import pytest

from backend.api.routes.adventures import dynamic_interlude_candidates as candidates_mod
from tests.conftest import TestSessionLocal
from tests.test_npc_give import _seed_world


@pytest.mark.asyncio
async def test_quote_candidate_carries_the_cast_voice(monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange: Bram has no stored voice; casting gives him one
        manager = await _seed_world(db)

        async def fake_cast(_db, npcs, _template_id, _session_id):
            return {npc.id: "voice-bram" for npc in npcs}, None

        monkeypatch.setattr(candidates_mod, "cast_adventure_voices", fake_cast)

        # Act
        candidates = await candidates_mod.load_interlude_candidates(db, manager.state)

        # Assert
        bram = next(c for c in candidates if c["id"] == "BRAM")
        assert bram["voice"] == "voice-bram"


@pytest.mark.asyncio
async def test_casting_failure_keeps_the_quote_candidates(monkeypatch):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        async def broken_cast(*_args):
            raise RuntimeError("no tts settings")

        monkeypatch.setattr(candidates_mod, "cast_adventure_voices", broken_cast)

        # Act
        candidates = await candidates_mod.load_interlude_candidates(db, manager.state)

        # Assert
        assert [c["id"] for c in candidates] == ["BRAM"]
        assert candidates[0]["voice"] is None
