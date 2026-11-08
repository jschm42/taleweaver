"""Paged profile session history: status filter, search, sorting, counts, ownership."""

from datetime import timedelta

import pytest

from backend.core.auth import create_access_token
from backend.crud.crud_player_sessions import SESSION_MANIFEST_SNAPSHOT_KEY
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.base import utc_now
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio
URL = "/api/users/me/sessions"
SEQUENCES = [{"id": "s1", "title": "Arrival", "order": 1}, {"id": "s2", "title": "End", "order": 2}]


def _headers(username: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': username})}"}


async def _add_session(db, user, template, *, title, avatar, status, exp, age_days, states=None):
    avatar_row = Avatar(user_id=user.id, template_id=template.id if template else None, name=avatar)
    avatar_row.exp = exp
    db.add(avatar_row)
    await db.flush()
    session = GameSession(
        user_id=user.id,
        avatar_id=avatar_row.id,
        template_id=template.id if template else None,
        adventure_title=title,
        status=status,
        created_at=utc_now() - timedelta(days=age_days),
        updated_at=utc_now() - timedelta(days=age_days),
    )
    db.add(session)
    await db.flush()
    db.add(SessionState(session_id=session.id, entity_states=states or {}, active_sequence_id="s2"))


async def _seed() -> None:
    async with TestSessionLocal() as db:
        player = User(username="player", hashed_password="x", role="user")
        other = User(username="other", hashed_password="x", role="user")
        db.add_all([player, other])
        await db.flush()
        template = AdventureTemplate(
            title="Dragon Keep", owner_id=player.id, version="2.0.0", sequences=SEQUENCES
        )
        db.add(template)
        await db.flush()
        await _add_session(
            db,
            player,
            template,
            title="Dragon Keep",
            avatar="Ayla",
            status="active",
            exp=10,
            age_days=1,
        )
        await _add_session(
            db,
            player,
            template,
            title="Dragon Keep",
            avatar="Borin",
            status="completed",
            exp=90,
            age_days=5,
        )
        await _add_session(
            db,
            player,
            None,
            title="Lost 100% Tomb",
            avatar="Cyra",
            status="game_over",
            exp=40,
            age_days=3,
            states={SESSION_MANIFEST_SNAPSHOT_KEY: {"adventure": {"sequences": SEQUENCES}}},
        )
        await _add_session(
            db,
            other,
            template,
            title="Dragon Keep",
            avatar="Intruder",
            status="active",
            exp=999,
            age_days=0,
        )
        await db.commit()


async def test_lists_only_own_sessions_newest_first_with_counts(client, setup_test_db):
    await _seed()

    res = await client.get(URL, headers=_headers("player"))

    assert res.status_code == 200
    page = res.json()
    assert [s["avatar_name"] for s in page["items"]] == ["Ayla", "Cyra", "Borin"]
    assert page["total"] == 3
    assert page["counts"] == {"all": 3, "active": 1, "completed": 1, "game_over": 1, "archived": 0}
    assert page["totals"] == page["counts"]


async def test_deleted_template_keeps_sequences_from_snapshot(client, setup_test_db):
    await _seed()

    res = await client.get(URL, params={"status": "game_over"}, headers=_headers("player"))

    item = res.json()["items"][0]
    assert item["adventure_title"] == "Lost 100% Tomb"
    assert item["sequences_total"] == 2
    assert item["sequences_completed"] == 1


async def test_search_matches_title_or_avatar_and_escapes_wildcards(client, setup_test_db):
    await _seed()

    by_title = (await client.get(URL, params={"search": "100%"}, headers=_headers("player"))).json()
    by_avatar = (await client.get(URL, params={"search": "bor"}, headers=_headers("player"))).json()

    assert [s["avatar_name"] for s in by_title["items"]] == ["Cyra"]
    assert by_title["counts"]["all"] == 1
    assert by_title["totals"]["all"] == 3
    assert [s["avatar_name"] for s in by_avatar["items"]] == ["Borin"]


async def test_sort_and_pagination(client, setup_test_db):
    await _seed()

    first = (
        await client.get(URL, params={"sort": "xp", "limit": 2}, headers=_headers("player"))
    ).json()
    second = (
        await client.get(
            URL, params={"sort": "xp", "limit": 2, "offset": 2}, headers=_headers("player")
        )
    ).json()

    assert [s["xp"] for s in first["items"]] == [90, 40]
    assert [s["xp"] for s in second["items"]] == [10]
    assert first["total"] == 3


async def test_rejects_unknown_status_and_sort(client, setup_test_db):
    await _seed()

    bad_status = await client.get(URL, params={"status": "deleted"}, headers=_headers("player"))
    bad_sort = await client.get(URL, params={"sort": "random"}, headers=_headers("player"))

    assert bad_status.status_code == 422
    assert bad_sort.status_code == 422
