"""Scripting / trigger instructions for the world builder (LLM world generation).

The trigger catalogue below mirrors what the gameplay engine actually executes:

* Top-level ``scripts`` (see ``WorldScriptSchema``) are dispatched by the script runner
  for ``on_turn_start``, ``on_enter_scene``, ``on_interact``, ``on_logic_pass_done``,
  ``on_narration_done``, and ``on_turn_end``.
* Inline ``on_*_script`` / ``on_*_text`` fields on entities are executed by the turn
  state applier (``turn_state_applier.py`` / ``turn_interactions.py``).
* Sequence ``soft_rules`` are judged by the GM and run by the soft rule guard
  (``engine/rules/soft_rules.py``); ``tw.dialog`` choice handlers live in ``init_script``
  (``engine/scripting/dialog.py``).

Keep this catalogue in sync with ``docs/scripting_engine.md``.
"""

# (trigger, when it fires, target_id meaning)
TOP_LEVEL_TRIGGERS: tuple[tuple[str, str, str], ...] = (
    ("on_init", "once when the adventure session is first created", "None (global)"),
    ("on_turn_start", "before every turn is processed", "None (global)"),
    ("on_enter_scene", "when the protagonist enters a scene", "scene ID (or None for any scene)"),
    (
        "on_interact",
        "when the protagonist examines/attacks/talks to/manipulates an entity",
        "NPC or object ID (or None for any entity)",
    ),
    (
        "on_logic_pass_done",
        "after game mechanics and state changes are evaluated, before narration generation",
        "None (global)",
    ),
    ("on_narration_done", "after narrative generation completes", "None (global)"),
    ("on_turn_end", "after narration and state changes of every turn", "None (global)"),
)

# Entity kind -> ((trigger base name, description), ...). Every base name has a
# `<base>_script` and a `<base>_text` field on the matching schema.
INLINE_TRIGGERS: dict[str, tuple[tuple[str, str], ...]] = {
    "OBJECTS": (
        ("on_pickup", "the item is taken into the inventory"),
        ("on_drop", "the item is dropped"),
        (
            "on_interact",
            "the protagonist inspects, uses, pushes or tampers with the object (also fixed objects)",
        ),
        ("on_equip", "the item is equipped (only WEAPON/WEARABLE items)"),
        ("on_unequip", "the item is unequipped (only WEAPON/WEARABLE items)"),
        ("on_read", "the readable item is inspected or read (only READABLE items)"),
        ("on_unlock_success", "container is successfully unlocked (only CONTAINER items)"),
        (
            "on_unlock_failure",
            "container unlock fails or is blocked by guard (only CONTAINER items)",
        ),
        ("on_craft_success", "the recipe is crafted (only CONSTRUCTABLE recipes)"),
        (
            "on_craft_failure",
            "recipe crafting fails or is blocked by guard (only CONSTRUCTABLE recipes)",
        ),
    ),
    "SCENES": (
        ("on_enter_scene", "the protagonist enters this scene"),
        ("on_leave_scene", "the protagonist leaves this scene"),
    ),
    "EXITS": (
        ("on_exit_used", "the protagonist traverses or uses this exit"),
        ("on_open_exit", "this exit is opened/traversed"),
        ("on_unlock_success", "this exit is successfully unlocked"),
        ("on_unlock_failure", "this exit unlock fails or is blocked by guard"),
    ),
    "NPCS": (
        ("on_defeat", "the NPC is defeated"),
        ("on_protagonist_enters_scene", "the protagonist enters the scene containing this NPC"),
        ("on_interact", "the protagonist talks to, inspects or otherwise interacts with this NPC"),
    ),
    "PROTAGONIST": (
        ("on_hp_change", "the protagonist HP changes (e.g. damaged or healed)"),
        ("on_status_change", "the protagonist status effects change"),
    ),
    "SEQUENCES": (
        ("on_start_sequence", "this chapter sequence becomes active"),
        ("on_end_sequence", "this chapter sequence is completed"),
    ),
    "SPECIAL_ACTIONS (entries of protagonist/NPC special_actions)": (
        ("on_success", "the special attack's d20 success roll succeeds (`special` dict in scope)"),
        ("on_failure", "the special attack's success roll fails"),
    ),
}

