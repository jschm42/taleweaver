"""Tests for the World-Builder blueprint syntax (parse, validate, prompt, merge)."""

import pytest
from httpx import AsyncClient

from backend.engine.blueprint import (
    BlueprintError,
    analyze_blueprint,
    apply_blueprint,
    has_blueprint_tags,
    parse_blueprint,
    prepare_blueprint,
)
from backend.engine.blueprint.prompt import blueprint_sequences, render_blueprint_prompt
from backend.engine.world.world_schemas import WorldSceneSchema

SAMPLE = """A salvage tech wakes in the brig of a derelict ship.

[World]
language: English
lose_guard: tw.vars.get('radiation', 0) >= 100

[Protagonist] Mara Voss
hp: ~80
inventory: MULTITOOL

[Scene: CELL] Brig Cell
Rusted and cramped.
on_enter_text: The hatch slams shut behind you.

[Scene: CORRIDOR] ?

[Exit: CELL -> CORRIDOR] a jammed bulkhead door
code: 4711
on_unlock: |
  tw.vars.set('alarm', True)
  tw.story.narrate("Klaxons howl.")

[NPC: WARDEN] Unit 7 Security Drone
in: CORRIDOR
hp: 40
attack_when_holding: CORE_KEY
  [Ability: TASER] Taser Burst
  kind: ATTACK
  damage: 2d6

[Switch: BREAKER] Breaker Panel
states: OFF, ON
transition: OFF -> ON | item: FUSE | fail: It sparks.
outcome: ON -> flag: POWER_ON

[Sequence: 1] Break Out
Mara must leave the cell.
goal_scene: CORRIDOR
xp: 150
  [Rule: BRIBE] The player convinces @WARDEN to open the door.
  script: tw.exits.unlock('CELL', 'CORRIDOR')
  max: 1

[Sequence: 2] Into the Reactor
Required Item: CORE_KEY

[Script: RADIATION_TICK]
trigger: on_turn_end
code: |
  tw.vars.set('radiation', tw.vars.get('radiation', 0) + 10)
"""


def _generated_manifest() -> dict:
    """A minimal manifest as the LLM might return it, deviating from the blueprint."""
    return {
        "language": "German",
        "protagonist": {"name": "Someone Else", "hp": 95, "starting_inventory": []},
        "scenes": [
            {"id": "CELL", "name": "Prison", "description": "x"},
            {"id": "CORRIDOR", "name": "Dark Corridor", "description": "y"},
        ],
        "exits": [
            {
                "from_scene_id": "CORRIDOR",
                "to_scene_id": "CELL",
                "label": "door",
                "is_locked": False,
                "is_bidirectional": True,
            }
        ],
        "npcs": [{"id": "WARDEN", "name": "Drone", "hp": 10, "special_actions": []}],
        "objects": [{"id": "BREAKER", "name": "Panel", "item_type": "STATIC"}],
        "sequences": [
            {"id": "SEQ_1_X", "order": 1, "title": "Escape", "exp_reward": 50, "soft_rules": []},
            {"id": "SEQ_2_Y", "order": 2, "title": "Reactor", "exp_reward": 50},
        ],
        "quests": [],
        "awards": [],
        "scripts": [],
    }


def test_text_without_tags_is_not_a_blueprint():
    # Arrange
    text = "A plain story idea about a dragon. Note: no tags here."

    # Act
    prepared = prepare_blueprint(text)

    # Assert
    assert has_blueprint_tags(text) is False
    assert prepared is None


def test_parses_entities_fields_and_modes():
    # Act
    blueprint, missing = analyze_blueprint(SAMPLE)

    # Assert
    assert blueprint.errors == []
    assert blueprint.premise == "A salvage tech wakes in the brig of a derelict ship."
    assert sorted(missing) == ["CORE_KEY", "FUSE", "MULTITOOL"]
    protagonist = blueprint.first("protagonist")
    assert protagonist.fixed()["name"] == "Mara Voss"
    assert protagonist.hints() == {"hp": 80}
    corridor = blueprint.of_kind("scene")[1]
    assert corridor.open_fields == ["name"]
    exit_block = blueprint.first("exit")
    assert exit_block.fixed()["is_locked"] is True
    assert "Klaxons" in exit_block.fixed()["on_unlock_success_script"]
    breaker = blueprint.first("item")
    assert breaker.fixed()["item_type"] == "SWITCH"
    assert breaker.fixed()["switch_transitions"][0]["gates"]["item"] == "FUSE"


