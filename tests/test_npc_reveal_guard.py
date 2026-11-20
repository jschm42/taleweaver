"""Hidden NPCs: never discovered by the Game Master, revealed by their reveal guard or scripts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.script_validator import check_scripts_and_guards
from backend.core.world_validation.context import ValidationContext
from backend.core.world_validation.hidden_npcs import check_hidden_npc_reveal
from backend.engine.blueprint import analyze_blueprint
from backend.engine.manifest_apply.npcs import npc_metadata
from backend.engine.rules.reveal_policy import entity_is_script_only, npc_reveal_guard
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.world.world_schemas import WorldNPCSchema
from backend.models.adventure import Adventure
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal

SCENE = "CRYPT"


def _hidden_npc(entity_id: str, session_id: str, adv_id: str, guard: str) -> WorldEntity:
    return WorldEntity(
        id=entity_id,
        session_id=session_id,
        template_id=adv_id,
        name=entity_id.title(),
        description="Lurks in the dark.",
        entity_type="NPC",
        current_scene_id=SCENE,
        reveal_rule="when the player searches the crypt",
        metadata_json={"reveal_guard_expression": guard} if guard else {},
        is_hidden=True,
    )


async def _manager(db, suffix: str, guard: str) -> GameTurnManager:
    user = User(id=f"u-nrg-{suffix}", username=f"nrg{suffix}", hashed_password="x")
    db.add(user)
    await db.flush()
    adv = Adventure(id=f"adv-nrg-{suffix}", title="Crypt", owner_id=user.id, origin_id=SCENE)
    db.add(adv)
    await db.flush()
    state = SessionState(
        session_id=f"s-nrg-{suffix}",
        adventure_id=adv.id,
        user_id=user.id,
        current_scene_id=SCENE,
        entity_states={},
    )
    avatar = Avatar(id=f"av-nrg-{suffix}", user_id=user.id, template_id=adv.id, name="Alex")
    db.add_all([state, avatar, _hidden_npc("GHOUL", state.session_id, adv.id, guard)])
    await db.commit()
    logic = GameTurnManager(db=db, game_id=state.session_id, user=user)
    logic.state = state
    logic.adventure = adv
    logic.avatar = avatar
    return logic


def _revealed(event: GameEvent) -> set[str]:
    return {up.entity_id for up in event.updated_entities or [] if up.is_hidden is False}


def test_every_npc_is_script_only_for_the_game_master():
    # Arrange
    npc = SimpleNamespace(entity_type="NPC", reveal_rule="when searched")
    item = SimpleNamespace(entity_type="OBJECT", reveal_rule="when searched")

    # Act / Assert
    assert entity_is_script_only(npc)
    assert not entity_is_script_only(item)


def test_reveal_guard_is_read_from_metadata():
    # Arrange
    npc = SimpleNamespace(metadata_json={"reveal_guard_expression": " tw.vars.get('x') "})

    # Act / Assert
    assert npc_reveal_guard(npc) == "tw.vars.get('x')"


@pytest.mark.asyncio
@pytest.mark.parametrize(("passed", "expected"), [(True, {"GHOUL"}), (False, set())])
async def test_guard_reveals_hidden_npc_only_when_true(passed, expected):
    async with TestSessionLocal() as db:
        # Arrange
        logic = await _manager(db, f"g{passed}", "tw.vars.get('bell_rung') == True")
        event = GameEvent()

        # Act
        with (
            patch.object(logic, "_build_script_context", AsyncMock(return_value=object())),
            patch(
                "backend.api.routes.adventures.guardrails.npc_reveal.SwitchService.evaluate_gate_expression",
                return_value=(passed, None),
            ),
        ):
            await logic._enforce_hidden_entity_reveal(event, "I ring the bell")

        # Assert
        assert _revealed(event) == expected


@pytest.mark.asyncio
async def test_searching_never_reveals_a_hidden_npc():
    async with TestSessionLocal() as db:
        # Arrange
        logic = await _manager(db, "s", "")
        event = GameEvent(discovered_entity_ids=["GHOUL"])

        # Act
        with (
            patch("backend.core.llm_router.GameMasterLLM.__init__", return_value=None),
            patch("backend.core.llm_router.GameMasterLLM.aexecute_complex_task") as mock_llm,
        ):
            mock_llm.return_value = {"discovered_ids": ["GHOUL"]}
            await logic.guardrails._block_script_only_reveals(event)
            await logic._enforce_hidden_entity_reveal(event, "I search the crypt")

        # Assert
        assert _revealed(event) == set()
        mock_llm.assert_not_called()


def test_blueprint_reveal_guard_reaches_the_manifest_metadata():
    # Arrange
    text = "[Scene: CRYPT] Crypt\nDark.\n[NPC: GHOUL] Ghoul\nin: CRYPT\nhidden: yes\nreveal_guard: tw.vars.get('bell_rung')\n"

    # Act
    blueprint, issues = analyze_blueprint(text)
    npc = next(b for b in blueprint.blocks if b.kind == "npc")
    guard = npc.fields["reveal_guard_expression"].value
    schema_field = WorldNPCSchema.model_fields["reveal_guard_expression"]
    metadata = npc_metadata({"id": "GHOUL", "reveal_guard_expression": guard})

    # Assert
    assert issues == [] and blueprint.issues == []
    assert guard == "tw.vars.get('bell_rung')"
    assert schema_field is not None and "reveal_rule" not in WorldNPCSchema.model_fields
    assert metadata["reveal_guard_expression"] == guard


def test_validator_warns_about_ignored_npc_reveal_rule_and_checks_guard_syntax():
    # Arrange
    payload = {
        "npcs": [
            {"id": "GHOUL", "entity_type": "NPC", "is_hidden": True, "reveal_rule": "on search"},
            {
                "id": "BAT",
                "entity_type": "NPC",
                "is_hidden": True,
                "metadata_json": {"reveal_guard_expression": "tw.vars.get('x' =="},
            },
        ],
    }

    # Act
    findings = check_hidden_npc_reveal(ValidationContext.from_payload(payload))
    syntax = check_scripts_and_guards(payload)

    # Assert
    assert [f.code for f in findings] == ["npc_reveal_rule_ignored"]
    assert any("reveal_guard_expression" in (f.message or "") for f in syntax)