# `tw` API reference. Only members that exist in engine/scripting/context.py.
TW_API_REFERENCE = (
    "AVAILABLE `tw` API (use ONLY these members, scripts run in a sandbox):\n"
    "- tw.player: hp, mana, stamina, xp, name | damage(n), heal(n), modify_hp/mana/stamina/xp(delta), "
    "give_item(item_id, name=None, description=None), remove_item(item_id), has_item(item_id), "
    "add_status_effect(name), remove_status_effect(name), has_status_effect(name)\n"
    "- tw.scene: id, npcs, items | teleport(scene_id)\n"
    "- tw.exits: is_locked(from_scene_id, to_scene_id), lock(from_scene_id, to_scene_id, reason), "
    "unlock(from_scene_id, to_scene_id)  (ALWAYS pass the two scene IDs of the exit)\n"
    "- tw.npcs / tw.objects (alias tw.items): get(id), exists(id), say(id, text), move(id, scene_id), "
    "move_to_player(id), kill(id), give_item(npc_id, item_id), drop_item(npc_id, item_id, scene_id=None), "
    "give_to_player(npc_id, item_id) (NPC hands an item it carries to the protagonist; None if it lacks it), "
    "attack(npc_id) (an NPC in the current scene starts turn-based combat after the turn)\n"
    "- tw.npcs persona (changes how the GM plays the NPC from then on, this session only): "
    "set_character(npc_id, text), set_goal(npc_id, text), add_trait(npc_id, trait), remove_trait(npc_id, trait)\n"
    "- entity proxies from get(): id, name, current_scene_id, is_hidden, set_hidden(bool); NPCs also hp, is_defeated, say(text), attack(), "
    "character, goal (read/write), set_character(text), set_goal(text), add_trait(t), remove_trait(t), has_trait(t); "
    "objects also state, switch_state, flip(), toggle()\n"
    "- tw.switches: get(id), get_state(id, default), set_state(id, new_state, apply_outcomes=True), "
    "is_state(id, state), flip(id, apply_outcomes=True), toggle(id, apply_outcomes=True) | switch proxies from get() or tw.switch(id): id, state, switch_state, states, initial_state, flip(), toggle()\n"
    "- tw.vars: get(key, default), set(key, value)  (persistent story flags)\n"
    "- tw.story: narrate(text), narrate_raw(text), system_message(text), reject_action(reason)\n"
    "- tw.memories.add(description, scope='global'|'local', emotion='positive'|'negative'|'neutral')\n"
    "- tw.quests: complete(quest_id), fail(quest_id), is_completed(quest_id)\n"
    "- tw.awards.grant(award_key) | tw.sequences.advance() | tw.dice.d20()\n"
    "- tw.llm.ask(prompt, model='simple'|'advanced', system='') -> str: asks the LLM for a short "
    "text (max 3 calls per trigger, returns '' on failure, not usable in guards). Use sparingly for "
    "flavour text and always provide a fallback: tw.llm.ask(...) or 'fixed text'.\n"
    "- tw.game: time | win(reason), game_over(reason)\n"
    "- tw.dialog.choose(prompt, options, on_choice, speaker=None, narrate=False): shows the player a "
    "multiple-choice dialog (NPC conversation, riddle, dilemma). `options` is a list of labels or "
    "{'label': ..., 'visible_if': '<guard expression>'} dicts (max 8). The call does NOT wait: once "
    "the player picks, the engine calls the function named by `on_choice` with the chosen option's "
    "index (its position in `options`). That handler MUST be defined in the top-level `init_script`; "
    "it may call tw.dialog.choose again for multi-step conversations. narrate=True lets the GM "
    "narrate the outcome.\n"
    "- tw.log / tw.debug: tw.log(msg), tw.log.info/warn/error(msg) or print(msg) (outputs to server console); "
    "tw.debug(msg) (emits in-game [DEBUG: Script] notification when debug mode is ON)\n"
)

