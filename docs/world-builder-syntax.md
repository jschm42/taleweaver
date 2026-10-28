# World-Builder Blueprint Syntax

TaleWeaver's World-Builder reads structured tags in the **Story Idea & Context** field. With them you can pin down anything from the chapter outline to single NPC stats, triggers and scripts. **Every part is optional.** Whatever you leave out, the World-Builder fills in itself, so a blueprint can be one `[Sequence]` line or a nearly complete adventure.

## How it works

1. **Pre-flight check.** When you click *Generate*, the backend parses the blueprint and checks script syntax, guard expressions, IDs and value types. Errors (with line numbers) stop the generation before any LLM call is made. Warnings, such as a referenced ID that is not declared, do not.
2. **Generation.** The LLM receives your premise text plus the blueprint as structured JSON. It must create every declared entity with exactly the given ID.
3. **Enforcement.** After generation, every *fixed* value is written back over the LLM output. Scripts, soft rules, abilities, exits, sidequests and awards that the LLM dropped are re-created from the blueprint. Missing scenes, NPCs and items are logged as violations.

## General rules

| Syntax | Meaning |
| :--- | :--- |
| `[Kind: ID] Name` | Starts a block. The text after the tag is the name (`?` = let the AI name it, `~Name` = only a suggestion). |
| `key: value` | **Fixed** value, guaranteed to end up in the adventure. |
| `key: ~value` | **Hint**: passed to the AI as a suggestion. |
| `key: ?` | Explicitly left open for the AI (same as omitting the key). |
| `key: \|` | Multi-line value (scripts, long texts). The following, deeper indented lines belong to it. |
| `@ID` | Reference to another entity inside free text. It is checked like any other reference. |
| any other line | Free text: the entity's description or design notes for the AI. |

- Text **before the first tag** is the premise (world, tone, twist plan, design rules).
- **IDs** are normalized to `UPPER_SNAKE_CASE` (`old man` → `OLD_MAN`). `[Scene: 1] Damp Cell` gets the ID `DAMP_CELL`. You can also write the ID in brackets after the name: `[Scene: 1] Damp Cell (CELL)`.
- Keys are case-insensitive, and spaces or hyphens count as underscores (`Goal Item:` = `goal_item:`).
- Unknown keys are treated as free text, so a prose line like `Note: ...` is safe.
- Lists are comma-separated: `inventory: ROPE, LANTERN`.
- Booleans accept `yes/no`, `true/false`, `on/off`.
- Scripts use the sandboxed `tw` API (`tw.vars`, `tw.flags`, `tw.player`, `tw.npcs`, `tw.objects`, `tw.exits`, `tw.story`, `tw.game`, `tw.dialog`, ...). See the scripting reference in the editor.
- The Story Idea is limited to 20,000 characters.

## Tags and keys

### `[World]`
`language`, `plot`, `rules`, `intro`, `teaser`, `cover` (English image keywords), `win`, `lose` (narrative conditions), `win_guard`, `lose_guard` (exact expressions), `init_script` (script).

### `[Protagonist] Name`
`role`, `goal`, `character`, `appearance`, `hp`, `mana`, `stamina`, `str`/`dex`/`int`/`wis`/`cha`/`ac` (or the full stat names), `inventory` (item IDs), `weapon`, `offhand`, `armor` (item IDs), `on_hp_change`, `on_status_change` (+ `_text` variants).
Nested `[Ability: ID] Name` blocks define special actions (see below).

### `[Scene: ID] Name`
`decor` (up to 7 decorative objects, comma-separated), `on_enter`, `on_enter_text`, `on_leave`, `on_leave_text`.

### `[Exit: FROM -> TO] label`
Use `->` for an exit (the AI decides the direction rules) or `<->` to force a two-way passage.
`via`/`label`, `locked`, `lock` (description), `code`, `key_item`, `rule` (soft narrative condition), `guard` (expression), `bidirectional`, `one_way`, `on_unlock`, `on_unlock_fail`, `on_open`, `on_use` (+ `_text` variants).
Setting `code`, `key_item`, `rule` or `guard` implies `locked: yes`.

