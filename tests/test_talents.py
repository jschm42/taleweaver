"""Protagonist talents: parsing, the deterministic use, unlocks, the editor API and blueprints."""

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.talent_use import resolve_talent_request, use_talent
from backend.engine.blueprint import analyze_blueprint
from backend.engine.blueprint.merge import apply_blueprint
from backend.engine.manifest_apply.avatar import starting_stats
from backend.engine.rules.talents import (
    normalize_talents,
    parse_talent_command,
    parse_typed_talent,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

MIND_READING = {
    "id": "MIND_READING",
    "name": "Mind Reading",
    "description": "Hear what someone really thinks.",
    "target_type": "NPC",
    "cost_type": "mana",
    "cost": 10,
    "max_uses": 2,
    "gm_hint": "Reveal the target's thoughts in italics.",
    "on_use_script": "tw.vars.set('read_target', talent['target_id'])",
}
GOSSIP = {
    "id": "GOSSIP_ATTACK",
    "name": "Gossip Attack",
    "description": "A vicious rumour.",
    "target_type": "NPC",
    "cost_type": "stamina",
    "cost": 5,
    "is_locked": True,
    "unlock_required_scene_id": "TAVERN",
}
LUCKY_GUESS = {"id": "LUCKY_GUESS", "name": "Lucky Guess", "description": "Guess right."}
TALENTS = normalize_talents([MIND_READING, GOSSIP, LUCKY_GUESS])


async def _seed_world(db, talents=None, unlocked=None) -> GameTurnManager:
    user, _adv, avatar, _state = await _seed_game_context(db)
    avatar.mana = 30
    avatar.max_mana = 100
    avatar.stamina = 50
    avatar.stats = {
        "talents": talents if talents is not None else [MIND_READING, GOSSIP, LUCKY_GUESS],
        "unlocked_talents": unlocked if unlocked is not None else ["MIND_READING", "LUCKY_GUESS"],
    }
    db.add(
        WorldEntity(
            id="GUARD",
            session_id="session-1",
            entity_type="NPC",
            name="Grim Guard",
            description="A guard.",
            current_scene_id="START",
            hp=20,
            max_hp=20,
        )
    )
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    return manager


# --- Parsing ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "talent_id", "target"),
    [
        ("use mind reading on the guard", "MIND_READING", "guard"),
        ("Cast Mind Reading at Grim Guard!", "MIND_READING", "Grim Guard"),
        ("I use my Gossip Attack against GUARD", "GOSSIP_ATTACK", "GUARD"),
        ("activate lucky guess", "LUCKY_GUESS", ""),
        ("use mind_reading guard", "MIND_READING", "guard"),
    ],
)
def test_typed_talent_names_a_known_talent(text, talent_id, target):
    # Act
    request = parse_typed_talent(TALENTS, text)

    # Assert
    assert request is not None
    assert request.talent["id"] == talent_id
    assert request.target_hint == target


@pytest.mark.parametrize(
    "text", ["use the key on the door", "cast a glance at the guard", "mind reading", "look"]
)
def test_typed_text_without_a_known_talent_stays_a_normal_turn(text):
    # Act / Assert
    assert parse_typed_talent(TALENTS, text) is None


def test_talent_command_resolves_id_name_and_target():
    # Act
    by_id = parse_talent_command(TALENTS, "/talent MIND_READING | GUARD")
    by_name = parse_talent_command(TALENTS, "/talent mind reading on the guard")
    unknown = parse_talent_command(TALENTS, "/talent flying")
    listing = parse_talent_command(TALENTS, "/talent")

    # Assert
    assert (by_id.talent["id"], by_id.target_hint) == ("MIND_READING", "GUARD")
    assert (by_name.talent["id"], by_name.target_hint) == ("MIND_READING", "guard")
    assert unknown.talent is None and unknown.query == "flying"
    assert listing.talent is None and listing.query == ""


