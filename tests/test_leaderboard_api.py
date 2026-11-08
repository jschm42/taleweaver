"""Tests for the leaderboard API (/api/leaderboard)."""

from typing import Any, Optional

import pytest
from httpx import AsyncClient

from backend.core.auth import create_access_token, get_password_hash
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

AWARD_DRAGON = {"key": "dragon_slayer", "title": "Dragon Slayer", "adventure": "Ember Peaks"}
AWARD_SCHOLAR = {"key": "scholar", "title": "Scholar", "adventure": "Old Library"}
AWARD_SCOUT = {"key": "scout", "title": "Scout", "adventure": "Ember Peaks"}


async def _create_user(
    username: str,
    *,
    awards: Optional[list[Any]] = None,
    bio: Optional[str] = None,
    profile_image_url: Optional[str] = None,
) -> str:
    async with TestSessionLocal() as session:
        user = User(
            username=username,
            hashed_password=get_password_hash("pw"),
            role="user",
            bio=bio,
            profile_image_url=profile_image_url,
            earned_awards=awards,
        )
        session.add(user)
        await session.commit()
        return user.id


async def _add_session(
    user_id: str,
    *,
    exp: int = 0,
    quests: Optional[list[Any]] = None,
    state_user_id: Optional[str] = "same",
) -> None:
    """Seeds an avatar, game session and session state for a user."""
    async with TestSessionLocal() as session:
        avatar = Avatar(user_id=user_id, name=f"Hero of {user_id[:8]}", exp=exp)
        session.add(avatar)
        await session.flush()
        game = GameSession(user_id=user_id, avatar_id=avatar.id)
        session.add(game)
        await session.flush()
        session.add(
            SessionState(
                session_id=game.id,
                user_id=user_id if state_user_id == "same" else state_user_id,
                avatar_id=avatar.id,
                quests=quests or [],
            )
        )
        await session.commit()


def _quests(completed: int = 0, failed: int = 0, active: int = 0) -> list[dict[str, str]]:
    return (
        [{"id": f"c{i}", "status": "completed"} for i in range(completed)]
        + [{"id": f"f{i}", "status": "failed"} for i in range(failed)]
        + [{"id": f"a{i}", "status": "active"} for i in range(active)]
    )


async def _seed_players() -> dict[str, str]:
    """Builds a field whose expected order exercises every ranking tiebreak.

    Expected order: bob, alice, carol, dave, erin, test_user.
    """
    ids = {
        "alice": await _create_user(
            "alice",
            awards=[AWARD_DRAGON],
            bio="Fearless explorer",
            profile_image_url="/data/data/users/alice.png",
        ),
        "bob": await _create_user("bob", awards=[AWARD_DRAGON, AWARD_SCHOLAR]),
        "carol": await _create_user("carol"),
        "dave": await _create_user("dave"),
        "erin": await _create_user("erin"),
    }
    # alice & bob tie on XP (300); bob wins on awards.
    await _add_session(ids["alice"], exp=200, quests=_quests(completed=1, active=1))
    await _add_session(ids["alice"], exp=100)
    await _add_session(ids["bob"], exp=300)
    # carol, dave & erin tie on XP (50) and awards (0).
    await _add_session(ids["carol"], exp=50, quests=_quests(completed=2))
    # dave has the same completed count as carol but one failure; the second
    # state has no user_id and must fall back to the game session owner.
    await _add_session(ids["dave"], exp=50, quests=_quests(completed=1))
    await _add_session(ids["dave"], quests=_quests(completed=1, failed=1), state_user_id=None)
    await _add_session(ids["erin"], exp=50, quests=_quests(completed=1))
    return ids


