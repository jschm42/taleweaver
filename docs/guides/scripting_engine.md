# TaleWeaver Scripting Engine Guide

The **TaleWeaver Scripting Engine** provides a secure, sandboxed environment for embedding deterministic event-driven logic directly into adventures. By authoring lightweight Python-style scripts, world builders and the AI World-Builder can craft complex interactive puzzles, reactive traps, dynamic NPC movements, and custom victory or defeat conditions that seamlessly interface with TaleWeaver's generative game master.

---

## Table of Contents
1. [Overview & Architecture](#overview--architecture)
2. [Sandbox Security & Limits](#sandbox-security--limits)
3. [Event Triggers & Lifecycle](#event-triggers--lifecycle)
4. [The `tw` Scripting API](#the-tw-scripting-api)
   - [tw.player](#twplayer)
   - [tw.scene](#twscene)
   - [tw.exits](#twexits)
   - [tw.npcs](#twnpcs)
   - [tw.objects](#twobjects)
   - [tw.vars](#twvars-persistent-state)
   - [tw.story](#twstory)
   - [tw.memories](#twmemories)
   - [tw.game](#twgame)
   - [tw.quests](#twquests)
   - [tw.awards](#twawards)
   - [tw.dice](#twdice)
5. [Practical Examples](#practical-examples)
   - [Example 1: Trapped Ancient Chest](#example-1-trapped-ancient-chest)
   - [Example 2: Gatekeeper Guard Blocking Passage](#example-2-gatekeeper-guard-blocking-passage)
   - [Example 3: Three-Lever Puzzle with Persistent State](#example-3-three-lever-puzzle-with-persistent-state)
   - [Example 4: Boss Encounter & Victory Condition](#example-4-boss-encounter--victory-condition)
   - [Example 5: Turn-Based Survival Countdown](#example-5-turn-based-survival-countdown)
6. [Authoring in the World-Editor](#authoring-in-the-world-editor)

---

## Overview & Architecture

While TaleWeaver's generative LLM master creates rich, adaptive prose and roleplay, certain game mechanics (such as combination locks, physical traps, locked gates, and badge criteria) require **deterministic, tamper-proof execution**.

```
                           +------------------------+
                           |     Player Action      |
                           +-----------+------------+
                                       |
                                       v
                           [on_turn_start scripts]
                                       |
                                       v
         +-----------------------------------------------------------+
         |                     TaleWeaver Turn                       |
         |  - Scene transition  --> [on_enter_scene scripts]         |
         |  - Entity action     --> [on_interact scripts]            |
         |  - Rule checks, combat, & LLM narration                  |
         +-----------------------------+-----------------------------+
                                       |
                                       v
                            [on_turn_end scripts]
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
- **No System Calls or Imports**: Statements like `import`, `from ... import`, `open()`, `eval()`, or `exec()` are rejected at parse time.
- **No Private or Dunder Attributes**: Accessing attributes starting with an underscore (such as `__class__`, `__subclasses__`, `__globals__`, or `__dict__`) is strictly forbidden.
- **Instruction Budget**: Each script execution is capped at **10,000 steps** (`ScriptTimeoutError`), preventing infinite loops and CPU exhaustion.
- **Memory Multiplication Protections**: Multiplying lists or strings by large factors (e.g. `[0] * 1_000_000`) is guarded against to prevent denial-of-service memory allocations.
- **Safe Builtins**: Available built-ins are restricted to `abs`, `all`, `any`, `bool`, `dict`, `float`, `int`, `len`, `list`, `max`, `min`, `range`, `round`, `str`, `sum`, `tuple`.

---

## Event Triggers & Lifecycle

Scripts declare a trigger event and an optional target entity or scene.

| Trigger | When it Executes | Target Field Usage |
| :--- | :--- | :--- |
| `on_turn_start` | Immediately when player submits an input, before LLM turn generation. | Global (`*` or empty). |
| `on_enter_scene` | When the player enters a new scene. | Specific `scene_id` or empty for any scene. |
| `on_interact` | When the player examines, attacks, talks to, or manipulates an entity. | Specific `entity_id` (NPC or object) or empty for all. |
| `on_turn_end` | After LLM narration and state changes are computed, before client response. | Global (`*` or empty). |

### Priority Execution
Scripts carry an integer `priority` (default: `100`). Scripts with **lower** priority numbers execute before scripts with higher numbers.

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
Inspects and repositions non-player characters:
- `tw.npcs.move(npc_id: str, target_scene_id: str)`: Teleports or moves an NPC into another scene.
- `tw.npcs.get(npc_id: str) -> dict | None`: Returns NPC attributes (name, current scene, HP).
- `tw.npcs.set_dialogue(npc_id: str, text: str)`: Overrides dialogue or hints provided by the NPC.

### `tw.objects`
Manages world objects and inventory items:
- `tw.objects.add_to_scene(item_id: str, scene_id: str)`: Spawns or moves an item into a scene.
- `tw.objects.add_to_player(item_id: str)`: Directly places an item into the avatar's inventory.
- `tw.objects.remove_from_player(item_id: str)`: Removes an item from the player's inventory.
- `tw.objects.hide(item_id: str)`: Hides an object in the scene until uncovered.
- `tw.objects.reveal(item_id: str)`: Reveals a previously hidden object.

### `tw.vars` (Persistent State)
A persistent key-value store saved into the session state under `__script_vars__`. State persists across turns, saves, and reloads:
- `tw.vars.get(key: str, default: Any = None) -> Any`: Retrieves variable value.
- `tw.vars.set(key: str, value: Any)`: Stores a value (numbers, strings, booleans, lists, dicts).
- `tw.vars.has(key: str) -> bool`: Checks whether `key` exists.
- `tw.vars.delete(key: str)`: Deletes `key`.

### `tw.story`
Injects high-priority narrative notices into the chat stream:
- `tw.story.show_message(text: str)`: Emits an emphasized narrative story banner in the client dialogue stream.
- `tw.story.log(text: str)`: Appends an internal log message visible during debugging.

### `tw.memories`
Directly writes into the avatar's episodic memory bank:
- `tw.memories.add(memory_text: str)`: Injects a factual memory into the avatar context that the Game Master LLM references in subsequent turns.

### `tw.game`
Controls session outcome conditions:
- `tw.game.set_victory(message: str)`: Ends the adventure in victory and displays `message`.
- `tw.game.set_game_over(reason: str)`: Ends the adventure in defeat with `reason`.

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
    tw.game.set_victory("The realm is saved! The eternal darkness has been banished forever.")
else:
    tw.player.damage(25)
    tw.story.show_message("The Shadow Lord's aura lashes out in icy tendrils (-25 HP). You need a source of holy light!")
```

---

### Example 5: Turn-Based Survival Countdown
Trigger: `on_turn_end`  
Target: `*`

```python
# Increment turn counter
turn = tw.vars.get("collapse_turn", 0) + 1
tw.vars.set("collapse_turn", turn)

remaining = 6 - turn
if remaining > 0:
    tw.story.show_message("The cavern tremors intensify! " + str(remaining) + " turn(s) before total collapse.")
else:
    tw.game.set_game_over("The cavern roof collapsed, burying all beneath tons of solid rock.")
```

---

## Authoring in the World-Editor

You can manage all scripts visually inside TaleWeaver:

1. Navigate to the **Adventure Editor** for your adventure.
2. Select the **Scripts** tab from the navigation sidebar.
3. Click **New Script** to open the script authoring modal:
   - Enter a human-readable **Name** and unique **Script ID**.
   - Select the desired **Trigger** (`on_turn_start`, `on_enter_scene`, `on_interact`, `on_turn_end`).
   - Optionally pick a **Target** scene or entity using the autocomplete selector.
   - Adjust **Priority** (lower numbers execute first).
   - Use the **Insert Snippet** dropdown to paste starter code.
4. Click **Check Syntax** to verify Python syntax, AST safety, and trigger parameters before saving.
5. Click **Create Script** or **Save Changes** to commit the script into the adventure manifest.
