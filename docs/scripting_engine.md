# TaleWeaver Scripting Engine Guide

The **TaleWeaver Scripting Engine** provides a secure, sandboxed environment for embedding deterministic event-driven logic directly into adventures. By authoring lightweight Python-style scripts, world builders and the AI World-Builder can craft complex interactive puzzles, reactive traps, dynamic NPC movements, and custom victory or defeat conditions that seamlessly interface with TaleWeaver's generative game master.

---

## Table of Contents
1. [Overview & Architecture](#overview--architecture)
2. [Sandbox Security & Limits](#sandbox-security--limits)
3. [Event Triggers & Lifecycle](#event-triggers--lifecycle)
4. [Global Initialization Script & Helper Methods](#global-initialization-script--helper-methods)
5. [The `tw` Scripting API](#the-tw-scripting-api)
   - [tw.player](#twplayer)
   - [tw.scene](#twscene)
   - [tw.exits](#twexits)
   - [tw.npcs](#twnpcs)
   - [tw.objects](#twobjects)
   - [tw.switches](#twswitches)
   - [tw.vars](#twvars-persistent-state)
   - [tw.story](#twstory)
   - [tw.memories](#twmemories)
   - [tw.game](#twgame)
   - [tw.quests](#twquests)
   - [tw.awards](#twawards)
   - [tw.dice](#twdice)
   - [tw.dialog (Choice Dialogs)](#twdialog-choice-dialogs)
   - [tw.llm (Ask the LLM)](#twllm-ask-the-llm)
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
               [on_turn_end] -> time + status ticks -> [on_turn_start]
                                       |
                                       v
                      LLM narration --> [on_narration_done scripts]
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
- **No Private or Dunder Identifiers**: Accessing attributes or defining functions starting with an underscore (e.g. `_internal`, `__class__`, `__subclasses__`, `__globals__`, or `__dict__`) is strictly forbidden.
- **No Introspection Escapes**: `str.format`, `format_map` and `mro` are blocked (format strings could otherwise walk `{0.__globals__}`), as are frame/generator/code attributes (`f_*`, `gi_*`, `cr_*`, `ag_*`, `tb_*`, `co_*`). Use f-strings or `+` for text.
- **Instruction & Time Budget**: Each script execution is capped at **10,000 steps** and **2 seconds** (`ScriptTimeoutError`), preventing infinite loops and CPU exhaustion. Time spent waiting for `tw.llm.ask` does not count against the 2 seconds.
- **Memory Protections**: Strings, lists, tuples and dicts are capped at **100,000** elements/characters (repetition, concatenation, `join`, padding methods and call results are all checked), `range()` at 100,000 elements, and integers at 10,000 bits (`ScriptSecurityError`).
- **Safe Builtins**: Available built-ins are restricted to `abs`, `all`, `any`, `bool`, `dict`, `float`, `int`, `len`, `list`, `max`, `min`, `range`, `round`, `str`, `sum`, `tuple`.
- **Inline conditionals**: `a if condition else b` is supported.

---

## Event Triggers & Lifecycle

Scripts declare a trigger event and an optional target entity or scene.

| Trigger | When it Executes | Target Field Usage |
| :--- | :--- | :--- |
| `on_init` | When a new game session starts, immediately after initial world manifest and entity state setup. | Global (`*` or empty). |
| `on_turn_start` | When a new in-game turn begins, i.e. right after the player's scene or the active sequence changed (after `on_turn_end` of the previous turn, before narration). | Global (`*` or empty). |
| `on_enter_scene` | When the player enters a new scene. | Specific `scene_id` or empty for any scene. |
| `on_interact` | When the player examines, attacks, talks to, or manipulates an entity: the GM reported a state change on it, or the player's message names an entity in the current scene or inventory (all context-menu actions such as *Inspect*, *Use*, *Push* do). | Specific `entity_id` (NPC or object) or empty for all. |
| `on_logic_pass_done` | After game mechanics and state mutations finish, before narration is generated. | Global (`*` or empty). |
| `on_narration_done` | After narration generation completes, before final turn persistence. | Global (`*` or empty). |
| `on_turn_end` | When the current in-game turn ends, i.e. when the player's scene or the active sequence changed (before `on_turn_start` of the next turn). | Global (`*` or empty). |

> **In-game turns vs. player messages:** An in-game turn spans all player messages within one scene and sequence. Base time (`time_per_turn`), status-effect ticks, and the `on_turn_end` / `on_turn_start` hooks only fire on a scene or sequence change. Use `on_logic_pass_done` or `on_narration_done` for logic that must run on every player message.

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
| **Container Items** | `unlock_expression` *(Guard)* | Deterministic Python boolean expression evaluated when attempting to unlock. If false, unlocking fails. |
| | `on_unlock_success_script`, `..._text` | Executes immediately when this container is successfully unlocked. |
| | `on_unlock_failure_script`, `..._text` | Executes when unlocking this container fails or is blocked by guard. |
| **Constructable Recipes** | `craft_guard_expression` *(Guard)* | Optional Python boolean expression evaluated in addition to ingredients. If false, crafting fails. |
| | `on_craft_success_script`, `..._text` | Executes when this recipe is successfully crafted (its `result_item_ids` are revealed). The script runs with the recipe as its entity. The text replaces the default craft message. |
| | `on_craft_failure_script`, `..._text` | Executes when crafting fails or is blocked by guard. |
| **NPCs** | `on_defeat_script`, `on_defeat_text` | Executes when the NPC is defeated. Use to spawn loot or change state. |
| | `on_protagonist_enters_scene_script` | Executes when the player enters the room containing this NPC. |
| | `on_interact_script`, `on_interact_text` | Executes whenever the player talks to, inspects or otherwise interacts with this NPC. |
| **Scenes** | `on_enter_scene_script`, `..._text` | Executes when the player enters this specific scene. |
| | `on_leave_scene_script`, `..._text` | Executes immediately when the player leaves this specific scene. |
| **Exits** | `on_open_exit_script`, `..._text` | Executes when the player opens or traverses this exit. |
| | `on_exit_used_script`, `..._text` | Transition Trigger: Executes specifically when the player successfully traverses this exit to enter the destination scene. |
| | `unlock_expression` *(Guard)* | Deterministic Python boolean expression evaluated when unlocking. If false, unlocking fails. |
| | `on_unlock_success_script`, `..._text` | Executes immediately when this exit is successfully unlocked. |
| | `on_unlock_failure_script`, `..._text` | Executes when unlocking this exit fails or is blocked by guard. |
| **Switches** | `gates.expression` *(Guard)* | Deterministic Python boolean condition required for a specific transition. |
| | `on_success_script` | Executes when any state transition succeeds on this switch (or transition-specific). |
| | `on_failure_script` | Executes when any state transition fails on this switch (or transition-specific). |
| **NPC combat** *(metadata)* | `attack_mode: ATTACK_ON_SIGHT` | The NPC starts turn-based combat as soon as the protagonist enters its scene. |
| | `attack_trigger` *(Hard Rules + Guard)* | `required_item_id`, `required_scene_id`, `required_defeated_npc_id`, `guard_expression`: the NPC attacks once when all are met while the protagonist shares its scene. |
| **Special attacks** (protagonist & NPC `special_actions` entries) | `on_success_script`, `..._text` | Executes after a successful d20 success roll. A `special` dict (`id`, `name`, `caster`, `target`, `success`, `crit`, `fumble`, `roll`, `dc`) is in scope. |
| | `on_failure_script`, `..._text` | Executes when the success roll fails. |
| | `unlock_required_item_id`, `unlock_required_scene_id`, `unlock_required_defeated_npc_id`, `unlock_guard_expression` *(Hard Rules + Guard, protagonist only)* | A locked special unlocks after the turn in which all configured conditions are met; a system message (plus optional `unlock_text`) announces it. |
| **Protagonist** | `on_hp_change_script`, `..._text` | Executes when protagonist HP changes (e.g. taking damage or healing). |
| | `on_status_change_script`, `..._text` | Executes when protagonist status effects or conditions change. |
| **Sequences** | `on_start_sequence_script`, `..._text` | Executes immediately when a sequence chapter becomes active. |
| | `on_end_sequence_script`, `..._text` | Executes immediately when a sequence chapter is completed. |
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
   - Any state mutations performed via `tw.vars.set(...)`, `tw.switches.set_state(...)`, or `tw.story.show_message(...)` are committed directly into the initial session state (`__script_vars__`).
   - The engine automatically records `__init_script_executed__ = True` so setup logic does not re-run on subsequent turns.
   - Any standalone scripts marked with the `on_init` trigger also fire during this phase.

2. **Every Turn Scope Injection (Reusable Methods & Constants)**:
   Whenever an event script fires during gameplay (`on_turn_start`, `on_interact`, `on_enter_scene`, `on_turn_end`, etc.), the engine loads function definitions (`def ...`) and top-level constants from the initialization script and injects them directly into the script's global execution scope.
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
    tw.story.show_message("You gained " + str(amount) + " gold! Total: " + str(current + amount))

def spend_gold(amount):
    current = tw.vars.get("gold", 0)
    if current < amount:
        tw.story.show_message("Not enough gold! Needed: " + str(amount) + ", Have: " + str(current))
        return False
    tw.vars.set("gold", current - amount)
    tw.story.show_message("You spent " + str(amount) + " gold. Remaining: " + str(current - amount))
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
    tw.story.show_message("The merchant smiles and hands you a steaming vial of healing draught.")
```

Inside an `on_enter_scene` script attached to `SCENE_INNER_SANCTUM`:
```python
if not can_access_sanctum():
    tw.story.show_message("A divine barrier repels you! Your reputation is insufficient.")
    tw.player.damage(10)
```

---

## The `tw` Scripting API

The global `tw` object is injected into every script execution environment.

### `tw.player`
Inspects and modifies the avatar's state:
- `tw.player.hp` *(int)*: Current avatar health points.
- `tw.player.name` *(str)*: Protagonist's name.
- `tw.player.inventory` *(list[dict])*: List of items currently held by the avatar.
- `tw.player.heal(amount: int)`: Restores `amount` HP (up to avatar maximum).
- `tw.player.damage(amount: int)`: Inflicts `amount` direct damage to the avatar.
- `tw.player.has_item(item_id: str) -> bool`: Returns `True` if `item_id` is in the inventory.

### `tw.scene`
Inspects the current scene:
- `tw.scene.id` *(str)*: ID of the current scene.
- `tw.scene.name` *(str)*: Display label of the current scene.
- `tw.scene.description` *(str)*: Scene description text.
- `tw.scene.entities` *(list[dict])*: List of active entities (items and NPCs) present in the scene.

### `tw.exits`
Queries and manipulates passage exits:
- `tw.exits.lock(exit_id: str, reason: str = "")`: Locks the exit. If the player attempts to traverse it, `reason` explains why it is blocked.
- `tw.exits.unlock(exit_id: str)`: Unlocks a previously locked passage.
- `tw.exits.hide(exit_id: str)`: Hides the exit from the player's map and navigation choices.
- `tw.exits.reveal(exit_id: str)`: Reveals a hidden exit or secret door.
- `tw.exits.is_locked(exit_id: str) -> bool`: Returns `True` if the exit is currently locked.

### `tw.npcs`
Inspects, dialogues with, moves, and manages Non-Player Characters:
- `tw.npcs.say(npc_id: str, text: str)`: Makes an NPC speak dialogue text. Appears in the narrative feed as `NPC Name: "text"`. Also available as `tw.npcs.get(npc_id).say(text)`.
- `tw.npcs.move(npc_id: str, target_scene_id: str, spatial_position: str = "")`: Moves an NPC to another scene. Accepts `"current"`, `"here"`, or `"player"` to move them into the protagonist's current location.
- `tw.npcs.move_to_player(npc_id: str, spatial_position: str = "")`: Convenience shortcut to move an NPC directly into the player's current scene.
- `tw.npcs.drop_item(npc_id: str, item_id: str, scene_id: str = None, spatial_position: str = "")`: Transfers an item from an NPC's inventory into a scene. If `scene_id` is omitted, it drops into the NPC's current scene; passing `"current"` drops it into the player's scene.
- `tw.npcs.give_item(npc_id: str, item_id: str)`: Transfers an item from a scene into an NPC's inventory and conceals it from the scene view.
- `tw.npcs.give_to_player(npc_id: str, item_id: str) -> dict | None`: Hands an item the NPC carries directly to the protagonist. The item leaves the NPC's inventory and keeps its world entity data (name, description, image, stats). Returns the new inventory entry, or `None` (and changes nothing) if the NPC doesn't hold the item, so scripts can't conjure items.
- `tw.npcs.kill(npc_id: str, drop_inventory: bool = True)`: Kills the NPC, setting HP to 0 and marking `is_defeated: True`. When `drop_inventory=True` (default), all items held by the NPC are dropped into their scene.
- `tw.npcs.attack(npc_id: str)`: Makes an NPC attack the protagonist. Turn-based combat starts right after the current turn if the NPC is in the protagonist's scene, alive and attackable (ignored while a fight is already running). Example (`on_turn_end`): `if tw.player.has_item('IDOL') and not tw.vars.get('alarm'): tw.vars.set('alarm', True); tw.npcs.attack('TEMPLE_GUARD')`.
- `tw.npcs.set_character(npc_id: str, text: str)`: Replaces the NPC's personality (the `character` field). The GM reads it on every turn, so the NPC talks and acts differently from then on (friendlier, aggressive, funny, frightened, …). An empty text clears it. Whitespace is collapsed to a single line and the text is cut at 1,000 characters.
- `tw.npcs.set_goal(npc_id: str, text: str)`: Replaces what the NPC wants (the `goal` field), with the same rules.
- `tw.npcs.add_trait(npc_id: str, trait: str)` / `tw.npcs.remove_trait(npc_id: str, trait: str)`: Adds or removes a single trait in the comma-separated `character` text (case-insensitive; adding an existing trait does nothing). Handy for temporary states such as `"drunk"` or `"frightened"`.
- `tw.npcs.get(npc_id: str) -> NPCProxy`: Returns an `NPCProxy` instance. Available properties and methods on `NPCProxy`:
  - `.name`, `.hp`, `.is_defeated`, `.current_scene_id`, `.inventory`
  - `.say(text: str)`
  - `.move_to(target_scene_id: str, spatial_position: str = "")` (supports `"current"`)
  - `.move_to_player(spatial_position: str = "")`
  - `.drop_item(item_id: str, scene_id: str = None, spatial_position: str = "")`
  - `.give_item(item_id: str)`
  - `.give_to_player(item_id: str) -> dict | None`
  - `.has_item(item_id: str) -> bool`
  - `.kill(drop_inventory: bool = True)` / `.die()`
  - `.attack()` (see `tw.npcs.attack`)
  - `.modify_hp(delta: int)` / `.damage(amount: int)` / `.heal(amount: int)`
  - `.character`, `.goal` *(read/write)*: assigning (`npc.character = "Gruff, impatient"`) is the same as calling `.set_character()` / `.set_goal()`
  - `.set_character(text)`, `.set_goal(text)`, `.add_trait(trait)`, `.remove_trait(trait)`, `.has_trait(trait) -> bool`

  Persona changes apply to the current game only: they are stored on the session's copy of the NPC, and the adventure template keeps its original text. To restore the original later, store it first, e.g. `tw.vars.set('brom_bio', tw.npcs.get('BROM').character)`. A persona change shapes the GM's narration and dialogue; it does not start a fight on its own (use `.attack()` for that).

### `tw.objects` (or `tw.items`)
Manages world objects and inventory items:
- `tw.objects.move_to_scene(item_id: str, scene_id: str, spatial_position: str = "")`: Moves an object/item into a scene. Accepts `"current"` for protagonist's scene.
- `tw.objects.give_to_npc(item_id: str, npc_id: str)`: Transfers an item into an NPC's inventory.
- `tw.objects.add_to_scene(item_id: str, scene_id: str)`: Spawns or moves an item into a scene.
- `tw.objects.add_to_player(item_id: str)`: Directly places an item into the avatar's inventory.
- `tw.objects.remove_from_player(item_id: str)`: Removes an item from the player's inventory.
- `tw.objects.hide(item_id: str)`: Hides an object in the scene until uncovered.
- `tw.objects.reveal(item_id: str)`: Reveals a previously hidden object.
- `tw.objects.get(item_id: str) -> ObjectProxy`: Returns an `ObjectProxy` with `.move_to_scene(scene_id)` and `.give_to_npc(npc_id)`. For switch items, `ObjectProxy` also exposes `.state`, `.switch_state`, `.get_state()`, `.set_state()`, `.is_state()`, `.flip()`, and `.toggle()`.

### `tw.switches`
Inspects and manipulates interactive switches, levers, buttons, and puzzle mechanisms across the adventure:
- `tw.switches.get(switch_id: str) -> SwitchProxy`: Retrieves a `SwitchProxy` for the switch entity. Also accessible via shortcut `tw.switch(switch_id)`.
- `tw.switches.get_state(switch_id: str, default: str = "") -> str`: Returns the current state string (e.g. `"OFF"`, `"ON"`, `"ACTIVE"`).
- `tw.switches.set_state(switch_id: str, new_state: str, apply_outcomes: bool = True) -> bool`: Deterministically transitions the switch to `new_state`, optionally triggering any associated switch outcomes (unlocking exits, containers, or setting story flags).
- `tw.switches.is_state(switch_id: str, state: str) -> bool`: Returns `True` if the switch currently matches `state`.
- `tw.switches.flip(switch_id: str, apply_outcomes: bool = True) -> str`: Cycles or toggles the switch to its next configured state, returning the new state.
- `tw.switches.toggle(switch_id: str, apply_outcomes: bool = True) -> str`: Alias for `flip()`.
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
- `tw.story.show_message(text: str)` / `tw.story.narrate(text: str)` / `tw.narrate(text: str)`: Emits Game Master narration (`role: "assistant"`), displayed with the Game Master avatar, dialogue parsing, and styled exactly like standard storytelling turns (e.g. `tw.story.show_message('Du nimmst das Stück Schokolade. Vielleicht hilft es beim Überzeugen.')`).
- `tw.story.system_message(text: str)` / `tw.story.system(text: str)` / `tw.system(text: str)`: Emits a technical system notification (`role: "system"`).
- `tw.story.log(text: str)`: Appends an internal log message visible during debugging.

### `tw.memories`
Directly writes into the avatar's episodic memory bank:
- `tw.memories.add(memory_text: str)`: Injects a factual memory into the avatar context that the Game Master LLM references in subsequent turns.

### `tw.game`
Controls session outcome conditions:
- `tw.game.win(message: str)`: Ends the adventure in victory and displays `message`.
- `tw.game.game_over(reason: str)`: Ends the adventure in defeat with `reason`.

### `tw.quests`
Directly manipulates adventure quest entries:
- `tw.quests.complete(quest_id: str)`: Marks `quest_id` as completed.
- `tw.quests.activate(quest_id: str)`: Activates an open quest.
- `tw.quests.fail(quest_id: str)`: Marks a quest as failed.

### `tw.awards`
Awards achievements to the player's profile:
- `tw.awards.grant(award_key: str)`: Immediately grants the specified trophy/badge.

### `tw.dice`
Provides deterministic, seeded random number generation:
- `tw.dice.roll(sides: int = 20) -> int`: Rolls a die with `sides` faces (1 to `sides`).
- `tw.dice.d6() -> int`: Convenience for a 6-sided die roll (1 to 6).
- `tw.dice.d20() -> int`: Convenience for a 20-sided die roll (1 to 20).
- `tw.dice.random() -> float`: Returns a pseudo-random float between `0.0` and `1.0`.

### `tw.dialog` (Choice Dialogs)
Shows the player a multiple-choice dialog for NPC conversations, riddles and dilemmas. Only scripts (including soft rule scripts) can open a dialog; the LLM never sees this API.

- `tw.dialog.choose(prompt, options, on_choice, speaker=None, narrate=False) -> bool` (alias `tw.dialog.ask`)
  - `prompt`: the question or situation shown above the options.
  - `options`: up to 8 entries, each a label string or `{"label": "...", "visible_if": "<guard expression>"}`. Hidden options keep their position, so indices stay stable.
  - `on_choice`: name of the handler function (a string, or the function itself). **The handler must be defined in the global `init_script`.**
  - `speaker`: optional NPC name shown as the dialog title.
  - `narrate`: when `True`, the small model narrates the outcome after the handler ran (it is told the handler's messages are binding facts). Default `False`: only the handler's own messages appear, which is instant and deterministic.
  - Returns `False` (and emits a debug note) when no dialog was opened: another dialog is already open this turn, the handler name is invalid, or no option is visible.

**How it works.** Scripts run to completion inside one request, so `choose()` does not wait for the answer. It stores a *pending dialog* in the session state (`entity_states["__pending_dialog__"]`) and the client shows a modal that cannot be dismissed. Free-text input is rejected (HTTP 409) until the player answers. The answer goes to `POST /adventures/{game_id}/dialog/choice`, which:

1. records the choice in the chat as `[Choice] <label>` (so the GM keeps continuity),
2. calls `<on_choice>(index)` with the **position of the chosen option in `options`**, plus a `dialog_choice` dict (`index`, `label`, `dialog_id`) in scope,
3. applies the handler's changeset (variables, items, HP, game over, sequence advance, …) and runs the post-turn checks (special unlocks, NPC attacks),
4. optionally narrates the outcome (`narrate=True`).

A handler may call `tw.dialog.choose()` again, which is how multi-step conversations and dialog trees are built. The editor validation warns (`dialog_handler_missing`) when a dialog references a handler that the init script does not define.

### `tw.llm` (Ask the LLM)

- `tw.llm.ask(prompt, model="simple", system="") -> str`: Sends `prompt` to the language model configured in the player's LLM settings and returns the answer as a string.
  - `model="simple"` uses the **small model** (`small_model` / `small_model_provider`), `model="advanced"` the **complex model** (`complex_model` / `complex_model_provider`). Any other value is a script error.
  - `system` optionally replaces the default system prompt ("answer briefly, return only the requested text"). The session language is appended automatically.
- `tw.llm.available -> bool`: `False` where the LLM cannot be used (see below).

Rules and limits:

- **Never raises for provider problems**: when the LLM is not configured, fails, or takes longer than **20 seconds**, `ask()` returns `""`. Always keep a fallback: `line = tw.llm.ask(...) or "The raven stays silent."`
- **At most 3 calls** per script context (one trigger pass); further calls return `""`. Prompts and system prompts are cut at 4,000 characters, answers at 2,000. Answers are capped at about 600 tokens.
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
```

### `tw.log` & `tw.debug` (Logging & Diagnostics)
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
    tw.story.show_message(
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
    tw.exits.lock("EXIT_TO_COURTYARD", "The armored sentry lowers his halberd: 'Halt! Only bearers of the Royal Signet may enter.'")
    tw.story.show_message("The castle guard steps forward, barring the iron gate.")
else:
    # Unlock and allow passage
    tw.exits.unlock("EXIT_TO_COURTYARD")
    tw.story.show_message("The guard notices the Royal Signet ring, salutes respectfully, and raises the heavy portcullis.")
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
        tw.exits.unlock("EXIT_VAULT_DOOR")
        tw.story.show_message("With a resonant chime, all three mechanisms lock into place and the massive vault door unseals!")
        tw.awards.grant("PUZZLE_MASTER")
```

---

### Example 4: Boss Encounter & Victory Condition
Trigger: `on_interact`  
Target: `NPC_SHADOW_LORD`

```python
# If the player uses the Sunstone against the Shadow Lord
if tw.player.has_item("RELIC_SUNSTONE"):
    tw.story.show_message(
        "You raise the Sunstone! Blinding solar radiance floods the chamber, dissolving the Shadow Lord into harmless embers."
    )
    tw.quests.complete("MAIN_QUEST_SLAY_SHADOWS")
    tw.awards.grant("SAVIOR_OF_THE_REALM")
    tw.game.win("The realm is saved! The eternal darkness has been banished forever.")
else:
    tw.player.damage(25)
    tw.story.show_message("The Shadow Lord's aura lashes out in icy tendrils (-25 HP). You need a source of holy light!")
```

---

### Example 5: Turn-Based Survival Countdown
Trigger: `on_turn_end`  
Target: `*`

The countdown advances once per in-game turn (scene or sequence change). For a per-message countdown use `on_narration_done` instead.

```python
# Increment turn counter
turn = tw.vars.get("collapse_turn", 0) + 1
tw.vars.set("collapse_turn", turn)

remaining = 6 - turn
if remaining > 0:
    tw.story.show_message("The cavern tremors intensify! " + str(remaining) + " turn(s) before total collapse.")
else:
    tw.game.game_over("The cavern roof collapsed, burying all beneath tons of solid rock.")
```

---

### Example 6: Cursed Amulet (Inline Object Script)
Trigger: `on_equip_script` (Configured directly on the `AMULET_OF_DOOM` item)

```python
# Apply a curse when equipped
tw.vars.set("cursed_hp_drain", True)
tw.story.show_message("As the amulet touches your skin, an icy chill grips your heart. You feel your vitality draining away.")
```

Trigger: `on_unequip_script` (Configured directly on the `AMULET_OF_DOOM` item)

```python
# Remove the curse when unequipped
tw.vars.set("cursed_hp_drain", False)
tw.story.show_message("You tear the amulet from your neck, gasping for breath. The icy grip subsides.")
```

---

### Example 7: Ambusher NPC (Inline NPC Script)
Trigger: `on_protagonist_enters_scene_script` (Configured directly on the `GOBLIN_AMBUSHER` NPC)

```python
# The NPC immediately attacks the player upon entering the scene
tw.player.damage(5)
tw.story.show_message("The goblin leaps from the shadows, scoring a quick hit with a rusty dagger! (-5 HP)")
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
    tw.exits.unlock("EXIT_VAULT_DOOR")
    tw.story.show_message("Coolant surges into the coils. The main power grid hums online and the vault unseals!")
else:
    tw.story.show_message("The lever clicks, but nothing happens. A red warning light blinks: 'Coolant valve must be opened first!'")
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
    tw.story.show_message("Discovered clue: " + str(clue_name) + " (" + str(count) + "/3)")
    if count >= 3:
        tw.quests.complete("QUEST_FIND_EVIDENCE")
        tw.story.show_message("All clues uncovered! The conspiracy is exposed.")

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
    tw.story.show_message("Brenda slips you " + key["name"] + ".")
```

If Arthur has angered Brenda first, the guard fails and the flirt has no mechanical effect. Because `give_to_player` returns `None` when Brenda no longer holds the key, the dialogue only plays when the hand-over actually happens.

### Example 11: Bomb Defusal Choice Dialog
Handler in the **global init script**:
```python
def on_bomb_wire(answ):
    if answ == 0:
        tw.vars.set("bomb_disarmed", True)
        tw.story.show_message("The ticking stops. You disarmed the trap.")
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
        tw.story.show_message("The sphinx steps aside.")
        return
    tw.player.damage(10)
    tw.story.show_message("The sphinx's tail lashes you. (-10 HP)")
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

From the next turn on, the GM plays Brom with the new personality, in this game only.

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
  - Select the desired **Trigger** (`on_init`, `on_turn_start`, `on_enter_scene`, `on_interact`, `on_logic_pass_done`, `on_narration_done`, `on_turn_end`).
  - Optionally pick a **Target** scene or entity using the autocomplete selector.
  - Adjust **Priority** (lower numbers execute first).
  - Use the **Insert Snippet** dropdown to paste starter code.
- Click **Check Syntax** to verify Python syntax, AST safety, and trigger parameters before saving.
- Click **Create Script** or **Save Changes** to commit the script into the adventure manifest.
