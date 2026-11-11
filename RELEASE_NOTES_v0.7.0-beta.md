# TaleWeaver v0.7.0-beta: The Adventure Library, UI Themes & Tactical Combat Release

We are excited to announce the release of **TaleWeaver v0.7.0-beta**! This major milestone expands TaleWeaver into a connected, highly customizable adventure platform with an in-game adventure catalog browser, 12 immersive UI skins, turn-based tactical combat, multi-provider voice mapping, extensive Python scripting engine enhancements, and two flagship showcase adventures: the engine-spanning **Test-Lab** and the 90s LucasArts-style comedy adventure **Suburban Sabotage**.

---

## 🌟 Major Highlights

### 📚 1. Built-in Adventure Library & Catalog Browser

Finding and playing adventures in TaleWeaver no longer requires manually managing `.adz` files:

* **Direct Catalog Browser (`/library`)**: Browse community and official adventures served straight from [`jschm42/taleweaver-adventures`](https://github.com/jschm42/taleweaver-adventures).
* **One-Click Download & Verification**: View adventure covers, teasers, creator attributions, and file sizes. Download, verify, and register adventures in your local library with a single click.
* **Smart Update Tracking**: Installed adventures automatically display an **Update** badge when a newer version is available (either upstream or as a local file), matching adventures by their stable origin UUID while preserving all existing player sessions and saves.
* **Format Migration**: Automatically upgrades legacy manifest packs on import.

---

### 🎨 2. Atmospheric UI Themes & Dialog Skins (12 Distinct Visual Styles)

A story's atmosphere extends to the user interface itself. TaleWeaver now features 12 distinct game UI themes:

* **12 Built-in Skins**:
  * **Classic**: Traditional high-fantasy parchment and clean serif typography.
  * **Chronicle**: Editorial book layout with elegant chapter formatting.
  * **Noir**: High-contrast monochrome aesthetic with typewriter fonts and selective red accents.
  * **Terminal**: CRT phosphor scanlines, cyan telemetry, and monospace diagnostics for sci-fi adventures.
  * **Grimoire**: Arcane, mystical aesthetics with ornate rune borders.
  * **Eldritch**: Unsettling, atmospheric gloom with acid-green accents.
  * **Toon**: Vibrant, cel-shaded comic-book styling with punchy speech bubbles.
  * **Ancient**: Weathered papyrus and dark leather tones for historical or mythic settings.
  * **Starship**: Sleek space station HUD with holographic interfaces.
  * **Pixel**: Retro 8-bit / 16-bit RPG aesthetic with pixel typography.
  * **Thriller**: High-tension cinematic suspense styling.
  * **Sitcom**: Playful retro-television aesthetic.
* **Complete Theme Styling**: Each skin customizes speech bubble geometry, tab styling, dice faces, scene tinting, and animated NPC entrances.
* **Author & Player Control**: Authors can choose a skin and custom accent color in the editor with live preview, or leave it on **Auto** to match narrative tone keywords. Players can override the theme at any time in their in-game settings.
* **Accessibility Tested**: Full WCAG contrast compliance testing across all skin stylesheets.

---

### 🎙️ 3. Multi-Provider TTS Voice Mapping & ElevenLabs Integration

* **Native ElevenLabs Voice Engine**: Integrated ElevenLabs text-to-speech with a full catalog of expressive voices for characters and narrators.
* **Voice Provider Mapping (`voice_provider_map`)**: Mix and match speech providers across different characters and narration roles (e.g. ElevenLabs for key NPCs, OpenAI-compatible TTS for side characters, local models for fast narration).
* **Admin Voice Center**: Dedicated administration tools for previewing voices, configuring speech rate, and managing tone mapping.
* **In-Game Voice Tags & Synchronization**: Speech audio is dynamically synchronized with character stage portraits and dialogue feeds.

---

### ⚔️ 4. Turn-Based Tactical Combat Arena & Audio Effects

* **Tactical Combat Modal (`FightModal.vue` / `CombatArena.vue`)**: Full interactive arena for turn-based encounters featuring round counters, initiative queues, attack animations, and dynamic health bars.
* **Area-of-Effect & Tactical Abilities**: Support for AoE spells, status modifiers, and custom attack mechanics (`specs/combat-aoe-abilities.md`).
* **Combat Sound Effects Engine**: Dedicated combat SFX library providing visceral audio feedback for weapon hits, critical strikes, spell casts, parries, and victories.
* **Post-Battle Loot & Spoils**: Structured post-combat loot modals allowing players to collect equipment, quest items, and currency.

---

### ⚡ 5. Extensive Scripting Engine Enhancements

Adventures now enjoy a dramatically expanded, deterministic Python scripting runtime with deep system hooks:

* **Choice Dialogs & Branching Dialogue Trees (`tw.dialog` & `tw.dialog.tree`)**:
  * Present interactive modal choice dialogs (`tw.dialog.show()`) with customizable options, danger prompts, and callback handlers.
  * Author multi-branch NPC dialogue trees with condition-gated conversation branches, player question menus, and reactive story outcomes.
* **Time Engine & Clock-Driven Events (`tw.time`)**:
  * Full programmatic control over the in-game clock, custom minutes-per-tick scaling, and GM-time toggling.
  * Schedule real-time deadline triggers with `on_time_reached` (e.g. 30m, 1h, 1h45m, 2h) to drive tense countdowns and world state shifts.
* **Dynamic Media Synthesis (`tw.image` & `tw.audio`)**:
  * **In-Game Image Generation (`tw.image.generate`)**: Trigger on-the-fly image synthesis using fast or high-quality diffusion models, seamlessly rendering illustrated discoveries directly in the story feed.
  * **Dynamic Audio Synthesis (`tw.audio.generate`)**: Procedurally compose music tracks and ambient audio on the fly using Google Lyria or ComfyUI workflows, cross-faded between scenes.
* **Advanced Item & Container Mechanics**:
  * Ergonomic item relocation aliases: `tw.items.to_container(item_id, container_id)`, `to_player(item_id)`, and `to_scene(item_id, scene_id)`.
  * Support for hidden item dispensers, container insertion hooks (`on_items_added`), and multi-item crafting recipes.
* **Multi-State Switches & Mechanisms (`tw.switches`)**:
  * State-machine switches with configurable initial states, transition tables, and reactive trigger handlers.
* **Script-Level LLM Queries (`tw.llm` & `tw.json`)**:
  * Ask the LLM structured questions from within deterministic scripts to evaluate complex player prose or parse custom intents into structured JSON data.
* **Global Init Scripts & Scene Helpers**:
  * Define global reusable helper functions in `init_script` and scene-scoped functions in `helpers_script` accessible by all triggers.
  * Dynamic win and lose guard expressions (`completed_guard_expression`, `gameover_guard_expression`) evaluating custom persistent session variables (`tw.vars`).

---

### 🗺️ 6. Adventure Format Specification & Entity Bundles (`.adv` / `.adz` v1.3.1)

* **Formal Format Specification**: Complete documentation of `.adv` manifests and `.adz` archive bundles in [`docs/specs/adventure_format.md`](docs/specs/adventure_format.md).
* **Schema Extensions**: Support for shared feature namespaces, switch mechanics, and schema versioning.
* **Entity Bundles (`.twe`)**: Modular entity format allowing creators to export, share, and import individual NPCs, items, containers, and crafting recipes between adventures.
* **Stable Adventure Identifiers**: Upstream UUID tracking ensuring seamless library catalog updates without duplicating local templates.

---

### 🛠️ 7. Architecture, Security & Production Deployment

* **Docker & Reverse Proxy**: Turnkey Docker deployment script (`scripts/docker_setup.sh`) and production Nginx reverse proxy configuration.
* **Backend Health & Connectivity Monitoring**: `GET /api/health` probes with a non-intrusive frontend connectivity banner that alerts users during disconnections and automatically resumes state upon reconnection.
* **Poetry & CI Pipeline**: Project dependency management completely modernized with Poetry, automated pre-commit linting (Ruff), and skill bundle verification.

---

### 🎮 8. Showcase Adventures: Test-Lab & Suburban Sabotage

This release comes with two showcase adventure packs demonstrating the full power of TaleWeaver's new engine:

#### 🧪 Test-Lab
A dedicated interactive testing facility and benchmark arena built to exercise every subsystem of TaleWeaver in a single world:
* **11 Dedicated Subsystem Chambers**:
  * **`ART_LAB`**: Tests on-the-fly in-game image generation and narrative feed rendering.
  * **`COMBAT_LAB`**: Tests turn-based tactical combat, initiative rolls, status effects, and damage tracking.
  * **`GUILD_VAULT`**: Tests locked containers, passcodes, key-item unlocks, and loot distribution.
  * **`LOCKED_ROOM`**: Tests door locks, bidirectional exit rules, and softlock prevention.
  * **`RIDDLE_LAB`**: Tests modal choice dialogs, player prompts, and riddle evaluation.
  * **`SOCIAL_HALL`**: Tests living NPCs, multi-branch dialogue trees, mood shifts, and vocal-tag audio.
  * **`SWITCH_LAB`**: Tests multi-state switch mechanisms, lever sequences, and state persistence.
  * **`TELEPORT_LAB`**: Tests dynamic room redirection and scene transit overlays.
  * **`TIME_MACHINE_LAB`**: Tests in-game clock mechanics, relative time ticks, and time-triggered events.
  * **`WORKSHOP`**: Tests constructable multi-ingredient crafting recipes.

#### 🏠 Suburban Sabotage
A full-length comedy adventure inspired by classic 90s LucasArts games (Monkey Island, Day of the Tentacle):
* **The Story**: It is 15:30 on a chaotic Saturday afternoon at the Miller household. At 18:00 sharp (2 real in-game hours), Dad's wealthy, tyrannical mother Grandma Evelyn arrives for dinner inspection. If the house is not spotless and the casserole is not baking in Grandma's sacred heirloom Ming porcelain dish, she will evict the Millers and ship Grandpa Joe off to a cheap nursing home!
* **The Mission**: Ten-year-old Jack must lure Mom out of her locked office, recover Dad's golden wrench from a piranha tank, distract freeloading neighbor Kevin with Dad's "Sports Magazines", glue the shattered Ming dish back together, bake the casserole, and uncover the hilarious truth behind Grandpa Joe's sabotage to turn the tables on Grandma with her own prenup morality clause!
* **Showcase Mechanics**: Demonstrates clock-driven deadline events (`on_time_reached`), choice dialogs, crafting recipes, dynamic NPC room-patrols, and multi-variable win/lose guards.

---

## 📦 What's Changed / Commit Summary

* **Frontend**:
  * Added in-game Adventure Library catalog browser and download manager (`LibraryView`, catalog integration).
  * Added 12 customizable UI skins with WCAG contrast verification and editor previews.
  * Added `CombatArena` and `FightModal` components with turn progression, combat sound effects, and loot rewards.
  * Added ElevenLabs voice selector, narrator voice pickers, and multi-provider voice mapping interfaces.
  * Added frontend connectivity monitoring banner and health check composables.
* **Backend**:
  * Implemented Adventure Library catalog index fetching, caching, and download verification.
  * Implemented multi-provider TTS voice mapping (`voice_provider_map` schema & migration).
  * Implemented tactical combat engine, special attacks, and post-battle loot distribution.
  * Implemented extensive scripting engine extensions: `tw.dialog`, `tw.dialog.tree`, `tw.time`, `tw.llm`, `tw.json`, `tw.image`, and `tw.audio`.
  * Added item manager placement aliases (`to_container`, `to_player`, `to_scene`).
  * Implemented upstream adventure UUID resolution and stable storage identifiers.
  * Modernized dependency management with Poetry and added pre-commit linting hooks.
* **Testing & Quality Assurance**:
  * Over 2,100 automated backend tests passing.
  * 82 automated frontend tests passing (including WCAG contrast audits).

---

## 🚀 Getting Started with v0.7.0-beta

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
