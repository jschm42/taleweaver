"""Companion config, the session party in ``entity_states["__party__"]`` and the starting party."""

from types import SimpleNamespace

from backend.engine.blueprint import analyze_blueprint
from backend.engine.manifest_apply.npcs import npc_metadata
from backend.engine.party.companion_config import companion_config, normalize_companion
from backend.engine.party.party_start import seed_starting_party
from backend.engine.party.party_state import PARTY_KEY, read_party, store_party
from backend.engine.party.party_view import mark_active_companion


def _npc(npc_id: str, companion=None, entity_type: str = "NPC") -> SimpleNamespace:
    return SimpleNamespace(
        id=npc_id, entity_type=entity_type, metadata_json={"companion": companion}
    )


def test_normalize_companion_defaults_and_cleanup():
    # Arrange / Act
    shorthand = normalize_companion(True)
    cleaned = normalize_companion({"tactics": "support", "banter": "loud", "downed_recovery": 30})

    # Assert
    assert normalize_companion(None) is None
    assert normalize_companion({}) is None
    assert shorthand == {
        "recruitable": True,
        "starts_in_party": False,
        "tactics": "BALANCED",
        "banter": "NORMAL",
        "downed_recovery": 0.25,
    }
    assert cleaned["tactics"] == "SUPPORT"
    assert cleaned["banter"] == "NORMAL"  # unknown values fall back to the default
    assert cleaned["downed_recovery"] == 0.3  # percent values are converted


def test_companion_config_reads_npc_metadata():
    # Arrange
    meta = {"companion": {"starts_in_party": True, "tactics": "DEFENSIVE"}}

    # Act
    config = companion_config(meta)

    # Assert
    assert config is not None
    assert config.starts_in_party is True
    assert config.tactics == "DEFENSIVE"
    assert companion_config({"companion": None}) is None


def test_party_recruit_dismiss_and_roundtrip():
    # Arrange
    states: dict = {}
    party = read_party(states)

    # Act
    party.recruit("LARA", "SUPPORT")
    party.recruit("BORIS")
    store_party(states, party)
    reread = read_party(states)

    # Assert: the last recruit is active, both are members
    assert reread.active_id == "BORIS"
    assert reread.recruited == ["LARA", "BORIS"]
    assert reread.follower_id() == "BORIS"
    assert reread.tactics == {"LARA": "SUPPORT"}

    # Act: dismissing the active companion leaves no active one; an empty party removes the key
    reread.dismiss("BORIS")
    assert reread.active_id is None
    reread.dismiss("LARA")
    store_party(states, reread)
    assert PARTY_KEY not in states


def test_read_party_is_defensive():
    # Arrange
    states = {PARTY_KEY: {"active_id": "LARA", "recruited": None, "tactics": "bad"}}

    # Act
    party = read_party(states)

    # Assert
    assert party.recruited == ["LARA"]
    assert party.tactics == {}
    assert read_party({PARTY_KEY: "garbage"}).recruited == []
    assert read_party(None).active_id is None


def test_following_off_means_no_follower():
    # Arrange
    party = read_party({})
    party.recruit("LARA")

    # Act
    party.following = False

    # Assert
    assert party.follower_id() is None


def test_seed_starting_party_places_first_starter_with_the_player():
    # Arrange
    states: dict = {}
    entities = [
        _npc("GUARD"),
        _npc("LARA", {"starts_in_party": True, "tactics": "SUPPORT"}),
        _npc("BORIS", {"starts_in_party": True}),
        _npc("SWORD", {"starts_in_party": True}, entity_type="OBJECT"),
    ]

    # Act
    seed_starting_party(states, entities, "START")

    # Assert
    party = read_party(states)
    assert party.active_id == "LARA"
    assert sorted(party.recruited) == ["BORIS", "LARA"]
    assert party.tactics["LARA"] == "SUPPORT"
    assert states["LARA"]["current_scene_id"] == "START"
    assert "BORIS" not in states  # further starters stay where they are


def test_seed_starting_party_without_starters_changes_nothing():
    # Arrange
    states: dict = {}

    # Act
    seed_starting_party(states, [_npc("LARA", {"recruitable": True})], "START")

    # Assert
    assert states == {}


def test_manifest_applier_keeps_and_normalizes_the_companion_block():
    # Arrange
    generated = {"id": "LARA", "companion": {"tactics": "offensive", "starts_in_party": True}}
    exported = {"id": "LARA", "metadata_json": {"companion": {"banter": "CHATTY"}}}

    # Act
    from_generation = npc_metadata(generated)
    from_export = npc_metadata(exported)

    # Assert
    assert from_generation["companion"]["tactics"] == "OFFENSIVE"
    assert from_generation["companion"]["starts_in_party"] is True
    assert from_export["companion"]["banter"] == "CHATTY"
    assert npc_metadata({"id": "GUARD"})["companion"] is None


def test_blueprint_keys_map_to_companion_fields():
    # Arrange
    text = (
        "[Scene: HALL] Hall\n[Scene: VENT] Vent\n"
        "[Exit: HALL -> VENT] a narrow vent\nsolo: yes\n"
        "[NPC: LARA] Lara\nin: HALL\ncompanion: yes\nin_party: yes\ntactics: support\n"
        "banter: quiet\ndowned_recovery: 0.5\n"
        "[Sequence: 1] Alone\ncompanions: no\n"
    )

    # Act
    blueprint, _ = analyze_blueprint(text)

    # Assert
    blocks = {block.kind: block for block in blueprint.blocks if block.kind != "scene"}
    assert blueprint.issues == []
    npc = {k: v.value for k, v in blocks["npc"].fields.items()}
    assert npc["companion.recruitable"] is True
    assert npc["companion.starts_in_party"] is True
    assert npc["companion.tactics"] == "SUPPORT"
    assert npc["companion.banter"] == "QUIET"
    assert blocks["exit"].fields["companions_allowed"].value is False
    assert blocks["sequence"].fields["companions_allowed"].value is False


def test_mark_active_companion_flags_only_the_active_member():
    # Arrange
    states = {PARTY_KEY: {"active_id": "BATLIN", "recruited": ["BATLIN", "LARA"]}}
    entities = [{"id": "BATLIN"}, {"id": "LARA"}, {"id": "GUARD"}]

    # Act
    mark_active_companion(entities, states)
    mark_active_companion(no_party := [{"id": "BATLIN"}], {})

    # Assert
    assert entities[0]["is_companion"] is True
    assert "is_companion" not in entities[1]
    assert "is_companion" not in entities[2]
    assert "is_companion" not in no_party[0]
