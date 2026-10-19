"""Tests for enhanced trigger system, deterministic guards, and sequence persistence."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.adventures.schemas import AdventureTemplateUpdate
from backend.engine.trigger_service import TriggerService
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldExit, WorldScene
from backend.schemas.adventure import SequenceSchema


def test_sequence_schema_new_trigger_fields():
    """Verify SequenceSchema supports start/end trigger fields."""
    seq = SequenceSchema(
        id="SEQ_1",
        order=1,
        title="Chapter 1",
        on_start_sequence_script="tw.story.narrate('Chapter 1 begins')",
        on_start_sequence_text="Chapter 1 intro",
        on_end_sequence_script="tw.story.narrate('Chapter 1 ends')",
        on_end_sequence_text="Chapter 1 conclusion",
    )
    assert seq.on_start_sequence_script == "tw.story.narrate('Chapter 1 begins')"
    assert seq.on_end_sequence_script == "tw.story.narrate('Chapter 1 ends')"


def test_adventure_template_update_sequences():
    """Verify AdventureTemplateUpdate accepts sequences and awards."""
    update = AdventureTemplateUpdate(
        sequences=[
            {
                "id": "SEQ_1",
                "order": 1,
                "title": "Escape",
                "on_start_sequence_script": "tw.vars.set('escaped', False)",
            }
        ]
    )
    dumped = update.model_dump(exclude_unset=True)
    assert "sequences" in dumped
    assert len(dumped["sequences"]) == 1
    assert dumped["sequences"][0]["id"] == "SEQ_1"


def _mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    mock_res_avatar = MagicMock()
    mock_res_avatar.scalars.return_value.first.return_value = None
    mock_res_entities = MagicMock()
    mock_res_entities.scalars.return_value.all.return_value = []

    async def mock_execute(stmt):
        stmt_str = str(stmt)
        if "avatar" in stmt_str.lower():
            return mock_res_avatar
        return mock_res_entities

    db.execute.side_effect = mock_execute
    return db


@pytest.mark.asyncio
async def test_trigger_service_evaluate_guard_truthy():
    """Test TriggerService evaluate_guard with truthy expression."""
    db = _mock_db()
    state = SessionState(
        session_id="test_sess", entity_states={"__script_vars__": {"safe_code": 42}}
    )

    passed, error = await TriggerService.evaluate_guard(
        db=db,
        state=state,
        guard_expression="tw.vars.get('safe_code') == 42",
    )
    assert passed is True
    assert error is None


@pytest.mark.asyncio
async def test_trigger_service_evaluate_guard_falsy():
    """Test TriggerService evaluate_guard with falsy expression."""
    db = _mock_db()
    state = SessionState(
        session_id="test_sess", entity_states={"__script_vars__": {"safe_code": 99}}
    )

    passed, error = await TriggerService.evaluate_guard(
        db=db,
        state=state,
        guard_expression="tw.vars.get('safe_code') == 42",
    )
    assert passed is False
    assert error is not None


@pytest.mark.asyncio
async def test_trigger_service_evaluate_guard_empty():
    """Empty or None expression always passes."""
    db = _mock_db()
    state = SessionState(session_id="test_sess")
    passed_empty, _ = await TriggerService.evaluate_guard(db, state, "")
    passed_none, _ = await TriggerService.evaluate_guard(db, state, None)
    assert passed_empty is True
    assert passed_none is True


@pytest.mark.asyncio
async def test_trigger_service_execute_trigger_with_debug(monkeypatch):
    """Verify execute_trigger adds debug message when debug is enabled."""
    db = _mock_db()
    state = SessionState(session_id="test_sess")
    monkeypatch.setattr("backend.engine.trigger_service.settings.TALEWEAVER_DEBUG_ENABLED", True)

    messages = await TriggerService.execute_trigger(
        db=db,
        state=state,
        trigger_name="on_read",
        target_id="SCROLL_01",
        script_code="tw.story.narrate('Secret unlocked!')",
        narrative_text="A whisper in the dark.",
    )

    # Should contain debug message first
    assert any("[DEBUG: Trigger fired] on_read on SCROLL_01" in m for m in messages)
    # Should contain text cue and narration
    assert any("A whisper in the dark." in m for m in messages)
    assert any("Secret unlocked!" in m for m in messages)
    # Messages should be added to db
    assert db.add.called


@pytest.mark.asyncio
async def test_trigger_service_execute_trigger_without_debug(monkeypatch):
    """Verify execute_trigger does not add debug message when debug is disabled."""
    db = _mock_db()
    state = SessionState(session_id="test_sess")
    monkeypatch.setattr("backend.engine.trigger_service.settings.TALEWEAVER_DEBUG_ENABLED", False)

    messages = await TriggerService.execute_trigger(
        db=db,
        state=state,
        trigger_name="on_read",
        target_id="SCROLL_01",
        script_code="",
        narrative_text="A whisper in the dark.",
    )

    assert not any("[DEBUG: Trigger fired]" in m for m in messages)
    assert any("A whisper in the dark." in m for m in messages)


def test_world_exit_and_scene_model_fields():
    """Verify SQLAlchemy models have the new trigger/guard columns."""
    exit_model = WorldExit()
    exit_model.unlock_expression = "tw.vars.get('unlocked') == True"
    exit_model.on_unlock_success_script = "tw.story.narrate('Door clicks open')"
    exit_model.on_unlock_success_text = "Click!"
    exit_model.on_unlock_failure_script = "tw.player.damage(5)"
    exit_model.on_unlock_failure_text = "Ouch!"

    exit_model.on_exit_used_script = "tw.vars.set('crossed_bridge', True)"
    exit_model.on_exit_used_text = "You cross the rickety wooden bridge."

    assert exit_model.unlock_expression == "tw.vars.get('unlocked') == True"
    assert exit_model.on_unlock_success_script == "tw.story.narrate('Door clicks open')"
    assert exit_model.on_exit_used_script == "tw.vars.set('crossed_bridge', True)"
    assert exit_model.on_exit_used_text == "You cross the rickety wooden bridge."

    scene_model = WorldScene()
    scene_model.on_leave_scene_script = "tw.vars.set('left_room', True)"
    scene_model.on_leave_scene_text = "You step into the hallway."
    assert scene_model.on_leave_scene_script == "tw.vars.set('left_room', True)"
    assert scene_model.on_leave_scene_text == "You step into the hallway."


@pytest.mark.asyncio
async def test_unlock_exit_direct_with_guard_success(monkeypatch):
    """Test unlocking an exit directly when unlock_expression passes."""
    from backend.api.routes.adventures.gameplay import unlock_exit
    from backend.models.user import User

    db = _mock_db()
    state = SessionState(
        session_id="test_sess",
        template_id="tpl_1",
        avatar_id="av_1",
        entity_states={"__script_vars__": {"bridge_lowered": True}},
    )
    exit_obj = WorldExit(
        id="EXIT_1",
        session_id="test_sess",
        is_locked=True,
        unlock_expression="tw.vars.get('bridge_lowered') == True",
        on_unlock_success_script="tw.vars.set('unlocked_direct', True)",
        on_unlock_success_text="Mechanism disengages.",
    )

    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay.AdventureLogic.resolve_session_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay._resolve_session_exit",
        AsyncMock(return_value=exit_obj),
    )

    user = User(id="user_1")
    res = await unlock_exit(
        game_id="test_sess",
        exit_id="EXIT_1",
        db=db,
        current_user=user,
    )
    assert res["status"] == "ok"
    assert res["is_locked"] is False
    assert exit_obj.is_locked is False
    assert db.commit.called


@pytest.mark.asyncio
async def test_unlock_exit_direct_with_guard_failure(monkeypatch):
    """Test unlocking an exit directly when unlock_expression fails."""
    from fastapi import HTTPException

    from backend.api.routes.adventures.gameplay import unlock_exit
    from backend.models.user import User

    db = _mock_db()
    state = SessionState(
        session_id="test_sess",
        template_id="tpl_1",
        avatar_id="av_1",
        entity_states={"__script_vars__": {"bridge_lowered": False}},
    )
    exit_obj = WorldExit(
        id="EXIT_1",
        session_id="test_sess",
        is_locked=True,
        unlock_expression="tw.vars.get('bridge_lowered') == True",
        on_unlock_failure_script="tw.vars.set('failed_attempt', True)",
        on_unlock_failure_text="The mechanism is firmly locked.",
    )

    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay.AdventureLogic.resolve_session_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay._resolve_session_exit",
        AsyncMock(return_value=exit_obj),
    )

    user = User(id="user_1")
    with pytest.raises(HTTPException) as exc_info:
        await unlock_exit(
            game_id="test_sess",
            exit_id="EXIT_1",
            db=db,
            current_user=user,
        )
    assert exc_info.value.status_code == 403
    assert "mechanism is firmly locked" in exc_info.value.detail
    assert exit_obj.is_locked is True


@pytest.mark.asyncio
async def test_unlock_container_direct_with_guard_success(monkeypatch):
    """Test unlocking a container directly when unlock_expression passes."""
    from backend.api.routes.adventures.gameplay import unlock_container
    from backend.models.user import User
    from backend.models.world_entity import WorldEntity

    db = _mock_db()
    state = SessionState(
        session_id="test_sess",
        template_id="tpl_1",
        avatar_id="av_1",
        entity_states={"__script_vars__": {"secret_found": True}},
    )
    chest = WorldEntity(
        id="CHEST_1",
        session_id="test_sess",
        entity_type="OBJECT",
        item_type="CONTAINER",
        name="Ancient Chest",
        metadata_json={
            "unlock_expression": "tw.vars.get('secret_found') == True",
            "on_unlock_success_text": "The chest opens with a click.",
        },
    )

    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay.AdventureLogic.resolve_session_state",
        AsyncMock(return_value=state),
    )

    mock_res_chest = MagicMock()
    mock_res_chest.scalars.return_value.first.return_value = chest
    mock_res_chest.scalars.return_value.all.return_value = [chest]

    async def mock_exec(stmt):
        stmt_str = str(stmt).lower()
        if "avatar" in stmt_str:
            mock_res_av = MagicMock()
            mock_res_av.scalars.return_value.first.return_value = None
            return mock_res_av
        return mock_res_chest

    db.execute.side_effect = mock_exec

    user = User(id="user_1")
    res = await unlock_container(
        game_id="test_sess",
        entity_id="CHEST_1",
        db=db,
        current_user=user,
    )
    assert res["status"] == "ok"
    assert res["locked"] is False
    assert state.entity_states["CHEST_1"]["locked"] is False
    assert db.commit.called


@pytest.mark.asyncio
async def test_traverse_exit_triggers_on_exit_used(monkeypatch):
    """Test traverse_exit triggers on_leave_scene and on_exit_used."""
    from backend.api.routes.adventures.gameplay import traverse_exit
    from backend.models.user import User

    db = _mock_db()
    state = SessionState(
        session_id="test_sess",
        template_id="tpl_1",
        avatar_id="av_1",
        current_scene_id="SCENE_A",
        entity_states={},
    )
    exit_obj = WorldExit(
        id="EXIT_AB",
        session_id="test_sess",
        from_scene_id="SCENE_A",
        to_scene_id="SCENE_B",
        exit_type="one_way",
        is_locked=False,
        on_exit_used_script="tw.vars.set('used_exit', True)",
        on_exit_used_text="You stride through the iron portal.",
    )
    old_scene = WorldScene(
        id="SCENE_A",
        session_id="test_sess",
        label="Dungeon Cell",
        description="A dark cell.",
        on_leave_scene_script="tw.vars.set('left_cell', True)",
        on_leave_scene_text="You leave the cell behind.",
    )
    target_scene = WorldScene(
        id="SCENE_B",
        session_id="test_sess",
        label="Great Hall",
        description="A grand hall.",
    )

    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay.AdventureLogic.resolve_session_state",
        AsyncMock(return_value=state),
    )
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay._resolve_session_exit",
        AsyncMock(return_value=exit_obj),
    )

    executed_triggers = []

    async def mock_execute_trigger(db, state, trigger_name, target_id, **kwargs):
        executed_triggers.append((trigger_name, target_id))
        return [f"{trigger_name} fired on {target_id}"]

    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay.TriggerService.execute_trigger",
        mock_execute_trigger,
    )

    async def mock_db_execute(stmt):
        params = stmt.compile().params
        res = MagicMock()
        if "SCENE_B" in params.values():
            res.scalars.return_value.first.return_value = target_scene
        elif "SCENE_A" in params.values():
            res.scalars.return_value.first.return_value = old_scene
        else:
            res.scalars.return_value.first.return_value = None
        return res

    db.execute.side_effect = mock_db_execute

    user = User(id="user_1")
    res = await traverse_exit(
        game_id="test_sess",
        exit_id="EXIT_AB",
        db=db,
        current_user=user,
    )
    assert res["status"] == "ok"
    assert res["scene_id"] == "SCENE_B"
    assert state.current_scene_id == "SCENE_B"
    assert ("on_leave_scene", "SCENE_A") in executed_triggers
    assert ("on_exit_used", "EXIT_AB") in executed_triggers
