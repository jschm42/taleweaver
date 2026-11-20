# TaleWeaver v0.8.0-beta: Companions, Dynamic Worlds & Living NPCs

**TaleWeaver v0.8.0-beta** gives the protagonist company and makes the world around them larger and more alive. Companions travel, fight and carry items at the hero's side. Dynamic zones generate whole mini-adventures on the fly. NPCs remember the protagonist, talk to each other and pass on gossip. Falling at 0 HP can now mean waking up at a revival point instead of the end. The Play-Agent becomes a feature for players, and the editor and admin console move to a new, consistent Workbench design.

This release introduces **adventure format 1.4.0**. Format 1.3.1 adventures keep working unchanged.

---

## 🌟 Major Highlights

### 🤝 1. Companions & Party

The protagonist can now travel with a sidekick.

* **Joining the party**: NPCs get an optional `companion` block. Companions can start in the party, join through scripts (`tw.party.recruit`), or be recruited by the player with the **Recruit** action (`/recruit`), either instantly or by handing over a specific item. Recruitable NPCs glow softly and carry an "Ally?" tag.
* **Following**: the active companion follows the protagonist on every scene change. Exits and chapters can keep companions out (`companions_allowed: false`).
* **Orders**: "Stay here" / "Follow me" from the companion's card, or typed in any language. The Game Master knows where the companion is and whether it follows.
* **Inventory & equipment**: a companion page in the hero dialog shows its stats and items. Hand items over and take them back, equip humanoid and being companions with weapons and armor, and switch their combat abilities on or off.
* **Combat**: the companion fights at the protagonist's side with its own initiative turn, following its tactics (offensive, balanced, defensive, support). It is downed, not killed, at 0 HP and recovers after the fight. The new **Mark** action focuses it on one enemy, and the new `ally` effect target lets heals reach the party partner.
* **Quest items**: items marked `quest_item` can never be given away by the player, and the Game Master cannot remove them. Only scripts move them. They show with a gold frame.
* **Scripting**: the `tw.party` API recruits, dismisses and steers companions.

### 🌀 2. Dynamic Scenes & Zones

Adventures are no longer limited to their authored scene graph.

* **Dynamic exits** generate new scenes with NPCs, items, containers and switches when the player walks through them. Base adventures stay unchanged; everything lives in the session.
* **Clusters as mini-adventures**: an exit's instructions become the premise of a small adventure. A cluster architect plans the story arc, antagonist, key item and climax, and gives every room its own brief. Clusters reach up to depth 10 (11 rooms).
* **Pre-mapped dynamic scenes**: authors can place dynamic scenes on a fixed map; their content is generated on first entry.
* **Control for authors**: spawn probabilities and caps per NPC type, an "Abandoned / Silent Place" preset, peaceful or random danger, per-exit audio and model selection, instructions scoped to one or all rooms, and the `on_after_generated_script` trigger.
* **Presentation**: an NPC quote with a voice and signature bridges the generation time. Scene and item images render in the background.
* **Scripting**: `tw.scene.teleport_dynamic(...)` and `tw.generated_scene`.

### 🧠 3. Living NPCs

* **NPC memory**: NPCs with memory slots keep short facts about the protagonist across the adventure. Characters who never met the protagonist don't know their name.
* **World memories**: important events are kept and handed to the Game Master when they are relevant to the current place.
* **NPC conversations**: present NPCs start short talks among themselves, shaped by their relations. Topics can carry clues and trigger scripts when overheard. Gossip spreads what one NPC knows to its friends. **Listening mode** (ear button or `/listen on`) lets the player stay and overhear.
* **Speech by NPC type**: humanoid and being NPCs speak in plain sentences; animals and monsters only use sounds and body language.
* **Handovers in dialogue**: giving an item inside a sentence ("Here is your drink, Tina") now counts as a real handover in any language and fires the NPC's receive trigger.
* **Deterministic reveals**: hidden NPCs appear only through a guard expression or a script, never by the Game Master's judgement (see upgrade notes).

### 💫 4. Respawn Instead of Game Over

Adventures can opt in to reviving the protagonist at 0 HP (`game_over_rules.on_zero_hp: "respawn"`). Scenes can be revival points; the protagonist wakes up at the last one reached with a configurable share of their HP. Chapters can still make defeat final.

### 🤖 5. Play-Agent for Players

The Play-Agent is now a regular player feature.

* **Auto-Play** card in the action bar; the control panel wears the adventure skin, floats over the stage and can be minimized to a dock.
* **Instructions**: tell the agent what to do (`/instruct` or the chat input while it plays). It follows the quest log, knows the map of visited places and travels there on its own (`/travel`), and keeps notes in its own memory.
* Walkthrough help only for chapters the player unlocked with XP. Earned awards are saved.
* Own admin page under **AI models → Play-Agent**.

### 🎨 6. Workbench: New Editor & Admin Design

