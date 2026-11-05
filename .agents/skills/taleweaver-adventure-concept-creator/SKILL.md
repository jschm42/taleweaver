---
name: taleweaver-adventure-concept-creator
description: Generates TaleWeaver adventure concepts (Story Idea text for the World-Builder) with a gripping story, a planted twist and non-trivial puzzles that the engine can actually enforce. Writes them in the World-Builder blueprint syntax (World, Protagonist, Scene, Exit, NPC, Item, Switch, Sequence, Rule, Script, Sidequest, Award tags with fixed/hint/open keys) and knows the parser's and engine's limits.
---

# TaleWeaver Adventure Creator

Use this skill to write, brainstorm or refine the **Story Idea & Context** text that the user pastes into the World-Builder. The World-Builder (an LLM) turns it into a playable adventure. Your text has two jobs:

1. **Tell a story worth playing**: stakes, a memorable antagonist, escalation and a twist.
2. **Only ask for things the engine can enforce.** If a puzzle or a turning point depends on something the engine cannot check, it falls apart in play: the GM improvises, players skip it or get stuck.

Work in this order: premise → twist → chapter skeleton → puzzles → blueprint → design checklist → output.

---

## 1. How the World-Builder reads your text

The Story Idea is a **blueprint**. The backend parses it deterministically and checks it before any LLM call. The builder LLM then fills every gap, and finally every *fixed* value is written back over the LLM output. The full key reference is in `docs/world-builder-syntax.md`. Read it when you need a key that is not listed here.

### Block rules
- Text **before the first tag** is the premise: world, tone, stakes, twist plan and design rules. It goes into the prompt as is.
- `[Kind: ID] Name` starts a block, which runs until the next tag. Kinds: `World`, `Protagonist`, `Scene`, `Exit`, `NPC`, `Item` (shortcuts `Readable`, `Container`, `Switch`/`Mechanism`, `ContainerSwitch`, `Weapon`), `Sequence`, `Rule`, `Script`, `Sidequest`, `Award`, `Ability`.
- Inside a block, `key: value` lines set manifest fields. Every other line is free text: the entity description, or the walkthrough for a sequence. Unknown keys are free text too.
- **Value modes:**
  - `key: value` is **fixed**: guaranteed and re-applied after generation.
  - `key: ~value` is a **hint**.
  - `key: ?` or leaving the key out means the builder decides.
  - Names after a tag follow the same modes: `[Scene: X] ?` and `[NPC: X] ~Name`.
- `key: |` starts a multi-line value. The following lines, indented deeper than the key, belong to it. Use this for every script with more than one statement.
- **Markdown (`.md`) format is also supported:** Tags may be written with `#` prefixes (`## [Scene: ID] Name`) or as pure Markdown headings (`## World`, `## Protagonist: Name`, `## Scene: ID — Name`, `## Exit: A -> B — label`, `## Sequence: 1 — Title`, `### Rule: ID — condition`), keys may use bullets/bold/backticks (`- **in**: \`CELL\``), and scripts may use fenced ```` ```python ... ``` ```` code blocks (after `key:` or directly inside `Script`/`Rule` blocks). Organizational headings (`## Locations`), `---` dividers and `<!-- comments -->` are ignored.
- IDs are normalized to `UPPER_SNAKE_CASE`. Always give explicit IDs (`[NPC: TOBIN] Tobin`) so other blocks can reference them. Write `@ID` in free text to link entities; those references are checked too.

### Nesting
- `[Rule: ID] condition` always belongs to the **latest** `[Sequence]`, even if entity tags came in between.
- An **indented** `[Script: ID]` is a chapter script of the latest `[Sequence]`. A `[Script]` at the start of a line is global.
- `[Ability: ID] Name` belongs to the NPC or Protagonist block it follows.
- Indent nested blocks by two spaces.

### Key cheat sheet

