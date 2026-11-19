"""NPC conversations: relations, chatter beats, overheard topics, gossip, script API, authoring."""

from types import SimpleNamespace

import pytest

from backend.api.routes.adventures import npc_conversation_flow as flow
from backend.api.routes.adventures.session_state_settings import apply_state_settings
from backend.core.script_validator import check_scripts_and_guards
from backend.core.world_validation.context import ValidationContext
from backend.core.world_validation.conversations import check_conversation_refs, check_topic_ids
from backend.engine.blueprint import analyze_blueprint
from backend.engine.blueprint.merge import apply_blueprint
from backend.engine.conversations.chatter import (
    LISTEN_ALONE_DIRECTION,
    BeatRequest,
    beat_direction,
    beat_due,
    can_chat,
    plan_beat,
)
from backend.engine.conversations.gossip import HEARSAY_PREFIX, spread_gossip
from backend.engine.conversations.ops import apply_conversation_ops
from backend.engine.conversations.relations import relation_between, relations_prompt_block
from backend.engine.conversations.settings import (
    chatter_sheet_fields,
    normalize_conversation_settings,
)
from backend.engine.conversations.state import (
    CONVERSATIONS_STATE_KEY,
    heard_topics,
    read_conversations,
    take_pending_beat,
)
from backend.engine.interaction.command_parser import CommandParser
from backend.engine.manifest_apply.npcs import npc_metadata
from backend.engine.rules.npc_memory import read_memories, remember
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.runner import ScriptRunner
from backend.engine.world.world_schemas import WorldManifesto, WorldNPCSchema
from backend.models.session_state import SessionState
from backend.schemas.session import GameSessionUpdate


def _npc(npc_id: str, scene: str = "INN", **metadata) -> SimpleNamespace:
    return SimpleNamespace(
        id=npc_id,
        name=npc_id.title(),
        entity_type="NPC",
        npc_type="HUMANOID",
        is_hidden=False,
        is_defeated=False,
        current_scene_id=scene,
        metadata_json=metadata,
    )


def _always(_expr: str) -> bool:
    return True


# --- Beat decision -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("request_", "due"),
    [
        (BeatRequest(level="OFF", player_enabled=True, listen=True), True),
        (BeatRequest(level="OFF", player_enabled=True, quiet=10), False),
        (BeatRequest(level="NORMAL", player_enabled=False, quiet=10), False),
        (BeatRequest(level="NORMAL", player_enabled=True, arrival=True), True),
        (BeatRequest(level="RARE", player_enabled=True, arrival=True), False),
        (BeatRequest(level="NORMAL", player_enabled=True, quiet=1), False),
        (BeatRequest(level="NORMAL", player_enabled=True, quiet=2), True),
        (BeatRequest(level="LIVELY", player_enabled=True, quiet=5, addressed_npc=True), False),
    ],
)
def test_beat_due_follows_level_switch_and_quiet_counter(request_, due):
    # Act / Assert
    assert beat_due(request_) is due


def test_can_chat_excludes_animals_hidden_opted_out_and_quiet_companion():
    # Arrange
    dog = _npc("DOG")
    dog.npc_type = "ANIMAL"
    guard = _npc("GUARD", chatty=False)
    ghost = _npc("GHOST")
    ghost.is_hidden = True

    # Act / Assert
    assert can_chat(_npc("BRAM"))
    assert not can_chat(dog) and not can_chat(guard) and not can_chat(ghost)
    assert not can_chat(_npc("PIP"), quiet_companion_id="PIP")


def test_plan_beat_prefers_open_topic_then_related_pair():
    # Arrange
    topic = {"id": "cellar", "topic": "the cellar", "with_npc_id": "MARA", "must_convey": "open"}
    bram = _npc("BRAM", conversation_topics=[topic])
    mara = _npc("MARA")
    tom = _npc("TOM", relations=[{"npc_id": "MARA", "kind": "FRIEND"}])

    # Act
    with_topic = plan_beat([tom, bram, mara], {}, set(), _always)
    heard = plan_beat([tom, bram, mara], {}, {"cellar"}, _always)
    guarded = plan_beat(
        [_npc("BRAM", conversation_topics=[{**topic, "guard_expression": "x"}]), mara],
        {},
        set(),
        lambda _e: False,
    )
    alone = plan_beat([bram], {}, set(), _always)

    # Assert
    assert with_topic.topic.id == "cellar" and with_topic.speaker_b is mara
    assert heard.topic is None and {heard.speaker_a.id, heard.speaker_b.id} == {"TOM", "MARA"}
    assert guarded.topic is None
    assert alone is None
    assert "must make this clear to a listener: open" in beat_direction(with_topic, listen=True)


