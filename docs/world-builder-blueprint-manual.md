# World-Builder Blueprint Manual

This manual shows you how to steer TaleWeaver's World-Builder with a **blueprint**: structured tags in the **Story Idea & Context** field. You can pin down anything from the chapter outline to a single door code or event script. Anything you leave out, the World-Builder invents itself.

It starts small and adds one layer at a time, then gives ready-to-use recipes for common puzzles. For the complete list of tags and keys, see the [Blueprint Syntax Reference](world-builder-syntax.md). For the `tw` script API, see the [Scripting Engine](scripting_engine.md).

---

## 1. When to use a blueprint

| You want... | Write... |
| :--- | :--- |
| A surprise adventure from a mood or idea | Plain text only. No tags are needed. |
| A fixed chapter outline | A few `[Sequence]` tags. |
| Specific characters, places or items | Add `[NPC]`, `[Scene]` and `[Item]` tags. |
| Puzzles that are guaranteed to work | Fix the codes, key items, guards and switch states. |
| Custom game logic | Add `[Rule]` and `[Script]` blocks. |

Every layer is optional, and you can mix them: fix one puzzle in detail and leave the rest of the world to the AI.

---

## 2. Quick start

Paste this into **Story Idea & Context** and generate:

```text
A lighthouse keeper's apprentice discovers that the light has been sabotaged
on the night a storm brings a ship full of refugees to the reef.

[Sequence: 1] The Dark Tower
The lamp has gone out and the keeper is missing.

[Sequence: 2] The Saboteur
The apprentice finds out who put out the light, and why.

[Sequence: 3] Light the Lamp
The ship must be guided past the reef before dawn.
```

The text before the first tag is the **premise**. Each `[Sequence]` becomes one chapter, in this order. The World-Builder creates all the scenes, characters, items and puzzles.

---

## 3. Anatomy of a blueprint

```text
Premise text: world, tone, protagonist, twist ideas.        <- free text before the first tag

[NPC: KEEPER] Old Haldor                                     <- tag: kind, ID, name
in: LAMP_ROOM                                                <- key: value  (fixed)
hp: ~30                                                      <- key: ~value (hint)
hidden: ?                                                    <- key: ?      (AI decides)
Gruff, loyal, hides a gambling debt. Talks to @SMUGGLER.     <- free text, @ID reference
on_defeat: |                                                 <- multi-line script
  tw.flags.set('KEEPER_DOWN')
  tw.story.narrate("The old man slumps against the railing.")
```

- **Tag:** `[Kind: ID] Name`. The ID is how other blocks refer to this entity. IDs are converted to `UPPER_SNAKE_CASE`, so `old keeper` becomes `OLD_KEEPER`. If you write a number (`[NPC: 1] Old Haldor`), the ID is made from the name (`OLD_HALDOR`).
- **Keys:** `key: value` lines set exact properties. Keys are not case-sensitive, and spaces count as underscores (`Goal Item:` = `goal_item:`).
- **Free text:** every line that is not a known key. It becomes the entity's description, or the walkthrough for a sequence. The AI reads it as design intent.
- **`@ID`:** links to another entity inside free text. The link is checked like any other reference.
- **`key: |`:** a multi-line value. Every following line indented deeper than the key belongs to it. Use this for scripts.

---

## 4. The three control levels

| Write | Meaning | After generation |
| :--- | :--- | :--- |
| `code: 4711` | **Fixed.** This exact value. | Written back, even if the AI changed it. |
| `code: ~4711` | **Hint.** A suggestion. | The AI's value stays. |
| `code: ?` or no line at all | **Open.** The AI decides. | The AI's value stays. |

The same works for names: `[Scene: CELL] ?` lets the AI name the scene, and `[NPC: KEEPER] ~Haldor` only suggests the name.

**Rule of thumb:**
- **Fix** whatever a puzzle or the plot depends on: codes, key items, guards, switch states, chapter goals, scripts.
- **Hint or leave open** everything else: descriptions, minor characters, stats, decoration.

A world that is completely fixed feels stiff. A puzzle that is left open may come out broken.

---

## 5. Building in layers

The examples in this section extend the quick-start adventure step by step.

### Layer 1: chapters with real goals