# --- Using a talent --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_use_talent_pays_cost_counts_use_runs_script_and_prompts_gm(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        request = resolve_talent_request(manager, "use mind reading on grim guard")

        # Act
        outcome = await use_talent(manager, request)

        # Assert
        assert outcome.messages[0] == "✨ You use Mind Reading on Grim Guard (-10 Mana)."
        assert manager.avatar.mana == 20
        assert manager.avatar.stats["talent_uses"] == {"MIND_READING": 1}
        assert manager.state.entity_states["__script_vars__"]["read_target"] == "GUARD"
        assert "[TALENT_USED]" in outcome.reaction_prompt
        assert "Grim Guard (ID GUARD)" in outcome.reaction_prompt
        assert "Reveal the target's thoughts in italics." in outcome.reaction_prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("use gossip attack on guard", "You have not unlocked Gossip Attack yet."),
        ("use mind reading", "Use Mind Reading on whom?"),
        ("use mind reading on the king", "There is no 'king' here to use Mind Reading on."),
    ],
)
async def test_use_talent_refuses_without_paying(setup_test_db, message, expected):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        # Act
        outcome = await use_talent(manager, resolve_talent_request(manager, message))

        # Assert
        assert outcome.reaction_prompt is None
        assert outcome.messages[0].startswith(expected)
        assert manager.avatar.mana == 30
        assert not manager.avatar.stats.get("talent_uses")


