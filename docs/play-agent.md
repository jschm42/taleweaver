# Play-Agent (Auto-Play)

The Play-Agent lets the AI play the adventure as your hero. It is a regular player feature:
use it to watch the story unfold, to get past a part you are stuck on, or to let the adventure
play itself while you listen. Developers use the same agent, with extra debug tools, to test
adventures.

## Starting and stopping

* Pick the **Auto-Play** card in the action bar under the story (or type `/playagent`).
* The control panel opens at the top right of the stage. **Stop** (square button) or
  `/playagent off` gives you back control at any time.
* The agent stops by itself when the adventure is won or lost, and after three turns in a row
  in which it got stuck.
* While the agent plays, the chat input talks to the agent instead of the game: what you type
  becomes its instruction (see below). Other commands than `/instruct` and `/playagent` wait
  until you are back in control, so you and the agent never act at once.

## Telling the agent what to do

Type what the hero should do next into **Your instruction** in the panel (or the field of the
minimized dock) and press Enter, for example "Ask the innkeeper about the missing girl". The
same works in the chat with `/instruct <text>`, and while the agent plays also with plain chat
text.

The instruction has priority over the agent's own plans and the walkthrough. The agent works
on it, in character, until it reports it done (or impossible); then it decides on its own again.
Clear it earlier with the **x** button or `/instruct clear`. An instruction sent while a step is
running is queued and takes effect from the next step on.

## The control panel

The panel wears the adventure's skin and floats over the stage, so the story keeps its full width. At the top it shows the status, your instruction, the mode and Pause/Next; the remaining options are under **Settings** (collapsed by default, your browser remembers it). The hero's thoughts are listed at the bottom. On small screens the panel scrolls.

| Control | What it does |
| --- | --- |
| **Auto / Step** | Auto plays one turn after another. Step plays one turn each time you press **Next Step**. |
| **Pause / Resume** | Holds the Auto mode after the current turn. |
| **Delay between steps** | Extra pause before the next turn (Auto mode). |
| **Wait for speech to finish** | Waits until text-to-speech has read the narration (needs auto-speech). On by default. |
| **Play style** | Casual, Bureaucrat, Powerplayer, or a Custom description of how the agent should play. |
| **Dialogue** | How much the agent talks with characters: Taciturn (only what is needed), Normal, Talkative, or Full roleplay (long in-character conversations with everyone). |
| **Your instruction** | What the agent should do next (see above). |
| **Use walkthrough** | Lets the agent follow the walkthrough of the current chapter (see below). |
| **Thoughts** | The hero's inner voice: what the agent noticed and plans, plus the action it played. |

**Minimize** (dash button) shrinks the panel to a small dock at the bottom right. The dock shows
the status, the hero's latest thought, the instruction field, play style and dialogue level, and
the most important controls: Pause/Resume (or Next Step), Auto/Step, expand and stop. Picking
the Custom play style there opens the full panel when no description exists yet. Your browser remembers whether the panel was minimized.

## Walkthrough

The agent may only use a chapter's walkthrough once you unlocked that chapter under **Hints**
(`/walkthrough reveal`, costs XP). Until then **Use walkthrough** is disabled and the agent plays
like a normal player who explores, talks and experiments. When you unlock the chapter later, the
agent uses it from its next turn on. The agent never spends your XP and never unlocks anything
itself. In debug mode every chapter's walkthrough is free.

## What the agent can do

The agent plays in the role of the protagonist (biography, personality and goal from the hero
sheet). It speaks with `/say` in the hero's voice and has the same actions as you:

* moving through exits and unlocking doors or containers with keys and discovered codes,
* using the **known map**: it sees the places you visited, their exits (open or locked) and
  which exits lead somewhere unexplored, exactly like your map. With `/travel <place>` it walks
  back to a visited place over open exits, one exit per step (each step is a normal move, so
  your companion follows and scene events run; it needs no extra AI decisions on the way).
  The map shows each exit's travel time, and unlocked fast travel points are listed under
  FAST TRAVEL: `/fast_travel <place>` walks the whole route in one step, like the map's
  travel strip,
* inspecting, searching, reading, taking, dropping, using, combining, crafting and consuming items,
* opening containers, taking items out, putting items in, giving items to characters,
* setting switches and levers,
* using the hero's unlocked **talents** (`/talent <name> | <target>`),
* steering the **companion**: wait/follow, giving and taking items, equipping it, and turning
  its combat abilities on or off,
* answering choice dialogs and dialogue trees,
* **combat**: a tactician picks attacks and special abilities against the weakest enemy, heals
  the hero (or a badly wounded companion with an "ally" ability), marks its focus target for the
  companion, drinks potions, rests or runs, and collects the loot afterwards.

It knows its goals like you do: the current chapter and the quests of your quest log, and, in
adventures with a clock, the in-game time and how many minutes one action costs, so it works
towards the chapter goal instead of wandering until a deadline passes.

It sees only what you see: hidden objects and exits, lock codes and game master notes stay
hidden, and unexplored places stay unnamed on its map. A new instruction from you ends a trip.

## Commands

| Command | Effect |
| --- | --- |
| `/playagent` or `/playagent on` | Start the agent. |
| `/playagent off` | Stop the agent. |
| `/playagent casual\|bureaucrat\|powerplayer` | Start with this play style. |
| `/playagent personality custom <text>` | Custom play style. |
| `/playagent dialogue taciturn\|normal\|talkative\|roleplay` | How much the agent talks with characters. |
| `/instruct <text>` or `/playagent do <text>` | Tell the agent what to do next. |
| `/instruct clear` | Remove the instruction. |
| `/instruct` | Show the current instruction. |
| `/playagent step on\|off` | Step or Auto mode. |
| `/playagent walkthrough on\|off` | Allow walkthrough use (only for unlocked chapters). |
| `/playagent delay <seconds>` | Pause between two turns in Auto mode (0-300). |
| `/playagent tts on\|off` | Wait for text-to-speech before the next turn. |

## Debug tools

Only in debug mode (server setting `TALEWEAVER_DEBUG_ENABLED` or `/debug on`):

* **Monkey mode** (`/playagent monkey on`): the agent deliberately tries invalid and chaotic
  actions to stress-test the engine.
* Stuck turns are written to `AGENTS.md` in the session folder; `/playagent off` links to it.
* Agent problems are reported with their technical details in the chat.

Defaults for new sessions (play style, walkthrough, step mode, monkey mode) and the agent's
model are set by the admin on the admin page **AI models → Play-Agent**.