# --- Relations -----------------------------------------------------------------------------


def test_relations_block_lists_present_pairs_and_script_overrides_win():
    # Arrange
    bram = _npc("BRAM", relations=[{"npc_id": "MARA", "kind": "rival", "note": "owes her"}])
    mara = _npc("MARA", relations=[{"npc_id": "ABSENT", "kind": "FRIEND"}])
    states: dict = {}
    apply_conversation_ops(
        states,
        [{"op": "set_relation", "npc_id": "MARA", "other_id": "BRAM", "kind": "friend"}],
    )

    # Act
    block = relations_prompt_block([bram, mara], states)

    # Assert
    assert 'Bram sees Mara as rival ("owes her")' in block
    assert "Mara sees Bram as friend" in block
    assert "ABSENT" not in block
    assert relations_prompt_block([bram], states) == ""


# --- Gossip --------------------------------------------------------------------------------


def test_gossip_travels_along_friendly_relations_only_once():
    # Arrange
    bram = _npc("BRAM", memory_slots=4, relations=[{"npc_id": "MARA", "kind": "FRIEND"}])
    mara = _npc("MARA", memory_slots=4, relations=[{"npc_id": "BRAM", "kind": "RIVAL"}])
    tom = _npc("TOM", scene="FORGE", memory_slots=4)
    states = remember({}, "BRAM", "player_name", "The protagonist is Kael.", 4)
    states = remember(states, "MARA", "deal", "Kael owes Mara.", 4)

    # Act
    states, events = spread_gossip(states, [bram, mara, tom])
    again, more = spread_gossip(states, [bram, mara, tom])

    # Assert
    assert [(e.teller_id, e.listener_id) for e in events] == [("BRAM", "MARA")]
    heard = [f for f in read_memories(states, "MARA") if f["key"] == "player_name"]
    assert heard and heard[0]["text"].startswith(HEARSAY_PREFIX + "Bram")
    assert read_memories(states, "BRAM")[-1]["key"] == "player_name"  # rival tells nothing
    assert more == [] and again is states


# --- Turn flow -----------------------------------------------------------------------------


class _FakeManager:
    """The GameTurnManager members the conversation flow uses."""

    def __init__(self, npcs: list, *, chatter: str = "NORMAL", message: str = "look") -> None:
        self.npcs = npcs
        self.state = SessionState(
            entity_states={}, current_scene_id="INN", session_id="s1", world_memories=[]
        )
        self.adventure = SimpleNamespace(npc_conversations={"chatter": chatter, "gossip": True})
        self.current_user_message = message
        self.listen_requested = False
        self.game_id = "s1"
        self.saved: list[str] = []

    def _has_combat_phase(self) -> bool:
        return False

    async def _build_script_context(self) -> GameContext:
        return GameContext(current_scene_id="INN", entities={})

    async def _save_chat_message(self, _role: str, content: str) -> None:
        self.saved.append(content)

    async def _execute_inline_script(self, *_args) -> list:
        return []

    def _get_script_runner(self) -> ScriptRunner:
        return ScriptRunner([])


async def _run(manager: _FakeManager, interacted: list[str] | None = None) -> list[str]:
    return [event async for event in flow.plan_conversation_beat(manager, interacted or [])]


@pytest.fixture
def patched_npcs(monkeypatch):
    def install(manager: _FakeManager) -> None:
        async def session_npcs(_manager):
            return manager.npcs

        monkeypatch.setattr(flow, "_session_npcs", session_npcs)

    return install


@pytest.mark.asyncio
async def test_listen_overhears_topic_once_with_consequences(patched_npcs):
    # Arrange
    topic = {
        "id": "cellar",
        "topic": "the cellar",
        "must_convey": "the cellar is open at night",
        "on_heard_text": "You learned a secret.",
    }
    manager = _FakeManager([_npc("BRAM", conversation_topics=[topic]), _npc("MARA")], chatter="OFF")
    patched_npcs(manager)
    manager.listen_requested = True

    # Act
    events = await _run(manager)
    direction = take_pending_beat(manager.state)
    second = take_pending_beat(manager.state)

    # Assert
    assert "CONVERSATION BEAT" in direction and "open at night" in direction
    assert second == ""
    assert heard_topics(manager.state.entity_states) == {"cellar"}
    assert manager.saved == ["You learned a secret."] and len(events) == 1
    assert (
        "Overheard: the cellar is open at night" in manager.state.world_memories[0]["description"]
    )