@pytest.mark.asyncio
async def test_use_talent_enforces_cost_and_uses_per_adventure(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        request = resolve_talent_request(manager, "/talent MIND_READING | GUARD")

        # Act
        first = await use_talent(manager, request)
        second = await use_talent(manager, request)
        third = await use_talent(manager, request)
        manager.avatar.mana = 5
        manager.avatar.stats = {**manager.avatar.stats, "talent_uses": {}}
        poor = await use_talent(manager, request)

        # Assert
        assert first.reaction_prompt and second.reaction_prompt
        assert third.messages == ["You have used up Mind Reading for this adventure."]
        assert poor.messages == ["Not enough mana for Mind Reading (needs 10, you have 5)."]


@pytest.mark.asyncio
async def test_refused_talent_turn_streams_message_without_gm_call(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)

        async def no_llm(*_args, **_kwargs):
            raise AssertionError("The Game Master must not run for a refused talent.")
            yield  # pragma: no cover

        manager._run_llm_cycle = no_llm

        # Act
        chunks = [c async for c in manager.process_turn("cast gossip attack on guard")]

        # Assert
        assert any("You have not unlocked Gossip Attack yet." in c for c in chunks)
        assert chunks[-1].startswith("event: final")
        rows = (await db.execute(select(ChatMessage.content))).scalars().all()
        assert "cast gossip attack on guard" in rows


@pytest.mark.asyncio
async def test_talent_turn_chains_the_game_master_reaction(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        prompts: list[str] = []

        async def fake_llm(prompt, *_args, **_kwargs):
            prompts.append(prompt)
            yield "event: final\ndata: {}\n\n"

        manager._run_llm_cycle = fake_llm

        # Act
        chunks = [c async for c in manager.process_turn("use lucky guess")]

        # Assert
        assert any("You use Lucky Guess." in c for c in chunks)
        assert prompts and prompts[0].startswith("[TALENT_USED] The player just used the talent")


@pytest.mark.asyncio
async def test_locked_talent_unlocks_when_its_rule_is_met(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _seed_world(db)
        manager.state.current_scene_id = "TAVERN"
        manager.state.visited_scenes = ["START", "TAVERN"]

        # Act
        messages = await manager.combat.check_special_unlocks()

        # Assert
        assert "✨ Talent unlocked: Gossip Attack!" in messages
        assert "GOSSIP_ATTACK" in manager.avatar.stats["unlocked_talents"]


# --- Editor API ------------------------------------------------------------------------


async def _seed_template() -> str:
    async with TestSessionLocal() as db:
        user = (
            (await db.execute(select(User).where(User.username == "test_user"))).scalars().first()
        )
        adv = AdventureTemplate(
            title="Talents", owner_id=user.id, original_manifest={"protagonist": {"name": "Mira"}}
        )
        db.add(adv)
        await db.flush()
        db.add(Avatar(user_id=user.id, template_id=adv.id, name="Mira", stats={}))
        await db.commit()
        return adv.id


@pytest.mark.asyncio
async def test_editor_saves_talents_on_avatar_and_manifest(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()

    # Act
    resp = await auth_client.put(
        f"/api/adventures/{template_id}/editor/talents",
        json={"talents": [{**MIND_READING, "id": "mind_reading"}, GOSSIP]},
    )

    # Assert
    assert resp.status_code == 200
    async with TestSessionLocal() as db:
        avatar = (
            (await db.execute(select(Avatar).where(Avatar.template_id == template_id)))
            .scalars()
            .first()
        )
        adv = await db.get(AdventureTemplate, template_id)
    assert [t["id"] for t in avatar.stats["talents"]] == ["MIND_READING", "GOSSIP_ATTACK"]
    assert avatar.stats["unlocked_talents"] == ["MIND_READING"]
    assert adv.original_manifest["protagonist"]["talents"][1]["unlock_required_scene_id"] == (
        "TAVERN"
    )


@pytest.mark.asyncio
async def test_editor_rejects_bad_talent_script_and_duplicates(auth_client, setup_test_db):
    # Arrange
    template_id = await _seed_template()
    url = f"/api/adventures/{template_id}/editor/talents"

    # Act
    bad_script = await auth_client.put(
        url, json={"talents": [{**LUCKY_GUESS, "on_use_script": "import os"}]}
    )
    duplicate = await auth_client.put(url, json={"talents": [LUCKY_GUESS, LUCKY_GUESS]})

    # Assert
    assert bad_script.status_code == 400
    assert "on_use_script" in bad_script.json()["detail"]
    assert duplicate.status_code == 400


# --- Blueprint and manifest ------------------------------------------------------------

BLUEPRINT = """
[Protagonist: Mira]
role: Court bard

[Talent: MIND_READING] Mind Reading
Hear what a person really thinks.
target: npc
cost: mana 10
uses: 3
gm: Reveal the target's true thoughts.
on_use: tw.vars.set('minds_read', True)

[Talent: GOSSIP_ATTACK]
target: npc
cost: stamina 5
locked: yes
unlock_scene: START
"""


def test_blueprint_talents_become_protagonist_talents():
    # Arrange
    blueprint, _missing = analyze_blueprint(BLUEPRINT + "\n[Scene: START] Start\nA room.\n")
    manifest = {"protagonist": {"name": "Mira"}, "scenes": [{"id": "START"}]}

    # Act
    violations = apply_blueprint(manifest, blueprint)
    stats = starting_stats(manifest["protagonist"])

    # Assert
    assert blueprint.errors == [] and violations == []
    mind, gossip = manifest["protagonist"]["talents"]
    assert mind["name"] == "Mind Reading"
    assert (mind["target_type"], mind["cost_type"], mind["cost"], mind["max_uses"]) == (
        "NPC",
        "mana",
        10,
        3,
    )
    assert mind["on_use_script"] == "tw.vars.set('minds_read', True)"
    assert gossip["name"] == "Gossip Attack"
    assert gossip["unlock_required_scene_id"] == "START"
    assert stats["unlocked_talents"] == ["MIND_READING"]
    assert stats["talent_uses"] == {}


def test_talent_tag_outside_the_protagonist_is_an_error():
    # Act
    blueprint, _missing = analyze_blueprint(
        "[Scene: START] Start\nA room.\n\n[NPC: GUARD] Guard\nin: START\n\n[Talent: X] X\n"
    )

    # Assert
    assert any(
        "[Talent] must be placed inside a protagonist" in e.message for e in blueprint.errors
    )
