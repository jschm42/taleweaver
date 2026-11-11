# TaleWeaver v0.7.0-beta: The Adventure Library, UI Themes & Tactical Combat Release

We are excited to announce the release of **TaleWeaver v0.7.0-beta**! This major milestone expands TaleWeaver into a connected, highly customizable adventure platform with an in-game adventure catalog browser, 12 immersive UI skins, turn-based tactical combat, multi-provider voice mapping, and dynamic in-game media synthesis.

---

## 🌟 Major Highlights

### 📚 1. Built-in Adventure Library & Catalog Browser

Finding and playing adventures in TaleWeaver no longer requires manually managing `.adz` files:

* **Direct Catalog Browser (`/library`)**: Browse community and official adventures served straight from [`jschm42/taleweaver-adventures`](https://github.com/jschm42/taleweaver-adventures).
* **One-Click Download & Verification**: View adventure covers, teasers, creator attributions, and sizes. Download, verify, and register adventures in your local library with a single click.
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

* **Tactical Combat Modal (`FightModal.vue` / `CombatArena.vue`)**: Full interactive arena for turn-based encounters featuring round counters, initiative queues, and dynamic health bars.
* **Area-of-Effect & Tactical Abilities**: Support for AoE spells, status modifiers, and custom attack mechanics (`specs/combat-aoe-abilities.md`).
* **Combat Sound Effects Engine**: Dedicated combat SFX library providing visceral audio feedback for weapon hits, critical strikes, spell casts, parries, and victories.
* **Post-Battle Loot & Spoils**: Structured post-combat loot modals allowing players to collect equipment, quest items, and currency.

---

### ⚡ 5. Scripting Engine & Creative Media Extensions

Adventures can now generate dynamic audio and visual assets during live gameplay:

* **In-Game Image Generation (`tw.image.generate`)**: Scripts can dynamically trigger on-the-fly image synthesis using fast or high-quality diffusion models, seamlessly displaying illustrated scenes and discoveries directly in the story feed.
* **Dynamic Audio Synthesis (`tw.audio.generate`)**: Procedurally compose music tracks and ambient audio on the fly using Google Lyria or ComfyUI workflows, cross-faded between scenes.
* **Item Manager Ergonomics**: High-level scripting aliases for moving items seamlessly: `tw.items.to_container()`, `to_player()`, and `to_scene()`.
* **Hardened Sandbox & Context**: Extended AST interpreter limits, instruction budgeting, memory safeguards, and complete test suites.

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
  * Implemented `tw.image.generate` and `tw.audio.generate` media synthesis in the scripting engine.
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