| Block | Most useful keys |
| :--- | :--- |
| `[World]` | `language`, `image_style`/`style`, `tone`, `win`, `lose`, `win_guard`, `lose_guard`, `rules`, `intro`, `init_script` |
| `[Protagonist] Name` | `role`, `goal`, `hp`, `str`…`ac`, `inventory`, `weapon`, `armor` |
| `[Scene: ID] Name` | `decor`, `on_enter`, `on_enter_text`, `on_leave`, `helpers` (only `def`s and constants; callable from every script, e.g. the scene's dialog handlers) |
| `[Exit: A -> B] label` (name the passage, e.g. `an old rusty gate`, never the way like `To the lab`; without one the AI writes it) | `code`, `key_item`, `rule`, `guard`, `revealed` (target known from the start), `one_way` (`<->` forces two-way), `on_unlock`, `on_unlock_fail_text` |
| `[NPC: ID] Name` | `in`, `type`, `hp`, `str`…`cha`, `ac`, `main_attack` (`Sabre \| 1d8 \| melee \| str`; no weapon item needed, `weapon`/`armor` are deprecated), `hidden`, `reveal`, `inventory`, `attack` (`passive`/`on_sight`), `attack_when_holding`, `attack_guard`, `group` (combat group: members fight together), `assist` (`group`/`anyone`/`never`), `killable`, `on_defeat`, `on_meet`, `on_interact`, `on_receive_item` |
| `[Item: ID] Name` | `in`, `type`, `hidden`, `reveal`, `portable`, `locked` (take-locked on regular items: visible/inspectable in scene or container, cannot be taken until unlocked), `code`, `unlock_item`, `unlock_guard`, `contains`, `min_items`, `max_items`, `reveals`, `bonus` (`str+2`), `damage`, `cost`, weapons: `category` (melee/ranged/magic), `hit` (`str`), `hit_effects` (`target sta -1d4, self hp +2`), `text` (readable, ≤500 chars), `on_pickup`, `on_use`, `on_read`, `on_items_added`, `on_items_removed` |
| `[Recipe: ID] Name` | `combine` (`A + B`), `results` (crafted item IDs), `keep` (ingredients not consumed), `craft_guard`, `on_craft`, `on_craft_fail_text` |
| `[Switch: ID] Name` / `[ContainerSwitch: ID] Name` | `states` (IDs ≤15 chars, `A-Z 0-9 _ -`; optional in-game text ≤20 chars: `OFF=Dark, ON=Lights on`), `initial`, `disabled_states`, `status_text`, `transition: A -> B \| item: X \| code: 1 \| guard: … \| fail: … \| script: …`, `outcome: B -> flag: KEY; unlock_container: ID; unlock_item: ID`, `on_success` / `on_fail` (or `on_success_script` / `on_failure_script`), `portable: yes` (carried switch, e.g. a remote). `[ContainerSwitch: ID]` combines container (`contains`, `min_items`, `max_items`, `on_items_added`, `on_items_removed`, locks) and switch states in one appliance (microwave, dispenser, fuse box). |
| `[Sequence: N] Title` | `goal_item`, `goal_scene`, `defeat`, `guard`, `end`, `xp`, `on_start`, `on_end`, `helpers` (only `def`s and constants, e.g. the chapter's dialog handlers; callable from every script) |
| `[Rule: ID] condition` | `guard`, `script`, `text`, `max` |
| `[Script: ID] Name` | `trigger` (`on_init`, `on_enter_scene`, `on_interact`, `on_turn_start`, `on_turn_end`, …), `target`, `code` |
| `[Sidequest: ID] Title` | `goal`, `goal_item`, `guard`, `xp` |
| `[Award: KEY] Title` | `tier`, `requires`, `guard` |
| `[Talent: ID] Name` (inside the Protagonist) | `target` (`none`/`npc`/`item`/`any`), `cost` (`mana 10`), `uses`, `gm` (what the GM reveals/narrates), `locked`, `unlock_*`, `on_use` (`talent` dict in scope). Non-combat; the player types `use <talent>` / `cast <talent> on <target>` |
| `[Ability: ID] Name` | `kind`, `category`, `cost` (`mana 10`), `damage`, `locked`, `unlock_item`, `area` (`splash 1` / `all`, protagonist only), `save` (`dex`), `spare_passive` |

All `on_*` hooks take a script, and each has a matching `on_*_text` key for a fixed message. Scripts use only the sandboxed `tw` API: `tw.vars.get/set`, `tw.flags.get/set`, `tw.player.has_item/take_item/damage/heal` (`take_item(ID)` moves an existing world item into the inventory), `tw.objects.clone(ID)` / `destroy(ID)` / `hide(ID)` / `reveal(ID)` / `lock(ID)` / `unlock(ID)` / `move_item(ID, target)` / `contents(holder)`, `tw.switches.enable_state(ID, *states)` / `disable_state(ID, *states)` / `set_status_text(ID, text)` / `clear_status_text(ID)`, `tw.npcs.get(ID)`, `tw.npcs.hide(ID)` / `reveal(ID)` (take an NPC out of the story or bring it back), `tw.npcs.set_character(ID, text)`/`add_trait(ID, trait)`/`remove_trait(ID, trait)`/`set_goal(ID, text)` (changes how the GM plays the NPC for the rest of the game), `tw.npcs.say_directed(ID, direction)` (the GM words the NPC's line in the next narration), `tw.npcs.consume(ID, ITEM)` (the NPC uses a consumable it carries; its HP/Mana/Stamina effects apply to the NPC), `tw.objects.get(ID)`, `tw.exits.unlock('A', 'B')`/`lock(...)`, `tw.story.narrate(...)` (or `narrate_raw(...)` for verbatim text), `tw.story.direct(...)` (soft hint the GM works into its next narration, e.g. "Let BRAM sing a sailor song"), `tw.game.win()`/`game_over()`, `tw.quests.complete(ID)`, `tw.awards.grant(KEY)`, `tw.dialog`, `tw.llm.ask` / `tw.llm.ask_json`, `tw.json`. No imports, no dunder access.

### Script formatting & readability
Keep scripts clean and human-readable in both the blueprint and the Adventure Editor:
- **Multi-line over one-liners:** Whenever a script has more than one statement, write it as a multi-line block (`key: |` or a fenced ```` ```python ```` block) with one statement per line. Never chain statements with `;`.
- **Clean structure:** Use consistent 4-space indentation inside control flow (`if` / `elif` / `else`, `for`) and separate distinct logical phases (e.g. validation/guards, state & item mutations, narrative output) with a blank line in longer scripts.
- **Sparse, purposeful comments:** Add short `# ...` comments **sparingly** to explain *why* a non-obvious puzzle state, lock, or twist transition happens (e.g. `# Lock the lamp room until Ines is defeated`). Do not add noisy comments that merely repeat obvious function calls.

### Sequences
- Sequences are numbered 1..N in order of appearance. At most 15.
- Legacy prefixes still work: `Required Item:`, `Required Scene:`, `Defeat NPC:`, `End Condition:`. So do their short forms `Item:`, `Scene:`, `Condition:` and `Defeat:`. **Never start a prose line inside a sequence with those words.**
- Entity tags placed after a sequence are mentioned in its walkthrough ("Introduces ..."). So declare a chapter's scenes, NPCs and items right after its `[Sequence]` block.

### Validation and enforcement
- **Errors block generation:**
  - invalid script or guard syntax;
  - a wrong value type (`hp: lots`);
  - an unknown enum value;
  - duplicate IDs;
  - `[Rule]` before any sequence;
  - `[Script]` without `code`/`trigger`;
  - a malformed `[Exit: A -> B]`.
- **Warnings only:**
  - a referenced but undeclared ID (the builder is told to create it with exactly that ID);
  - more than 15 sequences;
  - a readable over 500 characters.
- **After generation:**
  - Fixed values are re-applied to every entity the builder created.
  - Missing scripts, rules, abilities, exits (when both scenes exist), sidequests and awards are re-created from the blueprint.
  - Missing **scenes, NPCs and items are not re-created**. Give every entity that matters a clear role so the builder creates it.

### When a chapter completes
- With hard rules (`goal_item`, `goal_scene`, `defeat`, `guard`), the chapter completes **as soon as all of them are true**, deterministically. The `end` condition is then only flavour.
- Without hard rules, the GM decides when the `end` condition has happened. That is fine for social or story beats, but less reliable.
- **Pitfall:** a hard rule that is already true when the chapter begins completes it instantly. Pick items that only become obtainable in this chapter, and scenes the player has not reached yet.
- Chapters are strictly **linear**: one active chapter, no branches, no parallel arcs. Branching lives *inside* chapters (choices, soft rules, variables).

### How much to pin down
**Fix** what the design depends on:
- puzzle codes, key items, guards, switch transitions;
- chapter goals;
- the twist mechanics (attack triggers, locks, flags);
- scripts.

Leave descriptions, scene details, minor NPCs and stats as **hints or open**, so the builder can make the world rich. Over-specifying everything produces a stiff world. Under-specifying puzzles produces broken ones.

---

## 2. What the engine can and cannot do

**Can enforce deterministically (use these for every puzzle that matters):**

| Mechanic | Notes for your design |
| :--- | :--- |
| Locked **exits** | `code`, `key_item`, `rule` (narrative condition) or `guard`. A code is typed into a lock dialog, so it must be an exact string or number. |
| **CONTAINER** objects | Same locks as exits (`code`, `unlock_item`, `unlock_guard`); `contains` lists the items inside. |
| **READABLE** objects | Notes, books, scrolls, signs. `text:` holds at most **500 characters**. This is where clues live. |
| **SWITCH** objects | Levers, dials, lenses, valves: 2+ named states. Transitions can need a code, item or guard. Outcomes set story flags or unlock containers. To open an exit, guard it on the flag or call `tw.exits.unlock('A', 'B')` in the transition's script. |
| **CONSTRUCTABLE** recipes | A recipe is a meta item that never appears in the game: `[Recipe: ID]` with `combine: A + B`, `results: X` (one or more regular items of any type, hidden automatically) and optional `keep: A` (tools that are not consumed) and `craft_guard`. Players craft deterministically on the in-game Combine workbench (exact ingredient set) or via chat (GM-judged). |
| **Hidden** NPCs and objects | `hidden: yes` + `reveal:` (searching, an event). `reveal: script` = only a script brings it in (the GM never discovers it). Without `reveal:` searching the scene reveals it. Good for secret rooms and late reveals. |
| **Combat** | d20 turn-based fights, NPC abilities, protagonist area abilities (`area: all` + `save: dex` for a fireball), `attack: on_sight`, NPCs that attack once a condition holds (`attack_when_holding`, `attack_after_scene`, `attack_guard`), gangs that fight together (`group: bandits`; NPCs without a group stay bystanders, `assist: anyone` joins every fight in the scene). |
| **Scripts** (Event Scripts setting ON) | Hooks on enter/leave scene, pickup, read, equip, unlock, defeat, sequence start/end, every turn, and **interaction** with any object or NPC (also fixed objects). They can set variables, move NPCs, lock or unlock exits, hand over items, damage, win or lose. |
| **Sequence scripts** (scripts ON) | An indented `[Script]` under a chapter only runs while that chapter is active, e.g. "inspecting the bomb opens the wire dialog, but only in chapter 3" (`trigger: on_interact`, `target: BOMB`). |
| **Soft rules** (scripts ON) | `[Rule: ID] <condition the GM judges>` + `script:` the engine runs, with optional `guard:` and `max:`. This is how social solutions get real effects. |
| **Choice dialogs** (scripts ON) | A script shows up to 8 fixed answers (NPC conversation, riddle, confession, dilemma). Each answer runs deterministic code; answers can be hidden until a condition holds, and dialogs can chain. Describe them in prose (`Choice Dialog: ...`) unless you know the `tw.dialog` API. |
| **Save before a decision** (scripts ON) | `tw.save("label")` creates a save state the player can return to (Chronicles Timeline). Use it right before irreversible choices; describe it in prose (`Save point: before ...`). |
| **Dialogue trees** (scripts ON) | RPG-style NPC conversation (`tw.dialog.tree`): nodes with the NPC's line and up to 8 responses that lead to other nodes; responses can need a condition, disappear after one use, run a script or an action, and the end handler gets the visited path. Describe them in prose (`Dialogue Tree: ...`) with the topics and what each branch unlocks. |
| **Offerings / storing items** (scripts ON) | The player can put inventory items into an unlocked CONTAINER; its `on_items_added` hook sees `added_item_ids` (altar that wants a specific relic, scale that needs the right weight, mailbox). The hook may reject an offering by moving the items back to the player. |
| **Gifts / handing items to NPCs** (scripts ON) | The player can give inventory items to an NPC in the scene (context menu **Give** or `give <item> to <npc>`); the NPC's `on_receive_item` hook sees `received_item_ids` (return a lost heirloom, bribe a guard, deliver a letter). The hook may hand items back with `tw.npcs.give_to_player`; the GM then narrates the NPC's reaction. |
| **Talents** | Non-combat protagonist powers (Mind Reading, Animal Whisperer, an absurd Gossip Attack) used with `use <talent> on <target>`. The `on_use` hook can set flags (`tw.flags.set`) and steer the GM (`tw.story.direct`), so a talent can be a real alternative solution to a puzzle. |
| **Cloned items** (scripts ON) | `tw.objects.clone(ID)` copies a (hidden) template item with a new ID: dispensers, vending machines, refilling wells, a shop with unlimited stock. |
| **Variables & flags** | Remember trust, lies told, evidence found, earlier choices, and use them later in guards. |
| **Win / loss** | `[World] win`/`lose` plus optional exact `win_guard`/`lose_guard`; scripts can trigger either directly. |

**Cannot do (never design around these):**
- Branching or alternative chapter orders, multiple separate storylines, chapter skipping.
- Real-time pressure (seconds or minutes). In-game time only advances on scene or chapter changes. Express urgency with turn counters in variables (`[Script] trigger: on_turn_end`) or story stakes instead.
- Interacting with **decorative objects** (`decor`, max 7 per scene). They cannot be taken, used or checked.
- Puzzles that need images, audio, maps drawn by the player, spatial or visual inspection, or exact free-text answers typed into chat (the GM judges chat; only lock dialogs and choice dialogs are exact).
- Switch outcomes that unlock an exit directly by ID. Use a flag + exit guard, or a script.
- Companions or party mechanics beyond an NPC following the player via scripts; inventory weight; economy or shops with prices.
- Clue text longer than 500 characters in one readable.

If **Event Scripts** are off in the generator settings, soft rules, scripts, choice dialogs and hooks are unavailable. Say in the premise which features the design relies on, and remind the user to enable scripts.

---

## 3. Puzzle design: challenging, fair, enforceable

### Banned (trivial or filler) puzzles
- Counting things in a room ("count the torches / pillars / candles", "multiply the statues by the windows").
- Codes written in plain text, or split into fragments that are simply concatenated ("first half: 45, second half: 89").
- "Find the key in the next room", "the NPC just gives you the code when asked".
- Riddles that are unrelated to the story (generic sphinx riddles with no link to the plot).
- Fetch quests without a decision ("bring me 3 herbs").

Put a line in the premise like **"Design rule: no counting puzzles, no plain-text or simply split codes"**. The builder's default prompts like to add counting puzzles to container locks. Fixing the `code` yourself prevents that.

### Good puzzle patterns (always tie them to the story)
1. **Cross-referencing evidence**: the answer only appears when two or more clues from different sources are combined. For example, a tide table + a captain's log entry give the date of the wreck, which is the strongbox code. Every clue is a `[Readable]` or NPC statement placed in a *different* scene.
2. **Reading people**: an NPC only helps when the player uses information found elsewhere (their secret, their debt, their dead brother). Implement it as a `[Rule]` with a `guard:` on the evidence (`tw.player.has_item('BROTHERS_LETTER')`) so lucky guesses do not count.
3. **Interrogation / confession dialog**: a choice dialog where the correct accusation needs the right evidence. Answer options that require evidence stay hidden until the player has it, wrong accusations cost trust or HP, and lies are remembered in a variable.
4. **Mechanism with meaning**: a `[Switch]` whose correct state follows from the lore, not from trial and error (the lighthouse lens must be WHITE because ships steer by white; the log shows it was RED on every wreck night). Gate the critical transition with a `guard` so brute-forcing a lever does not solve the chapter.
5. **Crafting from insight**: a CONSTRUCTABLE recipe whose ingredients have to be deduced (an antidote from the alchemist's notes + an ingredient only the villain uses).
6. **Moral dilemma with consequence**: a choice dialog whose answers set variables that change later chapters (who survives, who helps, which ending text you get), while every branch stays winnable.
7. **Reversal puzzle**: what the player was told is the solution is the trap; the twist reveals the real solution (see below).

Every puzzle needs:
- a **fair clue trail**: at least 2 hints, at least one of them a `[Readable]` or NPC line;
- a **deterministic check**: a lock code, key item, switch state, guard, dialog answer, or rule with a guard;
- **its solution written in the chapter's free text**, so it ends up in the walkthrough.

No puzzle may be solvable only by guessing, and none may block the main path without a way back (retry, alternative clue, NPC hint after failure).

---

## 4. Story requirements

- **Premise with stakes**: who the protagonist is, what they want, and what is lost if they fail, personally and not only for the world.
- **Antagonist with a reason**: their motive must make sense in hindsight.
- **A twist (mandatory)**: a reveal in the second half, with at least one full chapter left after it, that **reframes the goal**. It is not just a surprise fact: after the twist, the player wants or needs something different. Proven twist shapes: the client is the culprit; the "monster" is the victim; the protagonist caused the disaster; the artifact being sought is the threat; the ally has been steering you all along.
- **Plant the twist**: at least **two clues before the reveal** that make sense on a second look (a signature on a receipt, an item in the wrong place, an NPC line with a double meaning). Write in the premise where they are planted.
- **Make the twist mechanical**: the reveal must change the game, not only the text. Examples:
  - a trusted NPC becomes hostile (`attack_guard` on a flag);
  - a safe route gets locked (`on_start: tw.exits.lock(...)`) and a new one opens;
  - an item changes meaning (a script swaps it);
  - the win condition changes.
- **Escalation**: every chapter raises the pressure (new danger, a closing window, a personal loss).
- **A climax that uses what the player learned**: the final obstacle is solved with knowledge and items from earlier chapters, not with a new, unrelated puzzle.
- **An ending with consequences**: earlier choices (variables) colour the ending text; optionally also a bad ending (loss condition) and a bittersweet one.

---

## 5. Output format

Deliver one code block, ready to paste:

```text
<Title>

Premise: <world, protagonist, stakes, tone - 4-8 sentences>
Antagonist: <who, motive>
Twist: <the reveal, in which chapter, what it changes mechanically>
Twist clues: <clue 1 (chapter, where)>, <clue 2 (chapter, where)>
Engine features used: <e.g. soft rules, choice dialogs, switches - requires Event Scripts ON>
Design rule: no counting puzzles, no plain-text or simply split codes, every puzzle has a fair clue trail.

[World]
win: <narrative win condition>
lose: <narrative loss condition>

[Protagonist] <Name>
role: <role>

[Sidequest: ID] <Title>
<goal; add goal_item / guard if completion is exact>

[Award: KEY] <Title>
tier: <bronze|silver|gold|negative>
requires: <requirement>

[Sequence: 1] <Title>
<What happens and why it matters. The step-by-step solution of this chapter's puzzle(s), naming clues and @IDs.>
Choice Dialog: <who asks what> - options: <A> (<effect>), <B> (<effect>), <C, only if ...> (<effect>).
goal_item: <ITEM_ID>
end: <narrative completion>
  [Rule: ID] <condition the GM judges>
  guard: <evidence check>
  script: <deterministic effect>
  max: 1

[Scene: ID] <Name>
<atmosphere notes>

[NPC: ID] <Name>
in: <SCENE_ID>
<personality, secret, role in the plot>

[Readable: ID] <Name>
in: <SCENE_ID>
text: <clue, max 500 characters>

[Sequence: 2] ...
```

Order: the premise, then `[World]`, `[Protagonist]`, `[Sidequest]`, `[Award]`. Then for each chapter: the `[Sequence]` block, its `[Rule]` and indented `[Script]` blocks, then the entities it introduces.

Then add one short line recommending the builder mode:
- **Strict Adherence** when the chapter structure, twist placement and puzzle chain must stay exactly as written (the usual case for a designed twist).
- **Creative Expansion** when the AI may add intermediate chapters and side content.

---

## 6. Design checklist (check every item before answering)

- [ ] Every referenced ID (`goal_item`, `key_item`, `in`, `contains`, `@ID`, IDs inside scripts) is declared as a block with exactly that ID, in UPPER_SNAKE_CASE, or is intentionally left for the builder to create.
- [ ] No prose line inside a chapter starts with `Item:`, `Scene:`, `Condition:` or `Defeat:`.
- [ ] `[World]`, `[Protagonist]`, `[Sidequest]` and `[Award]` come before `[Sequence: 1]`; every `[Rule]` comes after its sequence.
- [ ] Every script and guard is valid Python for the `tw` sandbox; multi-line scripts use `key: |` with clean indentation, one statement per line, and sparse `#` comments where intent is not self-evident.
- [ ] Puzzle-critical values (codes, key items, guards, switch transitions) are fixed; flavour is a hint or left open.
- [ ] No hard rule is already true when its chapter begins.
- [ ] Each chapter has at least one real obstacle, and the whole adventure has at least 3 different puzzle patterns from §3; there are no banned puzzles.
- [ ] Every clue fits in 500 characters, sits in a `[Readable]` or NPC, and the solution is written in the chapter text.
- [ ] Nothing relies on decorative objects, real time, branching chapters, exact chat input or switch outcomes that unlock exits by ID.
- [ ] The twist is planted at least twice, revealed after the midpoint with at least one chapter left to play it out, and changes a mechanic or the goal.
- [ ] The climax uses knowledge and items from earlier chapters.
- [ ] Every choice-dialog branch and every failure keeps the adventure winnable (or is an intended game over).
- [ ] At most 15 chapters; chapter count matches the story (usually 4–7).

---

## 7. Example (condensed)

```text
The Salt Ledger

Premise: Marine insurance investigator Ada Krell arrives in the fog-bound harbor town of Saltreach, where four ships have sunk on the same reef in a year. Her firm will pay out a ruinous sum unless she proves sabotage before the cargo ship Margarethe docks tonight - with Ada's younger brother aboard as a deckhand. Tone: maritime noir, cold and tense.
Antagonist: Harbormaster Ines Varga, who hired Ada. She sells salvage from the wrecks to pay off the town's debts and believes she is saving Saltreach.
Twist: In Sequence 4 Ada realizes her client Ines is the wrecker. The goal flips from "find the saboteur" to "stop Ines and save the Margarethe". Ines turns hostile and locks the lamp room.
Twist clues: (1) Sequence 2: the salvage receipt is signed "I.V."; (2) Sequence 3: Ines's sea-green shawl lies in the lamp room she claims she never enters.
Engine features used: soft rules, choice dialogs, a switch, attack triggers - requires Event Scripts ON.
Design rule: no counting puzzles, no plain-text or simply split codes, every puzzle has a fair clue trail.

[World]
win: The lighthouse lens shines WHITE when the Margarethe arrives and Ines is stopped.
lose: Ada dies, or the Margarethe is wrecked.

[Protagonist] Ada Krell
role: Marine insurance investigator

[Award: HONEST_BROKER] Honest Broker
tier: gold
requires: Finish without ever lying to Ines.
guard: not tw.vars.get('lied_to_ines', False)

[Sequence: 1] The Drowned Harbor
Ada must get into the sealed customs house. Clerk @TOBIN refuses; his brother drowned in the second wreck. On the beach Ada finds the torn manifest naming Tobin's brother as crew. Showing it to Tobin and speaking about his brother makes him hand over the customs key.
goal_item: CUSTOMS_KEY
end: Tobin trusts Ada and hands over the customs key.
  [Rule: TOBIN_TRUST] Ada confronts Tobin with his brother's death on the manifest.
  guard: tw.player.has_item('WRECK_MANIFEST')
  script: tw.npcs.get('TOBIN').give_to_player('CUSTOMS_KEY')
  max: 1

[Scene: SALTREACH_QUAY] Saltreach Quay
Fog, gulls, a boarded-up customs house.

[Scene: WRECK_BEACH] Wreck Beach
Debris from the sunken ships.

[NPC: TOBIN] Tobin
in: SALTREACH_QUAY
inventory: CUSTOMS_KEY
Grieving clerk, bitter and honest.

[NPC: INES_VARGA] Ines Varga
in: SALTREACH_QUAY
hp: 60
attack_guard: tw.flags.get('INES_EXPOSED')
on_defeat: tw.flags.set('INES_STOPPED')
Warm, efficient harbormaster; hires Ada and asks to be kept informed.

[Item: WRECK_MANIFEST] Torn Manifest
in: WRECK_BEACH
Lists the drowned crew, including Tobin's brother.

[Item: CUSTOMS_KEY] Customs Key
type: KEY

[Sequence: 2] Ledgers of the Dead
The customs strongbox holds the salvage records. Its code is the date of the last wreck as day+month (2203). The tide table says the ships sank "on the first spring tide after the equinox"; the harbor log lists the spring tides 7 March, 22 March, 6 April. The first one after the 20 March equinox is 22 March. Inside lies the salvage receipt, signed only "I.V.".
goal_item: SALVAGE_RECEIPT
end: Ada recovers the salvage receipt.

[Scene: CUSTOMS_HOUSE] Customs House

[Exit: SALTREACH_QUAY -> CUSTOMS_HOUSE] the customs house door
key_item: CUSTOMS_KEY

[Readable: TIDE_TABLE] Tide Table
in: CUSTOMS_HOUSE
text: Every wreck this year: lost on the first spring tide after the equinox. The reef shows its teeth then.

[Readable: HARBOR_LOG] Harbor Log
in: CUSTOMS_HOUSE
text: Spring tides this season - 7 March, 22 March, 6 April.

[Container: CUSTOMS_STRONGBOX] Customs Strongbox
in: CUSTOMS_HOUSE
code: 2203
contains: SALVAGE_RECEIPT

[Item: SALVAGE_RECEIPT] Salvage Receipt
Huge sums paid "to the harbor fund", signed I.V.

[Sequence: 3] The Red Lamp
At the lighthouse the drunk keeper @BRAM is suspected. His logbook shows the lens set to RED on every wreck night, although ships steer by white. In the lamp room Ada finds Ines's shawl.
Choice Dialog: Bram asks why Ada is here - options: "Accuse him of the wrecks" (Bram shuts down, trust -1), "Show the salvage receipt" (only if Ada has SALVAGE_RECEIPT: Bram admits someone else sets the lens and gives LAMP_ROOM_KEY), "Offer him a drink" (Bram rambles; dialog repeats).
goal_item: INES_SHAWL
end: Ada learns someone else changes the lens and finds the shawl.

[Scene: LIGHTHOUSE_BASE] Lighthouse Base
[Scene: LAMP_ROOM] Lamp Room

[Exit: LIGHTHOUSE_BASE -> LAMP_ROOM] a narrow iron stair
key_item: LAMP_ROOM_KEY

[NPC: BRAM] Bram
in: LIGHTHOUSE_BASE
inventory: LAMP_ROOM_KEY
Drunk, frightened lighthouse keeper.

[Item: LAMP_ROOM_KEY] Lamp Room Key
type: KEY

[Readable: KEEPER_LOG] Keeper's Logbook
in: LIGHTHOUSE_BASE
text: Wreck nights, all of them: lens RED. Not by my hand. Ships steer by white.

[Switch: LAMP_LENS] Lamp Lens
in: LAMP_ROOM
states: WHITE, RED, DARK
initial: RED
transition: * -> WHITE | guard: tw.flags.get('INES_STOPPED') | fail: The mechanism is jammed with a wedge of driftwood.
outcome: WHITE -> flag: LENS_WHITE

[Item: INES_SHAWL] Sea-green Shawl
in: LAMP_ROOM
hidden: yes
reveal: Ada searches the lamp room.

[Sequence: 4] The Client
Twist. Ines arrives at the lighthouse. Every option of her dialog ends with Ines exposed and hostile; the lamp room is locked until she is defeated.
Choice Dialog with Ines: "Say nothing" (Ines sends Ada to the reef - costs HP), "Show the receipt and the shawl" (Ines confesses her motive), "Offer to split the salvage" (sets lied_to_ines). Each option sets the flag INES_EXPOSED.
on_start: |
  # Cut off the lamp room until Ines is defeated
  tw.exits.lock('LIGHTHOUSE_BASE', 'LAMP_ROOM')
  tw.npcs.get('INES_VARGA').move_to('LIGHTHOUSE_BASE')
defeat: INES_VARGA
end: Ines is stopped.

[Sequence: 5] The Margarethe
Ada must set the lens to WHITE before the ship arrives. The ending text depends on whether Ada lied to Ines and whether Tobin was told the truth.
on_start: tw.exits.unlock('LIGHTHOUSE_BASE', 'LAMP_ROOM')
guard: tw.flags.get('LENS_WHITE')
end: The lens shines white and the Margarethe passes the reef safely.
```

Recommended mode: **Strict Adherence**, because the twist placement and clue chain must stay exactly as designed.

## References

This skill ships with copies of the TaleWeaver docs it relies on. All paths are relative to this skill directory:

- `docs/world-builder-syntax.md`: full key reference for every blueprint tag. Use it for any key not covered above.
- `docs/world-builder-blueprint-manual.md`: workflow, tag overview and design advice for Story Idea blueprints.
- `docs/scripting_engine.md`: the `tw.*` scripting API used by `on_start`, `guard`, `Rule` and `Script` blocks. `docs/scripting-enginge.md` is an identical alias for the misspelled name.
- `docs/specs/adventure_format.md`: the adventure file format (`adventure.adv` / `.adz`) the World-Builder produces.

The copies, `package.json` and `manifest.json` are generated by `python scripts/bundle_skill.py` from the repo `docs/` folder. Do not edit them here; edit the repo docs and rebuild the bundle.
