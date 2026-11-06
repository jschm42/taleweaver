"""A session id alone grants no access: every session endpoint checks that it is the caller's."""

import pytest

from backend.core.auth import create_access_token
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


def _headers(username: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': username})}"}


async def _setup(client) -> tuple[str, str]:
    """`player` plays a session of a template that `author` owns; returns (template, game) ids."""
    async with TestSessionLocal() as db:
        author = User(username="author", hashed_password="x", role="user")
        player = User(username="player", hashed_password="x", role="admin")
        db.add_all([author, player])
        await db.flush()
        template = AdventureTemplate(
            title="Owned",
            owner_id=author.id,
            version="2.0.0",
            is_ready=True,
            creation_status="Ready",
            original_manifest={"version": "2.0.0", "start_scene_id": "HALL"},
        )
        db.add(template)
        await db.flush()
        db.add(WorldScene(id="HALL", template_id=template.id, label="Hall", description="A hall."))
        db.add(Avatar(user_id=player.id, template_id=template.id, name="Hero", inventory=[]))
        await db.commit()
        template_id = template.id

    res = await client.post(
        f"/api/adventures/{template_id}/sessions/start", headers=_headers("player")
    )
    assert res.status_code == 201
    return template_id, res.json()["game_id"]


async def test_owner_reads_own_session(client, setup_test_db):
    _template_id, game_id = await _setup(client)

    res = await client.get(f"/api/adventures/{game_id}/chat", headers=_headers("player"))

    assert res.status_code == 200


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/api/adventures/{game}/chat", None),
        ("get", "/api/adventures/{game}/chat/history?before=x", None),
        ("patch", "/api/adventures/{game}/agent/settings", {"active": False}),
        ("post", "/api/adventures/{game}/dialog/choice", {"dialog_id": "d", "index": 0}),
    ],
)
async def test_foreign_user_cannot_use_session(client, setup_test_db, method, path, body):
    _template_id, game_id = await _setup(client)
    kwargs = {"headers": _headers("author")}
    if body is not None:
        kwargs["json"] = body

    res = await getattr(client, method)(path.format(game=game_id), **kwargs)

    assert res.status_code == 404


async def test_template_owner_cannot_read_players_session_map(client, setup_test_db):
    template_id, game_id = await _setup(client)

    own = await client.get(f"/api/adventures/{template_id}/map", headers=_headers("author"))
    foreign = await client.get(
        f"/api/adventures/{template_id}/map?session_id={game_id}", headers=_headers("author")
    )

    assert own.status_code == 200
    assert foreign.status_code == 404