def _by_name(players: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {player["username"]: player for player in players}


# ---------------------------------------------------------------------------
# GET /api/leaderboard
# ---------------------------------------------------------------------------


async def test_leaderboard_ranks_by_xp_awards_completed_and_failed(
    auth_client: AsyncClient,
) -> None:
    # Arrange
    await _seed_players()

    # Act
    response = await auth_client.get("/api/leaderboard")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["total_players"] == 6
    usernames = [player["username"] for player in body["players"]]
    assert usernames == ["bob", "alice", "carol", "dave", "erin", "test_user"]
    assert [player["rank"] for player in body["players"]] == [1, 2, 3, 4, 5, 6]


async def test_leaderboard_includes_profile_details(auth_client: AsyncClient) -> None:
    # Arrange
    ids = await _seed_players()

    # Act
    response = await auth_client.get("/api/leaderboard")

    # Assert
    alice = _by_name(response.json()["players"])["alice"]
    assert alice["id"] == ids["alice"]
    assert alice["username"] == "alice"
    assert alice["bio"] == "Fearless explorer"
    assert alice["profile_image_url"] == "/data/users/alice.png"
    assert alice["rank"] == 2


async def test_leaderboard_tallies_quests_from_session_state(auth_client: AsyncClient) -> None:
    # Arrange
    await _seed_players()

    # Act
    response = await auth_client.get("/api/leaderboard")

    # Assert
    players = _by_name(response.json()["players"])
    tallies = {
        name: (players[name]["completed_quests"], players[name]["failed_quests"])
        for name in players
    }
    assert tallies == {
        "alice": (1, 0),
        "bob": (0, 0),
        "carol": (2, 0),
        "dave": (2, 1),
        "erin": (1, 0),
        "test_user": (0, 0),
    }


async def test_leaderboard_quest_tally_ignores_malformed_entries(
    auth_client: AsyncClient,
) -> None:
    # Arrange
    user_id = await _create_user("mixed")
    await _add_session(
        user_id,
        quests=[
            {"status": "Completed"},
            {"status": "FAILED"},
            {"status": None},
            {"title": "no status"},
            "not-a-dict",
        ],
    )

    # Act
    response = await auth_client.get("/api/leaderboard")

    # Assert
    mixed = _by_name(response.json()["players"])["mixed"]
    assert mixed["completed_quests"] == 1
    assert mixed["failed_quests"] == 1


async def test_leaderboard_sums_xp_from_avatars(auth_client: AsyncClient) -> None:
    # Arrange
    await _seed_players()

    # Act
    response = await auth_client.get("/api/leaderboard")

    # Assert
    players = _by_name(response.json()["players"])
    assert {name: players[name]["total_xp"] for name in players} == {
        "alice": 300,
        "bob": 300,
        "carol": 50,
        "dave": 50,
        "erin": 50,
        "test_user": 0,
    }


async def test_leaderboard_tallies_awards_from_user(auth_client: AsyncClient) -> None:
    # Arrange
    await _seed_players()
    await _create_user("odd_awards", awards=[AWARD_SCOUT, "legacy-string", 42])

    # Act
    response = await auth_client.get("/api/leaderboard")

    # Assert
    players = _by_name(response.json()["players"])
    assert players["bob"]["total_awards"] == 2
    assert players["bob"]["earned_awards"] == [AWARD_DRAGON, AWARD_SCHOLAR]
    assert players["alice"]["total_awards"] == 1
    assert players["alice"]["earned_awards"] == [AWARD_DRAGON]
    assert players["carol"]["total_awards"] == 0
    assert players["carol"]["earned_awards"] == []
    assert players["odd_awards"]["total_awards"] == 1
    assert players["odd_awards"]["earned_awards"] == [AWARD_SCOUT]


async def test_leaderboard_requires_authentication(client: AsyncClient) -> None:
    # Act
    response = await client.get("/api/leaderboard")

    # Assert
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/leaderboard/player/{user_id}
# ---------------------------------------------------------------------------


async def test_player_entry_returns_requested_player_with_rank(
    auth_client: AsyncClient,
) -> None:
    # Arrange
    ids = await _seed_players()

    # Act
    response = await auth_client.get(f"/api/leaderboard/player/{ids['dave']}")

    # Assert
    assert response.status_code == 200
    dave = response.json()
    assert dave["id"] == ids["dave"]
    assert dave["username"] == "dave"
    assert dave["rank"] == 4
    assert dave["total_xp"] == 50
    assert dave["completed_quests"] == 2
    assert dave["failed_quests"] == 1
    assert dave["total_awards"] == 0


async def test_player_entry_rank_matches_full_leaderboard(auth_client: AsyncClient) -> None:
    # Arrange
    ids = await _seed_players()
    board = _by_name((await auth_client.get("/api/leaderboard")).json()["players"])

    # Act
    response = await auth_client.get(f"/api/leaderboard/player/{ids['bob']}")

    # Assert
    assert response.status_code == 200
    assert response.json() == board["bob"]


async def test_player_entry_returns_404_for_unknown_player(auth_client: AsyncClient) -> None:
    # Arrange
    await _seed_players()

    # Act
    response = await auth_client.get("/api/leaderboard/player/does-not-exist")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Player not found"


async def test_player_entry_requires_authentication(client: AsyncClient) -> None:
    # Arrange
    user_id = await _create_user("anon_target")

    # Act
    response = await client.get(f"/api/leaderboard/player/{user_id}")

    # Assert
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/leaderboard/player/{user_id}/awards
# ---------------------------------------------------------------------------


async def test_player_awards_returns_earned_awards(auth_client: AsyncClient) -> None:
    # Arrange
    ids = await _seed_players()

    # Act
    response = await auth_client.get(f"/api/leaderboard/player/{ids['bob']}/awards")

    # Assert
    assert response.status_code == 200
    assert response.json() == [AWARD_DRAGON, AWARD_SCHOLAR]


async def test_player_awards_returns_empty_list_without_awards(
    auth_client: AsyncClient,
) -> None:
    # Arrange
    ids = await _seed_players()

    # Act
    response = await auth_client.get(f"/api/leaderboard/player/{ids['carol']}/awards")

    # Assert
    assert response.status_code == 200
    assert response.json() == []


async def test_player_awards_returns_404_for_unknown_player(auth_client: AsyncClient) -> None:
    # Act
    response = await auth_client.get("/api/leaderboard/player/does-not-exist/awards")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Player not found"


async def test_player_awards_accessible_with_another_users_token(client: AsyncClient) -> None:
    # Arrange
    target_id = await _create_user("target", awards=[AWARD_SCOUT])
    await _create_user("viewer")
    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'viewer'})}"}

    # Act
    response = await client.get(f"/api/leaderboard/player/{target_id}/awards", headers=headers)

    # Assert
    assert response.status_code == 200
    assert response.json() == [AWARD_SCOUT]


async def test_player_awards_requires_authentication(client: AsyncClient) -> None:
    # Arrange
    user_id = await _create_user("anon_awards", awards=[AWARD_SCOUT])

    # Act
    response = await client.get(f"/api/leaderboard/player/{user_id}/awards")

    # Assert
    assert response.status_code == 401