@pytest.mark.asyncio
async def test_chatter_counts_quiet_messages_and_skips_prologue(patched_npcs):
    # Arrange
    manager = _FakeManager([_npc("BRAM"), _npc("MARA")], message="")
    patched_npcs(manager)

    # Act: prologue records the scene; then two quiet messages, the third brings a beat.
    await _run(manager)
    manager.current_user_message = "wait"
    await _run(manager)
    first = take_pending_beat(manager.state)
    await _run(manager, ["BRAM"])  # addressing an NPC does not count
    await _run(manager)
    second = take_pending_beat(manager.state)
    await _run(manager)
    third = take_pending_beat(manager.state)

    # Assert
    assert first == "" and second == ""
    assert third.startswith("CONVERSATION BEAT")
    assert read_conversations(manager.state.entity_states)["quiet"] == 0


@pytest.mark.asyncio
async def test_listen_alone_and_player_switch(patched_npcs):
    # Arrange
    manager = _FakeManager([_npc("BRAM")])
    patched_npcs(manager)
    manager.listen_requested = True

    # Act
    await _run(manager)
    alone = take_pending_beat(manager.state)
    apply_state_settings(manager.state, GameSessionUpdate(npc_chatter=False))
    sheet = chatter_sheet_fields({"chatter": "NORMAL"}, manager.state.entity_states)

    # Assert
    assert alone == LISTEN_ALONE_DIRECTION
    assert sheet == {
        "level": "NORMAL",
        "available": True,
        "enabled": False,
        "listen_possible": False,
    }


# --- Script API ----------------------------------------------------------------------------


def _script_ctx(store: dict | None = None) -> GameContext:
    entities = {
        "BRAM": {"id": "BRAM", "name": "Bram", "entity_type": "NPC", "current_scene_id": "INN"},
        "MARA": {
            "id": "MARA",
            "name": "Mara",
            "entity_type": "NPC",
            "current_scene_id": "INN",
            "metadata_json": {"relations": [{"npc_id": "BRAM", "kind": "RIVAL"}]},
        },
        "TOM": {"id": "TOM", "name": "Tom", "entity_type": "NPC", "current_scene_id": "FORGE"},
    }
    return GameContext(current_scene_id="INN", entities=entities, conversations=store)


def test_script_api_converse_relations_and_topics():
    # Arrange
    ctx = _script_ctx({"heard": ["old_news"]})
    code = """
tw.npcs.converse("BRAM", "MARA", topic="the storm", must_convey="the bridge is down")
tw.npcs.converse("BRAM", "TOM", topic="never shown")
tw.npcs.converse("BRAM", "MARA", lines=[("BRAM", "Evening."), ("MARA", "Hmpf.")])
before = tw.npcs.relation("MARA", "BRAM")["kind"]
tw.npcs.set_relation("MARA", "BRAM", "friend", "made up")
tw.vars.set("before", before)
tw.vars.set("after", tw.npcs.relation("MARA", "BRAM")["kind"])
tw.vars.set("old", tw.npcs.topic_heard("old_news"))
tw.npcs.mark_topic_heard("storm")
"""

    # Act
    ScriptRunner([]).execute_code(code, {"tw": ctx})
    states = {CONVERSATIONS_STATE_KEY: {"heard": ["old_news"]}}
    apply_conversation_ops(states, ctx.changeset.conversation_ops)

    # Assert
    assert len(ctx.changeset.gm_directions) == 1
    assert "the bridge is down" in ctx.changeset.gm_directions[0]
    assert list(ctx.changeset.narrative_messages) == ['Bram: "Evening."', 'Mara: "Hmpf."']
    assert ctx.changeset.var_updates == {"before": "RIVAL", "after": "FRIEND", "old": True}
    assert heard_topics(states) == {"old_news", "storm"}
    mara = SimpleNamespace(id="MARA", metadata_json={})
    assert relation_between(mara, "BRAM", states)["note"] == "made up"


