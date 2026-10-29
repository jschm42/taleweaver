import pytest
from pydantic import ValidationError

from backend.engine.world.world_schemas import (
    WorldExitSchema,
    WorldNPCSchema,
    WorldObjectSchema,
    WorldSceneSchema,
    WorldScriptSchema,
)
from backend.engine.world.world_scripting_prompt import (
    INLINE_TRIGGERS,
    TOP_LEVEL_TRIGGERS,
    build_scripts_requirement,
)


def test_top_level_and_inline_triggers_catalog():
    top_level_names = [t[0] for t in TOP_LEVEL_TRIGGERS]
    assert "on_enter_scene" in top_level_names
    assert "on_interact" in top_level_names
    assert "on_turn_start" in top_level_names
    assert "on_logic_pass_done" in top_level_names
    assert "on_narration_done" in top_level_names
    assert "on_turn_end" in top_level_names

    assert "SCENES" in INLINE_TRIGGERS
    scene_bases = [t[0] for t in INLINE_TRIGGERS["SCENES"]]
    assert "on_enter_scene" in scene_bases

    assert "EXITS" in INLINE_TRIGGERS
    exit_bases = [t[0] for t in INLINE_TRIGGERS["EXITS"]]
    assert "on_open_exit" in exit_bases

    assert "NPCS" in INLINE_TRIGGERS
    npc_bases = [t[0] for t in INLINE_TRIGGERS["NPCS"]]
    assert "on_defeat" in npc_bases
    assert "on_protagonist_enters_scene" in npc_bases

    assert "OBJECTS" in INLINE_TRIGGERS
    obj_bases = [t[0] for t in INLINE_TRIGGERS["OBJECTS"]]
    assert "on_pickup" in obj_bases
    assert "on_drop" in obj_bases
    assert "on_equip" in obj_bases
    assert "on_unequip" in obj_bases


def test_build_scripts_requirement_prompt_content():
    prompt = build_scripts_requirement(True)
    assert "TOP-LEVEL SCRIPTS" in prompt
    assert "on_enter_scene" in prompt
    assert "on_interact" in prompt
    assert "on_turn_start" in prompt
    assert "on_logic_pass_done" in prompt
    assert "on_narration_done" in prompt
    assert "on_turn_end" in prompt
    assert "INLINE TRIGGERS" in prompt
    assert "on_enter_scene_script" in prompt
    assert "on_open_exit_script" in prompt
    assert "on_defeat_script" in prompt
    assert "on_pickup_script" in prompt
    assert "on_drop_script" in prompt
    assert "on_equip_script" in prompt
    assert "on_unequip_script" in prompt
    assert "tw.player" in prompt
    assert "tw.player.give_item" in prompt

    assert "SEQUENCE SOFT RULES" in prompt
    assert "max_triggers" in prompt
    assert "tw.dialog.choose" in prompt
    assert "init_script" in prompt

    disabled_prompt = build_scripts_requirement(False)
    assert "Do NOT generate any custom scripts" in disabled_prompt
    assert "soft_rules: []" in disabled_prompt


def test_world_schemas_trigger_validation():
    script = WorldScriptSchema(
        id="SCRIPT_THRONE_ROOM",
        name="Throne Room Event",
        trigger="on_enter_scene",
        target_id="THRONE_ROOM",
        code="tw.system_message('Entered throne room!')",
        description="Trigger when entering throne room",
    )
    assert script.trigger == "on_enter_scene"
    assert script.target_id == "THRONE_ROOM"
    with pytest.raises(ValidationError):
        WorldScriptSchema(
            id="SCRIPT_BAD",
            name="Bad Script",
            trigger="invalid_trigger",  # type: ignore[arg-type]
            code="tw.system_message('test')",
        )

    scene = WorldSceneSchema(
        id="SCENE_1",
        name="Courtyard",
        description="A stone courtyard.",
        on_enter_scene_script="tw.system_message('Welcome!')",
        on_enter_scene_text="You hear crows cawing overhead.",
    )
    assert scene.on_enter_scene_script == "tw.system_message('Welcome!')"
    assert scene.on_enter_scene_text == "You hear crows cawing overhead."

    exit_obj = WorldExitSchema(
        from_scene_id="SCENE_1",
        to_scene_id="SCENE_2",
        label="Heavy Iron Gate",
        is_bidirectional=False,
        is_locked=False,
        on_open_exit_script="tw.system_message('The gate groans.')",
        on_open_exit_text="The gate hinges screech loudly.",
    )
    assert exit_obj.on_open_exit_script == "tw.system_message('The gate groans.')"

    npc = WorldNPCSchema(
        id="GUARD_1",
        name="Guard",
        description="A vigilant guard.",
        goal="Protect the castle.",
        character="Stoic and loyal.",
        start_scene_id="SCENE_1",
        spatial_position="standing by the gate",
        npc_type="HUMANOID",
        hp=50,
        mana=0,
        stamina=80,
        is_attackable=True,
        is_killable=True,
        is_hidden=False,
        on_defeat_script="tw.give_item('PRISON_KEY')",
        on_defeat_text="Ugh... you won't get far...",
        on_protagonist_enters_scene_script="tw.system_message('Halt!')",
        on_protagonist_enters_scene_text="Who goes there?",
    )
    assert npc.on_defeat_script == "tw.give_item('PRISON_KEY')"
    assert npc.on_protagonist_enters_scene_text == "Who goes there?"

    item = WorldObjectSchema(
        id="MAGIC_RING",
        name="Ring of Fortitude",
        description="A golden ring.",
        start_scene_id="SCENE_1",
        spatial_position="resting on a stone pedestal",
        item_type="WEARABLE",
        wearable_slots=["Ring"],
        is_hidden=False,
        is_portable=True,
        on_pickup_script="tw.system_message('The ring hums with power.')",
        on_pickup_text="You feel a warm tingle as you lift the ring.",
        on_drop_script="tw.system_message('The hum ceases.')",
        on_drop_text="The cold stone mutes the ring.",
        on_equip_script="tw.stat_mod('strength', 5)",
        on_equip_text="Power courses through your muscles.",
        on_unequip_script="tw.stat_mod('strength', -5)",
        on_unequip_text="Your strength ebbs back to normal.",
    )
    assert item.on_pickup_script == "tw.system_message('The ring hums with power.')"
    assert item.on_equip_text == "Power courses through your muscles."