_EXAMPLES = (
    "VALID EXAMPLES:\n"
    "1. Trap on interact (top-level: trigger='on_interact', target_id='CHEST_01'):\n"
    "   if not tw.vars.get('trap_disarmed', False):\\n"
    "       tw.player.damage(15)\\n"
    "       tw.story.narrate('A poisoned needle springs from the lock mechanism! (-15 HP)')\n"
    "2. Gatekeeper on enter scene (top-level: trigger='on_enter_scene', target_id='SCENE_GATES'):\n"
    "   if not tw.player.has_item('ITEM_KEY'):\\n"
    "       tw.exits.lock('SCENE_GATES', 'SCENE_COURTYARD', 'The heavy iron portcullis is barred.')\\n"
    "       tw.story.narrate('The sentinel lowers his spear, barring the passage.')\\n"
    "   else:\\n"
    "       tw.exits.unlock('SCENE_GATES', 'SCENE_COURTYARD')\n"
    "3. Cursed weapon (inline on the object: on_equip_script):\n"
    "   tw.player.damage(5)\\n"
    "   tw.story.narrate('The blade burns your palm as you grip it.')\n"
    "4. Boss loot (inline on the NPC: on_defeat_script):\n"
    "   tw.player.give_item('ITEM_BOSS_KEY')\\n"
    "   tw.story.narrate('The warlord drops a heavy iron key.')\n"
    "5. Atmosphere only (inline `..._text` field, no code): on_enter_scene_text = "
    "'A cold draft carries the smell of old blood.'\n"
    "6. Switch activation (inline on switch: on_success_script):\n"
    "   tw.exits.unlock('SCENE_LAB', 'SCENE_VAULT')\n"
    "   tw.story.narrate('A loud click echoes through the vault corridors.')\n"
    "7. Secret document on read (inline on READABLE object: on_read_script):\n"
    "   tw.vars.set('read_secret_plans', True)\n"
    "   tw.story.narrate('You memorize the classified blueprints.')\n"
    "8. Container unlock guard (inline on CONTAINER object: unlock_expression & on_unlock_success_script):\n"
    "   unlock_expression = \"tw.switches.get('POWER_CORE') == 'ACTIVE'\"\n"
    "   on_unlock_success_script = \"tw.story.narrate('The cryo-chamber decompresses with a hiss.')\"\n"
    "9. Exit unlock guard and traversal (inline on exit: unlock_expression, on_unlock_success_script, on_exit_used_script):\n"
    "   unlock_expression = \"tw.switches.get('DRAWBRIDGE_LEVER') == 'LOWERED'\"\n"
    "   on_unlock_success_script = \"tw.story.narrate('The heavy portcullis raises.')\"\n"
    "   on_exit_used_script = \"tw.vars.set('entered_keep', True)\"\n"
    "10. Quest deterministic guard (inline on quest: guard_expression):\n"
    "   guard_expression = \"tw.player.has_item('ANCIENT_RELIC') and tw.vars.get('relic_cleansed') == True\"\n"
    "11. Award deterministic guard (inline on award: guard_expression):\n"
    "   guard_expression = \"tw.vars.get('pacifist_boss_spared') == True\"\n"
    "12. Adventure Win deterministic guard (top-level completed_guard_expression):\n"
    "   completed_guard_expression = \"tw.vars.get('boss_defeated') == True and tw.player.has_item('ITEM_CRYSTAL')\"\n"
    "13. Adventure Loss deterministic guard (top-level gameover_guard_expression):\n"
    "   gameover_guard_expression = \"tw.vars.get('countdown', 10) <= 0 or tw.vars.get('alarm_tripped') == True\"\n"
    "14. Guard attacks once the idol is taken (top-level: trigger='on_turn_end', target_id=None):\n"
    "   if tw.player.has_item('ITEM_IDOL') and not tw.vars.get('idol_alarm', False):\\n"
    "       tw.vars.set('idol_alarm', True)\\n"
    "       tw.npcs.attack('NPC_TEMPLE_GUARD')\n"
    "15. Special attack success hook (inline on a special_actions entry: on_success_script):\n"
    "   if special['crit']:\\n"
    "       tw.story.narrate('The insult is so brutal that the troll starts to cry.')\n"
    "16. Special attack unlock guard (protagonist special_actions entry with is_locked=true):\n"
    "   unlock_guard_expression = \"tw.vars.get('trained_with_master') == True\"\n"
    "17. NPC hands over an item (sequence soft_rules entry: condition='Arthur flirts with Brenda', "
    "max_triggers=1, script):\n"
    "   if tw.npcs.give_to_player('BRENDA', 'BRENDA_KEY'):\\n"
    "       tw.npcs.say('BRENDA', 'Fine, charmer. Take it before I change my mind.')\n"
    "18. Bomb choice dialog (handler in top-level init_script, dialog opened by the bomb's "
    "on_pickup_script):\n"
    "   init_script:\n"
    "   def on_bomb_wire(answ):\\n"
    "       if answ == 0:\\n"
    "           tw.vars.set('bomb_disarmed', True)\\n"
    "           tw.story.narrate('The ticking stops. You disarmed the trap.')\\n"
    "       elif answ == 1:\\n"
    "           tw.game.game_over('The bomb exploded.')\\n"
    "       else:\\n"
    "           tw.player.damage(5)\\n"
    "           tw.story.narrate('Panic costs you precious seconds.')\n"
    "   on_pickup_script:\n"
    "   tw.dialog.choose('The bomb starts ticking. What do you do?', "
    "['Cut the red wire', 'Cut the blue wire', 'Scream like a baby'], on_choice='on_bomb_wire')\n"
    "19. Riddle conversation opened by a soft rule (sequence soft_rules entry: condition='The "
    "player asks the sphinx to let them pass', max_triggers=1, script):\n"
    "   tw.dialog.choose('What walks on four legs at dawn, two at noon, three at dusk?', "
    "['A man', 'A dog', 'A ghost'], on_choice='on_sphinx_riddle', speaker='The Sphinx', "
    "narrate=True)\n"
    "   (init_script defines on_sphinx_riddle(answ) and unlocks the gate exit when answ == 0)\n"
)