def test_script_api_rejects_unknown_relation_kind():
    # Arrange
    ctx = _script_ctx()

    # Act / Assert
    with pytest.raises(ValueError, match="Unknown relation kind"):
        ctx.npcs.set_relation("MARA", "BRAM", "nemesis")


# --- Authoring path ------------------------------------------------------------------------


def test_fields_survive_blueprint_schema_and_manifest():
    # Arrange
    text = (
        "[World]\nnpc_chatter: lively\ngossip: yes\n"
        "[Scene: INN] Inn\nCozy.\n"
        "[NPC: BRAM] Bram\nin: INN\nrelation: MARA = rival | owes her money\nchatty: no\n"
        "topic: the cellar door | with: MARA | convey: it is open at night | id: cellar\n"
        "[NPC: MARA] Mara\nin: INN\n"
    )

    # Act
    blueprint, missing = analyze_blueprint(text)
    manifest: dict = {"scenes": [], "npcs": [{"id": "BRAM"}, {"id": "MARA"}]}
    apply_blueprint(manifest, blueprint)
    bram = next(n for n in manifest["npcs"] if n["id"] == "BRAM")
    stored = npc_metadata(bram)
    exported = npc_metadata({"id": "BRAM", "metadata_json": stored})

    # Assert
    assert not [i for i in blueprint.issues if i.severity == "error"] and missing == []
    assert normalize_conversation_settings(manifest["npc_conversations"]) == {
        "chatter": "LIVELY",
        "gossip": True,
    }
    assert stored["relations"] == [{"npc_id": "MARA", "kind": "RIVAL", "note": "owes her money"}]
    assert stored["chatty"] is False
    assert stored["conversation_topics"][0]["id"] == "cellar"
    assert exported["conversation_topics"] == stored["conversation_topics"]
    assert {"relations", "chatty", "conversation_topics"} <= set(WorldNPCSchema.model_fields)
    assert "npc_conversations" in WorldManifesto.model_fields


def test_validators_flag_unknown_targets_duplicate_ids_and_bad_scripts():
    # Arrange
    topic = {"id": "dup", "topic": "x", "with_npc_id": "NOBODY", "on_heard_script": "if:"}
    payload = {
        "npcs": [
            {
                "id": "BRAM",
                "entity_type": "NPC",
                "metadata_json": {
                    "relations": [{"npc_id": "GHOST", "kind": "FRIEND"}],
                    "conversation_topics": [topic],
                },
            },
            {
                "id": "MARA",
                "entity_type": "NPC",
                "metadata_json": {"conversation_topics": [{"id": "dup", "topic": "y"}]},
            },
        ]
    }
    ctx = ValidationContext.from_payload(payload)

    # Act
    refs = check_conversation_refs(ctx)
    dups = check_topic_ids(ctx)
    syntax = check_scripts_and_guards(payload)

    # Assert
    assert [f.code for f in refs] == ["conversation_unknown_npc"] * 2
    assert [f.code for f in dups] == ["conversation_topic_duplicate_id"]
    assert any(f.code == "script_syntax_error" for f in syntax)


def test_listen_command_maps_to_trigger():
    # Arrange
    avatar = SimpleNamespace(inventory=[], equipment={})

    # Act
    response = CommandParser.parse_command(avatar, "/listen")

    # Assert
    assert response == "[TRIGGER_LISTEN]"


# --- Debug inspector -----------------------------------------------------------------------


def test_debug_payload_shows_memory_relations_topics_and_session_state():
    # Arrange
    from backend.api.routes.adventures.session_debug_npc_social import (
        conversation_session_debug,
        npc_social_debug,
    )

    topic = {"id": "cellar", "topic": "the cellar", "must_convey": "open at night"}
    bram = _npc(
        "BRAM",
        memory_slots=2,
        chatty=False,
        relations=[{"npc_id": "MARA", "kind": "RIVAL"}],
        conversation_topics=[topic],
    )
    states = remember({}, "BRAM", "player_name", "The protagonist is Kael.", 2)
    apply_conversation_ops(
        states,
        [
            {"op": "set_relation", "npc_id": "BRAM", "other_id": "MARA", "kind": "FRIEND"},
            {"op": "mark_heard", "topic_id": "cellar"},
        ],
    )
    adventure = SimpleNamespace(npc_conversations={"chatter": "RARE"})

    # Act
    social = npc_social_debug(bram, states, {"MARA": "Mara"})
    session = conversation_session_debug(adventure, states)

    # Assert
    assert social["memory"] == {
        "slots": 2,
        "facts": [{"key": "player_name", "text": "The protagonist is Kael.", "hearsay": False}],
    }
    relation = social["conversations"]["relations"][0]
    assert relation["kind"] == "FRIEND" and relation["name"] == "Mara"
    assert relation["changed_by_script"] is True
    assert social["conversations"]["chatty"] is False
    assert social["conversations"]["topics"][0]["heard"] is True
    assert session["chatter"] == "RARE" and session["heard"] == ["cellar"]
    assert session["player_enabled"] is True and session["pending_beat"] == ""