Without a goal, the Game Master decides when a chapter is over. With a **hard goal**, the engine completes the chapter the moment the goal is met:

```text
[Sequence: 1] The Dark Tower
The lamp has gone out and the keeper is missing.
goal_scene: LAMP_ROOM
end: The apprentice reaches the lamp room.
xp: 100
```

Available goals:
- `goal_item`: the player holds the item.
- `goal_scene`: the player is in the scene.
- `defeat`: the NPC is defeated.
- `guard`: any expression is true, e.g. `tw.flags.get('LAMP_LIT')`.

All the goals you give must be met.

> **Pitfall:** a goal that is already true when the chapter starts completes it at once. Choose items that only become obtainable in this chapter, and scenes the player has not reached yet.

### Layer 2: the entities that matter

Declare the places, people and things your plot depends on. Put them right after the chapter where they first appear:

```text
[Scene: TOWER_BASE] Tower Base
Wet stone stairs, a smashed oil lantern.

[Scene: LAMP_ROOM] Lamp Room

[NPC: KEEPER] Old Haldor
in: LAMP_ROOM
hidden: yes
reveal: The apprentice searches behind the lamp housing.
Unconscious, a bruise on his temple.

[Item: OIL_CAN] Can of Lamp Oil
in: TOWER_BASE
```

### Layer 3: puzzles the engine can check

Lock things and fix the solution. The clues go in readables:

```text
[Exit: TOWER_BASE -> LAMP_ROOM] an iron trapdoor
code: 1857

[Readable: BUILDERS_PLAQUE] Builder's Plaque
in: TOWER_BASE
text: Raised against the sea in the year the great storm took the old light.

[Readable: HARBOR_CHRONICLE] Harbor Chronicle
in: TOWER_BASE
text: The great storm of 1857 swept the old wooden light into the bay.
```

Setting a `code`, `key_item`, `rule` or `guard` automatically makes the exit locked.

### Layer 4: rules and scripts

**Soft rules** turn a social solution into a real effect. The Game Master judges the condition; the engine runs the script:

```text
[Sequence: 2] The Saboteur
The apprentice finds out who put out the light, and why.
defeat: SMUGGLER
  [Rule: KEEPER_CONFESSES] The apprentice shows Haldor the smuggler's IOU.
  guard: tw.player.has_item('SMUGGLER_IOU')
  script: tw.flags.set('SMUGGLER_EXPOSED')
  text: Haldor stares at the paper and finally talks.
  max: 1
```

**Scripts** react to game events. A `[Script]` at the start of a line runs for the whole adventure. Indent it under a sequence to make it run only during that chapter:

```text
[Script: STORM_CLOCK] The storm closes in
trigger: on_turn_end
code: |
  turns = tw.vars.get('storm_turns', 0) + 1
  tw.vars.set('storm_turns', turns)
  if turns == 20:
      tw.story.narrate("Thunder. The refugee ship is almost at the reef.")
```

Scripts need the **Event Scripts Engine** switched on in the generator settings.

---

## 6. Recipes

Every recipe passes the pre-flight check without errors. Copy them and change the IDs. The recipes are excerpts, so they refer to scenes and items they don't declare (`CABIN`, `QUAY`, ...). Such references only cause a warning: declare those entities in your blueprint, or let the AI create them.

### Clue-based code lock on a container

```text
[Container: SEA_CHEST] Captain's Sea Chest
in: CABIN
code: 2203
contains: SALVAGE_RECEIPT
The lid is engraved with a tide symbol.

[Readable: TIDE_TABLE] Tide Table
in: CABIN
text: Ships were lost on the first spring tide after the equinox.

[Readable: HARBOR_LOG] Harbor Log
in: OFFICE
text: Spring tides this season: 7 March, 22 March, 6 April.
```

### An NPC hands over an item only with evidence

```text
[NPC: CLERK] Tobin the Clerk
in: QUAY
inventory: OFFICE_KEY
Grieving; his brother drowned in the second wreck.

[Sequence: 1] The Sealed Office
goal_item: OFFICE_KEY
  [Rule: CLERK_TRUST] The player confronts Tobin with his brother's name on the manifest.
  guard: tw.player.has_item('WRECK_MANIFEST')
  script: tw.npcs.get('CLERK').give_to_player('OFFICE_KEY')
  max: 1
```

