import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.auth import get_password_hash
from backend.engine.rules.sequence_walkthrough import (
    apply_legacy_walkthrough,
    format_walkthrough_steps,
    sequence_walkthrough_steps,
)
from backend.engine.rules.walkthrough_unlocks import (
    revealed_sequence_ids,
    walkthrough_payload,
    walkthrough_status,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User

_SEQUENCES = [
    {"id": "SEQ_2", "order": 2, "title": "The Vault", "walkthrough": "Open the vault."},
    {
        "id": "SEQ_1",
        "order": 1,
        "title": "The Temple",
        "walkthrough": "1. Enter temple\n2. Solve puzzle",
    },
    {"id": "SEQ_3", "order": 3, "title": "Epilogue", "walkthrough": ""},
]


def test_sequence_walkthrough_steps_follow_story_order_and_mark_active():
    # Act
    steps = sequence_walkthrough_steps(_SEQUENCES, active_sequence_id="SEQ_2")

    # Assert
    assert [step["title"] for step in steps] == ["The Temple", "The Vault (current)"]
    assert steps[0]["content"] == "1. Enter temple\n2. Solve puzzle"


def test_sequence_walkthrough_steps_default_to_first_sequence_and_format():
    # Act
    steps = sequence_walkthrough_steps(_SEQUENCES)
    text = format_walkthrough_steps(steps)

    # Assert
    assert steps[0]["title"] == "The Temple (current)"
    assert text.startswith("## The Temple (current)\n1. Enter temple")
    assert sequence_walkthrough_steps(None) == []


def test_apply_legacy_walkthrough_only_converts_templates_without_sequences():
    # Arrange
    legacy = AdventureTemplate(id="legacy", title="Legacy", plot="Old plot", sequences=None)
    modern = AdventureTemplate(id="modern", title="Modern", sequences=list(_SEQUENCES))

    # Act
    apply_legacy_walkthrough(legacy, "Do everything.")
    apply_legacy_walkthrough(modern, "Ignored.")

    # Assert
    assert legacy.sequences[0]["id"] == "SEQ_1_MAIN"
    assert legacy.sequences[0]["walkthrough"] == "Do everything."
    assert legacy.sequences[0]["description"] == "Old plot"
    assert modern.sequences == _SEQUENCES


@pytest.mark.asyncio
async def test_walkthrough_reveal_deducts_150_xp_and_grants_negative_award(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = User(
            username="walkthrough-player",
            hashed_password=get_password_hash("pw"),
            role="user",
            earned_awards=[],
        )
        adv = AdventureTemplate(
            id="adv-walkthrough",
            title="Walkthrough Adventure",
            owner_id="owner",
            sequences=[dict(seq) for seq in _SEQUENCES],
            awards=[
                {
                    "key": "GOLD_EXPLORER",
                    "title": "Gold Explorer",
                    "tier": "gold",
                    "description": "Found gold",
                }
            ],
        )
        db.add_all([user, adv])
        await db.flush()

        avatar = Avatar(
            id="av-walkthrough",
            template_id=adv.id,
            user_id=user.id,
            name="Hero",
            exp=200,
        )
        session = GameSession(
            id="session-walkthrough",
            user_id=user.id,
            avatar_id=avatar.id,
            template_id=adv.id,
            adventure_title=adv.title,
        )
        state = SessionState(
            session_id=session.id,
            template_id=adv.id,
            avatar_id=avatar.id,
            user_id=user.id,
            is_walkthrough_revealed=False,
            current_scene_id="SCENE_1",
        )
        db.add_all([avatar, session, state])
        await db.commit()

        manager = GameTurnManager(db, session.id, user)
        assert await manager.initialize()

        # Check that the universal negative award is present even before reveal (unearned)
        initial_awards = await manager.state_applier._build_awards_payload(adv)
        initial_spoiler = next(
            (aw for aw in initial_awards if aw.get("key") == "SPOILER_SEEKER"), None
        )
        assert initial_spoiler is not None
        assert initial_spoiler.get("tier") == "negative"
        assert initial_spoiler.get("is_earned") is False

        # Trigger walkthrough reveal via process_turn
        chunks = []
        async for chunk in manager.process_turn("/walkthrough reveal"):
            chunks.append(chunk)

        combined = "".join(chunks)
        assert "Walkthrough unlocked" in combined
        assert "-150 XP" in combined
        assert revealed_sequence_ids(manager.state) == ["SEQ_1"]
        # Avatar XP was 200, should now be 50 (200 - 150)
        assert manager.avatar.exp == 50

        # Check negative award was granted
        awards = user.earned_awards or []
        assert any(
            aw.get("key") == "SPOILER_SEEKER" and aw.get("tier") == "negative" for aw in awards
        )

        # Check _build_awards_payload includes the negative award as earned
        payload_awards = await manager.state_applier._build_awards_payload(adv)
        spoiler_award = next(
            (aw for aw in payload_awards if aw.get("key") == "SPOILER_SEEKER"), None
        )
        assert spoiler_award is not None
        assert spoiler_award.get("tier") == "negative"
        assert spoiler_award.get("is_earned") is True

        # Same chapter again: nothing more is charged
        repeat = "".join([c async for c in manager.process_turn("/walkthrough reveal")])
        assert "already unlocked" in repeat
        assert manager.avatar.exp == 50

        # Next chapter: only its walkthrough can be unlocked, for another 150 XP
        manager.state.active_sequence_id = "SEQ_2"
        await db.commit()
        status = walkthrough_status(manager.adventure, manager.state)
        assert [s["sequence_id"] for s in status["steps"]] == ["SEQ_1"]
        assert status["current_revealed"] is False
        async for _ in manager.process_turn("/walkthrough reveal"):
            pass
        assert revealed_sequence_ids(manager.state) == ["SEQ_1", "SEQ_2"]
        assert manager.avatar.exp == -100


class _State:
    def __init__(self, active=None, revealed=None, legacy=False):
        self.active_sequence_id = active
        self.entity_states = {"__walkthrough_revealed__": revealed} if revealed else {}
        self.is_walkthrough_revealed = legacy


class _Adventure:
    sequences = _SEQUENCES


def test_walkthrough_status_never_shows_later_chapters():
    # Act
    sealed = walkthrough_status(_Adventure(), _State(active="SEQ_1"))
    legacy = walkthrough_status(_Adventure(), _State(active="SEQ_1", legacy=True))
    unlocked = walkthrough_status(_Adventure(), _State(active="SEQ_2", revealed=["SEQ_2"]))

    # Assert
    assert sealed["steps"] == [] and sealed["current"]["sequence_id"] == "SEQ_1"
    assert walkthrough_payload(sealed, 10)["can_reveal"] is True
    assert [s["sequence_id"] for s in legacy["steps"]] == ["SEQ_1"]
    assert [s["sequence_id"] for s in unlocked["steps"]] == ["SEQ_2"]
    assert walkthrough_payload(unlocked, 10)["can_reveal"] is False


def test_walkthrough_status_without_guide_for_current_chapter():
    # Act: SEQ_3 has no walkthrough text
    status = walkthrough_status(_Adventure(), _State(active="SEQ_3", revealed=["SEQ_1"]))

    # Assert
    assert status["current"] is None
    assert [s["sequence_id"] for s in status["steps"]] == ["SEQ_1"]
    assert walkthrough_payload(status, 0)["can_reveal"] is False
