# TaleWeaver v0.6.0-beta: The Immersive In-Game & Scripting Engine Release

We are thrilled to announce the release of **TaleWeaver v0.6.0-beta**! This milestone represents one of our biggest updates yet, introducing a completely reimagined **comic-style immersive gameplay experience** and a secure, deterministic **Python event scripting engine**.

---

## 🌟 Major Highlights

### 🎭 1. Reimagined Immersive In-Game Experience

TaleWeaver's core gameplay UI has been rebuilt from the ground up for maximum visual richness, tactile interaction, and sensory immersion:

* **Comic-Style Turn Presentation (`ImmersiveStoryFeed` & `useComicTurns`)**:
  * Turns are dynamically formatted like an illustrated comic strip.
  * Gamemaster narrative exposition is cleanly partitioned from in-character dialogue.
  * Expressive speech bubbles and dialogue cards feature NPC portraits, speaker attribution, and dedicated action markers.
* **Point-and-Click Scene Hotspots (`ImmersiveSceneHotspots`)**:
  * Interactive hotspots are projected directly onto scene artwork.
  * Players can click directly on the artwork to inspect items, open containers, engage NPCs, or transition between connected scenes with smooth visual fade transitions (`SceneTransitionOverlay`).
* **Dynamic Character Stage (`ImmersiveCharacterStage`)**:
  * An interactive character staging area visualizes all NPCs present in the active scene.
  * Includes portrait badges, active status indicators, and integrated voice-tag playback that plays character dialogue lines.
* **Streamlined In-Game HUD**:
  * **In-Game Clock Widget**: Visualizes the flow of in-game time with configurable calendar systems, day/night pacing, and passage of time indicators.
  * **Contextual Action Bar (`ImmersiveActionBar`) & Input Bar (`ImmersiveInputBar`)**: Clean command submission with autocomplete, quick inventory triggers, speech-to-text push-to-talk, and quick action shortcuts.
  * **Dedicated In-Game Modals**: Rich full-screen and drawer dialogs for Character Sheet & Equipment, Map navigation, Switch/Container unlocks, and Tactical Combat.

---

### ⚡ 2. Sandboxed Deterministic Python Scripting Engine

Adventures now support deterministic, tamper-proof event logic alongside TaleWeaver's generative LLM master:

* **Pure AST Interpretation Sandbox (`backend/engine/scripting/sandbox.py`)**:
  * Zero use of unrestricted `eval()` or `exec()`.
  * Node-by-node AST validation strictly forbids system calls, filesystem access, imports, or private dunder attribute navigation (`__class__`, `__subclasses__`).
  * Enforced instruction budget (capped at 10,000 steps per script execution) and memory multiplication safeguards prevent infinite loops and denial-of-service allocations.
* **High-Level `tw` Scripting API (`backend/engine/scripting/context.py`)**:
  * **`tw.player`**: Manipulate HP, stamina, mana, status effects, and inventory items.
  * **`tw.scene`**: Inspect and mutate scene titles, descriptions, and dynamic entity placements.
  * **`tw.exits`**: Lock, unlock, hide, or reveal exits and change navigation destinations.
  * **`tw.npcs` & `tw.objects`**: Alter dialogue states, spawn or despawn items, and move NPCs dynamically across scenes.
  * **`tw.vars`**: Custom persistent session key-value storage for complex puzzle states (e.g. combination locks, countdown timers, faction reputation).
  * **`tw.game`**: Trigger programmatic victory or defeat states, or inject high-priority narrative prose (`tw.story.narrate()`).
* **Lifecycle Event Triggers**:
  * `on_turn_start`: Runs immediately when the player acts, before LLM turn generation.
  * `on_enter_scene`: Fires upon entering a specific scene or any scene.
  * `on_interact`: Triggers when examining, talking to, or using an item/NPC/switch.
  * `on_turn_end`: Executes after LLM mechanics and narrative generation to finalize state.
* **Adventure Editor Integration (`ScriptsTab.vue`)**:
  * A complete in-browser IDE tab for world builders to create, inspect, search, test, and prioritize event scripts.
  * Built-in template generator for common puzzle archetypes (traps, locked doors, lever puzzles, boss victory conditions).
* **AI World Generator Script Synthesis**:
  * TaleWeaver's world generator can automatically synthesize Python event scripts tailored to the generated adventure's lore and puzzle constraints (`scripts_generation_enabled`).
* **Adventure Import/Export Support**:
  * Scripts are fully serialized and restored within the adventure `.adv` / `.adz` world manifest.
* Read the full [Scripting Engine Guide](docs/guides/scripting_engine.md) for detailed syntax and practical examples.

---

### 🏗️ 3. Improved World-Editor & AI-Powered Validation

Building and curating adventures is now significantly more powerful, visual, and automated thanks to a comprehensive suite of authoring tools and validation intelligence:

* **Next-Gen Tabbed World-Editor**:
  * **Dedicated Workbenches**: Streamlined editing tabs for Scenes, Map Navigation, Inhabitants/NPCs, Items, Switches & Containers, Quests, Awards, Visuals, Tone, and Scripts.
  * **Bidirectional Exit & Scene Route Panels (`SceneRoutePanel.vue`, `ExitRoutePanel.vue`)**: Visually manage room connections, directional routes, lock descriptions, passcode requirements, and item prerequisites without manual coordination.
  * **Rich Entity & Container Modals (`EditEntityModal.vue`, `EditExitModal.vue`)**: Full CRUD support for complex object states, container locks, and multi-state interactive switches with state transition rules.
  * **Entity Reference Autocomplete (`EntityReferenceCombobox.vue`)**: Smart cross-referencing between scenes, quest targets, and inventory items to eliminate typos and dangling references.