The admin console and the adventure editor are rebuilt on one design system with shared components.

* Grouped navigation, one save bar per page, and linkable pages (the open page and tab live in the URL).
* Characters and items get their own detail pages with previous / next navigation and **one save** for the whole form.
* Rebuilt pages: Overview, Chapters, Side quests, Awards, Time & pacing, character and protagonist tabs.
* The World-Builder moves into a drawer (**Ctrl+K**).
* Inhabitants are grouped by scene, companions are marked.

### 🎙️ 7. Voices & Story Feed

* **Browser Voice**: a free TTS provider that reads the story with the browser's built-in voices. No key and no server audio, ideal for testing.
* **Separate vault key** for OpenAI-compatible speech servers, so a local Piper or Kokoro server no longer receives the LLM gateway's key.
* The story feed follows the voice to the end, and the bubble being read lights up and pulses in every skin.

### ⚙️ 8. Model Selection Made Easier

* Every pass in **Admin → Intelligence** explains the minimum model class and what breaks with a too-weak model. Full guide: [docs/model-selection.md](docs/model-selection.md).
* **Test capabilities** runs small fixed scenarios per pass (schema, handovers, exact IDs, secret lock codes, language) and rates the speed as fast, ok or slow.
* Tests show which OpenRouter provider answered and warn when a pinned provider was not used.
* The setup wizard has a Base-URL field for OpenAI-compatible endpoints.

### 🗺️ 9. Format 1.4.0 & Entity Bundles

* Adventure format **1.4.0** adds dynamic scenes and zones, item visuals, companions and respawning. 1.3.1 manifests import unchanged.
* `.twe` entity bundles carry the manifest spec version. Bundles newer than the engine are rejected instead of silently losing fields.
* The debug inspector downloads all session images as a ZIP and exports single NPCs or items as `.twe`.

---

## 🐞 Notable Fixes

* **Security**: the debug image ZIP and `.twe` export only pack real image files inside the data folder. Before, a crafted image URL could pull other files from the data folder, including the database.
* Leaving a fight scene ends an open loot phase instead of blocking every later message.
* Responses that arrive after the player switched sessions are dropped, so no stray stat popups or old narration in the new session.
* Times like "16:30" are no longer shown as speaker names.
* Running sessions keep the adventure's chapter progression mode instead of falling back to "linear".
* Readables in dynamic rooms show real line breaks.
* The Play-Agent no longer loops on choice dialogs.

---

## ⚠️ Upgrade Notes

* **Hidden NPCs**: the natural-language `reveal_rule` of NPCs is kept but ignored. A hidden NPC appears only through its `reveal_guard_expression` or a script. Check adventures that relied on the Game Master revealing a hidden NPC.
* **Clock format**: the unused 24-hour and date switches in the admin game settings are removed. Players choose 12- or 24-hour display in their profile.
* **Play-Agent settings** moved from Intelligence ("Pass 4") to their own admin page. Existing settings are kept.
* **Database**: 5 new migrations (exit `companions_allowed` and `dynamic_zone`, scene `dynamic_zone` and `is_respawn_point`, adventure `npc_conversations`) plus 2 merge revisions. All new columns are nullable or have defaults; existing data is unchanged.
* **Development**: the tests are split into suites, and a pre-push hook runs the affected tests ([docs/testing.md](docs/testing.md)). With a manual setup, enable the hooks with `git config core.hooksPath .githooks`. CI now fails on failing tests.

---

## 📦 What's Changed / Commit Summary

* **Frontend**:
  * Workbench design system (`src/components/ui`, tokens) for admin, editor and setup; entity detail pages and one save model.
  * Companion card, companion page in the hero dialog, recruit dialog, Mark action and ally card in the combat arena.
  * Auto-Play panel and dock, listening mode button, browser voice provider, story feed that follows TTS.
  * Library portal with a "Continue your journey" row.
* **Backend**:
  * Party system (`engine/party/`), `tw.party`, companion combat and loadout, quest items.
  * Dynamic scene generation, cluster architect and materialization.
  * NPC memory, world memories and NPC conversations (`engine/conversations/`) with scripting APIs.
  * Respawn rules, deterministic NPC reveal guards, dialogue handovers.
  * Model capability probe, speed rating and OpenRouter route report.
* **Testing & Quality Assurance**:
  * 2,407 automated backend tests passing, organized in 14 suites.
  * 109 automated frontend tests passing.
  * Pre-push hook for affected tests; CI runs the full suite as a gate.

---

## 🚀 Getting Started with v0.8.0-beta

### Upgrading Backend & Database
```bash
# Pull latest code
git pull origin main

# Install dependencies with Poetry
poetry install

# Apply database migrations
poetry run alembic upgrade head

# Start backend server
poetry run taleweaver
```

### Upgrading Frontend
```bash
cd frontend
npm install
npm run build # or npm run dev
```