def test_children_attach_to_their_parents():
    # Act
    blueprint = parse_blueprint(SAMPLE)

    # Assert
    warden = blueprint.first("npc")
    assert [child.ref for child in warden.children] == ["TASER"]
    first_sequence = blueprint.of_kind("sequence")[0]
    rule = first_sequence.children[0]
    assert rule.kind == "rule"
    assert rule.fixed()["max_triggers"] == 1
    assert rule.fixed()["condition"].startswith("The player convinces")
    assert [block.ref for block in blueprint.of_kind("script")] == ["RADIATION_TICK"]


def test_legacy_sequence_syntax_still_works():
    # Arrange
    text = (
        "Premise text.\n"
        "[Sequence: 1] The Prison Escape\n"
        "The player picks the lock.\n"
        "Required Item: rusty shiv\n"
        "End Condition: The player leaves the cell.\n"
        "[Sequence: 2] The Sewers\n"
        "Defeat NPC: GIANT_RAT\n"
    )

    # Act
    prepared = prepare_blueprint(text)

    # Assert
    assert prepared.premise == "Premise text."
    first, second = prepared.sequences
    assert first["title"] == "The Prison Escape"
    assert first["required_item_id"] == "RUSTY_SHIV"
    assert first["end_condition"] == "The player leaves the cell."
    assert first["walkthrough"] == "The player picks the lock."
    assert second["required_defeated_npc_id"] == "GIANT_RAT"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[NPC: A] Bob\nhp: lots", "expected a whole number"),
        ("[Scene: A] Hall\non_enter: |\n  if True\n", "Syntax error"),
        ("[Sequence: 1] X\nguard: import os", "Syntax error"),
        ("[Rule: X] Something happens", "must be placed inside a sequence"),
        ("[Scene: A] One\n[Scene: A] Two", "Duplicate ID 'A'"),
        ("[Exit: A to B]", "must look like [Exit: FROM -> TO]"),
        ("[Script: S]\ntrigger: on_turn_end", "has no 'code:'"),
    ],
)
def test_reports_errors(text, expected):
    # Act
    blueprint, _missing = analyze_blueprint(text)

    # Assert
    messages = [issue.message for issue in blueprint.errors]
    assert any(expected in message for message in messages), messages


def test_prepare_raises_on_errors():
    # Act / Assert
    with pytest.raises(BlueprintError, match="expected a whole number"):
        prepare_blueprint("[NPC: A] Bob\nhp: lots")


def test_more_than_fifteen_sequences_are_capped():
    # Arrange
    text = "\n".join(f"[Sequence: {i}] Chapter {i}" for i in range(1, 18))

    # Act
    blueprint, _missing = analyze_blueprint(text)

    # Assert
    assert len(blueprint_sequences(blueprint)) == 15
    assert any("More than 15" in issue.message for issue in blueprint.warnings)


def test_prompt_section_lists_fixed_values_and_missing_ids():
    # Arrange
    blueprint, missing = analyze_blueprint(SAMPLE)

    # Act
    section = render_blueprint_prompt(blueprint, missing, "strict")

    # Assert
    assert "STRUCTURED BLUEPRINT" in section
    assert "STRICT ADHERENCE" in section
    assert "CORE_KEY, FUSE, MULTITOOL" in section
    assert '"code_to_unlock": "4711"' in section