@pytest.mark.asyncio
async def test_listening_mode_continues_the_same_pair(patched_npcs):
    # Arrange
    bram = _npc("BRAM", relations=[{"npc_id": "MARA", "kind": "FRIEND"}])
    manager = _FakeManager([bram, _npc("MARA"), _npc("TOM")], chatter="OFF")
    patched_npcs(manager)
    manager.listen_requested = True

    # Act
    await _run(manager)
    first = take_pending_beat(manager.state)
    await _run(manager)
    second = take_pending_beat(manager.state)
    manager.listen_requested = False
    await _run(manager)  # a player action ends the streak
    manager.listen_requested = True
    await _run(manager)
    third = take_pending_beat(manager.state)
    sheet = chatter_sheet_fields(None, manager.state.entity_states)

    # Assert
    assert "talk with each other" in first and "Bram" in first and "Mara" in first
    assert "go on with their conversation" in second and "Bram" in second and "Mara" in second
    assert "go on with their conversation" not in third
    assert sheet["listen_possible"] is True


def test_gossip_log_and_hearsay_reach_the_debug_view():
    # Arrange
    from backend.api.routes.adventures.session_debug_npc_social import (
        conversation_session_debug,
        npc_social_debug,
    )
    from backend.engine.conversations.gossip import append_gossip_log
    from backend.engine.conversations.state import write_conversations

    bram = _npc("BRAM", memory_slots=4, relations=[{"npc_id": "MARA", "kind": "FRIEND"}])
    mara = _npc("MARA", memory_slots=4)
    states = remember({}, "BRAM", "player_name", "The protagonist is Kael.", 4)
    states, events = spread_gossip(states, [bram, mara])
    log = append_gossip_log([], events, SimpleNamespace(in_game_time=90))
    states = write_conversations(states, {"gossip_log": log})
    names = {"BRAM": "Bram", "MARA": "Mara"}

    # Act
    listener = npc_social_debug(mara, states, names)
    teller = npc_social_debug(bram, states, names)
    session = conversation_session_debug(SimpleNamespace(npc_conversations=None), states, names)

    # Assert
    assert listener["memory"]["facts"][0]["hearsay"] is True
    assert listener["gossip"]["heard"] == [{"from": "Bram", "key": "player_name"}]
    assert teller["gossip"]["told"] == [{"to": "Mara", "key": "player_name"}]
    assert session["gossip_log"] == [
        {
            "teller": "Bram",
            "listener": "Mara",
            "key": "player_name",
            "scene_id": "INN",
            "minute": 90,
        }
    ]
    assert session["gossip"] is False


@pytest.mark.asyncio
async def test_listen_mode_command_saves_a_system_message():
    # Arrange
    from backend.api.routes.adventures.listen_mode_command import (
        LISTEN_MODE_MESSAGES,
        handle_listen_mode_command,
        is_listen_mode_command,
    )

    saved: list[tuple[str, str]] = []

    class _Db:
        async def commit(self) -> None:
            return None

    async def save(role: str, content: str) -> None:
        saved.append((role, content))

    manager = SimpleNamespace(_save_chat_message=save, db=_Db())

    # Act
    on = [e async for e in handle_listen_mode_command(manager, "/listen_mode on")]
    unknown = [e async for e in handle_listen_mode_command(manager, "/listen_mode nonsense")]

    # Assert
    assert is_listen_mode_command("/listen_mode off") and not is_listen_mode_command("/listen")
    assert saved == [("system", LISTEN_MODE_MESSAGES["on"])]
    assert len(on) == 1 and unknown == []