* **Dual-Tier Validation Pipeline (`ValidationTab.vue`)**:
  * **Structural Graph Validation**: Real-time deterministic audits verifying graph connectivity, reachable scenes, valid exit endpoints, proper container contents, and crafting ingredient completeness.
  * **Semantic AI Validation**: LLM-powered deep story critique analyzing narrative cohesion, plot logic consistency, character motivation plausibility, and puzzle solvability.
* **One-Click AI Fix Suggestions (`AIFixSuggestionsModal.vue`)**:
  * The AI doesn't just point out errors—it actively proposes concrete, non-destructive fixes.
  * Authors can preview AI-generated corrections to broken exits, missing keys, inconsistent descriptions, or unreachable objectives and apply them immediately with a single click.
* **Persistent Validation Audits**:
  * Full validation runs, findings, and dismissal states are saved with timestamps, allowing creators to track world health across iterations.

---

### 🛠️ 4. Session Runtime Architecture, Checkpoints & Security

* **Session State Independence**:
  * Active sessions clone and enrich adventure blueprints into isolated session runtime states without modifying original templates.
  * Template asset directories are cloned to session-specific storage to ensure complete visual and state isolation.
* **Chronicles Milestones & Timeline Rollback**:
  * Automatic checkpoint milestones saved on key narrative events.
  * In-game Chronicles modal allows rolling back to earlier milestones if disaster strikes.
* **Security & Path Hardening**:
  * Strict path traversal mitigations applied across all API endpoints, media routes, and user profile upload handlers.
  * Sensitive data and credential scrubbing in logging.

---

## 📦 What's Changed / Commit Summary

* **Frontend**:
  * Added `ImmersiveGameView`, `ImmersiveStoryFeed`, `ImmersiveSceneHotspots`, `ImmersiveCharacterStage`, `ImmersiveHeader`, `ImmersiveActionBar`, and `ImmersiveInputBar`.
  * Added `useComicTurns` composable for comic-strip formatting and dialogue bubble generation.
  * Added `ScriptsTab.vue` editor component with syntax validation and script test runners.
  * Added `ValidationTab.vue` and `AIFixSuggestionsModal.vue` with one-click automated fix proposals.
  * Added `SceneRoutePanel.vue` and `ExitRoutePanel.vue` for visual bidirectional route configuration.
  * Added `AdventureWorldConstraints.vue` and `AdventureGameSettings.vue` script generation toggles.
* **Backend**:
  * Implemented AST-interpreted scripting engine sandbox (`backend/engine/scripting/sandbox.py`).
  * Implemented runtime scripting context (`backend/engine/scripting/context.py`) and runner (`backend/engine/scripting/runner.py`).
  * Implemented dual-tier world validation engine with structural graph checks and semantic LLM audit.
  * Integrated scripting execution hooks into `GameTurnManager` pipeline.
  * Added Alembic migration `469bc262d980_add_scripts_generation_enabled.py`.
  * Hardened exit CRUD endpoints and session exit resolution.
* **Testing & Quality Assurance**:
  * Added `test_script_sandbox.py` and `test_script_turn_integration.py`.
  * 100% test suite passing (553 passed tests).

---

## 🧠 Updated LLM Recommendations

For the optimal gameplay and authoring experience in `v0.6.0-beta`:

| Pipeline Step | Recommended Models | Description |
| :--- | :--- | :--- |
| **World Generation** | Any Flagship model like **Anthropic Opus 5.x**, **OpenAI 5.x**, **DeepSeek v4 Pro** | Complex world lore, scene graph connectivity, and script generation. |
| **Mechanics (Pass 1)** | **DeepSeek v4.1 Flash**, **GPT 6 Luna**, **Claude 4.5 Haiku** | High-speed, strict adherence to RPG rules, dice checks, and state modifications. |
| **Narrative (Pass 2)** | **DeepSeek-v4 Pro**, **GPT 6 Luna Pro**, **Claude 4.5 Sonnet** | Rich, atmospheric prose, character voice embodiment, and comic dialogue. |

> **Cost-Efficiency Tip**: While **Claude 4.5 Sonnet** and **Claude 4.5 Haiku** deliver top-tier narrative fidelity and instruction compliance, the **DeepSeek** (`v4.1 Flash`, `v4 Pro`) and **GPT 6 Luna** (`Luna`, `Luna Pro`) models are **drastically more cost-efficient**, making them ideal for high-volume, turn-heavy play sessions.

---

## 🚀 Getting Started with v0.6.0-beta

### Upgrading Backend & Database
```bash
# Pull latest code
git pull origin main

# Activate your virtual environment
.\venv\Scripts\activate   # Windows
source venv/bin/activate  # Linux/macOS

# Apply database migrations
alembic upgrade head
```

### Upgrading Frontend
```bash
cd frontend
npm install
npm run build # or npm run dev
```