### A lever that opens a door

Switch outcomes can set flags but cannot unlock exits directly, so the exit checks the flag:

```text
[Switch: FLOODGATE_LEVER] Floodgate Lever
in: PUMP_ROOM
states: DOWN=Lowered, UP=Raised
initial: DOWN
transition: DOWN -> UP | item: CRANK_HANDLE | fail: The socket is empty. A handle is missing.
outcome: UP -> flag: FLOODGATE_OPEN

[Exit: PUMP_ROOM -> SLUICE] the floodgate
guard: tw.flags.get('FLOODGATE_OPEN')
lock: The floodgate is shut. Water roars behind it.
```

`DOWN` and `UP` are the state IDs: transitions, outcomes and scripts use them (`tw.switch('FLOODGATE_LEVER').is_state('UP')`). The text after `=` is what the player sees ("Raised"). It is optional and at most 20 characters; without it the ID is shown. IDs may use letters, digits, `_` and `-`, up to 15 characters.

### A hidden item revealed by searching

```text
[Item: SMUGGLER_IOU] Crumpled IOU
in: LAMP_ROOM
hidden: yes
reveal: The player searches the keeper's coat.
```

### An ally who turns hostile after the twist

```text
[NPC: INES] Harbormaster Ines
in: QUAY
hp: 60
attack_guard: tw.flags.get('INES_EXPOSED')
on_defeat: tw.flags.set('INES_STOPPED')
```

Set the flag `INES_EXPOSED` in a rule, dialog or script when the twist happens. From that moment, Ines attacks.

### An NPC whose mood changes with the player's behavior

```text
[NPC: CLERK] Tobin the Clerk
in: QUAY
character: Grieving, polite, talkative

[Sequence: 1] The Sealed Office
  [Rule: CLERK_INSULTED] The player mocks Tobin's dead brother.
  script: tw.npcs.set_character('CLERK', 'Bitter and hostile toward the player; answers in one cold sentence')
  max: 1
```

The GM reads `character` on every turn, so from then on Tobin talks like a bitter man, in this game only. Use `tw.npcs.add_trait('CLERK', 'drunk')` / `remove_trait(...)` for a single trait, or `set_goal(...)` to change what the NPC wants. The change affects dialogue, not combat: pair it with `attack_guard` (see above) if the NPC should also fight.

### A route that locks when a chapter starts

```text
[Sequence: 4] The Client
on_start: tw.exits.lock('LIGHTHOUSE_BASE', 'LAMP_ROOM')
defeat: INES
```

### A crafted item

Crafting needs two parts: the item that gets made, and a **recipe** (item type `CONSTRUCTABLE`) that says what to combine. The recipe itself never appears in the game. The crafted item is a regular item of any type: a weapon, a readable, a switch, and so on.

```text
[Item: ANTIDOTE] Antidote
in: LAB
type: CONSUMABLE
heal: 30

[Recipe: ANTIDOTE_RECIPE] Antidote recipe
combine: NIGHTSHADE_ROOT + SILVER_SALT + MORTAR
keep: MORTAR
results: ANTIDOTE
craft_guard: tw.player.has_item('ALCHEMIST_NOTES')
on_craft_fail_text: You don't know the proportions yet.
```

- `[Recipe: ID]` is short for `[Item: ID]` with `type: CONSTRUCTABLE`. `combine:` and `results:` also imply that type.
- `combine:` lists **all** ingredients (at least 2).
- `results:` lists the item(s) the recipe produces (at least 1). Results start **hidden** automatically, so you don't need `hidden: yes`.
- `keep:` lists ingredients that are not used up, such as tools. Every other ingredient is consumed.
- Results usually have no `reveal:`, so crafting is the only way to get them. If a result also has a `reveal:` (or another item `reveals:` it), it can turn up that way too. A recipe can't be crafted again once all of its results are visible.

Players can craft in two ways:

- **Combine workbench (deterministic):** the *Combine* entry in the context menu of any inventory or scene item opens a workbench in the story feed. The player puts items on it and presses *Combine* (the `/craft A | B` command). It succeeds only when the chosen items are **exactly** the ingredients of a recipe that still has hidden results, and all of them are carried or in the current scene. A wrong or extra item fails without using anything up. No GM call is involved.
- **Chat (GM-judged):** the player describes the attempt (*"I mix the root with the salt"*) or uses `/combine`. The GM decides whether it is a combine attempt; the engine still enforces the ingredient rules.

Both ways run the `craft_guard` and the craft success and failure scripts. An `on_craft_success_text` replaces the default *"You combine … to create …!"* message, and an `on_craft_fail_text` replaces the default message when the `craft_guard` blocks. The result items go into the inventory when all ingredients were carried, otherwise they appear in the current scene. The workbench offers every item, so it never gives away which items are ingredients.

### A doom clock with a loss condition

```text
[World]
lose: The ship hits the reef.
lose_guard: tw.vars.get('storm_turns', 0) >= 30
```

Combine this with the `STORM_CLOCK` script from Layer 4.

### Sidequest and award

```text
[Sidequest: LOST_CAT] The Keeper's Cat
goal: Bring Whiskers back to the tower.
goal_item: WHISKERS
xp: 50

[Award: NO_BLOOD] Peacekeeper
tier: gold
requires: Finish the adventure without defeating anyone.
guard: not tw.vars.get('anyone_defeated', False)
```

---

## 7. Strict Adherence or Creative Expansion

Choose the builder mode below the Story Idea field:

- **Strict Adherence:** the AI keeps your chapters in their order and adds only what is needed to make the blueprint playable. Use it for designed twists and puzzle chains.
- **Creative Expansion:** your blueprint is the backbone. The AI may add chapters, scenes, characters and side content.

Fixed values are enforced in **both** modes.

---

## 8. Generating and checking

When you click **Generate**:

1. **Pre-flight check.** The blueprint is parsed and checked before any AI call.
   - **Errors** stop generation and are shown with their line number. Examples: invalid script syntax, `hp: lots`, an unknown `type`, a duplicate ID, a `[Rule]` before any sequence, a malformed `[Exit]`.
   - **Warnings** do not stop generation. Examples: a referenced but undeclared ID (the AI is told to create it with exactly that ID), more than 15 sequences, a readable over 500 characters.
2. **Generation.** The AI receives your premise and the blueprint and fills in everything that is open.
3. **Enforcement.** Every fixed value is written back. Scripts, rules, abilities, exits, sidequests and awards that the AI left out are re-created from your blueprint.

**Not re-created:** scenes, NPCs and items that the AI did not generate. Give every entity that matters a clear role in the free text, so that the AI creates it.

### Troubleshooting

| Problem | Cause and fix |
| :--- | :--- |
| "must be placed inside a sequence" | A `[Rule]` comes before the first `[Sequence]`. Move it below its chapter. |
| "Syntax error" in a script | Check the indentation under `key: \|`. The code must be indented deeper than the key. |
| A prose line turned into a chapter goal | Inside a sequence, a line starting with `Item:`, `Scene:`, `Condition:` or `Defeat:` is read as a goal (legacy syntax). Rephrase the line. |
| A chapter completes immediately | Its goal is already true at the start. See the pitfall in Layer 1. |
| A script does nothing in the game | The **Event Scripts Engine** is off in the generator settings. |
| The AI invented a different code | The code was written as a hint (`~`) or not at all. Fix it: `code: 4711`. |
| The Story Idea is rejected as too long | The field holds at most 20,000 characters. Leave descriptions open and fix only what matters. |

---

## 9. Tips

- **Start small.** Write the chapter outline first and generate. Then fix only the parts that came out wrong.
- **Give explicit IDs** to everything that is referenced. `[NPC: TOBIN] Tobin` is safer than `[NPC: 1] Tobin`.
- **One fact per readable.** Put clues in different scenes, so the player has to combine them.
- **Write the solution into the chapter text.** It becomes the Game Master's walkthrough and keeps hints consistent.
- **Let the AI write the atmosphere.** Your free text should say *what matters*; the AI is good at *how it looks*.
- **Use the adventure-creator skill.** Ask Claude to "create a TaleWeaver adventure about ...". The `taleweaver-adventure-creator` skill writes complete blueprints with a twist and enforceable puzzles in this syntax.
