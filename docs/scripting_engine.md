# TaleWeaver Scripting Engine Guide

The **TaleWeaver Scripting Engine** provides a secure, sandboxed environment for embedding deterministic event-driven logic directly into adventures. By authoring lightweight Python-style scripts, world builders and the AI World-Builder can craft complex interactive puzzles, reactive traps, dynamic NPC movements, and custom victory or defeat conditions that seamlessly interface with TaleWeaver's generative game master.

---

## Table of Contents
1. [Overview & Architecture](#overview--architecture)
2. [Sandbox Security & Limits](#sandbox-security--limits)
3. [Event Triggers & Lifecycle](#event-triggers--lifecycle)
4. [Global Initialization Script & Helper Methods](#global-initialization-script--helper-methods)
   - [Scene Helpers](#scene-helpers-helpers_script)
   - [Sequence Helpers](#sequence-helpers)
5. [The `tw` Scripting API](#the-tw-scripting-api)
   - [tw.player](#twplayer)
   - [tw.scene](#twscene)
   - [tw.exits](#twexits)
   - [tw.npcs](#twnpcs)
   - [tw.objects](#twobjects)
   - [tw.switches](#twswitches)
   - [tw.vars](#twvars-persistent-state)
   - [tw.story](#twstory)
   - [tw.save (Save States)](#twsave-save-states)
   - [tw.memories](#twmemories)
   - [tw.game](#twgame)
   - [tw.time (In-Game Clock)](#twtime-in-game-clock)
   - [tw.audio (Generated Background Audio)](#twaudio-generated-background-audio)
   - [tw.quests](#twquests)
   - [tw.awards](#twawards)
   - [tw.dice](#twdice)
   - [tw.dialog (Choice Dialogs)](#twdialog-choice-dialogs)
   - [tw.dialog.tree (Nested NPC Dialogues)](#twdialogtree-nested-npc-dialogues)
   - [tw.llm & tw.json (Ask the LLM & Structured JSON)](#twllm--twjson-ask-the-llm--structured-json)
   - [tw.image & tw.media (In-Game Image Generation)](#twimage--twmedia-in-game-image-generation)
   - [tw.turn (Player Message & Turn Info)](#twturn-player-message--turn-info)
   - [tw.log & tw.debug (Logging & Diagnostics)](#twlog--twdebug-logging--diagnostics)
6. [Practical Examples](#practical-examples)
   - [Example 1: Trapped Ancient Chest](#example-1-trapped-ancient-chest)
   - [Example 2: Gatekeeper Guard Blocking Passage](#example-2-gatekeeper-guard-blocking-passage)
   - [Example 3: Three-Lever Puzzle with Persistent State](#example-3-three-lever-puzzle-with-persistent-state)
   - [Example 4: Boss Encounter & Victory Condition](#example-4-boss-encounter--victory-condition)
   - [Example 5: Turn-Based Survival Countdown](#example-5-turn-based-survival-countdown)
   - [Example 8: Switch Mechanism State & Guard Expression](#example-8-switch-mechanism-state--guard-expression)
   - [Example 9: Global Init Script with Helper Functions](#example-9-global-init-script-with-helper-functions)
   - [Example 10: NPC Hands the Player an Item (Sequence Soft Rule)](#example-10-npc-hands-the-player-an-item-sequence-soft-rule)
   - [Example 11: Bomb Defusal Choice Dialog](#example-11-bomb-defusal-choice-dialog)
   - [Example 12: Sphinx Riddle Conversation (Soft Rule + Dialog)](#example-12-sphinx-riddle-conversation-soft-rule--dialog)
   - [Example 13: The Player's Words Change an NPC's Mood](#example-13-the-players-words-change-an-npcs-mood)
   - [Example 14: Potion Dispenser (Cloning a Hidden Item)](#example-14-potion-dispenser-cloning-a-hidden-item)
   - [Example 15: Offering Altar (Player Puts Items into a Container)](#example-15-offering-altar-player-puts-items-into-a-container)
   - [Example 16: Blacksmith Conversation (Dialogue Tree)](#example-16-blacksmith-conversation-dialogue-tree)
   - [Example 18: Ticking Bomb and Nightfall (Time Events)](#example-18-ticking-bomb-and-nightfall-time-events)
7. [Authoring in the World-Editor](#authoring-in-the-world-editor)

---

## Overview & Architecture

While TaleWeaver's generative LLM master creates rich, adaptive prose and roleplay, certain game mechanics (such as combination locks, physical traps, locked gates, and badge criteria) require **deterministic, tamper-proof execution**.

```
                           +------------------------+
                           |   Session Start / New  |
                           +-----------+------------+
                                       |
                                       v
                           [Global Init Script]
                           [on_init scripts]
                                       |
                                       v
                           +------------------------+
                           |     Player Action      |
                           +-----------+------------+
                                       |
                                       v
         +-----------------------------------------------------------+
         |                 Player Message Processing                 |
         |  - Scene transition  --> [on_enter_scene scripts]         |
         |  - Entity action     --> [on_interact scripts]            |
         |  - Rule checks & combat --> [on_logic_pass_done scripts]  |
         +-----------------------------+-----------------------------+
                                       |
                     scene or sequence changed this message?
                                       |  yes
                                       v
               [on_turn_end] -> status ticks -> [on_turn_start]
                                       |
                                       v
                      LLM narration --> [on_narration_done scripts]
                                       |
                                       v
               clock tick (minutes per tick) --> [time events:
                     on_time_reached scripts, tw.time timers]
                                       |
                                       v
                           +-----------+------------+
                           |  Narrative & UI State  |
                           +------------------------+
```

Every script executes inside an isolated AST interpreter (`SafeAstInterpreter`), generating an atomic `ScriptChangeset` that updates scenes, locks, items, NPC locations, and avatar parameters before client rendering.

---

## Sandbox Security & Limits

To ensure player safety and server reliability:

- **Pure AST Interpretation**: Scripts are evaluated node-by-node against a strict AST whitelist without calling unrestricted `eval()`, `exec()`, or invoking CPython bytecode.
- **Custom Functions & Lambdas**: Scripts can declare custom helper functions (`def func_name(arg1, arg2=default): ...`) and lambda expressions (`lambda x: ...`). Return values are safely handled via internal signal exceptions.
- **No System Calls or Imports**: Statements like `import`, `from ... import`, `open()`, `eval()`, or `exec()` are rejected at parse time.
- **No Private or Dunder Identifiers**: Accessing attributes or defining functions starting with an underscore (e.g. `_internal`, `__class__`, `__subclasses__`, `__globals__`, or `__dict__`) is strictly forbidden. Variables starting with an underscore cannot be assigned either; the only exception is the bare throwaway name `_` (e.g. `for item_id, _ in ITEMS:` or `first, _ = pair`).
- **No Introspection Escapes**: `str.format`, `format_map` and `mro` are blocked (format strings could otherwise walk `{0.__globals__}`), as are frame/generator/code attributes (`f_*`, `gi_*`, `cr_*`, `ag_*`, `tb_*`, `co_*`). Use f-strings or `+` for text.
- **Instruction & Time Budget**: Each script execution is capped at **10,000 steps** and **2 seconds** (`ScriptTimeoutError`), preventing infinite loops and CPU exhaustion. Time spent waiting for `tw.llm.ask` or `tw.image.generate` does not count against the 2 seconds. Loading the definitions of `init_script` and all helper blocks before a run has its own budget of the same size, so large helper blocks (e.g. dialogue-tree constants) do not eat into the script's steps.
- **Memory Protections**: Strings, lists, tuples and dicts are capped at **100,000** elements/characters (repetition, concatenation, `join`, padding methods and call results are all checked), `range()` at 100,000 elements, and integers at 10,000 bits (`ScriptSecurityError`).
- **Safe Builtins**: Available built-ins are restricted to `abs`, `all`, `any`, `bool`, `dict`, `enumerate`, `float`, `int`, `len`, `list`, `max`, `min`, `print`, `range`, `reversed`, `round`, `set`, `sorted`, `str`, `sum`, `tuple`, `zip`. Set literals (`{1, 2, 3}`) and set comprehensions are supported.
- **Inline conditionals**: `a if condition else b` is supported.
- **Comprehensions**: list, set and dict comprehensions and generator expressions are supported, including filters and nested `for` clauses (`[n.id for n in tw.scene.npcs if not n.is_hidden]`, `any(n.id == "GUARD" for n in tw.scene.npcs)`). They are evaluated eagerly: every element counts against the step budget and the result against the size limit, and a generator expression yields a list (so `any()` does not stop at the first match). Loop variables stay inside the comprehension. Async comprehensions are not supported.
- **Not supported**: `while` loops, `try`/`except`, `with` and `class`.

---

## Event Triggers & Lifecycle

Scripts declare a trigger event and an optional target entity or scene.

| Trigger | When it Executes | Target Field Usage |
| :--- | :--- | :--- |
| `on_init` | When a new game session starts, immediately after initial world manifest and entity state setup. | Global (`*` or empty). |
| `on_turn_start` | When a new in-game turn begins, i.e. right after the player's scene or the active sequence changed (after `on_turn_end` of the previous turn, before narration). | Global (`*` or empty). |
| `on_enter_scene` | When the player enters a new scene. | Specific `scene_id` or empty for any scene. |
| `on_interact` | When the player examines, attacks, talks to, or manipulates an entity: the GM reported a state change on it, or the player's message names an entity in the current scene or inventory (all context-menu actions such as *Inspect*, *Use*, *Push* do). Naming means the full name, the ID, or a single word of the name (at least 4 letters) that no other entity's name in the scene or inventory contains: "talk to Grimsby" reaches *Grimsby the Gargoyle*, while "open the casket" reaches none of several caskets. It does not fire during the opening narration of a new session or the arrival narration after walking through an exit: those only describe the scene. | Specific `entity_id` (NPC or object) or empty for all. |
| `on_logic_pass_done` | After game mechanics and state mutations finish, before narration is generated. | Global (`*` or empty). |
| `on_narration_done` | After narration generation completes, before final turn persistence. | Global (`*` or empty). |
| `on_turn_end` | When the current in-game turn ends, i.e. when the player's scene or the active sequence changed (before `on_turn_start` of the next turn). | Global (`*` or empty). |
| `on_time_reached` | Once, when the in-game clock reaches the target time (elapsed time since the adventure started). It fires again only after the time was set back below the target. See [tw.time](#twtime-in-game-clock). | **Required**: the elapsed time, e.g. `90`, `2h 30m`, `1d 4h`, `1:30`. |

> **In-game turns vs. player messages:** An in-game turn spans all player messages within one scene and sequence. Status-effect ticks and the `on_turn_end` / `on_turn_start` hooks only fire on a scene or sequence change. The **clock** is different: it advances once per narrated player message (see [tw.time](#twtime-in-game-clock)). Use `on_logic_pass_done` or `on_narration_done` for logic that must run on every player message.

### Inline Entity Triggers

In addition to standalone script assets, TaleWeaver allows configuring short inline scripts directly on entities, NPCs, scenes, exits, protagonist, and sequences via the World Editor. These execute automatically during specific interactions.

| Entity Type | Available Triggers / Guards | Description |
| :--- | :--- | :--- |
| **Objects (General)** | `on_interact_script`, `on_interact_text` | Executes whenever the player interacts with the object (inspect, use, push, tamper), also for fixed, non-portable objects. |
| | `on_pickup_script`, `on_pickup_text` | Executes when the item is taken into inventory. |
| | `on_drop_script`, `on_drop_text` | Executes when the item is dropped into the scene. |
| **Wearables & Weapons** | `on_equip_script`, `on_equip_text` | Executes when the player equips a WEAPON or WEARABLE. |
| | `on_unequip_script`, `on_unequip_text` | Executes when the player unequips a WEAPON or WEARABLE. |
| **Readable Items** | `on_read_script`, `on_read_text` | Executes when the player inspects or reads this item. |
| **Container & Container-Switch Items** | `unlock_expression` *(Guard)* | Deterministic Python boolean expression evaluated when attempting to unlock. If false, unlocking fails. |
| | `on_unlock_success_script`, `..._text` | Executes immediately when this container is successfully unlocked. |
| | `on_unlock_failure_script`, `..._text` | Executes when unlocking this container fails or is blocked by guard. |
| | `on_items_added_script`, `..._text` | Executes once after the player put one or more items into this container (container panel → **Put In**, or `/container_put_items`). `added_items` (list of dicts) and `added_item_ids` (list of IDs) are in scope. |
| | `on_items_removed_script`, `..._text` | Executes once after the player takes or drops one or more items out of this container (`Take`, `Take All`, or `Drop in Scene`). `removed_items` (list of dicts) and `removed_item_ids` (list of IDs) are in scope. |
| **Switches & Container-Switches** | `gates.expression` *(Guard)* | Deterministic Python boolean condition required for a specific transition. |
| | `on_success_script` | Executes when any state transition succeeds on this switch (or transition-specific). |
| | `on_failure_script` | Executes when any state transition fails on this switch (or transition-specific). |
| **Constructable Recipes** | `craft_guard_expression` *(Guard)* | Optional Python boolean expression evaluated in addition to ingredients. If false, crafting fails. |
| | `on_craft_success_script`, `..._text` | Executes when this recipe is successfully crafted (its `result_item_ids` are revealed). The script runs with the recipe as its entity. The text replaces the default craft message. |
| | `on_craft_failure_script`, `..._text` | Executes when crafting fails or is blocked by guard. |
| **NPCs** | `on_defeat_script`, `on_defeat_text` | Executes when the NPC is defeated. Use to spawn loot or change state. |
| | `on_protagonist_enters_scene_script` | Executes when the player enters the room containing this NPC. |
| | `on_interact_script`, `on_interact_text` | Executes whenever the player talks to, inspects or otherwise interacts with this NPC. The NPC context menu's **Greet** entry also counts as an interaction and fires it. |
| | `on_receive_item_script`, `..._text` | Executes once after the player gave this NPC one or more items (NPC context menu → **Give**, `/give_items <npc> \| A, B`, or typing `give <item> to <npc>`). The items are already in the NPC's inventory. `received_items` (list of dicts) and `received_item_ids` (list of IDs) are in scope. Afterwards the Game Master narrates the NPC's reaction, unless the script opened a choice dialog (`tw.dialog.choose` / `tw.dialog.tree`): then the player's answer drives what happens next and no GM reaction runs. |
| **Scenes** | `on_enter_scene_script`, `..._text` | Executes when the player enters this specific scene. |
| | `on_leave_scene_script`, `..._text` | Executes immediately when the player leaves this specific scene. |
| | `helpers_script` *(definitions)* | Not a trigger: functions and constants every script can call. See [Scene Helpers](#scene-helpers-helpers_script). |
| **Exits** | `on_open_exit_script`, `..._text` | Executes when the player opens or traverses this exit. |
| | `on_exit_used_script`, `..._text` | Transition Trigger: Executes specifically when the player successfully traverses this exit to enter the destination scene. |
| | `unlock_expression` *(Guard)* | Deterministic Python boolean expression evaluated when unlocking. If false, unlocking fails. |
| | `on_unlock_success_script`, `..._text` | Executes immediately when this exit is successfully unlocked. |
| | `on_unlock_failure_script`, `..._text` | Executes when unlocking this exit fails or is blocked by guard. |
| **NPC combat** *(metadata)* | `attack_mode: ATTACK_ON_SIGHT` | The NPC starts turn-based combat as soon as the protagonist enters its scene. |
| | `combat_group`, `assist_mode` (`GROUP` / `ANYONE` / `NEVER`) | Not a trigger: decide which NPCs in the scene join a fight they were not attacked in. NPCs sharing a `combat_group` fight together; NPCs without one are bystanders by default. See [Combat groups](world-builder-syntax.md#npc-id-name). |
| | `attack_trigger` *(Hard Rules + Guard)* | `required_item_id`, `required_scene_id`, `required_defeated_npc_id`, `guard_expression`: the NPC attacks once when all are met while the protagonist shares its scene. |
| **Special attacks** (protagonist & NPC `special_actions` entries) | `on_success_script`, `..._text` | Executes after a successful d20 success roll. A `special` dict (`id`, `name`, `caster`, `target`, `success`, `crit`, `fumble`, `roll`, `dc`) is in scope. |
| | `on_failure_script`, `..._text` | Executes when the success roll fails. |
| | `unlock_required_item_id`, `unlock_required_scene_id`, `unlock_required_defeated_npc_id`, `unlock_guard_expression` *(Hard Rules + Guard, protagonist only)* | A locked special unlocks after the turn in which all configured conditions are met; a system message (plus optional `unlock_text`) announces it. |
| **Talents** (protagonist `talents` entries) | `on_use_script`, `on_use_text` | Executes on every successful use of the talent (menu, right-click menu, `/talent` or typed `use <talent>` / `cast <talent> on <target>`), after the engine paid the cost and before the Game Master narrates the effect. A `talent` dict (`id`, `name`, `target_id`, `target_name`, `target_type` (`NPC`/`ITEM`/`None`), `uses`, `uses_left`) is in scope. Example: `if talent['target_id'] == 'CLERK': tw.flags.set('CLERK_SECRET_KNOWN')`. |
| | `unlock_required_item_id`, `unlock_required_scene_id`, `unlock_required_defeated_npc_id`, `unlock_guard_expression` *(Hard Rules + Guard)* | A locked talent unlocks after the turn in which all configured conditions are met; a system message (plus optional `unlock_text`) announces it. |
| **Protagonist** | `on_hp_change_script`, `..._text` | Executes when protagonist HP changes (e.g. taking damage or healing). |
| | `on_status_change_script`, `..._text` | Executes when protagonist status effects or conditions change. |
| **Sequences** | `on_start_sequence_script`, `..._text` | Executes immediately when a sequence chapter becomes active. |
| | `on_end_sequence_script`, `..._text` | Executes immediately when a sequence chapter is completed. |
| | `helpers_script` *(definitions)* | Not a trigger: functions and constants every script can call. See [Sequence Helpers](#sequence-helpers). |
| **Quests (Sidequests)** | `required_item_id`, `required_scene_id`, `required_defeated_npc_id` *(Hard Rules)* | Deterministic entity conditions required to complete quest. |
| | `guard_expression` *(Guard)* | Deterministic Python boolean expression required for completion. Evaluated in Pass 1.5. |
| **Awards (Achievements)** | `required_item_id`, `required_scene_id`, `required_defeated_npc_id` *(Hard Rules)* | Deterministic entity conditions required to grant award. |
| | `guard_expression` *(Guard)* | Deterministic Python boolean expression required for granting. Evaluated in Pass 1.5. |
| **Adventure (Victory)** | `completed_guard_expression` *(Guard)* | Deterministic Python boolean expression required for game victory. Triggers victory deterministically and blocks hallucinated win intents. |
| **Adventure (Defeat)** | `gameover_guard_expression` *(Guard)* | Deterministic Python boolean expression triggering game over. Evaluated in Pass 1.5; blocks hallucinated game-over intents. |

### Cardinal Rule: Soft Rules vs. Hard Rules (Mutual Exclusivity)

For **all assets** in TaleWeaver (Win/Loss conditions, Sequences, Quests, Awards, Exits, Containers, and Switches):
> [!IMPORTANT]
> **Use EITHER a soft narrative rule OR deterministic hard rules / scripted guards, but NOT both on the same asset.**
> 
> Mixing a narrative soft rule and a scripted guard expression on the same asset causes ambiguous triggers and LLM hallucination conflicts. If an asset has hard rules or guard expressions, leave its soft narrative rule empty or purely decorative. If an asset relies on narrative GM judgment, leave its hard rules and guard expressions empty.
>
> **Exception: sequence soft rules.** A `soft_rules` entry on a sequence is built to combine both: the GM judges the narrative `condition`, and the optional `guard_expression` is a deterministic *precondition* that must also hold. They never compete, because the guard can only veto, never trigger.

### Sequence Soft Rules

Sequences can declare `soft_rules`, which are active only while that sequence is active. Each rule pairs a narrative condition with a deterministic effect:

| Field | Purpose |
|---|---|
| `id` | Unique slug, e.g. `BRENDA_FLIRT`. |
| `condition` | Natural-language condition judged by the GM, e.g. `"Arthur flirts with Brenda"`. |
| `script` | Script executed when the rule fires (trigger name `on_soft_rule`). |
| `text` | Optional system message shown when the rule fires. |
| `guard_expression` | Optional deterministic precondition; the rule is ignored while it is falsy. |
| `max_triggers` | How often the rule may fire per session (`1` for one-time rewards); empty means unlimited. |

Pass 1 only ever sees each open rule's `id` and `condition` (never the script or guard) and reports fulfilled rules in `triggered_soft_rule_ids`. Pass 1.5 then checks each one in reported order: it must belong to the sequence active when the message started, be under its trigger limit, and pass its guard. Only then does the script run. Later rules see the effects of earlier ones in the same message. Rules that fail a check are dropped silently (with a `[DEBUG soft_rule …]` line in debug mode).

### Sequence Scripts

Sequences can also declare `scripts`: event scripts with the same shape as top-level scripts (`id`, `name`, `trigger`, `target_id`, `code`, `description`) that **only run while that sequence is active**. Every top-level trigger is available except `on_init` (no sequence is active before the session exists; use `on_start_sequence_script` for chapter set-up).

Use them for chapter-specific behaviour instead of top-level scripts that check the active chapter themselves, e.g. an `on_interact` script on a bomb that only opens its dialog during the bomb chapter. The runner collects them from the sequence that is active when the player's message starts, so a chapter change mid-message takes effect from the next message. Edit them in the World-Editor under **Sequence → Scripts**.

### Deterministic Guard Expressions

Deterministic guards (`unlock_expression` on containers and exits, `craft_guard_expression` on constructable recipes, `gates.expression` on switches, `completed_guard_expression` / `gameover_guard_expression` on the adventure, and `guard_expression` on sequences, sidequests, and awards) evaluate safe Python expressions against the `tw` context:
- `tw.switches.get('POWER') == 'ON'`
- `tw.vars.get('has_badge', False) == True and tw.player.hp > 20`
- `tw.player.has_item('KEYCARD_RED') or tw.switches.is_state('OVERRIDE', 'ACTIVE')`
- `tw.vars.get('boss_defeated') == True and tw.player.has_item('MOB_LEDGER')`
- `tw.vars.get('countdown') <= 0 or tw.vars.get('cover_blown') == True`

If the expression evaluates to truthy, the guard passes; otherwise, the action or completion is blocked deterministically.

**When progress guards are checked.** The hard rules and `guard_expression` of sidequests, awards and sequences (and the adventure's win/loss guards) are checked when the logic pass is applied, and **again after the scripts that run later in the same message**: `on_interact` triggers (top-level, sequence and inline) and `on_logic_pass_done` scripts. A dialog choice (`tw.dialog.choose` handler) runs the same check. So a console script that sets `tw.vars.set('teleport_attempt', 3)` completes a sidequest guarded by `tw.vars.get('teleport_attempt', 0) >= 3` in the same message, not one message later.

### Priority Execution
Scripts carry an integer `priority` (default: `100`). Scripts with **lower** priority numbers execute before scripts with higher numbers.

---

## Global Initialization Script (`init_script`) & Helper Methods

In complex adventures, multiple scripts often need to share common utility logic, mathematical calculations, custom state machines, or common inventory transactions. Furthermore, adventures often require initializing starting variables, reputation meters, or world flags before the player's first turn.

The **Global Initialization Script** solves this by providing a single centralized script stored at the top level of the adventure manifest (`init_script`).

### Lifecycle & Execution Model

The initialization script runs under a dual lifecycle model:

1. **Session Creation (Run Once)**:
   When a player begins a new game session (`/sessions/start`), the initialization script is evaluated with the full `GameContext` before any player actions occur.
   - Any state mutations performed via `tw.vars.set(...)`, `tw.switches.set_state(...)`, or `tw.story.narrate(...)` are committed directly into the initial session state (`__script_vars__`).
   - The engine automatically records `__init_script_executed__ = True` so setup logic does not re-run on subsequent turns.
   - Any standalone scripts marked with the `on_init` trigger also fire during this phase.

2. **Every Turn Scope Injection (Reusable Methods & Constants)**:
   Whenever any script runs during gameplay (top-level and sequence scripts, inline entity, scene and exit triggers, soft rules, dialog handlers), the engine loads function definitions (`def ...`) and top-level constants from the initialization script and injects them directly into the script's global execution scope. Constants are assignments of a literal value (number, string, list, tuple, dict).
   - You can call your helper functions directly from any event script without repeating code!
   - State mutation statements in the initialization script are **not** re-evaluated during this step, ensuring deterministic performance and avoiding unwanted side-effects.

### Defining Reusable Helper Functions

You can declare custom functions using standard Python `def` syntax, including parameters, default values, and `return` statements:

```python
# --- Global Variables & Constants ---
DEFAULT_GOLD = 50
MAX_REPUTATION = 100

tw.vars.set("gold", DEFAULT_GOLD)
tw.vars.set("reputation", 10)
tw.vars.set("solved_puzzles", [])

# --- Reusable Helper Functions ---
def add_gold(amount):
    current = tw.vars.get("gold", 0)
    tw.vars.set("gold", current + amount)
    tw.story.narrate("You gained " + str(amount) + " gold! Total: " + str(current + amount))

def spend_gold(amount):
    current = tw.vars.get("gold", 0)
    if current < amount:
        tw.story.narrate("Not enough gold! Needed: " + str(amount) + ", Have: " + str(current))
        return False
    tw.vars.set("gold", current - amount)
    tw.story.narrate("You spent " + str(amount) + " gold. Remaining: " + str(current - amount))
    return True

def can_access_sanctum():
    rep = tw.vars.get("reputation", 0)
    return rep >= 25 and tw.player.has_item("AMULET_OF_PASSAGE")
```

### Calling Helpers in Event Scripts

Inside an `on_interact` script attached to `NPC_MERCHANT`:
```python
# The merchant offers a health potion for 20 gold
if spend_gold(20):
    tw.player.heal(30)
    tw.story.narrate("The merchant smiles and hands you a steaming vial of healing draught.")
```

Inside an `on_enter_scene` script attached to `SCENE_INNER_SANCTUM`:
```python
if not can_access_sanctum():
    tw.story.narrate("A divine barrier repels you! Your reputation is insufficient.")
    tw.player.damage(10)
```

### Scene Helpers (`helpers_script`)

In a large adventure, putting every helper into the one `init_script` makes it hard to read. A scene can carry its own helper block (`helpers_script`) for the logic of that place's puzzle, dialog or NPC. In the World-Editor, edit it on the scene's page in the **Advanced** tab, next to the enter/leave scripts. The **Trigger Overview** tab lists it under the scene as *Helpers (definitions)*. In a Story Idea blueprint it is the `helpers:` key of a `[Scene]` tag, and the World-Builder fills it when it generates scripts.

Scene helpers work exactly like the definitions part of `init_script`:

- Only `def` statements and constant assignments are loaded. Any other statement in the block **never runs**; the editor validation warns about it (`helpers_statement_ignored`). Put set-up code into `init_script` or an `on_enter_scene` script.
- They are loaded on **every script run**, after `init_script` and the [sequence helpers](#sequence-helpers), from all scenes in manifest order. They are available **wherever the player is**, not only in their own scene. This is deliberate: a function that exists only after the player visited a scene would make scripts work for some routes and fail for others.
- Nothing is stored in the game state. Like everything else, a running game keeps the definitions it started with.
- A name defined twice (in `init_script` and a scene, or in two scenes) is shadowed by the later block; the editor validation warns (`helper_name_conflict`). Prefix helpers with their scene, e.g. `crypt_open_sarcophagus()`.
- Dialog handlers (`on_choice`) may live in scene helpers.
- A syntax error in one block is reported as a script error named after its scene (`helpers_CRYPT`); the other blocks still load.

Helpers block on scene `CRYPT`:
```python
CRYPT_CURSE_DAMAGE = 8

def crypt_curse():
    tw.player.damage(CRYPT_CURSE_DAMAGE)
    tw.vars.set("crypt_cursed", True)

def on_sarcophagus_choice(answ):
    if answ == 0:
        crypt_curse()
        tw.story.narrate("A cold breath escapes the stone. (-8 HP)")
        return
    tw.story.narrate("You leave the lid untouched.")
```

`on_enter_scene_script` of `CRYPT`:
```python
if not tw.vars.get("crypt_cursed"):
    tw.dialog.choose("The sarcophagus lid is ajar.", ["Push it open", "Leave it"],
                     on_choice="on_sarcophagus_choice")
```

### Sequence Helpers

A sequence (chapter) has the same kind of helper block (`helpers_script`) for logic that belongs to the chapter rather than to one place, e.g. a trial whose questions are asked in several rooms, or a chapter's dialog handlers. In the World-Editor it is in the sequence dialog's **Advanced** tab, below the start/end scripts; the **Trigger Overview** lists it under the sequence. In a blueprint it is the `helpers:` key of a `[Sequence]` tag.

Sequence helpers follow every rule of [scene helpers](#scene-helpers-helpers_script), with two details:

- They are **not limited to their chapter**: they are loaded on every script run, whichever chapter is active (unlike the sequence's `scripts` and `soft_rules`, which only run while it is active). A chapter-only effect belongs in the code that calls the helper, e.g. a soft rule of that sequence.
- **Load order:** `init_script`, then sequence helpers by chapter `order`, then scene helpers. A later block shadows an earlier name; the editor validation warns (`helper_name_conflict`). Script errors name the block `helpers_sequence_<ID>`.

Helpers block on sequence `SEQ_TRIAL`:
```python
TRIAL_PASS_SCORE = 2

def trial_answer(correct):
    if correct:
        tw.vars.set("trial_score", tw.vars.get("trial_score", 0) + 1)
    if tw.vars.get("trial_score", 0) >= TRIAL_PASS_SCORE:
        tw.story.narrate("The judges nod. You are free to go.")
```

A soft rule of the same sequence, condition *"The player answers the judges' question correctly"*:
```python
trial_answer(True)
```

---

## The `tw` Scripting API

The global `tw` object is injected into every script execution environment.

### `tw.player`
Inspects and modifies the avatar's state:
- `tw.player.hp` *(int)*: Current avatar health points.
- `tw.player.name` *(str)*: Protagonist's name.
- `tw.player.inventory` *(list[dict])*: The items the avatar carries right now (`id`, `name`, ...), including changes made earlier in the same script.
- `tw.player.item_ids` *(list[str])*: IDs of the carried items.
- `tw.player.heal(amount: int)`: Restores `amount` HP (up to avatar maximum).
- `tw.player.damage(amount: int)`: Inflicts `amount` direct damage to the avatar.
- `tw.player.xp` *(int)*: The protagonist's experience points, including changes made earlier in the same script.
- `tw.player.add_xp(amount: int)` (also `modify_xp(delta)`): Gives the protagonist `amount` XP; a negative amount takes XP away (never below 0). The player sees `You gain 25 XP (Script).`
- `tw.player.has_item(item_id: str) -> bool`: Returns `True` if `item_id` is in the inventory (case-insensitive).
- `tw.player.take_item(item_id: str) -> bool`: Moves an existing world item into the inventory, wherever it is (scene, container, NPC inventory). The entry keeps the item's world data (name, description, image, effects). Returns `False` for an unknown ID.
- `tw.player.drop_item(item_id: str, scene_id: str = None) -> bool`: Drops a carried item into a scene (default: the protagonist's scene).
- `tw.player.transfer_item(item_id: str, target_id: str) -> bool`: Hands a carried item to an NPC or puts it into a container.
- `tw.player.remove_item(item_id: str)`: Takes an item out of the inventory without placing it anywhere.
- `tw.player.give_item(item_id: str, name: str = None, description: str = None)`: Adds a *new* inventory entry that is not a world item (no image, no effects). To hand over an item that exists in the world, use `take_item` instead.
- To move the protagonist to another scene, use `tw.scene.teleport(scene_id)` (see [`tw.scene`](#twscene)).

### `tw.scene`
Inspects the current scene:
- `tw.scene.id` *(str)*: ID of the current scene (the target scene once the script called `tw.scene.teleport`).
- `tw.scene.npcs` *(list[NPCProxy])*: All NPCs in the current scene, as the same proxies `tw.npcs.get()` returns. Includes NPCs that are hidden (`.is_hidden`) or defeated (`.is_defeated`) and NPCs moved here earlier in the same script; filter them yourself if needed.
- `tw.scene.items` *(list[ObjectProxy])*: All objects and items lying in the current scene.
- `tw.scene.teleport(target_scene_id: str)`: Moves the protagonist directly into another scene, whether or not an exit connects the two. If `target_scene_id` matches an unmaterialized dynamic exit placeholder (`to_scene_id`), exit ID, dynamic `zone_id`, or an unmaterialized pre-mapped Dynamic Scene (`WorldScene.dynamic_zone`), that scene is generated and materialized automatically before moving the protagonist there. Works in every script, including scene and exit triggers (`on_enter_scene`, `on_leave_scene`, exit scripts). After the call, `tw.scene.id`, `tw.scene.npcs`, `tw.scene.items` and `"current"` targets (e.g. `tw.npcs.move_to_player`) refer to the target scene. A teleport does **not** fire the target scene's `on_enter_scene` or the old scene's `on_leave_scene` script, and no "You have entered" message is shown, so describe the jump yourself (e.g. with `tw.story.direct`). The player sees the travel overlay with the target scene, just like after walking through an exit, whether the teleport happens during a turn or in a script fired by a pickup, a dialog choice or an unlock.
- `tw.scene.teleport_dynamic(theme_or_zone_id: str = "", theme: str | None = None, *, zone_id: str | None = None, max_depth: int | None = None, danger_level: str | None = None, max_npcs: int | None = None, audio_mode: str | None = None, cul_de_sac: bool | None = None, instructions: str | None = None, instructions_scope: str | None = None, cluster_consistency: bool | None = None, return_exit: bool = True, label: str = "Teleporter", fresh: bool = False) -> str`: Materializes a procedural dynamic scene on the fly and teleports the protagonist into it, returning the target scene ID (`str`) and updating `tw.scene.id` immediately. Can be called either with a freeform `theme` description (e.g. `tw.scene.teleport_dynamic("Shifting astral nexus of floating obelisks", danger_level="random", fresh=True)`) or by referencing an existing dynamic exit's `zone_id`, `id`, or `to_scene_id` with optional overrides.
  - `max_depth` (`1..6`, default `3`), `danger_level` (`"peaceful"`, `"low"`, `"medium"`, `"high"`, `"deadly"`, `"random"`), `max_npcs` (`0..5`), `audio_mode` (`"inherit"`, `"empty"`, `"generate"`), `cul_de_sac` (whether reaching `max_depth` terminates in a cul-de-sac), `instructions` (optional freeform prompt or Blueprint blocks guiding generation within the cluster), `instructions_scope` (`"once"` default, `"first_scene"`, `"max_depth"`, `"all_scenes"`), `cluster_consistency` (`True`/`False`, default `True`; passes global theme, base exit theme, and already-generated cluster scenes/NPCs/items), `return_exit` (default `True`; adds an unlocked return exit back to the origin scene), `label` (display name for the virtual passage / return context), and `fresh` (default `False`; `True` generates a brand-new dynamic scene instance on every activation instead of reusing the previously materialized scene).
  - Ideal for interactive teleporters, portals, or switches:
    ```python
    # On a teleporter pad's on_interact script:
    dest_id = tw.scene.teleport_dynamic(
        "Ancient clockwork vault pulsing with golden gears",
        zone_id="clockwork_vault",
        danger_level="random",
        max_depth=2,
        return_exit=True,
        label="Brass Teleporter",
    )
    tw.story.narrate("Arcane runes flare beneath your boots, folding space around you.")
    ```
- **Dynamic Zone `on_after_generated_script` & `generated_scene`** *(also `tw.generated_scene`)*: Optional trigger script on a dynamic exit's `dynamic_zone` configuration, executed immediately after the procedural scene, its NPCs, objects, and forward exits are persisted. Both top-level `generated_scene` and `tw.generated_scene` provide a read-only dictionary with `id`, `origin_scene_id`, `zone_id`, `theme`, `depth`, `max_depth`, `danger_level`, `name`, `description`, `visual_description`, `music_prompt`, `npcs`, `objects`, and `forward_exits`, allowing scripts to inspect the generated scene and add items or NPCs (e.g., `tw.items.clone("RELIC_KEY", scene_id=generated_scene["id"])` or `tw.npcs.clone("GUARD", scene_id=generated_scene["id"])`).
- `tw.scene.get_attribute(name, default=None)` / `tw.scene.set_attribute(name, value)`: A script-defined value stored per scene.

```python
# Everyone present (and visible) gets angry
for npc in tw.scene.npcs:
    if not npc.is_hidden and not npc.is_defeated:
        npc.add_trait("angry")
```

```python
# Who is visible here, and is the guard among them?
present = [n.id for n in tw.scene.npcs if not n.is_hidden]
guard_here = "GUARD" in present
```

```python
# A trap door drops the player into the cellar, where the guard is already waiting
tw.scene.teleport("CELLAR")
tw.npcs.move_to_player("GUARD", "blocking the stairs")
tw.story.direct("The floor gives way. The player tumbles down into the cellar.")
```

### `tw.exits`
Queries and locks/unlocks passage exits. Exits are addressed by their route (`from_scene_id`, `to_scene_id`), not by the generated exit ID; a bidirectional exit can be named from either side. `"FROM:TO"` in one string works as well.
- `tw.exits.lock(from_scene_id: str, to_scene_id: str, reason: str = None)`: Locks the exit. If the player attempts to traverse it, `reason` explains why it is blocked.
- `tw.exits.unlock(from_scene_id: str, to_scene_id: str)`: Unlocks a previously locked passage.
- `tw.exits.is_locked(from_scene_id: str, to_scene_id: str) -> bool`: Returns `True` if the exit is currently locked.

Exits cannot be hidden: every exit of a scene is listed. For a secret door, lock the exit and unlock it from a script, or set `is_revealed` on the exit to show its destination on the map before the player has been there.

### `tw.npcs`
Inspects, dialogues with, moves, and manages Non-Player Characters:
- `tw.npcs.say(npc_id: str, text: str)`: Makes an NPC speak dialogue text. Appears in the narrative feed as `NPC Name: "text"`. An NPC outside the player's current scene stays silent (the speech bubble is suppressed), so timer or background scripts running while the player is elsewhere do not create confusing dialogue bubbles. The GM's narration of the same turn treats the line as already shown to the player: it continues from it and does not repeat or paraphrase it, so a clue spoken here is said once. Also available as `tw.npcs.get(npc_id).say(text)`.
- `tw.npcs.say_directed(npc_id: str, direction: str, after=None, after_args=None)`: Lets the NPC speak in the next GM narration, worded by the GM instead of a fixed text: the direction says *what* the NPC says or does with their voice (`tw.npcs.say_directed("BRAM", "sings Yellow Submarine")`), and the GM writes the actual line in character and in the scene's language. An NPC outside the player's current scene does not speak (the direction is dropped), but any `after=` callback still executes. It works like [`tw.story.direct`](#twstory): a soft direction, used once by the next narration (max. 500 characters, at most the 5 newest directions are kept). The GM is asked to write the line as a separate `Name: "..."` dialogue line, so it shows up as the NPC's own speech bubble (also in the narration of a choice dialog with `narrate=True`); as with every direction, the GM may still word it freely. With `after=` a callback runs once that narration is done, see [Running code after the narration](#running-code-after-the-narration-after). Also available as `tw.npcs.get(npc_id).say_directed(direction, after=None, after_args=None)`.
- `tw.npcs.move(npc_id: str, target_scene_id: str, spatial_position: str = "")`: Moves an NPC to another scene. Accepts `"current"`, `"here"`, or `"player"` to move them into the protagonist's current location.
- `tw.npcs.move_to_player(npc_id: str, spatial_position: str = "")`: Convenience shortcut to move an NPC directly into the player's current scene.
- `tw.npcs.drop_item(npc_id: str, item_id: str, scene_id: str = None, spatial_position: str = "")`: Transfers an item from an NPC's inventory into a scene. If `scene_id` is omitted, it drops into the NPC's current scene; passing `"current"` drops it into the player's scene.
- `tw.npcs.give_item(npc_id: str, item_id: str)`: Transfers an item from a scene into an NPC's inventory and conceals it from the scene view.
- `tw.npcs.give_to_player(npc_id: str, item_id: str) -> dict | None`: Hands an item the NPC carries directly to the protagonist. The item leaves the NPC's inventory and keeps its world entity data (name, description, image, stats). Returns the new inventory entry, or `None` (and changes nothing) if the NPC doesn't hold the item, so scripts can't conjure items.
- `tw.npcs.consume(npc_id: str, item_id: str) -> dict | None`: Lets the NPC use a consumable it carries (`item_type` `CONSUMABLE`). The item is destroyed and its HP, Mana and Stamina effects apply to the NPC, read the same way as for the protagonist's `/consume` (fields such as `hp_change`, `mana_change`, `stamina_change`, else amounts named in the description). Values stay between 0 and the NPC's maximum; HP reaching 0 defeats the NPC. Returns the applied effects, e.g. `{"hp": 25, "stamina": -4}`, or `None` (and changes nothing) if the NPC does not carry the item or it is not a consumable. To let an NPC drink a potion from the scene or from the player, move it first: `tw.npcs.get('BRAM').put_item('POTION')`. The GM sees the new values from the next narration on; describe the moment yourself if needed (e.g. with `tw.npcs.say_directed`).
- `tw.npcs.kill(npc_id: str, drop_inventory: bool = True)`: Kills the NPC, setting HP to 0 and marking `is_defeated: True`. When `drop_inventory=True` (default), all items held by the NPC are dropped into their scene. An NPC whose **NPC can be damaged** is off is not killed; the chat shows a script error that the kill was ignored.
- `tw.npcs.attack(npc_id: str)`: Makes an NPC attack the protagonist. Turn-based combat starts right after the current turn if the NPC is in the protagonist's scene, alive and attackable (ignored while a fight is already running). Example (`on_turn_end`): `if tw.player.has_item('IDOL') and not tw.vars.get('alarm'): tw.vars.set('alarm', True); tw.npcs.attack('TEMPLE_GUARD')`.
- `tw.npcs.hide(npc_id: str) -> bool` / `tw.npcs.reveal(npc_id: str) -> bool`: Takes an NPC out of the story or brings it back. A hidden NPC disappears from its scene: it is not listed, cannot be talked to, attacked, given items or targeted by talents, and the Game Master no longer sees it as present. Unless its reveal rule is `script`, the Game Master still knows it as a *hidden* NPC and may reveal it again when the player searches the scene (or by its reveal condition); set the reveal rule to `script` (`reveal: script` in a blueprint) when only scripts may bring it back. `reveal` brings it back where it stands; call `tw.npcs.move(npc_id, scene_id)` first to make it reappear somewhere else. Returns `False` (and changes nothing) for an unknown NPC ID. Also available as `tw.npcs.get(npc_id).hide()` / `.reveal()`; `.is_hidden` reads the current state.
- `tw.npcs.set_character(npc_id: str, text: str)`: Replaces the NPC's personality (the `character` field). The GM reads it on every turn, so the NPC talks and acts differently from then on (friendlier, aggressive, funny, frightened, …). An empty text clears it. Whitespace is collapsed to a single line and the text is cut at 1,000 characters.
- `tw.npcs.set_goal(npc_id: str, text: str)`: Replaces what the NPC wants (the `goal` field), with the same rules.
- `tw.npcs.add_trait(npc_id: str, trait: str)` / `tw.npcs.remove_trait(npc_id: str, trait: str)`: Adds or removes a single trait in the comma-separated `character` text (case-insensitive; adding an existing trait does nothing). Handy for temporary states such as `"drunk"` or `"frightened"`.
- `tw.npcs.clone(npc_id: str, scene_id: str = None, hidden: bool = None) -> NPCProxy | None`: Creates a copy of the NPC with a new ID (`<ID>_1`, `<ID>_2`, ...; cloning a clone counts on from the original). The copy has the original's name, description, portrait, combat profile, combat group, special attacks and scripts, but starts fresh: full HP (`max_hp`), not defeated, empty inventory (so loot is not duplicated). Without `scene_id` it stands in the original's scene; `"current"` puts it in the protagonist's scene. It keeps the original's hidden flag unless `hidden` is given, so a hidden template NPC can spawn visible copies: `for i in range(10): tw.npcs.clone('ARENA_RAT', hidden=False)`. Clones of the same template share its `combat_group`, so attacking one pulls the whole pack into the fight. At most 20 clones (NPCs and items together) per script run; returns `None` for an unknown ID or past the limit. The copy exists in the current game only and is usable right away in the same script (`.get_attribute('cloned_from')` names the original). A fight holds at most 20 NPCs besides the protagonist; allies of the attacked NPC get the slots first.
- `tw.npcs.set_combat_group(npc_id: str, group: str)`: Moves the NPC into another combat group (any tag, normalized to an upper-case ID). NPCs in the same group fight together: when one of them fights, the others in its scene join. An empty text removes the NPC from every group, which makes it a bystander unless its assist mode says otherwise. Example (a bribed guard stops helping his squad): `tw.npcs.set_combat_group('GATE_GUARD', '')`.
- `tw.npcs.set_assist_mode(npc_id: str, mode: str)`: Sets when the NPC joins a fight it was not attacked in: `'GROUP'` (a member of its group fights), `'ANYONE'` (any fight in its scene) or `'NEVER'` (bystander; it only fights when attacked directly). An empty text restores the automatic mode (`GROUP` with a group, `NEVER` without). Other values raise an error. Both changes apply to the current game only and take effect when the next fight starts.
- `tw.npcs.get(npc_id: str) -> NPCProxy`: Returns an `NPCProxy` instance. The ID is matched exactly, then case-insensitively, then against the NPC's name. An unknown ID does not raise: it returns a detached proxy whose changes have no effect, and the server log shows `[Script Warning] Unknown entity ID '...'`, so check the log when a change seems to be ignored. Available properties and methods on `NPCProxy`:
  - `.name`, `.hp`, `.mana`, `.stamina`, `.is_defeated`, `.current_scene_id`, `.is_with_player`, `.inventory`
  - `.say(text: str)` / `.say_directed(direction: str, after=None, after_args=None)`
  - `.move_to(target_scene_id: str, spatial_position: str = "")` (supports `"current"`)
  - `.move_to_player(spatial_position: str = "")`
  - `.drop_item(item_id: str, scene_id: str = None, spatial_position: str = "")`
  - `.give_item(item_id: str)`
  - `.give_to_player(item_id: str) -> dict | None`
  - `.has_item(item_id: str) -> bool`
  - `.items` *(list[ObjectProxy])* / `.item_ids` *(list[str])*: The items the NPC carries.
  - `.put_item(item_id: str) -> bool`: Moves a world item from anywhere (scene, container, the protagonist) into the NPC's inventory.
  - `.take_item(item_id: str, to: str = "player") -> bool`: Moves a carried item out, to `"player"`, `"current"` (the protagonist's scene), a scene ID, another NPC or a container.
  - `.kill(drop_inventory: bool = True)` / `.die()`
  - `.attack()` (see `tw.npcs.attack`)
  - `.hide()` / `.reveal()` / `.is_hidden` (see `tw.npcs.hide`)
  - `.modify_hp(delta: int)` / `.damage(amount: int)` / `.heal(amount: int)` (healing stops at the NPC's maximum HP). Damage that brings HP to 0 defeats the NPC. When **NPC can be damaged** is off, every HP loss is blocked (also when assigning `.hp` a lower value); healing still works.
  - `.is_killable` *(bool)*: `False` when **NPC can be damaged** is off in the editor (or the game switched it off). The field keeps its historical name `is_killable`.
  - `.consume(item_id: str) -> dict | None` (see `tw.npcs.consume`)
  - `.character`, `.goal` *(read/write)*: assigning (`npc.character = "Gruff, impatient"`) is the same as calling `.set_character()` / `.set_goal()`
  - `.set_character(text)`, `.set_goal(text)`, `.add_trait(trait)`, `.remove_trait(trait)`, `.has_trait(trait) -> bool`
  - `.clone(scene_id=None, hidden=None) -> NPCProxy | None` (see `tw.npcs.clone`)
  - `.combat_group` *(str, `""` without a group)*, `.assist_mode` *(effective mode: `GROUP`, `ANYONE` or `NEVER`)*, `.set_combat_group(group)`, `.set_assist_mode(mode)` (see `tw.npcs.set_combat_group`)

  Persona changes apply to the current game only: they are stored on the session's copy of the NPC, and the adventure template keeps its original text. To restore the original later, store it first, e.g. `tw.vars.set('brom_bio', tw.npcs.get('BROM').character)`. A persona change shapes the GM's narration and dialogue from the next turn on; it does not start a fight on its own (use `.attack()` for that). The NPC cards in the in-game Debug dialog show the current character and goal, so you can check that a change was applied.

### `tw.objects` (or `tw.items`)
Manages world objects and inventory items. Every world item is held by exactly **one** place: the protagonist's inventory, an NPC's inventory, a container (its contents) or a scene. A move always takes the item away from its current holder first, so items never exist twice and never vanish. Item IDs are matched case-insensitively.

**Moving items**
- `tw.objects.move_item(item_id: str, target: str) -> bool`: Moves an item to `"player"`, an NPC ID, a container ID, `"current"`/`"here"` (the protagonist's scene) or a scene ID.
- `tw.objects.add_to_player(item_id: str) -> bool`: Same as `tw.player.take_item(item_id)`.
- `tw.objects.remove_from_player(item_id: str) -> bool`: Same as `tw.player.remove_item(item_id)`; `False` if the protagonist does not carry it.
- `tw.objects.add_to_scene(item_id: str, scene_id: str = None) -> bool`: Moves an item into a scene (default: the protagonist's scene).
- `tw.objects.put_in_container(item_id: str, container_id: str) -> bool`: Moves an item into a container. Only containers that stand in a scene accept items (not one the protagonist carries), and a container never goes into itself.
- `tw.objects.take_from_container(container_id: str, item_id: str, to: str = "player") -> bool`: Moves an item out of a container; `False` if the container does not hold it. `to` accepts the same targets as `move_item`.
- `tw.objects.move_to_scene(item_id: str, scene_id: str, spatial_position: str = "")` and `tw.objects.give_to_npc(item_id: str, npc_id: str)`: Older shortcuts, kept for existing adventures.

**Querying items**
- `tw.objects.contents(holder_id: str) -> list[ObjectProxy]`: The items held by `"player"`, an NPC or a container.
- `tw.objects.location(item_id: str) -> dict`: Where an item is: `{"type": "player"|"npc"|"container"|"scene"|"destroyed"|"unknown", "id": "<holder or scene ID>"}`.

**Creating, destroying, hiding, and locking items**
- `tw.objects.clone(item_id: str, scene_id: str = None, hidden: bool = None) -> ObjectProxy | None`: Creates a copy of the item with a new ID (`<ID>_1`, `<ID>_2`, ...; cloning a clone counts on from the original). The copy has the original's name, description, image, type, effects and scripts. Without `scene_id` it lies where the original lies when that is a scene, otherwise in the protagonist's scene; `"current"` puts it in the protagonist's scene. It keeps the original's hidden flag unless `hidden` is given. A cloned container starts empty. At most 20 clones per script run; returns `None` for an unknown ID. The copy is a new entity of the current game only (the adventure template is not changed) and is usable right away in the same script.
- `tw.objects.destroy(item_id: str) -> bool`: Removes the item from the game for good: it leaves its holder and is moved to the internal scene `__DESTROYED__`.
- `tw.objects.hide(item_id: str)` / `tw.objects.reveal(item_id: str)`: Hides an item until revealed again, or reveals it. A hidden item can also be discovered by searching or by its reveal condition, unless its reveal rule is `script`.
- `tw.objects.lock(item_id: str) -> bool` / `tw.objects.unlock(item_id: str) -> bool` / `tw.objects.is_locked(item_id: str) -> bool`: Locks or unlocks an item or container, or checks whether it is currently locked. For `CONTAINER` and `CONTAINER_SWITCH` entities, locking prevents opening the container until unlocked. For all other item types, locking makes the item **take-locked**: it remains visible and inspectable in the scene or inside an open container (marked with a lock icon), but the player cannot pick it up until unlocked via `tw.objects.unlock(item_id)` or a switch outcome (`unlock_item`). Moving an item directly into the player's inventory via script (`tw.player.take_item(item_id)` or `tw.objects.add_to_player(item_id)`) automatically unlocks it.

**`ObjectProxy`** (`tw.objects.get(item_id)`):
- `.clone(scene_id=None, hidden=None)`, `.destroy()`, `.is_destroyed`, `.hide()`, `.reveal()`, `.is_hidden`, `.lock()`, `.unlock()`, `.is_locked`, `.location`
- `.move_to(target)`, `.give_to_player()`, `.put_into(container_id)`, `.move_to_scene(scene_id)`, `.give_to_npc(npc_id)`
- For containers (`CONTAINER` and `CONTAINER_SWITCH`): `.items` *(list[ObjectProxy])*, `.item_ids` *(list[str])*, `.contains(item_id)`, `.put_item(item_id)`, `.take_item(item_id, to="player")`, `.min_items` *(int | None)*, `.max_items` *(int | None)*, `.is_full` *(bool)*, `.has_min_items` *(bool)*
- For switch items (`SWITCH` and `CONTAINER_SWITCH`): `.state`, `.switch_state`, `.get_state()`, `.set_state()`, `.is_state()`, `.flip()`, `.toggle()`, `.disabled_states`, `.is_state_enabled(state)`, `.is_state_disabled(state)`, `.enable_state(*states)`, `.disable_state(*states)`, `.set_state_enabled(state, enabled)`, `.status_text`, `.set_status_text(text)`, and `.clear_status_text()`.

```python
# Potion dispenser: copy a hidden template potion and hand the copy over
potion = tw.objects.get('HEALING_POTION').clone()
if potion:
    potion.reveal()
    potion.move_to('player')

# Which coins lie in the offering bowl? Move them to the priest.
for coin in tw.objects.get('OFFERING_BOWL').items:
    tw.objects.take_from_container('OFFERING_BOWL', coin.id, to='PRIEST')
```

### `tw.switches`
Inspects and manipulates interactive switches, levers, buttons, and puzzle mechanisms across the adventure:
- `tw.switches.get(switch_id: str) -> SwitchProxy`: Retrieves a `SwitchProxy` for the switch entity. Also accessible via shortcut `tw.switch(switch_id)`.
- `tw.switches.get_state(switch_id: str, default: str = "") -> str`: Returns the current state string (e.g. `"OFF"`, `"ON"`, `"ACTIVE"`). A known switch without a stored state reports its configured initial state; `default` is only returned when no switch with that ID or name exists.
- `tw.switches.set_state(switch_id: str, new_state: str, apply_outcomes: bool = True) -> bool`: Deterministically transitions the switch to `new_state`, optionally triggering any associated switch outcomes (unlocking exits, containers, or setting story flags).
- `tw.switches.is_state(switch_id: str, state: str) -> bool`: Returns `True` if the switch currently matches `state`.
- `tw.switches.flip(switch_id: str, apply_outcomes: bool = True) -> str`: Cycles or toggles the switch to its next configured state, returning the new state.
- `tw.switches.toggle(switch_id: str, apply_outcomes: bool = True) -> str`: Alias for `flip()`.
- `tw.switches.enable_state(switch_id: str, *states: str) -> list[str]` / `tw.switches.disable_state(switch_id: str, *states: str) -> list[str]`: Enables or disables specific switch state buttons on `switch_id` (e.g. `tw.switches.disable_state('MICROWAVE', 'DEFROST', 'COOK')`), returning the updated list of disabled state IDs. Disabled states are shown with a lock icon and cannot be clicked by the player until re-enabled.
- `tw.switches.is_state_enabled(switch_id: str, state: str) -> bool` / `tw.switches.is_state_disabled(switch_id: str, state: str) -> bool` / `tw.switches.disabled_states(switch_id: str) -> list[str]`: Checks whether a specific state on `switch_id` is enabled/disabled, or returns all currently disabled state IDs.
- `tw.switches.get_status_text(switch_id: str) -> str` / `tw.switches.set_status_text(switch_id: str, text: str) -> str` / `tw.switches.clear_status_text(switch_id: str) -> str`: Gets, sets, or clears the optional status/hint message displayed inside the switch or container-switch dialog (e.g. `"The microwave needs some electrical power first."`).
- `tw.switch(switch_id: str) -> SwitchProxy`: Convenience shortcut for `tw.switches.get(switch_id)`.

#### `SwitchProxy` and `ObjectProxy` Switch Attributes
When interacting with a `SwitchProxy` or an `ObjectProxy` for a switch entity:
- `.state` *(str)*: Gets or sets the switch state. Assigning a new state (e.g. `switch.state = "ON"`) triggers the state transition and runs configured outcomes.
- `.switch_state` *(str)*: Alias for `.state`.
- `.label` *(str, read-only)*: In-game text of the current state (its label, or the state ID when no label is set). Use `.state` in conditions and `.label` in narration.
- `.get_state() -> str`: Returns current state.
- `.set_state(new_state: str, apply_outcomes: bool = True)`: Sets state and optionally applies outcomes.
- `.is_state(state: str) -> bool`: Checks if the switch matches `state`.
- `.flip(apply_outcomes: bool = True) -> str`: Cycles to the next state in sequence.
- `.toggle(apply_outcomes: bool = True) -> str`: Alias for `flip()`.
- `.states` *(list[str])*: List of declared switch state IDs (1-15 characters: `A-Z`, `0-9`, `_`, `-`).
- `.disabled_states` *(list[str])*: List of currently disabled (locked) state IDs on this switch.
- `.is_state_enabled(state: str) -> bool` / `.is_state_disabled(state: str) -> bool`: Checks whether `state` is currently enabled or disabled.
- `.enable_state(*states: str) -> list[str]` / `.disable_state(*states: str) -> list[str]` / `.set_state_enabled(state: str, enabled: bool) -> list[str]`: Enables or disables one or more state IDs on this switch.
- `.status_text` *(str)*: Gets or sets the status/hint message shown inside the switch or container-switch panel.
- `.set_status_text(text: str) -> str` / `.clear_status_text() -> str`: Sets or clears the status/hint message.
- `.initial_state` *(str)*: Configured initial state.
- `.is_switch` *(bool)*: `True` if the object is a switch.

### `tw.vars` (Persistent State)
A persistent key-value store saved into the session state under `__script_vars__`. State persists across turns, saves, and reloads:
- `tw.vars.get(key: str, default: Any = None) -> Any`: Retrieves variable value.
- `tw.vars.set(key: str, value: Any)`: Stores a value (numbers, strings, booleans, lists, dicts).
- `tw.vars.has(key: str) -> bool`: Checks whether `key` exists.
- `tw.vars.delete(key: str)`: Deletes `key`.

### `tw.story`
Injects narrative messages or system notifications into the turn stream:
- `tw.story.narrate(text: str)` (shortcut `tw.narrate(text)`): Emits Game Master narration (`role: "assistant"`), displayed with the Game Master avatar and styled exactly like standard storytelling turns. The text is parsed like LLM narration: `Name: "..."` lines become NPC speech bubbles, `[tags]` become voice tags, `**bold**` is highlighted (e.g. `tw.story.narrate('You take the piece of chocolate. Maybe it will help with the persuasion.')`).
- `tw.story.narrate_raw(text: str)` (shortcut `tw.narrate_raw(text)`): Emits Game Master narration that is shown **verbatim**, as one Game Master block: no speaker detection, no voice tags, no bold or `##ID` formatting. Line breaks are kept. Use it for text that must not be interpreted, e.g. LLM output from `tw.llm.ask(...)` that may contain colons or quotes (`tw.story.narrate_raw(news or "Just static noise.")`).
- `tw.story.direct(instruction: str, after=None, after_args=None)` (shortcut `tw.direct(...)`): Gives the Game Master a **soft stage direction** instead of fixed text, e.g. `tw.story.direct("Let BRAM sing a sailor song")`. Nothing is shown right away. The direction is stored in the session (`entity_states["__gm_directions__"]`) and handed to the **next GM narration**: the narration of the current turn when the script runs during a turn (e.g. a soft rule in Pass 1.5), otherwise the next turn's narration, or the outcome narration of a choice dialog opened with `narrate=True`. That narration works it in naturally and drops it afterwards, so every direction is used once. The GM treats it as a wish, not as a fact: it never overrides game rules or the technical outcome, and it does not change any state (use the other `tw.*` calls for that). Whitespace is collapsed to a single line, each direction is cut at 500 characters, and at most the 5 newest directions wait at a time. With `after=` a callback runs once that narration is done (see below).
- `tw.story.skip_narration()` (shortcut `tw.skip_narration()`): the **next GM narration is skipped**, so no narration text and no TTS for it. Use it when a script starts an audio track (music or recorded speech) that must not be talked over. Like `direct`, the request waits in the session and applies to the next narration pass: the current turn's when the script runs during a turn (e.g. `on_logic_pass_done`, an interaction trigger), otherwise the next turn's (the opening narration when the init script calls it). It is used once. Script messages (`narrate`, `system`), system events, `on_narration_done` and the clock tick still happen.
- *Deprecated aliases:* `tw.story.show_message(text)`, `tw.story.message(text)` and `tw.show_message(text)` behave exactly like `tw.story.narrate(text)`. They remain for existing adventures; new scripts should use `narrate`.
- `tw.story.system_message(text: str)` / `tw.story.system(text: str)` / `tw.system(text: str)`: Emits a technical system notification (`role: "system"`). System messages and narration calls (`narrate`, `narrate_raw`) are rendered in the exact chronological order in which the script executed them.
- `tw.story.log(text: str)`: Appends an internal log message visible during debugging.
- `tw.story.generate_image(...)` / `tw.story.show_image(...)`: Shortcuts for `tw.image.generate(...)` and `tw.image.show(...)`, see [tw.image & tw.media](#twimage--twmedia-in-game-image-generation).

#### Running code after the narration (`after=`)

Everything a script does takes effect right away, but a direction only becomes text in the **next** narration. So in

```python
tw.npcs.say_directed('BRAM', 'grumbles and returns the teacup')
tw.story.system('Bram gives the teacup back to you.')
tw.npcs.give_to_player('BRAM', 'TEACUP')
```

the system message and the item appear *before* Bram's line. To run code after the narration instead, pass a callback:

```python
# Script that reacts (e.g. Bram's on_receive_item):
tw.npcs.say_directed('BRAM', 'grumbles and returns the teacup',
                     after='give_back',
                     after_args={'npc_id': 'BRAM', 'item_id': 'TEACUP'})

# Global init_script (or a sequence/scene helper block):
def give_back(npc_id, item_id):
    npc = tw.npcs.get(npc_id)
    tw.story.system(npc.name + ' gives ' + tw.objects.get(item_id).name + ' back to you.')
    npc.give_to_player(item_id)
```

- `after` names a function of the **global `init_script`** or of a sequence/scene helper block (a string or the function itself). Like a dialog's `on_choice` handler it runs in a later step, where the reacting script's local variables no longer exist, so pass what it needs in `after_args`.
- `after_args` is a dict of plain values (text, numbers, booleans, lists, dicts; at most 4000 characters as JSON). Each key becomes a keyword argument of the callback, so keys must be valid parameter names.
- The callback runs right after the narration that used the direction: after the turn's narration (before `on_narration_done`), or after the outcome narration of a choice dialog with `narrate=True`. Its messages and state changes appear below the narration. A callback queued by `on_narration_done` or by another callback waits for the next narration.
- After a choice dialog without `narrate=True`, the scene goes on by itself: when a callback waits and no new dialog is open, the client sends `/continue_story` (with auto-speech on, once the lines before it have been read aloud), a narration-only step (no mechanics pass, no interaction triggers, no clock tick, no player message). Its narration uses the direction, then the callback runs. Use this for beats that should follow a choice right away, e.g. a character bursting in only after the scream that summoned them.
- If no narration comes (e.g. the GM call failed), the callback waits for the next one, together with its direction. At most 10 callbacks wait at a time; they are stored in `entity_states["__gm_after_narration__"]`.
- An unusable `after`/`after_args` is reported as a visible `Script error: direction callback ignored: ...` message; the direction itself is still used. A callback name that no definition block defines is reported as `Script error in 'after_<name>'` when it should run, and the editor validation warns about it (`direction_callback_missing`).

### `tw.save` (Save States)
- `tw.save(label: str = "")`: Saves the game as a checkpoint, for example right before an important decision. The player can return to it from the **Chronicles Timeline** in the game.
  - The save is written when the script's changes are applied, so it already contains everything the same script changed before.
  - The system message `Game saved: <label>` (or `Game saved.`) is shown and stored before the save, so it is still there after a restore.
  - The label is the checkpoint's title in the timeline (`Save: <label>`), collapsed to one line and cut at 80 characters.
  - At most 3 saves per script run. A session keeps its 10 newest saves; they are counted apart from the automatic checkpoints, so scene changes never push them out.

```python
# Before the player chooses a side, keep a way back.
tw.save("Before the duel")
tw.dialog.choose("Draw your sword?", ["Fight", "Walk away"], on_choice="on_duel_choice")
```

A save holds the full session state: the protagonist (vitals, stats, inventory, equipment, status effects), scene, in-game time, script variables and entity overrides, exits, quests, the active sequence, world memories and rumours, and every session-scoped world entity and exit row (positions, container contents, clones). Restoring a save rewinds all of it and deletes the chat messages written after it. Player preferences (narration style, skin, debug mode) are not part of a save.

Besides `tw.save()`, checkpoints are created automatically when a turn changes the **scene** (any way: exit, map, script teleport, Game Master) or the **active sequence**, on quest updates and awards, and when the player types `/save [name]`.

### `tw.memories`
Directly writes into the avatar's episodic memory bank:
- `tw.memories.add(memory_text: str)`: Injects a factual memory into the avatar context that the Game Master LLM references in subsequent turns.

### `tw.game`
Controls session outcome conditions (alias: `tw.session`):
- `tw.game.win(message: str = None)` / `tw.game.game_won(message: str = None)`: Ends the adventure in victory and displays `message`.
- `tw.game.game_over(reason: str = None)`: Ends the adventure in defeat with `reason`.
- What the player sees: once the current turn (or dialog step) is done, the Game Master tells a short epilogue and an ending card follows in the story feed (**Victory** or **Game Over**, with `message` / `reason`, EXP, quests and awards). After a win the player can keep playing in the world; after a game over the input is locked and the card offers **Load a Save** (Chronicles). To let a character react before the end, end the game in an `after=` callback of a direction (see [Running code after the narration](#running-code-after-the-narration-after)).
- `tw.game.time`: Elapsed in-game minutes (same as `tw.time.now`).

> [!NOTE]
> **When finishing the last sequence ends the adventure** (linear and dynamic modes): if the adventure has a deterministic win guard (`completed_guard_expression`), completing the final sequence does **not** end it; only that guard or a script calling `tw.game.win()` / `tw.game.game_won()` does, and the player stays in the world until then (e.g. for a finale scripted at a later time). Without a win guard, completing every sequence ends the adventure in victory. The Game Master can additionally end it when the soft `completed_condition` is met.
>
> A sequence completes when its hard rules hold (`required_item_id`, `required_scene_id`, `required_defeated_npc_id`, and its guard). `completion_guard_expression` is an alias of `guard_expression`; set only one of them. If both are set, `guard_expression` is the one that counts.

### `tw.time` (In-Game Clock)
The in-game time is the number of minutes (units for the *units* time system) that passed since the adventure started.

**How time passes**
- **Narration tick**: after every narrated player message the clock advances by the *minutes per tick* (the adventure's **Round Pacing** in the editor's **Time & Pacing** tab, `time_per_turn`, default 5). One player message is one tick, even when it chains a follow-up narration. The opening prologue, choice dialogs and script output (`tw.narrate`, dialog narration) do not tick.
- **Game Master**: when **GM May Change Time** is enabled in the editor's **Time & Pacing** tab (`gm_time_control`, default on), the GM may add extra time for long actions ("the search took 20 minutes", `extra_time_minutes`) or jump the clock (`time_override_minutes`, `start_datetime_override`). Tick plus extra time of one message is capped by **Max Time per Turn (GM Limit)**. With the flag off, while the clock is paused, or after `tw.time.allow_gm_time(False)`, GM time requests are ignored and Pass 1 is told `TIME CONTROL: LOCKED`.
- **Scripts and debug commands** can set or move the time at any moment, also while the clock is paused.

**Reading**
- `tw.time.now` / `tw.time.minutes`: elapsed minutes (includes changes made earlier in the same script).
- `tw.time.day`, `tw.time.hour`, `tw.time.minute`: the clock of day (from the adventure's start time, default `08:00`, and its initial day).
- `tw.time.format()`: the time as the player sees it, e.g. `"Day 2, 14:30"`.
- `tw.time.ticks`: how many narration ticks advanced the clock.
- `tw.time.is_paused`, `tw.time.minutes_per_tick`, `tw.time.default_minutes_per_tick`, `tw.time.gm_can_change_time`.
- `tw.time.parse(value)`: converts `"1h 30m"`, `"2d"`, `"1:30"` or `90` to minutes (`None` if it is no time amount).

**Changing** (every time amount accepts minutes or text like `"2h 30m"`, `"1d"`, `"1w"`, `"1:30"`)
- `tw.time.set(t)`: sets the elapsed time. `tw.time.advance(t)` / `tw.time.rewind(t)`: moves it forward / back (never below 0).
- `tw.time.set_minutes_per_tick(t)` / `tw.time.reset_minutes_per_tick()`: changes the time per narration tick for the rest of the session (e.g. `0` in a frozen dream world) / goes back to the adventure's pacing.
- `tw.time.pause()` / `tw.time.resume()`: stops and restarts the narration ticks; GM time requests are ignored while paused.
- `tw.time.allow_gm_time(allowed=True)` / `tw.time.reset_gm_time()`: overrides the editor's **GM May Change Time** flag for this session / goes back to it.

**Timers (time event handlers)**
- `tw.time.at(t, handler, timer_id=None, data=None)`: runs `handler` once when the clock reaches the elapsed time `t`.
- `tw.time.after(t, handler, timer_id=None, data=None)`: runs `handler` once when `t` has passed from now.
- `tw.time.every(t, handler, timer_id=None, data=None, start=None)`: runs `handler` each time `t` has passed (first at `start`, default now + `t`). A big jump runs it once, not once per missed interval.
- `tw.time.cancel(timer_id)`, `tw.time.has_timer(timer_id)`, `tw.time.timers` (list of `{id, at, handler, every, data}`).
- `handler` is a function of the init script, or its name (like `tw.dialog` handlers). Each call returns the timer id (`None` if it was rejected); registering an existing `timer_id` again replaces that timer. `data` must be plain values (text, numbers, lists, dicts). At most 50 timers can be active.
- A handler with one parameter receives `time_event`: `{"id", "at", "now", "data", "repeats"}`. `on_time_reached` scripts can read the same `time_event` variable.

**When time events fire**: after the narration tick of a player message (after `on_narration_done`), after `/debug time` commands that move the clock, and after `/script` commands that changed the time. A time change inside other scripts (e.g. a dialog choice handler) fires its events at the next of these points. Due events run oldest first; a handler may change the time or register timers again (at most 5 rounds per check). The runtime state (pause, overrides, timers, fired `on_time_reached` scripts) is stored in the session and is part of every save.

### `tw.audio` (Generated Background Audio)
> **Experimental.** Needs audio generation in **Admin > Audio (Experimental)**: switched on, with Google Lyria (a Google key) or an uploaded ComfyUI workflow. When it is off, `tw.audio` calls are still accepted and stored, but nothing new is rendered. Design notes: `docs/specs/audio_generation.md` in the repository.

Scripts compose background audio on the fly from a text prompt. A call only records the request; the server renders the track in the background (seconds to minutes; ComfyUI renders one track at a time) and the player's client cross-fades to it once it is ready. Until then, the previous audio keeps playing.

**What plays**: a script track (`tw.audio`) beats the track the current scene selected from the adventure's audio library (editor: **Audio** tab and the scene dialog). Scenes with the same library track keep it playing when the player walks between them; a scene without a track fades the audio out. `tw.audio.stop()` silences scene audio too until the next `play`/`generate`; `tw.audio.release()` ends the script audio and hands back to the scene's track.

**Changing**
- `tw.audio.generate(prompt, name=None, duration=None, play=True, loop=True, negative_prompt="", seed=None, regenerate=False, fade=2.0, volume=1.0)`: requests a new track and returns its id (`None` if the prompt is empty or the session already holds 100 tracks). The prompt describes the audio, not the scene: genre, instruments, mood, tempo (e.g. `"slow dark ambient, low strings, dripping water, 60 bpm"`). `duration` is in seconds (default and maximum come from the admin settings). With `play=False` the track is rendered in advance and played later.
- A **name** makes a track reusable: `generate` with a name that already exists plays the stored track instead of rendering a new one (pass `regenerate=True` to render it again). Always name audio that comes back, such as scene themes or battle audio, so it is rendered once per session.
- `tw.audio.play(name, loop=True, fade=2.0, volume=1.0)`: plays a track. `volume` (0..1) applies to this playback only; it multiplies with `tw.audio.set_volume` and the player's own volume. It looks first for a track this session generated (by its `name` or the id `generate` returned), then for a track of the adventure's **audio library** (by the track ID shown in the editor's **Audio** tab, or its exact name). Returns `False` if there is none and shows a script error in the chat (`Script error in 'tw.audio.play': no audio track '...'`), so a typo is visible.
- `tw.audio.stop(fade=2.0)`: fades all audio out, scene and theme audio too.
- `tw.audio.release()`: ends the script audio; the current scene's library track plays again.
- `tw.audio.stop_speech(fade=0.5)`: fades out the text-to-speech that plays right now (`fade` in seconds, 0 to 5), drops its queued lines and **holds automatic speech until the player's next action**, so the script's own lines (`tw.story.narrate`, NPC lines) are shown but not read over the audio. Use it before a track starts that must not be talked over. During a turn it reaches the player before the turn's narration; combine it with `tw.story.skip_narration()` so no narration is written either. Speech the player starts by hand (the speaker button of a message) still plays.
- `tw.audio.set_volume(value)`: script volume `0..1`, multiplied with the player's own audio volume.
- `tw.audio.forget(name)`: drops the name, so the next `generate` with it renders a new track.

**Reading** (includes changes made earlier in the same script)
- `tw.audio.current`: name (or id) of the track that should play now, else `None`.
- `tw.audio.is_playing`: `True` while a script track is set to play, also while it is still rendering.
- `tw.audio.is_silenced`: `True` after `stop()`, until `play`, `generate` or `release`.
- `tw.audio.has(name)`, `tw.audio.tracks` (names of this session's generated tracks), `tw.audio.library` (track IDs of the adventure's audio library), `tw.audio.volume`.

**Two kinds of tracks and IDs**

| | Library tracks | Script tracks |
| --- | --- | --- |
| Made in | the editor's **Audio** tab (generated or uploaded), or planned by the World-Builder | a script, with `tw.audio.generate(...)` during play |
| ID | shown under the track name in the Audio tab (copy button) and editable there: letters, digits and underscores, max. 30, upper case (e.g. `CRYPT_THEME`); suggested from the track or file name | random 32-character id returned by `generate`; give the track a `name` instead |
| Lives in | the adventure (exported with it) | the play session only |
| Played by | scenes (their track choice), the title track, `tw.audio.play("<track id>")` | `tw.audio.play("<name>")` |

```python
# Scene on_enter_scene: each place gets its own theme, rendered only on the first visit.
tw.audio.generate("slow dark ambient, low strings, dripping water, distant choir", name="crypt_theme")

# Sequence on_start_sequence: render the boss audio ahead, start it when the fight begins.
tw.audio.generate("epic orchestral battle, taiko drums, brass, 140 bpm", name="boss", play=False)

# Later, e.g. in the boss NPC's on_interact_script:
tw.audio.play("boss")

# Or play a track from the editor's Audio tab by its track ID:
tw.audio.play("CRYPT_THEME")

# A recorded speech at 80% volume that the narration must not talk over:
tw.audio.stop_speech(fade=0.5)   # end the GM's current speech with a short fade
tw.audio.play("KINGS_SPEECH", loop=False, volume=0.8)
tw.story.skip_narration()        # and no new narration (or TTS) this turn

# After the fight: back to the scene's own audio from the editor.
tw.audio.release()
```

**Limits and storage**: the admin sets the number of tracks a play session may render (further requests fail and keep the old audio). The audio state (what plays, the named tracks, the volume) is part of every save; restoring a checkpoint restores the audio. The rendered files live in the session folder (`adventures/sessions/<session>/audio/`); a track whose file is missing (e.g. after a session import) is rendered again.

### `tw.quests`
Directly manipulates adventure quest entries:
- `tw.quests.complete(quest_id: str)`: Marks `quest_id` as completed.
- `tw.quests.activate(quest_id: str)`: Activates an open quest.
- `tw.quests.fail(quest_id: str)`: Marks a quest as failed.

### `tw.awards`
Awards achievements to the player's profile:
- `tw.awards.grant(award_key: str)`: Grants the award, exactly like an award the Game Master grants: it is added to the player's earned awards (once per adventure), the chat shows `Award Achievement: <title>`, a checkpoint is saved, and the game shows the award in a short overlay. The key is matched case-insensitively against the adventure's award keys; an unknown key is ignored (see the server log).

### `tw.sequences` & `tw.sequence`
Controls adventure story chapters and sequences. In TaleWeaver, **only one sequence can be active at a time** (`state.active_sequence_id`). Both `tw.sequences` and `tw.sequence` provide the same API.

#### Starting & Ending Sequences
- `tw.sequences.start(sequence_id: str)`: Immediately switches to and activates the specified sequence. Sets it as the active sequence, logs a system notification (`Sequence started: <title>`), and executes the sequence's `on_start_sequence_script` / `on_start_sequence_text` if defined.
- `tw.sequences.end(sequence_id: Optional[str] = None, advance: Optional[bool] = None)`: Ends the currently active sequence (or `sequence_id` if specified).
  - When `advance=True`: triggers `on_end_sequence_script` / text, awards sequence completion XP, and advances to the next chapter in order (or completes the adventure if no chapters remain).
  - When `advance=False`: triggers `on_end_sequence_script` / text, awards sequence completion XP, and clears the active sequence (`active_sequence_id = None`) without advancing.
  - When `advance` is omitted: defaults to `True` in `linear` mode, and `False` in `dynamic` mode.
- `tw.sequences.complete(sequence_id: Optional[str] = None, advance: Optional[bool] = None)`: Convenience alias for `tw.sequences.end(sequence_id, advance=advance)`.
- `tw.sequences.complete_current(advance: Optional[bool] = None)`: Convenience alias for `tw.sequences.end(None, advance=advance)`.
- `tw.sequences.advance()`: Advances to the next sequence in linear order.
- `tw.sequences.clear()`: Clears the active sequence without marking it completed or advancing.

#### Determining the Active Sequence
- `tw.sequences.get_active() -> Optional[dict]`: Returns the dictionary definition of the currently active sequence (e.g. `{"id": "...", "title": "...", "order": 1}`), or `None` if no sequence is active.
- `tw.sequences.get_active_id() -> Optional[str]`: Returns the ID string of the currently active sequence (e.g. `"CHAPTER_1"`), or `None`.
- `tw.sequences.is_active(sequence_id: str) -> bool`: Returns `True` if `sequence_id` matches the currently active sequence (case-insensitive).
- `tw.sequences.is_completed(sequence_id: str) -> bool`: Returns `True` if the specified sequence has already been completed in this playthrough.
- `tw.sequences.progression_mode`: Property returning the adventure's progression mode (`"linear"` or `"dynamic"`).
- `tw.sequences.active_id`: Property returning the active sequence ID (or `None`).
- `tw.sequences.active` / `tw.sequences.current`: Property returning the active sequence dictionary (or `None`).
- `tw.sequence.id`: Property returning the active sequence ID.
- `tw.sequence.title`: Property returning the active sequence title.
- `tw.sequences.all() -> list[dict]`: Returns a list of all sequences defined in the adventure.

#### Progression Modes: Linear vs. Dynamic
Adventures configure `sequence_progression_mode` in their manifest or template:
- **`"linear"` (default)**: Classic story chapters. Completing sequence $N$ automatically unlocks sequence $N+1$. Completing the final sequence ends the adventure only when it has no win guard (see the note under `tw.game`).
- **`"dynamic"`**: Ideal for hubs, sandboxes, QA workbenches, and open-world investigations:
  - Sequences do not auto-advance to the next array index on completion.
  - Completing a sequence clears `active_sequence_id = None` without finishing the entire adventure.
  - Sequences are activated explicitly via `tw.sequences.start(seq_id)` or automatically via their `activation_scene_id` upon entering a designated room.

```python
# Check which sequence is active
if tw.sequences.is_active("HEIST_PHASE"):
    tw.narrate("Security remains on high alert!")

# Retrieve active sequence properties
current_id = tw.sequence.id
if current_id == "RIDDLE_TOWER":
    tw.sequences.end()  # Complete and advance to next sequence

# Jump directly to a specific sequence
tw.sequences.start("VAULT_SHOWDOWN")
```

### `tw.dice`
Provides deterministic, seeded random number generation:
- `tw.dice.roll(sides: int = 20) -> int`: Rolls a die with `sides` faces (1 to `sides`).
- `tw.dice.d6() -> int`: Convenience for a 6-sided die roll (1 to 6).
- `tw.dice.d20() -> int`: Convenience for a 20-sided die roll (1 to 20).
- `tw.dice.random() -> float`: Returns a pseudo-random float between `0.0` and `1.0`.

### `tw.dialog` (Choice Dialogs)
Shows the player a multiple-choice dialog for NPC conversations, riddles and dilemmas. Only scripts (including soft rule scripts) can open a dialog; the LLM never sees this API.

- `tw.dialog.choose(prompt, options, on_choice, speaker=None, narrate=False) -> bool` (alias `tw.dialog.ask`)
  - `prompt`: the question or situation shown above the options (up to 2,000 characters). Supports fenced code blocks (` ```python ... ``` `), inline code (`` `...` ``), `**bold**`, and preserves line breaks and leading indentation.
  - `options`: up to 8 entries, each a label string (up to 500 characters) or `{"label": "...", "visible_if": "<guard expression>"}`. Supports fenced code blocks, inline code, `**bold**`, and multi-line indentation. Hidden options keep their position, so indices stay stable.
  - `on_choice`: name of the handler function (a string, or the function itself). **The handler must be defined in the global `init_script` or in a [scene](#scene-helpers-helpers_script) or [sequence](#sequence-helpers) helper block.**
  - `speaker`: optional NPC name shown as the dialog title.
  - `narrate`: when `True`, the small model narrates the outcome after the handler ran. The handler's notices (e.g. "Mom moved to ...") are binding facts; its `tw.story.narrate` / `tw.npcs.say` lines count as already read, so the narration continues after them instead of retelling them. It also receives the current character and goal of the visible NPCs in the player's scene (including changes the handler just made, e.g. `npc.character = "Very angry"`) and any pending `tw.story.direct(...)` directions, which this narration then uses up. Default `False`: only the handler's own messages appear, which is instant and deterministic; directions then wait for the next turn's narration.
  - Returns `False` (and emits a debug note) when no dialog was opened: another dialog is already open this turn, the handler name is invalid, or no option is visible.

**How it works.** Scripts run to completion inside one request, so `choose()` does not wait for the answer. It stores a *pending dialog* in the session state (`entity_states["__pending_dialog__"]`) and the client shows a modal that cannot be dismissed. Free-text input is rejected (HTTP 409) until the player answers. The answer goes to `POST /adventures/{game_id}/dialog/choice`, which:

1. records the choice in the chat as `[Choice] <label>` (so the GM keeps continuity),
2. calls `<on_choice>(index)` with the **position of the chosen option in `options`**, plus a `dialog_choice` dict (`index`, `label`, `dialog_id`) in scope,
3. applies the handler's changeset (variables, items, HP, game over, sequence advance, …), completes sidequests, awards and sequences whose hard rules now hold, checks the win/loss guards and runs the post-turn checks (special unlocks, NPC attacks),
4. optionally narrates the outcome (`narrate=True`).

A handler may call `tw.dialog.choose()` again, which is how multi-step conversations and dialog trees are built. The editor validation warns (`dialog_handler_missing`) when a dialog references a handler that neither the init script nor any sequence or scene helper block defines.

### `tw.dialog.tree` (Nested NPC Dialogues)
RPG-style conversations as a tree of nodes. The NPC says a node's `npc_text`; each player response leads to another node, back to an earlier one, or ends the conversation. At the end the adventure gets the list of visited steps.

- `tw.dialog.tree(tree, on_end=None, on_action=None, speaker=None, start_node=None) -> bool`
  - `tree`: a dict (best defined as a constant in the `init_script`, a scene or a sequence helper block):
    - `nodes` *(required)*: node ID → `{"npc_text": "...", "responses": [...], "speaker": "..." (optional)}`. At most 100 nodes and 8 responses per node.
    - `initial_node`: ID of the first node (default: the first node in `nodes`).
    - `npc_id`: the speaking NPC; its name is the dialog title unless `speaker` is given.
    - `dialogue_id`: optional name for your own bookkeeping.
  - A **response** is `{"text": "...", "next_node": "<node ID>" | None, ...}` with the optional keys:
    - `condition`: a [guard expression](#deterministic-guard-expressions) (e.g. `"tw.vars.get('gold', 0) >= 250"`). The response is only shown while it is true. Guards are evaluated anew for every node, so they see changes made earlier in the conversation.
    - `once`: `True` hides the response after it was picked once in this conversation (e.g. a question that is answered).
    - `script`: inline code that runs when the response is picked, e.g. `"tw.vars.set('knows_about_mine', True)"`.
    - `action`: a string passed to the `on_action` handler, e.g. `"START_QUEST_STAR_SILVER"`. Use it to keep the logic of many responses in one function.
    - `next_node: None` (or a missing `next_node`) ends the conversation.
  - `on_end`: handler called as `on_end(path)` when the conversation ends. `path` is the list of visited steps, each `{"node": "<node ID>", "response": <index>, "text": "<response text>", "action": "..." (if any)}`.
  - `on_action`: handler called as `on_action(action)` after the response's `script`.
  - **Both handlers must be defined in the global `init_script` or in a scene or sequence helper block** (like `on_choice` handlers; the editor validation warns with `dialog_handler_missing`).
  - `speaker`: dialog title; `start_node`: start somewhere else than `initial_node` (e.g. to resume a conversation).
  - Returns `False` (and emits a debug note) when no dialog was opened: another dialog is already open, the tree is invalid (a response points to an unknown node, the start node does not exist), a handler name is invalid, or the start node has no visible response.

**How it works.** The whole tree is stored with the pending dialog, and the client shows one node at a time in the same dialog panel as `tw.dialog.choose` (the player cannot type until the conversation is over). Each answer goes to `POST /adventures/{game_id}/dialog/choice`, which:

1. writes the NPC's line to the story feed as `Speaker: "npc_text"` and the answer as `[Choice] <text>`,
2. runs the response's `script`, then `on_action(action)`; both get `dialog_choice` (`index`, `label`, `node`, `action`, `dialog_id`) and `dialog_path` in scope,
3. shows `next_node` with the responses whose `condition` holds,
4. ends the conversation when `next_node` is `None` or the next node has no visible response, and then calls `on_end(path)`.

A response script that opens another dialog (`tw.dialog.choose` or `tw.dialog.tree`) or ends the adventure (`tw.game.win`, `tw.game.game_over`) stops the conversation; `on_end` is not called then. The tree's text is shown as written: there is no LLM narration of tree steps.

See [Example 16](#example-16-blacksmith-conversation-dialogue-tree) for a complete conversation.

### `tw.llm` & `tw.json` (Ask the LLM & Structured JSON)

- `tw.llm.ask(prompt, model="simple", system="") -> str`: Sends `prompt` to the language model configured in the player's LLM settings and returns the answer as a string.
  - `model="simple"` uses the **small model** (`small_model` / `small_model_provider`), `model="advanced"` the **complex model** (`complex_model` / `complex_model_provider`). Any other value is a script error.
  - `system` optionally replaces the default system prompt ("answer briefly, return only the requested text"). The session language is appended automatically.
- `tw.llm.ask_json(prompt, schema=None, model="simple", system="") -> dict | list | Any | None`: Asks the model for structured JSON, strips `<think>` tags and markdown ` ```json ` fences, repairs minor JSON formatting errors, and validates the result against `schema`.
  - Returns the parsed Python `dict` / `list` (or primitive when matched by `schema`), or `None` when the LLM is unavailable, fails, returns invalid JSON, or fails schema validation.
  - `schema` is an optional sandbox-friendly schema descriptor:
    - Type names or Python types: `"str"` (`str`), `"int"` (`int`), `"float"` (`float`), `"bool"` (`bool`), `"list"` (`list`), `"dict"` (`dict`), `"any"`.
    - Object mapping: `{"question": "str", "correct_index": {"type": "int", "min": 0, "max": 3}, "hint": {"type": "str", "optional": True}}` — every key is required unless `"optional": True` is set.
    - Constraint dict: `{"type": "list", "items": {"type": "str", "min_len": 1}, "min_len": 4, "max_len": 4}` (supported constraints: `min`, `max` for numbers; `min_len`, `max_len` for strings/lists/dicts; `enum` for allowed values; `items` for list elements; `fields` for nested object dicts).
- `tw.llm.available -> bool`: `False` where the LLM cannot be used (see below).
- `tw.json` (sandbox-safe JSON utilities, no `import json` needed):
  - `tw.json.loads(text, schema=None, default=None)`: Safely parses a JSON string (with fence stripping and repair) and validates against `schema` if given; returns `default` (`None`) on any error.
  - `tw.json.validate(data, schema) -> bool`: Returns `True` if `data` satisfies `schema`.
  - `tw.json.dumps(value) -> str`: Serializes `value` to a JSON string (or `""` on error).

Rules and limits:

- **Never raises for provider problems**: when the LLM is not configured, fails, or takes longer than **20 seconds**, `ask()` returns `""`. Always keep a fallback: `line = tw.llm.ask(...) or "The raven stays silent."`
- **At most 3 calls** per script context (one trigger pass, shared across `ask` and `ask_json`); further calls return `""` / `None`. Prompts and system prompts are cut at 4,000 characters, `ask()` answers at 2,000, and `ask_json()` answers at 8,000. Answers are capped at about 1,200 tokens.
- **Not available in guard expressions** (`guard`, `visible_if`, unlock and lock guards, soft-rule guards) or in the session's `init_script` run: guards must stay deterministic and cheap. There `ask()` returns `""` without calling the model.
- **The call blocks**: the turn waits until the model answers. Use it for occasional flavour text, not on every turn.
- In debug mode, skipped or failed calls show a `[DEBUG]` system message. Calls are logged with the operation `script.llm_ask`.

```python
# NPC on_interact: a fresh riddle each time, with a fixed fallback.
riddle = tw.llm.ask(
    "Write a one-sentence riddle a grumpy bridge troll asks. Only the riddle.",
    model="simple",
)
tw.npcs.say("TROLL", riddle or "What has roots nobody sees and is taller than trees?")

# Dynamic Python PCEP multiple-choice question with schema validation and code formatting
QUIZ_SCHEMA = {
    "question": {"type": "str", "min_len": 10},
    "options": {"type": "list", "items": {"type": "str", "min_len": 1}, "min_len": 4, "max_len": 4},
    "correct_index": {"type": "int", "min": 0, "max": 3},
    "explanation": {"type": "str", "optional": True},
}
quiz = tw.llm.ask_json(
    "Create one PCEP multiple-choice question about Python loops with a ```python code block.",
    schema=QUIZ_SCHEMA,
    model="simple",
)
if quiz:
    tw.vars.set("current_quiz", quiz)
    tw.dialog.choose(quiz["question"], quiz["options"], on_choice="on_quiz_answer", speaker="Examiner")
```

### `tw.image` & `tw.media` (In-Game Image Generation)

Scripts can generate an image during play and show it in the story feed. `tw.media` is the same object as `tw.image`.

- `tw.image.generate(prompt, model="simple", apply_style=True, show_in_chat=True, caption="") -> str`: Generates an image with the image model from the player's **Visual Preferences** and returns its URL (`/data/adventures/sessions/<game_id>/script_images/...`), or `""` on failure.
  - `model="simple"` uses the **simple image model** (`simple_model` / `simple_model_provider` and the `simple_*` quality settings). `model="hq"` uses the **advanced image model** (`advanced_model` / `advanced_model_provider` and the `advanced_*` settings); `"advanced"` is accepted as an alias for `"hq"`. Any other value is a script error.
  - `apply_style=True` adds the adventure's image style (the first entry of its selected image styles, resolved against the player's style catalog) to the prompt, so the image matches the cover and scene art. Pass `apply_style=False` for a neutral look, e.g. a photo-like document.
  - `show_in_chat=True` posts the image to the story feed as a Game Master block, with `caption` shown below it. With `show_in_chat=False` only the URL is returned, e.g. to show it later with `tw.image.show(url)` or to keep it in `tw.vars`.
- `tw.image.generate_simple(prompt, apply_style=True, show_in_chat=True, caption="") -> str`: Same as `generate(prompt, model="simple", ...)`.
- `tw.image.generate_hq(prompt, apply_style=True, show_in_chat=True, caption="") -> str`: Same as `generate(prompt, model="hq", ...)`.
- `tw.image.show(image_url, caption="")`: Shows an existing image in the story feed. Only TaleWeaver asset URLs (`/data/...`) and `http(s)://` URLs are accepted; others are skipped (with a `[DEBUG]` note in debug mode).
- `tw.image.available -> bool`: `False` where images cannot be generated (see below).
- Shortcuts: `tw.generate_image(...)` and `tw.story.generate_image(...)` call `tw.image.generate(...)`; `tw.show_image(url, caption="")` and `tw.story.show_image(url, caption="")` call `tw.image.show(...)`.

How the image appears: the call adds a line `![caption](url)` to the script's narration. The story feed renders this markdown image syntax as an image block (rounded, scaled to the feed width, limited in height, caption below), in `tw.story.narrate(...)` and `tw.story.narrate_raw(...)` text alike. You can therefore also write `tw.narrate("![The old map](/data/...)")` yourself. Text-to-speech reads only the caption.

Rules and limits:

- **Never raises for provider problems**: when no image model or API key is configured, the provider fails or blocks the prompt, or generation takes longer than **60 seconds**, `generate()` returns `""` and shows nothing. Keep a text fallback: `if not tw.image.generate_simple("A torn map"): tw.narrate("The map is too faded to make out.")`
- **At most 2 images** per script context (one trigger pass, shared across all `generate*` calls and shortcuts); further calls return `""`. Prompts are cut at 1,500 characters, captions at 200. `show()` has no limit.
- **Only in scripts run by a chat turn** (soft rules, entity triggers and scripts the turn loop fires). Not available in guard expressions, in the session's `init_script` run, or in scripts fired directly by UI buttons outside a turn; there `generate()` returns `""` without calling the model.
- **The call blocks** the turn until the image is saved. The player sees the turn spinner and cannot send input meanwhile. Waiting does not count against the script's 2-second time budget. Image generation is slow and may cost money, so use it for key moments, not on every turn.
- Images are stored in the session's own folder, never in the adventure template.
- In debug mode, skipped or failed calls show a `[DEBUG]` system message.

```python
# Object on_examine: show the treasure map once, in the adventure's art style.
if not tw.vars.get("map_url"):
    url = tw.image.generate_hq(
        "An old hand-drawn treasure map of a small island, a red X near a skull-shaped rock",
        caption="The map from the sea chest",
    )
    tw.vars.set("map_url", url)
    if not url:
        tw.narrate("The map shows a small island and a red X near a skull-shaped rock.")
else:
    tw.image.show(tw.vars.get("map_url"), "The map from the sea chest")

# A quick sketch without the adventure style, kept for later instead of shown right away.
sketch = tw.media.generate("A pencil sketch of a stranger's face", apply_style=False, show_in_chat=False)
```

### `tw.turn` (Player Message & Turn Info)

Provides access to the current turn's player input and language context:

- `tw.turn.player_message` (alias `tw.turn.message`, shortcut `tw.player_message` or bare `player_message`): The verbatim or normalized input string sent by the player during this turn. In choice dialog handlers, this holds the chosen option's label. In empty prologue turns, this defaults to `""`.
- `tw.turn.language`: The language code configured for the current turn (e.g. `"en"`, `"de"`), or `None`.

```python
# Check if the player asked an NPC to draw or paint something specific
msg = tw.turn.player_message.lower()
if "paint" in msg or "draw" in msg:
    # Use tw.llm.ask to synthesize an art prompt dynamically from the player's message
    prompt = tw.llm.ask(
        f"You are an artist. Turn the user request '{tw.turn.player_message}' into an image prompt. Output only the prompt.",
        model="simple",
    )
    tw.image.generate(prompt, model="simple")
```

### `tw.log` & `tw.debug` (Logging & Diagnostics)

To try a script line in a running game, turn on debug mode and use `/script <code>` (see [In-Game Debugging](in_game_debugging.md)): `/script tw.npcs.get('BRAM').hp` answers with the value as a debug message.
Provides simple, clean logging methods to inspect state during development and playtesting:

#### 1. Server Console Logging
Outputs diagnostics directly to the server terminal/process logs without showing anything to the player in-game:
- `tw.log(*args, sep=" ")`: Outputs an informational log entry (`[Script Log] ...`) to the server console.
- `tw.log.info(*args, sep=" ")`: Outputs an informational message to the server console.
- `tw.log.warn(*args, sep=" ")` / `tw.log.warning(*args, sep=" ")`: Outputs a warning message to the server console.
- `tw.log.error(*args, sep=" ")`: Outputs an error message to the server console.
- `tw.console.log(*args, sep=" ")`: JavaScript-style alias for `tw.log()`.
- `print(*args, sep=" ")`: Safe built-in Python `print()` routing directly to the server console logger.

```python
# Inspect variable state in server console
tw.log("Player entered chamber with key:", tw.player.has_item("KEY_GOLD"))
tw.log.warn("Low player HP detected:", tw.player.hp)
print("Standard print also routes safely to the server console!")
```

#### 2. In-Game Debug Notifications
Emits interactive diagnostic messages inside the game's message feed. **Only displayed when Debug Mode is ON** (`debug_mode` enabled in game settings or session):
- `tw.debug(*args, sep=" ")` / `tw.debug_message(*args, sep=" ")`: Emits an in-game system notification (`[DEBUG: Script] ...`) visible in the in-game chat when Debug Mode is active. Also logs to the server console at DEBUG level.
- `tw.story.debug(*args, sep=" ")`: Alias via the story proxy.
- `tw.log.in_game(*args, sep=" ")`: Explicit helper to emit an in-game debug notification.

```python
# Only visible to developers/playtesters when Debug Mode is ON
tw.debug("Door lock status:", tw.exits.is_locked("SCENE_A", "SCENE_B"))
if tw.switches.is_state("LEVER_01", "ON"):
    tw.debug("Switch mechanism active, calculating door bypass...")
```

---

## Practical Examples

### Example 1: Trapped Ancient Chest
Trigger: `on_interact`  
Target: `CHEST_GILDED`

```python
# Check if the chest trap was already triggered
if not tw.vars.get("chest_trap_sprung", False):
    tw.vars.set("chest_trap_sprung", True)
    
    # Inflict trap poison damage
    tw.player.damage(18)
    tw.story.narrate(
        "A hidden needle snaps forward from the lock mechanism! Poison burns through your veins (-18 HP)."
    )
    tw.memories.add("Triggered a poison needle trap on the gilded chest.")
    
    # Reveal a secret compartment key on the floor
    tw.objects.reveal("KEY_BRASS")
```

---

### Example 2: Gatekeeper Guard Blocking Passage
Trigger: `on_enter_scene`  
Target: `SCENE_CASTLE_GATES`

```python
# Check if the player possesses the royal seal
if not tw.player.has_item("ROYAL_SIGNET"):
    # Lock the inner courtyard exit
    tw.exits.lock("SCENE_CASTLE_GATES", "SCENE_COURTYARD", "The armored sentry lowers his halberd: 'Halt! Only bearers of the Royal Signet may enter.'")
    tw.story.narrate("The castle guard steps forward, barring the iron gate.")
else:
    # Unlock and allow passage
    tw.exits.unlock("SCENE_CASTLE_GATES", "SCENE_COURTYARD")
    tw.story.narrate("The guard notices the Royal Signet ring, salutes respectfully, and raises the heavy portcullis.")
```

---

### Example 3: Three-Lever Puzzle with Persistent State
Trigger: `on_interact`  
Target: `LEVER_` *(or separate scripts for each lever)*

```python
# Track the state of 3 levers: lever_1, lever_2, lever_3
lever_id = tw.scene.id # or target entity id
tw.vars.set("lever_blue", True)

b = tw.vars.get("lever_blue", False)
r = tw.vars.get("lever_red", False)
g = tw.vars.get("lever_gold", False)

if b and r and g:
    if not tw.vars.get("vault_unlocked", False):
        tw.vars.set("vault_unlocked", True)
        tw.exits.unlock("SCENE_VAULT_HALL", "SCENE_VAULT")
        tw.story.narrate("With a resonant chime, all three mechanisms lock into place and the massive vault door unseals!")
        tw.awards.grant("PUZZLE_MASTER")
```

---

### Example 4: Boss Encounter & Victory Condition
Trigger: `on_interact`  
Target: `NPC_SHADOW_LORD`

```python
# If the player uses the Sunstone against the Shadow Lord
if tw.player.has_item("RELIC_SUNSTONE"):
    tw.story.narrate(
        "You raise the Sunstone! Blinding solar radiance floods the chamber, dissolving the Shadow Lord into harmless embers."
    )
    tw.quests.complete("MAIN_QUEST_SLAY_SHADOWS")
    tw.awards.grant("SAVIOR_OF_THE_REALM")
    tw.game.win("The realm is saved! The eternal darkness has been banished forever.")
else:
    tw.player.damage(25)
    tw.story.narrate("The Shadow Lord's aura lashes out in icy tendrils (-25 HP). You need a source of holy light!")
```

---

### Example 5: Turn-Based Survival Countdown
Trigger: `on_turn_end`  
Target: `*`

The countdown advances once per in-game turn (scene or sequence change). For a per-message countdown use `on_narration_done`; for a countdown in in-game time use `tw.time` (see [Example 18](#example-18-ticking-bomb-and-nightfall-time-events)).

```python
# Increment turn counter
turn = tw.vars.get("collapse_turn", 0) + 1
tw.vars.set("collapse_turn", turn)

remaining = 6 - turn
if remaining > 0:
    tw.story.narrate("The cavern tremors intensify! " + str(remaining) + " turn(s) before total collapse.")
else:
    tw.game.game_over("The cavern roof collapsed, burying all beneath tons of solid rock.")
```

---

### Example 6: Cursed Amulet (Inline Object Script)
Trigger: `on_equip_script` (Configured directly on the `AMULET_OF_DOOM` item)

```python
# Apply a curse when equipped
tw.vars.set("cursed_hp_drain", True)
tw.story.narrate("As the amulet touches your skin, an icy chill grips your heart. You feel your vitality draining away.")
```

Trigger: `on_unequip_script` (Configured directly on the `AMULET_OF_DOOM` item)

```python
# Remove the curse when unequipped
tw.vars.set("cursed_hp_drain", False)
tw.story.narrate("You tear the amulet from your neck, gasping for breath. The icy grip subsides.")
```

---

### Example 7: Ambusher NPC (Inline NPC Script)
Trigger: `on_protagonist_enters_scene_script` (Configured directly on the `GOBLIN_AMBUSHER` NPC)

```python
# The NPC immediately attacks the player upon entering the scene
tw.player.damage(5)
tw.story.narrate("The goblin leaps from the shadows, scoring a quick hit with a rusty dagger! (-5 HP)")
tw.memories.add("A goblin ambushed me from the shadows.")
```

---

### Example 8: Switch Mechanism State & Guard Expression
Trigger: `on_interact` (or switch transition trigger)  
Target: `LEVER_POWER_GRID`

```python
# Check state of another mechanism before powering the main grid
if tw.switches.is_state("VALVE_COOLANT", "OPEN"):
    tw.switches.set_state("LEVER_POWER_GRID", "ONLINE")
    tw.exits.unlock("SCENE_VAULT_HALL", "SCENE_VAULT")
    tw.story.narrate("Coolant surges into the coils. The main power grid hums online and the vault unseals!")
else:
    tw.story.narrate("The lever clicks, but nothing happens. A red warning light blinks: 'Coolant valve must be opened first!'")
```

**Using Guard Expressions (`gates.expression`):**  
Within the Switch Configurator, a transition to `"ONLINE"` can declare a deterministic guard condition:
```python
tw.switches.get_state("VALVE_COOLANT") == "OPEN" and tw.player.has_item("SAFETY_KEY")
```
If this condition evaluates to `False`, the transition is blocked and the transition's `fail_message` is narrated to the player.

---

### Example 9: Global Init Script with Helper Functions
Configured in: **Global Initialization Script** (`init_script`)

```python
# Initialize starting adventure variables
tw.vars.set("investigation_stage", 1)
tw.vars.set("clues_found", 0)
tw.vars.set("bribe_accepted", False)

# Reusable method available across all scene and turn scripts
def discover_clue(clue_name):
    count = tw.vars.get("clues_found", 0) + 1
    tw.vars.set("clues_found", count)
    tw.story.narrate("Discovered clue: " + str(clue_name) + " (" + str(count) + "/3)")
    if count >= 3:
        tw.quests.complete("QUEST_FIND_EVIDENCE")
        tw.story.narrate("All clues uncovered! The conspiracy is exposed.")

def advance_investigation():
    stage = tw.vars.get("investigation_stage", 1) + 1
    tw.vars.set("investigation_stage", stage)
    return stage
```

Event Script using `discover_clue` (Trigger: `on_interact`, Target: `ITEM_SECRET_JOURNAL`):
```python
discover_clue("Conspirator Journal")
tw.player.remove_item("ITEM_SECRET_JOURNAL")
```

### Example 10: NPC Hands the Player an Item (Sequence Soft Rule)
Configured in: **Sequence → Soft Rules** (sequence `SEQ_1_TAVERN`, NPC `BRENDA` carries `BRENDA_KEY`)

Soft rule `BRENDA_ANGRY`, condition *"Arthur makes Brenda angry"*:
```python
tw.vars.set("BRENDA_TRUST", tw.vars.get("BRENDA_TRUST", 0) - 1)
```

Soft rule `BRENDA_FLIRT`, condition *"Arthur flirts with Brenda"*, `max_triggers: 1`, guard `tw.vars.get("BRENDA_TRUST", 0) >= 0 and tw.npcs.get("BRENDA").current_scene_id == tw.scene.id`:
```python
key = tw.npcs.give_to_player("BRENDA", "BRENDA_KEY")
if key:
    tw.npcs.say("BRENDA", "Fine, charmer. Take it before I change my mind.")
    tw.story.narrate("Brenda slips you " + key["name"] + ".")
```

If Arthur has angered Brenda first, the guard fails and the flirt has no mechanical effect. Because `give_to_player` returns `None` when Brenda no longer holds the key, the dialogue only plays when the hand-over actually happens.

### Example 11: Bomb Defusal Choice Dialog
Handler in the **global init script**:
```python
def on_bomb_wire(answ):
    if answ == 0:
        tw.vars.set("bomb_disarmed", True)
        tw.story.narrate("The ticking stops. You disarmed the trap.")
        return
    if answ == 1:
        tw.game.game_over("The bomb exploded.")
        return
    tw.player.damage(5)
    tw.dialog.choose("Panic costs you precious seconds. It is still ticking!",
                     ["Cut the red wire", "Cut the blue wire", "Scream like a baby"],
                     on_choice=on_bomb_wire)
```

Dialog opened by a **sequence script** on the bomb chapter (`trigger: on_interact`, `target_id: TICKING_BOMB`), so the fixed bomb reacts to *Inspect*, *Use* or *Push* only during that chapter. The bomb's inline `on_interact_script` works the same way if it should react in every chapter:
```python
tw.dialog.choose(
    "The bomb starts ticking. What do you do?",
    ["Cut the red wire", "Cut the blue wire", "Scream like a baby"],
    on_choice="on_bomb_wire",
)
```

Screaming re-opens the dialog (at the cost of 5 HP) until the player commits to a wire.

### Example 12: Sphinx Riddle Conversation (Soft Rule + Dialog)
Soft rule `SPHINX_ASK_PASSAGE` on the sequence, condition *"The player asks the sphinx to let them pass"*, `max_triggers: 1`:
```python
tw.dialog.choose(
    "What walks on four legs at dawn, two at noon and three at dusk?",
    ["A man", "A dog", {"label": "A ghost (read in the old scroll)",
                        "visible_if": "tw.player.has_item('OLD_SCROLL')"}],
    on_choice="on_sphinx_riddle",
    speaker="The Sphinx",
    narrate=True,
)
```

Handler in the global init script:
```python
def on_sphinx_riddle(answ):
    if answ == 0:
        tw.exits.unlock("SCENE_SPHINX", "SCENE_TEMPLE")
        tw.story.narrate("The sphinx steps aside.")
        return
    tw.player.damage(10)
    tw.story.narrate("The sphinx's tail lashes you. (-10 HP)")
```

The GM decides *that* the player asked (soft rule); the dialog and its handler decide *what* happens, deterministically.

### Example 13: The Player's Words Change an NPC's Mood
The innkeeper Brom (`character: "Friendly, talkative"`) reacts to how the player treats him. Inline `on_interact_script` on `NPC_BROM`:
```python
if not tw.vars.get('brom_mood_asked'):
    tw.vars.set('brom_mood_asked', True)
    tw.dialog.choose(
        "Brom wipes the counter. \"Long road behind you?\"",
        ["Compliment his ale", "Mock his tavern", "Ignore him"],
        on_choice="on_brom_mood",
        speaker="Brom",
    )
```

Handler in the global init script:
```python
def on_brom_mood(answ):
    brom = tw.npcs.get('NPC_BROM')
    if answ == 0:
        brom.add_trait('jokes a lot')
        brom.say("Ha! Finally someone with taste.")
        return
    if answ == 1:
        brom.character = "Hostile and insulted; short, rude answers; refuses to share rumors"
        brom.goal = "Get the hero out of his tavern"
        brom.say("Then drink somewhere else.")
        return
    brom.remove_trait('talkative')
```

### Example 14: Potion Dispenser (Cloning a Hidden Item)
A hidden template item `HEALING_POTION` (type `CONSUMABLE`, `is_hidden: true`) lies in the scene `ALCHEMY_LAB`. The switch `POTION_DISPENSER` produces a fresh copy each time it is pulled, three times at most. `on_success_script` of the switch:
```python
dispensed = tw.vars.get('potions_dispensed', 0)
if dispensed >= 3:
    tw.narrate("The dispenser only coughs up a puff of green dust.")
else:
    potion = tw.objects.get('HEALING_POTION').clone(scene_id='current', hidden=False)
    if potion:
        tw.vars.set('potions_dispensed', dispensed + 1)
        tw.narrate("With a gurgle, a fresh healing potion drops into the tray.")
```
The copies (`HEALING_POTION_1`, `HEALING_POTION_2`, ...) lie visibly in the scene and can be picked up like any item; use `potion.move_to('player')` instead to put them straight into the inventory. The template itself stays hidden.

### Example 15: Offering Altar (Player Puts Items into a Container)
The container `MOON_ALTAR` stands unlocked in the shrine. In the container panel the player presses **Put In**, selects items from the inventory and confirms. `on_items_added_script` of the altar:
```python
if 'SILVER_MOON' in added_item_ids:
    tw.objects.destroy('SILVER_MOON')
    tw.exits.unlock('SHRINE', 'MOON_GATE')
    tw.narrate("The silver moon melts into the altar. Somewhere, a gate grinds open.")
else:
    # Not what the altar wants: it spits the offering back out.
    for item_id in added_item_ids:
        tw.objects.take_from_container('MOON_ALTAR', item_id, to='player')
    tw.narrate("The altar stays cold. Your offering rolls back into your hands.")
```

### Example 16: Blacksmith Conversation (Dialogue Tree)
In the global init script:
```python
GORAN_TALK = {
    "dialogue_id": "goran_intro",
    "npc_id": "NPC_GORAN",
    "initial_node": "root",
    "nodes": {
        "root": {
            "npc_text": "What do you want? I have no time for idle talk.",
            "responses": [
                {"text": "I need decent gear for the wilds.", "next_node": "equipment"},
                {"text": "I heard rumours about the abandoned mine.", "next_node": "mine"},
                {"text": "Never mind, I'm leaving.", "next_node": None},
            ],
        },
        "equipment": {
            "npc_text": "Good iron costs good gold. A dwarf-steel broadsword: 250 gold pieces.",
            "responses": [
                {"text": "I'll take the sword. [250 Gold]",
                 "condition": "tw.vars.get('gold', 0) >= 250",
                 "action": "BUY_DWARF_SWORD", "next_node": "equipment"},
                {"text": "Too expensive.", "next_node": "root"},
            ],
        },
        "mine": {
            "npc_text": "The baron sealed the tunnel two months ago. Things crawl down there.",
            "responses": [
                {"text": "Is there still ore to find?", "once": True,
                 "script": "tw.vars.set('knows_star_silver', True)", "next_node": "mine_ore"},
                {"text": "Enough about mines.", "next_node": "root"},
            ],
        },
        "mine_ore": {
            "npc_text": "Veins of star silver. Bring me five chunks and I'll forge you a king-slayer.",
            "responses": [
                {"text": "Deal. [Accept quest]", "action": "START_QUEST_STAR_SILVER", "next_node": "mine"},
                {"text": "Too risky.", "next_node": "mine"},
            ],
        },
    },
}

def on_goran_action(action):
    if action == "BUY_DWARF_SWORD":
        tw.vars.set('gold', tw.vars.get('gold', 0) - 250)
        tw.player.take_item('DWARF_SWORD')
        return
    if action == "START_QUEST_STAR_SILVER":
        tw.vars.set('quest_star_silver', 'active')

def on_goran_end(path):
    tw.vars.set('goran_topics', [step['node'] for step in path])
```
Inline `on_interact_script` of `NPC_GORAN`:
```python
tw.dialog.tree(GORAN_TALK, on_end="on_goran_end", on_action="on_goran_action")
```

From the next turn on, the GM plays Brom with the new personality, in this game only.

### Example 17: Returning a Lost Ring (Giving an NPC Items)
The widow `NPC_MARTA` lost her ring. The player opens her context menu, chooses **Give**, selects items from the inventory and confirms (typing `give the silver ring to Marta` does the same). `on_receive_item_script` of Marta:
```python
if 'SILVER_RING' in received_item_ids:
    tw.vars.set('ring_returned', True)
    tw.npcs.give_to_player('NPC_MARTA', 'CELLAR_KEY')
    tw.story.direct('Marta is moved to tears, thanks the player and hands over the cellar key.')
else:
    # Not her ring: she gives everything back.
    for item_id in received_item_ids:
        tw.npcs.give_to_player('NPC_MARTA', item_id)
    tw.story.direct('Marta politely returns the gift; it is not what she is looking for.')
```
The handover itself is deterministic; the Game Master then narrates Marta's reaction and follows the direction. Giving is refused for defeated NPCs and for items the player does not carry.

---

### Example 18: Ticking Bomb and Nightfall (Time Events)
The init script defines the handlers, an `on_interact` script arms the bomb, and an `on_time_reached` script with target `10h` makes it night after ten hours of play.

`init_script`:
```python
def bomb_explodes(event):
    if tw.vars.get("bomb_defused"):
        return
    tw.game.game_over("The bomb detonates " + str(event["data"]["room"]) + ".")

def bomb_warning(event):
    left = tw.vars.get("bomb_at", 0) - tw.time.now
    if left > 0:
        tw.system(str(left) + " minutes left on the bomb timer.")
```

Script `ARM_BOMB` (trigger `on_interact`, target `BOMB`):
```python
if not tw.time.has_timer("BOMB"):
    tw.time.after("30m", bomb_explodes, timer_id="BOMB", data={"room": "in the cellar"})
    tw.time.every(10, bomb_warning, timer_id="BOMB_WARNING")
    tw.vars.set("bomb_at", tw.time.now + 30)
    tw.narrate("A red display lights up: 00:30:00.")
```

Script `DEFUSE` (trigger `on_interact`, target `BOMB_WIRES`):
```python
tw.vars.set("bomb_defused", True)
tw.time.cancel("BOMB")
tw.time.cancel("BOMB_WARNING")
tw.narrate("The display flickers and dies.")
```

Script `NIGHTFALL` (trigger `on_time_reached`, target `10h`):
```python
tw.direct("Night has fallen: describe darkness, cold and the sounds of the night.")
tw.time.set_minutes_per_tick(15)  # the night passes faster
```

---

## Authoring in the World-Editor

You can manage all scripts visually inside TaleWeaver:

1. Navigate to the **Adventure Editor** for your adventure.
2. Select the **Scripts** tab from the navigation sidebar.

### Event Scripts & Triggers
All scripts are managed directly in the **Scripts** tab:
- **Session Initialization**: To execute logic when a new game session starts (initializing variables, quest flags, starting state), create an event script with the **`on_init`** ("On Session Init") trigger.

- Click **New Script** to open the script authoring modal:
  - Enter a human-readable **Name** and unique **Script ID**.
  - Select the desired **Trigger** (`on_init`, `on_turn_start`, `on_enter_scene`, `on_interact`, `on_logic_pass_done`, `on_narration_done`, `on_turn_end`, `on_time_reached`).
  - Optionally pick a **Target** scene or entity using the autocomplete selector. For `on_time_reached` the target field holds the elapsed in-game time instead (e.g. `90`, `2h 30m`, `1d`); **Check Syntax** rejects other values.
  - Adjust **Priority** (lower numbers execute first).
  - Use the **Insert Snippet** dropdown to paste starter code.
- Click **Check Syntax** to verify Python syntax, AST safety, and trigger parameters before saving.
- Click **Create Script** or **Save Changes** to commit the script into the adventure manifest.

### AI Optimize & AI Generate
Every script and guard editor in the Adventure Editor has two AI buttons next to **Check Syntax**:
- **AI Optimize** fixes errors and API misuse in the current code, simplifies it while keeping its behaviour, and replaces placeholder comments (`# TODO: give the player the key`) with working code.
- **AI Generate** opens a prompt: describe what the code should do ("every NPC in the scene gets angry and says what they think about the player"). The AI builds on the current code unless you ask for a rewrite.

The AI knows the field it writes for (e.g. *On Pickup Script* or a guard expression), the `tw` API, the sandbox rules, the adventure's scenes, NPCs, objects, existing hooks and the `init_script` helpers. Every proposal runs through the sandbox syntax check; a failing proposal gets one automatic repair round, and remaining errors are shown as a warning.

Nothing changes until you decide: the proposal opens as a line diff (removed lines red, added lines green) with **Accept** and **Discard**. After accepting, **Ctrl+Z** in the editor restores the previous code. Saving still works as usual through the surrounding form. Texts shown to the player follow the adventure language; code, identifiers and comments are English.

### Scripts from World-Builder Instructions
The **World-Builder** prompt at the top of the Adventure Editor can also write inline triggers and guards. Describe the behaviour in plain words, for example *"The chest only opens after the lever in the cellar was pulled"* or *"The amulet hurts the player when it is equipped"*, and pick one of up to three proposals.

- **Supported fields**: the inline `..._script` / `..._text` triggers of scenes (`on_enter_scene`, `on_leave_scene`, `helpers_script`), exits (`on_open_exit`, `on_exit_used`, `on_unlock_success`, `on_unlock_failure`, `unlock_expression`), NPCs (`on_defeat`, `on_protagonist_enters_scene`, `on_interact`, `on_receive_item`), objects (`on_pickup`, `on_drop`, `on_interact` for every item; `on_equip` / `on_unequip` for weapons and wearables; `on_read` for readables; `unlock_expression` and the unlock hooks for containers; `craft_guard_expression` and the craft hooks for recipes), the protagonist (`on_hp_change`, `on_status_change`) and sequences (`on_start_sequence`, `on_end_sequence`, `helpers_script`, soft rules).
- **New entities**: a newly created NPC or item gets its hooks from a second patch in the same proposal.
- **Not supported**: top-level `scripts`, sequence `scripts` and `init_script`. Write those in the **Scripts** tab.
- **Syntax check**: every proposed script and guard runs through the sandbox syntax check. Proposals with invalid code are discarded and the reason is shown instead.
- **Existing logic**: the World-Builder sees the hooks that already exist and reuses their `tw.vars` flags.
- **Language**: proposal titles, summaries and notes are always English. Narrative texts (descriptions, `..._text` fields) follow the adventure's language setting, or English when none is set, never the language the instruction was typed in.

### Interactive Autocomplete & IntelliSense
The in-browser CodeMirror Python script editor provides VS Code-style autocomplete for the entire `tw` scripting API:
- **Namespace Exploration**: Typing `tw.` immediately opens an interactive dropdown listing all available sub-namespaces (`story`, `player`, `npcs`, `objects`, `switches`, `scene`, `exits`, `vars`, `dialog`, `time`, etc.) and top-level shortcuts (`narrate`, `system`, `direct`, `save`, `switch`, `debug`).
- **Method & Signature Inspection**: Typing a dot after any sub-namespace (e.g. `tw.story.`, `tw.player.`, `tw.switches.`) or chained proxy (`tw.npcs.get(...).`, `tw.switch(...).`) filters available methods and properties, showing parameter signatures, return types, and doc summaries.
- **Manual Trigger**: Press `Ctrl+Space` anywhere inside the editor to open or refresh completion suggestions.
- **Smart Call Insertion**: Selecting a method automatically inserts its call syntax (e.g. `narrate()`) and places the cursor between the parentheses when arguments are expected.
- **Synchronization**: The autocomplete registry (`frontend/src/utils/twScriptApiDefinitions.ts`) is kept in direct sync with the engine backend and this guide.