def _top_level_trigger_lines() -> str:
    return "".join(
        f"  - `{name}`: {when}; `target_id` = {target}\n"
        for name, when, target in TOP_LEVEL_TRIGGERS
    )


def _inline_trigger_lines() -> str:
    lines = []
    for kind, triggers in INLINE_TRIGGERS.items():
        fields = ", ".join(f"`{base}_script`, `{base}_text`" for base, _ in triggers)
        whens = "; ".join(f"{base}: {desc}" for base, desc in triggers)
        lines.append(f"- {kind}: {fields}  ({whens})\n")
    return "".join(lines)


def build_scripts_requirement(scripts_generation_enabled: bool) -> str:
    """Return the scripting section appended to the world generation user prompt."""
    if not scripts_generation_enabled:
        return (
            "\nSCRIPTING: Do NOT generate any custom scripts. Keep scripts: [], init_script empty, "
            "every sequence's soft_rules: [] and do not populate any on_*_script or on_*_text "
            "fields (leave them as empty strings). Do not use tw.dialog."
        )
    separator = "=" * 80
    return (
        f"\n\n{separator}\n"
        "CRITICAL DIRECTIVE - EVENT SCRIPTS ACTIVELY REQUESTED BY USER:\n"
        "The user has explicitly turned ON the Event Scripts Engine for this adventure. "
        "The world MUST contain interactive event scripts!\n\n"
        "1) TOP-LEVEL SCRIPTS: generate between 1 and 3 high-quality, deterministic scripts in the "
        "top-level `scripts` array. Each has `id` (unique uppercase slug, e.g. 'SCRIPT_TRAP_CHEST'), "
        "`name`, `trigger`, `target_id`, `code` and optional `description`. "
        "`trigger` must be EXACTLY one of:\n"
        f"{_top_level_trigger_lines()}\n"
        "2) INLINE TRIGGERS: you MUST ALSO attach inline triggers directly to entities. Every trigger has a "
        "`..._text` field (prints a fixed message) and a `..._script` field (runs `tw` code). "
        "Use an empty string for every trigger you do not need. Fill the following fields where they fit "
        "the story (aim for several across different entity kinds, e.g. a cursed item, a guarded scene, "
        "a boss that drops loot):\n"
        f"{_inline_trigger_lines()}\n"
        "3) SEQUENCE SOFT RULES: every sequence has a `soft_rules` list of narrative rules that are "
        "ONLY active while that sequence runs. Each entry has `id` (unique uppercase slug), "
        "`condition` (a concrete, observable player action judged by the GM, e.g. 'The player bribes "
        "the guard'), `script` (tw code the engine runs when the GM reports the condition as "
        "fulfilled), optional `text`, optional `guard_expression` (deterministic precondition) and "
        "optional `max_triggers` (use 1 for one-off rewards). Add soft rules where a chapter has "
        "social or creative solutions (persuading, flirting, threatening, bargaining) that need a "
        "deterministic effect. The GM never sees the script, so the condition must describe the "
        "action, not its outcome. Use [] for sequences without such interactions.\n\n"
        "4) CHOICE DIALOGS: use tw.dialog.choose (see API below) for NPC conversations, riddles and "
        "dilemmas where the player picks from fixed answers. Open the dialog from a script or a soft "
        "rule script and define its `on_choice` handler function in the top-level `init_script`. "
        "Every branch must keep the adventure winnable: a wrong answer may cost HP or reopen the "
        "dialog, but must not block the main path unless it is an intended game over.\n\n"
        "5) SEQUENCE SCRIPTS: every sequence has a `scripts` list with the same shape as top-level "
        "scripts (`id`, `name`, `trigger`, `target_id`, `code`) that ONLY run while that sequence "
        "is active (any top-level trigger except on_init). Prefer them over top-level scripts for "
        "chapter-specific behaviour, e.g. an on_interact script on an object that should only "
        "react during one chapter. Use [] for sequences without such scripts.\n\n"
        "RULES:\n"
        "- NATURAL-LANGUAGE CONDITIONS VS. HARD RULES (MUTUAL EXCLUSIVITY): Use EITHER a natural-language condition (quest goal, award/win/loss condition text judged by the GM) OR deterministic hard rules / scripted guards on any given asset, but NOT both. If you set a guard_expression or hard rule on a sequence, quest, award, container, exit, or win/loss condition, keep its natural-language condition strictly descriptive. This does not restrict sequence `soft_rules`, which may carry their own guard_expression.\n"
        "- Only reference scene/exit/NPC/object/quest IDs that exist in this manifest.\n"
        "- Prefer `..._text` for pure flavour, `..._script` for mechanics (damage, items, locks, flags).\n"
        "- Keep inline scripts short (max ~10 lines); never use imports, file/network access or loops over huge ranges.\n"
        "- `on_equip_*`/`on_unequip_*` are only meaningful for WEAPON/WEARABLE objects.\n"
        "- Scripts must be consistent with the walkthrough: they must never make the adventure unwinnable.\n\n"
        f"{TW_API_REFERENCE}\n"
        f"{_EXAMPLES}"
        f"{separator}\n"
    )
