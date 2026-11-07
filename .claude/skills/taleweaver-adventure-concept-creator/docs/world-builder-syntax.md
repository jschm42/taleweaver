# World-Builder Blueprint Syntax

> New to blueprints? Start with the [Blueprint Manual](world-builder-blueprint-manual.md). This page is the complete reference.

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
| `key: \|` | Multi-line value (scripts, long texts). The following, deeper indented lines belong to it, up to the next tag line such as an indented `[Rule: ...]`. |
| `@ID` | Reference to another entity inside free text. It is checked like any other reference. |
| any other line | Free text: the entity's description or design notes for the AI. |

- Text **before the first tag** is the premise (world, tone, twist plan, design rules).
- **IDs** are normalized to `UPPER_SNAKE_CASE` (`old man` → `OLD_MAN`). `[Scene: 1] Damp Cell` gets the ID `DAMP_CELL`. You can also write the ID in brackets after the name: `[Scene: 1] Damp Cell (CELL)`.
- Keys are case-insensitive, and spaces or hyphens count as underscores (`Goal Item:` = `goal_item:`).
- Unknown keys are treated as free text, so a prose line like `Note: ...` is safe.
- Lists are comma-separated: `inventory: ROPE, LANTERN`.
- Booleans accept `yes/no`, `true/false`, `on/off`.
- Scripts use the sandboxed `tw` API (`tw.vars`, `tw.flags`, `tw.player`, `tw.npcs`, `tw.objects`, `tw.exits`, `tw.story`, `tw.game`, `tw.dialog`, ...). See the scripting reference in the editor.
- The Story Idea is limited to 50,000 characters.
- **Markdown (`.md`) format is fully supported** alongside bracketed tags (or mixed freely):
  - **Headings as tags:** `## [Scene: CELL] Brig Cell` or pure Markdown headings like `## World`, `## Protagonist: Mara Voss`, `## Scene: CELL — Brig Cell` (using `—`, `–`, `-` or `:` between ID and name), `## Exit: CELL -> CORRIDOR — a jammed door`, `## Sequence: 1 — Break Out`, `### Rule: BRIBE — The player convinces @WARDEN`.
  - **Child nesting via sub-headings:** A deeper Markdown heading under a sequence (`### Script: TIMER` under `## Sequence: 1`) attaches the script to that sequence just like two-space indentation does.
  - **Bullet & bold/code keys:** `- **in**: \`CORRIDOR\``, `- **hp**: \`~80\``, or `` - `code`: 4711 `` work identically to `in: CORRIDOR`.
  - **Fenced code blocks for scripts:** Write a fenced ```` ```python ... ``` ```` block right after `key:` (or `key: |`), or directly inside a `[Script]` / `## Script:` or `### Rule:` block without needing `code: |` indentation.
  - **Section headers & dividers:** A top-level `# Adventure Title` sets the blueprint title, and organizational headings (`## Locations`, `## Characters`), horizontal rules (`---`) and HTML comments (`<!-- ... -->`) are ignored so they never pollute entity descriptions. You can also import `.md` files directly via the **Load .md** button in the World-Builder UI.

## Tags and keys