def test_merge_enforces_fixed_values():
    # Arrange
    blueprint = parse_blueprint(SAMPLE)
    manifest = _generated_manifest()

    # Act
    violations = apply_blueprint(manifest, blueprint)

    # Assert
    assert violations == []
    assert manifest["language"] == "English"
    assert manifest["protagonist"]["name"] == "Mara Voss"
    assert manifest["protagonist"]["hp"] == 95  # hint only, LLM value stays
    assert manifest["protagonist"]["starting_inventory"] == ["MULTITOOL"]
    assert manifest["scenes"][0]["name"] == "Brig Cell"
    assert manifest["scenes"][1]["name"] == "Dark Corridor"  # open field
    exit_def = manifest["exits"][0]
    assert exit_def["code_to_unlock"] == "4711"
    assert exit_def["is_locked"] is True
    warden = manifest["npcs"][0]
    assert warden["hp"] == 40
    assert warden["attack_trigger"] == {"required_item_id": "CORE_KEY"}
    assert warden["special_actions"][0]["damage_value"] == "2d6"
    assert manifest["objects"][0]["item_type"] == "SWITCH"
    first_sequence = manifest["sequences"][0]
    assert first_sequence["title"] == "Break Out"
    assert first_sequence["required_scene_id"] == "CORRIDOR"
    assert first_sequence["soft_rules"][0]["id"] == "BRIBE"
    assert manifest["sequences"][1]["required_item_id"] == "CORE_KEY"
    assert manifest["scripts"][0]["trigger"] == "on_turn_end"


def test_merge_reports_entities_the_llm_dropped():
    # Arrange
    blueprint = parse_blueprint(SAMPLE)
    manifest = _generated_manifest()
    manifest["npcs"] = []
    manifest["scenes"] = manifest["scenes"][:1]
    manifest["exits"] = []

    # Act
    violations = apply_blueprint(manifest, blueprint)

    # Assert
    assert any("npc 'WARDEN' is missing" in violation for violation in violations)
    assert any("exit CELL -> CORRIDOR skipped" in violation for violation in violations)
    assert manifest["exits"] == []


@pytest.mark.asyncio
async def test_validate_endpoint_reports_issues(auth_client: AsyncClient):
    # Act
    response = await auth_client.post(
        "/api/adventures/blueprint/validate", json={"text": "[NPC: A] Bob\nhp: lots"}
    )

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["has_tags"] is True
    assert body["counts"] == {"npc": 1}
    assert "expected a whole number" in body["errors"][0]["message"]


def test_recipe_tag_maps_ingredients_results_and_kept_items():
    # Arrange
    text = (
        "A plague village.\n\n"
        "[Item: ANTIDOTE] Antidote\ntype: CONSUMABLE\n\n"
        "[Recipe: ANTIDOTE_RECIPE] Antidote recipe\n"
        "combine: ROOT + SALT + MORTAR\nkeep: mortar\nresults: ANTIDOTE\n\n"
        "[Item: CURE] Cure\nresult: ANTIDOTE\n"
    )

    # Act
    blueprint, _missing = analyze_blueprint(text)

    # Assert: `[Recipe]` and `results:` both imply CONSTRUCTABLE.
    assert blueprint.errors == []
    recipe, cure = blueprint.of_kind("item")[1:]
    assert recipe.fixed()["item_type"] == "CONSTRUCTABLE"
    assert recipe.fixed()["combination_ingredients"] == ["ROOT", "SALT", "MORTAR"]
    assert recipe.fixed()["kept_ingredients"] == ["MORTAR"]
    assert recipe.fixed()["result_item_ids"] == ["ANTIDOTE"]
    assert cure.fixed()["item_type"] == "CONSTRUCTABLE"


def test_scene_helpers_key_reaches_the_generated_scene():
    # Arrange
    text = (
        "[Scene: CRYPT] The Crypt\n"
        "helpers: |\n"
        "  CURSE_DAMAGE = 8\n"
        "  def crypt_curse():\n"
        "      tw.player.damage(CURSE_DAMAGE)\n"
    )
    blueprint, _missing = analyze_blueprint(text)
    manifest = {"scenes": [{"id": "CRYPT", "name": "Crypt", "description": "Cold stone."}]}

    # Act
    violations = apply_blueprint(manifest, blueprint)

    # Assert
    assert blueprint.errors == []
    assert violations == []
    helpers = manifest["scenes"][0]["helpers_script"]
    assert helpers.startswith("CURSE_DAMAGE = 8\ndef crypt_curse():")
    assert WorldSceneSchema.model_validate(manifest["scenes"][0]).helpers_script == helpers


