import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.api.routes.adventures.session_adventure import SESSION_MANIFEST_SNAPSHOT_KEY
from backend.core.auth import create_access_token
from backend.core.database import get_db
from backend.core.script_validator import check_scripts_and_guards
from backend.engine.interaction.trigger_service import TriggerService
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.scene_helpers import runner_for_manifest, scene_helpers
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

INIT_SCRIPT = "BONUS = 5\ndef reward():\n    return BONUS\n"
CRYPT_HELPERS = "def crypt_curse():\n    tw.vars.set('cursed', True)\n"


def _manifest(**extra) -> dict:
    return {
        "init_script": INIT_SCRIPT,
        "scenes": [
            {"id": "HALL", "helpers_script": ""},
            {"id": "CRYPT", "helpers_script": CRYPT_HELPERS},
        ],
        **extra,
    }


def _state(manifest: dict) -> SessionState:
    snapshot = {"adventure": {"title": "Helpers"}, "original_manifest": manifest}
    return SessionState(
        session_id="sess_helpers",
        current_scene_id="HALL",
        entity_states={SESSION_MANIFEST_SNAPSHOT_KEY: snapshot},
    )


def test_scene_helpers_are_listed_in_manifest_order():
    # Act
    helpers = scene_helpers(_manifest())

    # Assert
    assert helpers == [("helpers_CRYPT", CRYPT_HELPERS.strip())]


def test_runner_loads_init_and_all_scene_helpers_wherever_the_player_is():
    # Arrange
    ctx = GameContext(avatar_data={}, current_scene_id="HALL", entities={})
    runner = runner_for_manifest(_manifest())

    # Act
    runner.execute_code("tw.vars.set('bonus', reward())\ncrypt_curse()", {"tw": ctx})

    # Assert
    assert ctx.changeset.var_updates == {"bonus": 5, "cursed": True}
    assert ctx.changeset.system_messages == []


def test_later_helper_block_shadows_init_script():
    # Arrange
    manifest = _manifest()
    manifest["scenes"][1]["helpers_script"] = "def reward():\n    return 99\n"
    ctx = GameContext(avatar_data={}, current_scene_id="HALL", entities={})

    # Act
    runner_for_manifest(manifest).execute_code("tw.vars.set('bonus', reward())", {"tw": ctx})

    # Assert
    assert ctx.changeset.var_updates == {"bonus": 99}


def test_broken_helper_block_reports_its_scene():
    # Arrange
    manifest = _manifest()
    manifest["scenes"][1]["helpers_script"] = "def broken(:\n"
    ctx = GameContext(avatar_data={}, current_scene_id="HALL", entities={})

    # Act
    runner_for_manifest(manifest).execute_code("tw.vars.set('bonus', reward())", {"tw": ctx})

    # Assert: init_script still loads; the error names the scene block
    assert ctx.changeset.var_updates == {"bonus": 5}
    assert any("helpers_CRYPT" in m for m in ctx.changeset.system_messages)


@pytest.mark.asyncio
async def test_inline_trigger_can_call_init_script_and_scene_helpers(setup_test_db):
    # Arrange: inline scene/exit/read triggers run through TriggerService
    state = _state(_manifest())

    # Act
    async with TestSessionLocal() as db:
        messages = await TriggerService.execute_trigger(
            db,
            state,
            trigger_name="on_enter_scene",
            target_id="CRYPT",
            script_code="tw.vars.set('bonus', reward())\ncrypt_curse()",
        )

    # Assert
    assert not any("Script error" in m for m in messages)
    assert state.entity_states["__script_vars__"] == {"bonus": 5, "cursed": True}


def test_validator_flags_ignored_statements_and_name_conflicts():
    # Arrange
    payload = {
        "adventure": {"init_script": INIT_SCRIPT},
        "scenes": [
            {
                "id": "CRYPT",
                "helpers_script": "tw.vars.set('x', 1)\ndef reward():\n    return 1\n",
            }
        ],
    }

    # Act
    findings = check_scripts_and_guards(payload)

    # Assert
    codes = {f.code for f in findings}
    assert "helpers_statement_ignored" in codes
    conflict = next(f for f in findings if f.code == "helper_name_conflict")
    assert conflict.context["name"] == "reward"
    assert conflict.context["shadowed"] == "init_script"


def test_dialog_handler_in_scene_helpers_is_not_flagged():
    # Arrange
    payload = {
        "adventure": {"init_script": ""},
        "scenes": [
            {
                "id": "CRYPT",
                "on_enter_scene_script": "tw.dialog.choose('Q?', ['A'], on_choice='on_crypt')",
                "helpers_script": "def on_crypt(answ):\n    tw.vars.set('a', answ)\n",
            }
        ],
    }

    # Act
    findings = check_scripts_and_guards(payload)

    # Assert
    assert "dialog_handler_missing" not in {f.code for f in findings}


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


@pytest.mark.asyncio
async def test_editor_scene_helpers_reach_the_manifest_also_after_rename(client, setup_test_db):
    # Arrange: a scene created in the editor has no manifest entry yet
    async with TestSessionLocal() as db:
        user = User(username="helpers_user", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        template = AdventureTemplate(
            title="Helpers", owner_id=user.id, original_manifest={"version": "2.0.0"}
        )
        db.add(template)
        await db.flush()
        db.add(WorldScene(id="CRYPT", template_id=template.id, label="Crypt", description=""))
        await db.commit()
        template_id = template.id
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'helpers_user'})}"}
    url = f"/api/adventures/{template_id}/editor/entity"

    # Act
    saved = await client.patch(
        url,
        headers=headers,
        json={"target_type": "scene", "target_id": "CRYPT", "helpers_script": CRYPT_HELPERS},
    )
    renamed = await client.patch(
        url,
        headers=headers,
        json={"target_type": "scene", "target_id": "CRYPT", "new_id": "TOMB"},
    )

    # Assert
    assert saved.status_code == 200, saved.text
    assert renamed.status_code == 200, renamed.text
    async with TestSessionLocal() as db:
        adv = await db.get(AdventureTemplate, template_id)
        row = (await db.execute(select(WorldScene).where(WorldScene.id == "TOMB"))).scalar_one()
        assert row.helpers_script == CRYPT_HELPERS.strip()
        assert scene_helpers(adv.original_manifest) == [("helpers_TOMB", CRYPT_HELPERS.strip())]