### `[World]`
`language`, `image_style`/`style`/`visual_style` (custom image style instruction or catalog ID/name), `tone`/`narrative_tone` (custom narrative tone instruction or catalog ID/name), `plot`, `rules`, `intro`, `teaser`, `cover` (English image keywords), `music`/`theme_music` (English prompt for the main theme music), `win`, `lose` (narrative conditions), `win_guard`, `lose_guard` (exact expressions), `init_script` (script), `progression` (`linear` or `dynamic`, see [Sequence progression](#sequence-n-title)).

### `[Protagonist] Name`
`role`, `goal`, `character`, `appearance`, `hp`, `mana`, `stamina`, `str`/`dex`/`int`/`wis`/`cha`/`ac` (or the full stat names), `inventory` (item IDs), `weapon`, `offhand`, `armor` (item IDs), `on_hp_change`, `on_status_change` (+ `_text` variants).
Nested `[Ability: ID] Name` blocks define special actions and nested `[Talent: ID] Name` blocks define non-combat talents (see below).

### `[Scene: ID] Name`
`decor` (up to 7 decorative objects, comma-separated), `music` (English prompt for the scene's background music loop: genre, instruments, tempo, mood; instrumental, no artist names), `on_enter`, `on_enter_text`, `on_leave`, `on_leave_text`, `helpers` (script: functions and constants every script can call, see [Scene Helpers](scripting_engine.md#scene-helpers-helpers_script)).

### `[Exit: FROM -> TO] label`
Use `->` for an exit (the AI decides the direction rules) or `<->` to force a two-way passage.
`via`/`label`, `locked`, `revealed` (yes = the target scene is known from the start), `lock` (description), `code`, `key_item`, `rule` (soft narrative condition), `guard` (expression), `bidirectional`, `one_way`, `on_unlock`, `on_unlock_fail`, `on_open`, `on_use` (+ `_text` variants).
Setting `code`, `key_item`, `rule` or `guard` implies `locked: yes`.

Every exit has a label. Give it in the tag (`[Exit: HALL <-> CRYPT] a heavy oak door`), or leave it out and the AI writes one. The exit tile shows the label on both sides of a two-way exit, with `→ Target scene` below it only once the player has visited that scene; unexplored targets are not named on the tile. With `revealed: yes` the target counts as known from the start: the tile shows its image and `→ Target scene`, and the map shows the scene, before the player has been there (a signposted door, a gate with a view). Only locked exits carry a badge on the tile. Hovering a tile opens a popup with the label, the target's image and where the exit leads, once that is known.

Write the label as the passage itself, not as the way: `an old rusty gate`, `a narrow spiral staircase`, not `Way to the Combat Lab` or `Back to the hall`. A two-way exit shows the same label in both scenes, and the game already adds the target. The World-Builder AI follows the same rule for the labels it writes.

### `[NPC: ID] Name`
`in` (scene ID), `position`, `type` (HUMANOID, ANIMAL, MONSTER, BEING), `goal`, `character`, `appearance`, `notes`, `hp`, `mana`, `stamina`, `str`/`dex`/`int`/`wis`/`cha` (or the full stat names, 1-30, default 10), `ac` (armor class, default 10), `main_attack` (see below), `moves` (yes/no), `allowed_scenes`, `attackable`, `killable`, `hidden`, `reveal` (reveal condition; `script` = only scripts reveal it, see [Hidden entities](#hidden-entities-and-reveal)), `inventory`, `weapon`, `armor` (both **deprecated**, see below), `attack` (`passive` / `on_sight`), `attack_when_holding` (item), `attack_after_scene`, `attack_after_defeat`, `attack_guard`, `special_chance`, `group` (combat group), `assist` (`group` / `anyone` / `never`), `on_defeat`, `on_meet` (player enters the NPC's scene), `on_interact`, `on_receive_item` (the player gave the NPC items; `received_items` / `received_item_ids` in scope) (+ `_text` variants).

**Main attack.** `main_attack: Name | dice | category | stat | cost: <resource> <n> | effects: <effects>` configures the NPC's standard attack without any item. Only the name is required; the other parts may come in any order: damage dice (default `1d6`), `melee` / `ranged` / `magic` (default melee), the attack-roll stat (`str`, `dex`, `int`, ...; default `dex`), `cost: stamina 5` (default free) and `effects:` in the weapon `hit_effects` format.

```text
[NPC: GATE_GUARD] Gate Guard
in: GATE
str: 14
dex: 11
ac: 16
main_attack: Halberd | 1d10 | melee | str | cost: stamina 5
```

`weapon` and `armor` (equipped item IDs) are **deprecated**. They still work as a fallback (an NPC without `main_attack` fights with its weapon item, and armor bonuses still count), but the parser warns. Use `main_attack` and `ac` instead.

`killable: no` is the editor's **NPC can be damaged** switch turned off: the NPC never loses HP (scripts, Game Master, combat), cannot be defeated and cannot be fought.

**Combat groups.** When a fight starts, every attackable NPC in the scene is part of the encounter, but only some of them fight. `group: BANDITS` puts NPCs into a combat group (any tag; it is normalized to an upper-case ID): when one member fights, the other members in the same scene join right away, and attacking an idle member later pulls its whole group in. `assist` sets when an NPC joins a fight it was not attacked in:

| `assist` | Joins when |
|---|---|
| `group` | a member of its group fights (default for NPCs with a `group`) |
| `anyone` | any fight starts in its scene (guard dog, berserker) |
| `never` | never; it only fights when the protagonist attacks it directly (default for NPCs without a `group`) |

NPCs that do not fight are **bystanders**: the battle dialog lists them in a collapsed *Bystanders* section, away from the enemy cards. They take no turns, and the fight is won once every engaged enemy is down. `attack: on_sight` NPCs always fight, and their group joins them.

```text
[NPC: VAREK] Varek the Bandit Chief
in: ROAD
group: bandits
attack: on_sight

[NPC: GRIM] Grim
in: ROAD
group: bandits

[NPC: HOUND] Varek's Hound
in: ROAD
assist: anyone

[NPC: MIRA] Mira the Peddler
in: ROAD
```

Varek attacks on sight, and Grim and the hound join in. Mira stays a bystander until the player attacks her. In the World-Editor, every combat setting of an NPC (the **NPC can be damaged** switch, aggression, combat group, *Joins a fight*, attributes, main attack and special attacks) is in the **Combat** tab of the NPC dialog. Scripts can change both settings during a game (`tw.npcs.set_combat_group`, `tw.npcs.set_assist_mode`, see [scripting_engine.md](scripting_engine.md#twnpcs)).

#### Hidden entities and `reveal`

`hidden: yes` makes an NPC or item start invisible. How it becomes visible depends on `reveal`:

- `reveal: <condition>`: the Game Master reveals it when the condition is met (e.g. `reveal: The player searches the keeper's coat.`).
- no `reveal`: the default applies. The entity is revealed when the protagonist searches the scene (an NPC also when it starts speaking).
- `reveal: script`: **only scripts** reveal it (`tw.npcs.reveal`, `tw.objects.reveal`, `.set_hidden(False)`); for items also crafting and another item's `reveals`. The Game Master is not told about the entity, and searching, narration or the discovery check never reveal it. Use this for things a console, a dialog or a puzzle script must bring in.

### `[Item: ID] Name`
Shortcuts that also set the type: `[Readable: ...]`, `[Container: ...]`, `[Switch: ...]`/`[Mechanism: ...]`, `[ContainerSwitch: ...]`, `[Weapon: ...]`, `[Recipe: ...]` (CONSTRUCTABLE). `portable` defaults to `no` for STATIC items, switches and container-switches and to `yes` for everything else; a `portable: yes` switch (e.g. a remote) can be taken and flipped from the inventory.
`in` (scene ID), `position`, `type` (CONSUMABLE, WEARABLE, STATIC, CONSTRUCTABLE, PICKABLE, WEAPON, TOOL, KEY, READABLE, CONTAINER, SWITCH, CONTAINER_SWITCH), `appearance`, `slots`, `hidden`, `reveal` (reveal condition; `script` = only scripts reveal it, see [Hidden entities](#hidden-entities-and-reveal)), `portable`, `locked` (for containers: requires unlocking to open; for all other items: **take-locked**, visible and inspectable in the scene or inside a container, but cannot be picked up until unlocked by a script), `code`, `unlock_item`, `unlock_rule`, `unlock_guard`, `contains` (item IDs), `min_items` / `max_items` (container / container-switch item slot bounds, e.g. `min_items: 3` and `max_items: 3` for a fuse box requiring 3 components, or `max_items: 1` for a microwave), `combine` (recipe ingredient IDs, `A + B`), `results`/`result` (item IDs the recipe produces), `keep` (ingredient IDs that are not consumed), `craft_guard`, `reveals` (item ID), `bonus` (`str+2, ac+1`), `heal`, `stamina`, `mana`, `damage` (dice, e.g. `1d8+2`), `cost` (`stamina 3` / `mana 5`), `category` (weapons: MELEE, RANGED, MAGIC), `hit` (weapons: attack-roll stat, default `dex`), `hit_effects` (weapons: extra effects on a hit, e.g. `target sta -1d4, self hp +2`), `text` (readable content, max 500 characters), `format` (DOCUMENT, SCROLL, BOOK, SIGN).
Hooks: `on_pickup`, `on_drop`, `on_equip`, `on_unequip`, `on_interact`/`on_use`, `on_unlock`, `on_unlock_fail`, `on_items_added` (container / container-switch: the player put items in; `added_items` / `added_item_ids` in scope), `on_items_removed` (container / container-switch: the player took or dropped items out; `removed_items` / `removed_item_ids` in scope), `on_read`, `on_craft`, `on_craft_fail` (+ `_text` variants).

Switch keys:
- `states: OFF, ON`, `initial: OFF`, optional `disabled_states: ON` (states that start locked/disabled until enabled via `tw.switches.enable_state(...)`), and optional `status_text: The microwave needs some electrical power first.` (hint shown inside the switch/container-switch panel; can be updated or cleared via `obj.set_status_text(...)` / `obj.clear_status_text()`). Each state is an **ID** used by scripts, transitions and gates: 1-15 characters, letters, digits, `_` and `-` (stored upper-case, e.g. `HALF-OPEN`). Add an optional **in-game text** (max. 20 characters) with `=`: `states: OFF=Dark, HALF-OPEN=Half open, ON=Lights on`. States without a text show their ID to the player.
- `transition: OFF -> ON | item: FUSE | code: 12 | guard: <expr> | rule: <text> | fail: <msg> | success: <msg> | script: <code> | on_fail: <code>` (repeatable; use `*` as the source state for "any")
- `on_success` (or `on_success_script` / `on_switch`) and `on_fail` (or `on_failure_script` / `on_switch_fail`): switch-level scripts executed whenever any transition on this switch succeeds or fails (`current_state` in scope).
- `outcome: ON -> flag: POWER_ON; unlock_container: FUSE_BOX; unlock_item: SODA_CAN` (repeatable; also supports `lock_item: ID`). To unlock an exit, set a flag and give the exit `guard: tw.flags.get('POWER_ON')`, or call `tw.exits.unlock('FROM', 'TO')` in a script.

`text:` implies READABLE, `states:` + container keys (`contains` / `on_items_added`) implies CONTAINER_SWITCH, `states:` alone implies SWITCH, and `combine:` or `results:` implies CONSTRUCTABLE.

A **CONTAINER_SWITCH** (`[ContainerSwitch: ID] Name` or `type: CONTAINER_SWITCH`) combines a container and a switch in a single entity (e.g. a microwave, beverage dispenser, or fuse box). In-game it appears in Room Discoveries like a container, and its switch control is integrated directly inside the open container panel next to the stored items.

A CONSTRUCTABLE is a **recipe**: a meta item that never appears in the game and therefore gets no image. It needs at least 2 `combine` ingredients and at least 1 `results` item. Results are regular items of any type; they are hidden automatically and revealed when the recipe is crafted. All ingredients are consumed except those listed in `keep`. The `craft_guard` and the `on_craft` / `on_craft_fail` hooks belong to the recipe.

### `[Sequence: N] Title`
At most **15** sequences. They are numbered 1..N in the order they appear.
`goal_item`, `goal_scene`, `defeat` (hard completion rules), `guard` (completion expression), `end` (narrative end condition), `xp`, `walkthrough`, `activation` (scene ID; aliases `activation_scene`, `start_in`: entering this scene starts the sequence if it is not completed yet), `on_start`, `on_end` (+ `_text` variants), `helpers` (script: the chapter's functions and constants, see [Sequence Helpers](scripting_engine.md#sequence-helpers)).
The free text becomes the chapter's description and walkthrough.

**Sequence progression** is set with `progression:` in `[World]`:
- `linear` (default): completing a sequence starts the next one by number.
- `dynamic`: for hubs and open investigations. Completing a sequence only ends it; the next one starts when the protagonist enters its `activation` scene or when a script calls `tw.sequences.start('SEQ_ID')`. Give every sequence after the first an `activation` scene or a starting script.

In both modes, finishing the last sequence does not win the adventure; use `win` / `win_guard` or `tw.game.win()`.

```text
[World]
progression: dynamic

[Sequence: 1] The Archive
activation: ARCHIVE
goal_item: LEDGER
```
Legacy keys still work: `Required Item:`, `Required Scene:`, `Defeat NPC:`, `End Condition:`.

Nested blocks (indent them for readability; they always belong to the **latest** sequence):
- `[Rule: ID] condition`: a soft rule judged by the GM. Keys: `when` (condition), `guard`, `max` (trigger limit), `script`, `text`.
- `[Script: ID] Name` (indented): a chapter script that only runs while this sequence is active. Keys: `trigger`, `target`, `at` (for `on_time_reached`), `code`.

### `[Script: ID] Name`
A global script (written at the start of a line, not indented). `trigger` (`on_init`, `on_enter_scene`, `on_interact`, `on_turn_start`, `on_turn_end`, `on_logic_pass_done`, `on_narration_done`, `on_time_reached`), `target` (entity ID), `at` (only for `on_time_reached`: the elapsed in-game time, e.g. `90`, `2h 30m`, `1d`), `code`.

```
[Script: NIGHTFALL] Night falls
trigger: on_time_reached
at: 10h
code: tw.direct('Night has fallen: describe darkness and cold.')
```
Requires **Event Scripts** to be enabled in the generator settings.

### `[Sidequest: ID] Title`
`goal`, `impact`, `goal_item`, `goal_scene`, `defeat`, `guard`, `xp`.

### `[Award: KEY] Title`
`tier` (bronze, silver, gold, negative), `requires`, `goal_item`, `goal_scene`, `defeat`, `guard`.

Award keys of newly generated adventures are stored in upper case (`brass lever` becomes `BRASS_LEVER`). Granting matches keys case-insensitively, so `tw.awards.grant('brass_lever')` still finds `BRASS_LEVER`, and older adventures keep their stored keys.

### `[Ability: ID] Name` (inside an NPC or the Protagonist)
`kind` (ATTACK, HEAL, UTILITY), `category` (MAGIC, MELEE, RANGED, SOCIAL, OTHER), `cost` (`mana 10`), `stat`, `dc`, `damage` (`2d6` or `12`), `area` (`single`, `splash`, `splash 2`, `all`), `save` (`dex`, `wisdom`, ...), `spare_passive` (yes/no), `outcome`, `locked`, `unlock_item`, `unlock_scene`, `unlock_defeat`, `unlock_guard`, `unlock_text`, `on_success`, `on_fail` (+ `_text` variants).

**Area abilities** (protagonist only; NPC abilities always hit one target): `area: all` hits every
engaged enemy, `area: splash` (or `splash 2`) hits the target plus 1 (or 2) neighbours in the
encounter order, who take half. The cost is paid once and damage is rolled once. Without `save`,
one success roll is compared against each target's AC (or `dc`). With `save: dex`, every target
rolls a saving throw against `dc` (default 12) and takes half on a success. Bystanders of the
encounter (passive NPCs) are hit too and then join the fight, together with their combat group;
`spare_passive: yes` leaves them out.

```text
[Protagonist] Mara Voss
  [Ability: FIREBALL] Fireball
  kind: ATTACK
  category: MAGIC
  cost: mana 12
  dc: 13
  damage: 3d6
  area: all
  save: dex
```

### `[Talent: ID] Name` (inside the Protagonist)
Non-combat talents such as *Mind Reading* or an absurd *Gossip Attack*. The player uses them from the Talents menu, the right-click menu of an NPC or item, or by typing `use <talent>` / `cast <talent> on <target>`. The block's text is the description.
`target` (`none`, `npc`, `item`, `any`; default none), `cost` (`mana 10` / `stamina 5`), `uses` (uses per adventure; default unlimited), `gm` (instruction for the Game Master on what the talent reveals or causes), `locked`, `unlock_item`, `unlock_scene`, `unlock_defeat`, `unlock_guard`, `unlock_text`, `on_use` (script, `talent` dict in scope) (+ `on_use_text`).

```text
[Protagonist] Mira
  [Talent: MIND_READING] Mind Reading
  Hear what a person really thinks for a moment.
  target: npc
  cost: mana 10
  uses: 3
  gm: Reveal the target's true thoughts in one italic sentence.
  on_use: tw.vars.set('minds_read', tw.vars.get('minds_read', 0) + 1)
```

Put the readable name after the bracket (`[Talent: MIND_READING] Mind Reading`); players type that name.

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
ac: 14
main_attack: Stun Prod | 1d6 | melee | dex
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