def test_indented_tag_ends_a_multiline_value():
    # Arrange: a sequence's helpers block followed by one of its rules
    text = (
        "[Sequence: 1] The Trial\n"
        "helpers: |\n"
        "  def trial_answer(correct):\n"
        "      return correct\n"
        "  [Rule: RIGHT_ANSWER] The player answers correctly.\n"
        "  script: trial_answer(True)\n"
    )

    # Act
    blueprint, _missing = analyze_blueprint(text)

    # Assert
    sequence = next(b for b in blueprint.blocks if b.kind == "sequence")
    assert blueprint.errors == []
    assert sequence.fixed()["helpers_script"] == "def trial_answer(correct):\n    return correct"
    assert [(c.kind, c.ref) for c in sequence.children] == [("rule", "RIGHT_ANSWER")]
    assert sequence.children[0].fixed()["script"] == "trial_answer(True)"


MARKDOWN_SAMPLE = """# Derelict Salvage

A salvage tech wakes in the brig of a derelict ship.

---
<!-- World and Protagonist -->

## World
- **language**: English
- **lose_guard**: `tw.vars.get('radiation', 0) >= 100`
- **init_script**:
```python
tw.vars.set('radiation', 0)
```

## Protagonist: Mara Voss
- **hp**: `~80`
- `inventory`: `MULTITOOL`

## Locations

### Scene: CELL — Brig Cell
Rusted and cramped.
- **on_enter_text**: The hatch slams shut behind you.

### [Scene: CORRIDOR] ?

### Exit: CELL -> CORRIDOR — a jammed bulkhead door
- **code:** `4711`
- **on_unlock**:
```python
tw.vars.set('alarm', True)
tw.story.narrate("Klaxons howl.")
```

## Characters & Objects

### NPC: WARDEN - Unit 7 Security Drone
- **in**: `CORRIDOR`
- **hp**: 40
- **attack_when_holding**: `CORE_KEY`

#### Ability: TASER — Taser Burst
- **kind**: ATTACK
- **damage**: 2d6

### Switch: BREAKER — Breaker Panel
- **states**: OFF, ON
- **transition**: OFF -> ON | item: FUSE | fail: It sparks.
- **outcome**: ON -> flag: POWER_ON

## Story Chapters

## Sequence: 1 — Break Out
Mara must leave the cell.
- **goal_scene**: `CORRIDOR`
- **xp**: 150

### Rule: BRIBE — The player convinces @WARDEN to open the door.
- **max**: 1
```python
tw.exits.unlock('CELL', 'CORRIDOR')
```

### Script: ALARM_CHECK
- **trigger**: on_turn_end
```python
if tw.vars.get('alarm'):
    tw.story.narrate("Sirens echo.")
```

## Sequence: 2 — Into the Reactor
- **Required Item**: `CORE_KEY`

## Script: RADIATION_TICK
- **trigger**: on_turn_end
- **code**: |
  ```python
  tw.vars.set('radiation', tw.vars.get('radiation', 0) + 10)
  ```
"""


def test_markdown_blueprint_parses_identically_to_tag_syntax():
    # Act
    blueprint, missing = analyze_blueprint(MARKDOWN_SAMPLE)
    manifest = _generated_manifest()
    violations = apply_blueprint(manifest, blueprint)

    # Assert
    assert blueprint.errors == []
    assert violations == []
    assert blueprint.title == "Derelict Salvage"
    assert blueprint.premise == "A salvage tech wakes in the brig of a derelict ship."
    assert sorted(missing) == ["CORE_KEY", "FUSE", "MULTITOOL"]

    world = blueprint.first("world")
    assert world.fixed()["init_script"] == "tw.vars.set('radiation', 0)"

    cell = blueprint.of_kind("scene")[0]
    assert cell.description == "Rusted and cramped."

    corridor = blueprint.of_kind("scene")[1]
    assert corridor.open_fields == ["name"]

    warden = blueprint.first("npc")
    assert [child.ref for child in warden.children] == ["TASER"]

    first_seq = blueprint.of_kind("sequence")[0]
    assert [(c.kind, c.ref) for c in first_seq.children] == [
        ("rule", "BRIBE"),
        ("script", "ALARM_CHECK"),
    ]
    assert first_seq.children[0].fixed()["script"] == "tw.exits.unlock('CELL', 'CORRIDOR')"
    assert [b.ref for b in blueprint.of_kind("script")] == ["RADIATION_TICK"]
    assert manifest["exits"][0]["code_to_unlock"] == "4711"
    assert manifest["protagonist"]["name"] == "Mara Voss"
    assert manifest["protagonist"]["hp"] == 95