### `[NPC: ID] Name`
`in` (scene ID), `position`, `type` (HUMANOID, ANIMAL, MONSTER, BEING), `goal`, `character`, `appearance`, `notes`, `hp`, `mana`, `stamina`, `moves` (yes/no), `allowed_scenes`, `attackable`, `killable`, `hidden`, `reveal` (reveal condition), `inventory`, `weapon`, `armor`, `attack` (`passive` / `on_sight`), `attack_when_holding` (item), `attack_after_scene`, `attack_after_defeat`, `attack_guard`, `special_chance`, `on_defeat`, `on_meet` (player enters the NPC's scene), `on_interact` (+ `_text` variants).

### `[Item: ID] Name`
Shortcuts that also set the type: `[Readable: ...]`, `[Container: ...]`, `[Switch: ...]`/`[Mechanism: ...]`, `[Weapon: ...]`.
`in` (scene ID), `position`, `type` (CONSUMABLE, WEARABLE, STATIC, CONSTRUCTABLE, PICKABLE, WEAPON, TOOL, KEY, READABLE, CONTAINER, SWITCH), `appearance`, `slots`, `hidden`, `reveal`, `portable`, `code`, `unlock_item`, `unlock_rule`, `unlock_guard`, `contains` (item IDs), `combine` (ingredient IDs, `A + B`), `craft_guard`, `reveals` (item ID), `bonus` (`str+2, ac+1`), `heal`, `stamina`, `mana`, `damage` (dice, e.g. `1d8+2`), `cost` (`stamina 3` / `mana 5`), `text` (readable content, max 500 characters), `format` (DOCUMENT, SCROLL, BOOK, SIGN).
Hooks: `on_pickup`, `on_drop`, `on_equip`, `on_unequip`, `on_interact`/`on_use`, `on_unlock`, `on_unlock_fail`, `on_read`, `on_craft`, `on_craft_fail` (+ `_text` variants).

Switch keys:
- `states: OFF, ON` and `initial: OFF`
- `transition: OFF -> ON | item: FUSE | code: 12 | guard: <expr> | rule: <text> | fail: <msg> | success: <msg>` (repeatable; use `*` as the source state for "any")
- `outcome: ON -> flag: POWER_ON; unlock_container: FUSE_BOX` (repeatable). To unlock an exit, set a flag and give the exit `guard: tw.flags.get('POWER_ON')`, or call `tw.exits.unlock('FROM', 'TO')` in a script.

`text:` implies READABLE, `states:` implies SWITCH, and `combine:` implies CONSTRUCTABLE.

### `[Sequence: N] Title`
At most **15** sequences. They are numbered 1..N in the order they appear.
`goal_item`, `goal_scene`, `defeat` (hard completion rules), `guard` (completion expression), `end` (narrative end condition), `xp`, `walkthrough`, `on_start`, `on_end` (+ `_text` variants).
The free text becomes the chapter's description and walkthrough.
Legacy keys still work: `Required Item:`, `Required Scene:`, `Defeat NPC:`, `End Condition:`.

Nested blocks (indent them for readability; they always belong to the **latest** sequence):
- `[Rule: ID] condition`: a soft rule judged by the GM. Keys: `when` (condition), `guard`, `max` (trigger limit), `script`, `text`.
- `[Script: ID] Name` (indented): a chapter script that only runs while this sequence is active. Keys: `trigger`, `target`, `code`.

### `[Script: ID] Name`
A global script (written at the start of a line, not indented). `trigger` (`on_init`, `on_enter_scene`, `on_interact`, `on_turn_start`, `on_turn_end`, `on_logic_pass_done`, `on_narration_done`), `target` (entity ID), `code`.
Requires **Event Scripts** to be enabled in the generator settings.

### `[Sidequest: ID] Title`
`goal`, `impact`, `goal_item`, `goal_scene`, `defeat`, `guard`, `xp`.

### `[Award: KEY] Title`
`tier` (bronze, silver, gold, negative), `requires`, `goal_item`, `goal_scene`, `defeat`, `guard`.

### `[Ability: ID] Name` (inside an NPC or the Protagonist)
`kind` (ATTACK, HEAL, UTILITY), `category` (MAGIC, MELEE, RANGED, SOCIAL, OTHER), `cost` (`mana 10`), `stat`, `dc`, `damage` (`2d6` or `12`), `outcome`, `locked`, `unlock_item`, `unlock_scene`, `unlock_defeat`, `unlock_guard`, `unlock_text`, `on_success`, `on_fail` (+ `_text` variants).

## Builder modes

- **Strict Adherence**: the AI keeps the blueprint's structure and the sequence order, and only adds entities that are needed to make it playable.
- **Creative Expansion**: the blueprint is the backbone. The AI may add sequences, scenes, NPCs and side content around it.

Fixed values are enforced in **both** modes.

## Example

```text
A salvage technician wakes up in the brig of a derelict ship drifting toward a star.
Tone: claustrophobic sci-fi. Twist: the ship's AI locked her up to protect her.

[World]
win: The reactor is shut down and Mara reaches the escape pod.
lose_guard: tw.vars.get('radiation', 0) >= 100

[Protagonist] Mara Voss
role: Salvage technician
hp: ~80
inventory: MULTITOOL

[Scene: CELL] Brig Cell
Rusted, cramped, lit only by an emergency lamp.
on_enter_text: The hatch slams shut behind you.

[Scene: CORRIDOR] ?

[Exit: CELL -> CORRIDOR] a jammed bulkhead door
code: 4711
on_unlock: |
  tw.vars.set('alarm', True)
  tw.story.narrate("Klaxons start howling deep inside the ship.")

[Readable: LOGBOOK] Torn Logbook
in: CELL
text: Day 212 - the bulkhead code is the year the ship was launched, 47-11.

[NPC: WARDEN] Unit 7 Security Drone
in: CORRIDOR
type: MONSTER
hp: 40
attack_when_holding: CORE_KEY
  [Ability: TASER] Taser Burst
  kind: ATTACK
  damage: 2d6

[Switch: BREAKER] Breaker Panel
in: CORRIDOR
states: OFF, ON
transition: OFF -> ON | item: FUSE | fail: Sparks fly. Something is missing.
outcome: ON -> flag: POWER_ON

[Sequence: 1] Break Out
Mara has to get out of the cell. The logbook holds the door code.
goal_scene: CORRIDOR
xp: 150
  [Rule: TALK_DRONE] Mara convinces @WARDEN over the intercom to open the door.
  script: tw.exits.unlock('CELL', 'CORRIDOR')
  max: 1

[Sequence: 2] Into the Reactor
The AI fills in this chapter's scenes, puzzles and exits.
goal_item: CORE_KEY

[Script: RADIATION_TICK] Radiation rises
trigger: on_turn_end
code: |
  if tw.scene.id.startswith('REACTOR'):
      tw.vars.set('radiation', tw.vars.get('radiation', 0) + 10)
```

Here `CORE_KEY`, `FUSE` and `MULTITOOL` are referenced but not declared, so the World-Builder is told to create them with exactly these IDs.
