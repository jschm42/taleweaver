import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.api.routes.adventures import gameplay_logic
from backend.core.auth import create_access_token
from backend.core.database import get_db
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_template(username: str, trigger: dict | None) -> str:
    async with TestSessionLocal() as db:
        user = User(username=username, hashed_password="test_hash", role="admin")
        db.add(user)
        await db.flush()

        template = AdventureTemplate(
            title="Pickup Trigger Test",
            owner_id=user.id,
            version="2.0.0",
            sequences=[{"id": "SEQ_1", "title": "Sequence 1", "order": 1}],
            is_ready=True,
            creation_status="Ready",
            original_manifest={"version": "2.0.0", "format_version": "2.0.0", "sequences": [{"id": "SEQ_1", "title": "Sequence 1", "order": 1}], "start_scene_id": "HR"},
        )
        db.add(template)
        await db.flush()

        db.add(WorldScene(id="HR", template_id=template.id, label="HR Office", description="An office."))
        db.add(Avatar(user_id=user.id, template_id=template.id, name="Arthur", inventory=[]))
        db.add(
            WorldEntity(
                id="CONTRACT",
                template_id=template.id,
                entity_type="OBJECT",
                name="Employment Contract",
                description="A thick contract.",
                current_scene_id="HR",
                is_portable=True,
                is_in_inventory=False,
                is_hidden=False,
                metadata_json={"pickup_trigger": trigger} if trigger else {},
            )
        )
        await db.commit()
        return template.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "trigger,expect_prompt,expect_text",
    [
        ({"mode": "narration", "cue": "The clerk smirks."}, True, "The clerk smirks."),
        ({"mode": "turn", "cue": ""}, True, "React to this action as the Game Master"),
        ({"mode": "silent", "cue": ""}, False, ""),
        (None, False, ""),
    ],
)
async def test_pickup_trigger_chains_llm_pass(client, setup_test_db, monkeypatch, trigger, expect_prompt, expect_text):
    prompts: list[str] = []

    async def fake_cycle(self, user_msg, auto_visualize, language=None):
        prompts.append(user_msg)
        yield 'event: final\ndata: {"status": "success"}\n\n'

    monkeypatch.setattr(gameplay_logic.GameTurnManager, "_run_llm_cycle", fake_cycle)

    username = f"pickup_user_{len(prompts)}_{expect_text[:4] or 'x'}_{trigger['mode'] if trigger else 'none'}"
    template_id = await _seed_template(username, trigger)
    headers = _auth_headers(username)

    start_res = await client.post(f"/api/adventures/{template_id}/sessions/start", headers=headers)
    assert start_res.status_code == 201
    game_id = start_res.json()["game_id"]

    res = await client.post(
        f"/api/adventures/{game_id}/chat",
        headers=headers,
        json={"content": "/take_direct CONTRACT"},
    )
    assert res.status_code == 200

    # The item is always taken deterministically.
    async with TestSessionLocal() as db:
        ent = (
            await db.execute(
                select(WorldEntity).where(WorldEntity.id == "CONTRACT", WorldEntity.session_id == game_id)
            )
        ).scalars().first()
        assert ent is not None and ent.is_in_inventory is True

    if expect_prompt:
        assert len(prompts) == 1
        assert prompts[0].startswith("[ITEM_PICKUP]")
        assert "Employment Contract" in prompts[0]
        assert expect_text in prompts[0]
        assert res.text.count("event: final") == 1
    else:
        assert prompts == []
        assert res.text.count("event: final") == 1