def test_switch_script_hooks_and_transition_scripts_are_parsed_and_validated():
    # Arrange
    text = (
        "## Switch: DIFFICULTY_SELECTOR — Difficulty Selector\n"
        "- **states**: EASY=Easy, MEDIUM=Medium, HARD=Hard\n"
        "- **initial**: EASY\n"
        "- **transition**: EASY -> MEDIUM | script: sync_active_teacher()\n"
        "- **on_success_script**:\n"
        "```python\n"
        "sync_active_teacher()\n"
        "```\n"
        "- **on_fail**: tw.story.narrate('Locked.')\n"
    )

    # Act
    blueprint, _missing = analyze_blueprint(text)

    # Assert
    assert blueprint.errors == []
    switch = blueprint.first("item")
    fixed = switch.fixed()
    assert fixed["item_type"] == "SWITCH"
    assert fixed["on_success_script"] == "sync_active_teacher()"
    assert fixed["on_failure_script"] == "tw.story.narrate('Locked.')"
    assert fixed["switch_transitions"][0]["on_success_script"] == "sync_active_teacher()"

    bad_bp, _ = analyze_blueprint(
        "[Switch: S] S\nstates: OFF, ON\ntransition: OFF -> ON | script: if True\n"
    )
    assert any("Syntax error" in err.message for err in bad_bp.errors)


def test_world_custom_and_catalog_image_style_and_tone():
    # Arrange: custom style + custom tone in Markdown
    custom_bp = prepare_blueprint(
        "## World\n"
        "- **image_style**: Isometric 16-bit pixel art, warm CRT amber glow\n"
        "- **tone**: Friendly, encouraging Python mentor with dry geek humor\n"
    )
    manifest: dict = {}
    apply_blueprint(manifest, custom_bp.blueprint)

    # Assert custom style and tone
    assert manifest["selected_image_styles"][0]["instruction"] == (
        "Isometric 16-bit pixel art, warm CRT amber glow"
    )
    assert manifest["selected_tone"]["instruction"] == (
        "Friendly, encouraging Python mentor with dry geek humor"
    )

    # Arrange: catalog style + catalog tone (hint mode)
    catalog_bp = prepare_blueprint("## World\n- **style**: ~Pixelart\n- **tone**: ~Sci-Fi\n")
    manifest_hint: dict = {}
    apply_blueprint(manifest_hint, catalog_bp.blueprint)

    # Assert catalog resolution and hint fallback
    assert manifest_hint["selected_image_styles"][0]["id"] == "pixelart"
    assert "pixel" in manifest_hint["selected_image_styles"][0]["instruction"].lower()
    assert manifest_hint["selected_tone"]["id"] == "sci-fi"


def test_container_switch_and_take_locked_items_parse_correctly():
    # Arrange
    text = (
        "[Scene: BREAK_ROOM] Break Room\n"
        "[ContainerSwitch: DISPENSER] Beverage Dispenser\n"
        "in: BREAK_ROOM\n"
        "contains: SODA_CAN\n"
        "states: OFF=Idle, ON=Dispensing\n"
        "initial: OFF\n"
        "outcome: ON -> unlock_item: SODA_CAN\n"
        "\n"
        "[Item: SODA_CAN] Cold Soda\n"
        "type: CONSUMABLE\n"
        "locked: yes\n"
    )

    # Act
    blueprint, missing = analyze_blueprint(text)

    # Assert
    assert blueprint.errors == []
    assert missing == []
    dispenser, soda = blueprint.of_kind("item")
    assert dispenser.fixed()["item_type"] == "CONTAINER_SWITCH"
    assert dispenser.fixed()["inventory"] == ["SODA_CAN"]
    assert dispenser.fixed()["switch_states"] == ["OFF", "ON"]
    assert dispenser.fixed()["switch_state_labels"] == {"OFF": "Idle", "ON": "Dispensing"}
    assert dispenser.fixed()["switch_outcomes"][0]["effects"][0] == {
        "type": "unlock_item",
        "target_id": "SODA_CAN",
        "key": "",
    }
    assert soda.fixed()["locked"] is True
