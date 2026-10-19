<div align="center">

<img src="frontend/src/assets/svg/app-logo.svg" alt="TaleWeaver Logo" width="100" height="100" />

# TaleWeaver

**Weave Infinite Adventures. Direct and Star in Your Own Playable Audiobook.**

A self-hosted, local-first generative AI roleplaying studio: combining an omniscient AI Gamemaster,
cinematic voice acting, comic-style narrative feeds, and deterministic Python event scripting.

[![License: MIT](https://img.shields.io/badge/license-MIT-0ea5e9.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Vue 3](https://img.shields.io/badge/Vue%203-SPA-42b883?logo=vue.js&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local%20data-003b57?logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ed?logo=docker&logoColor=white)

[Features](#-features) · [Supported AI](#-supported-ai-ecosystem) · [Quick Start](#-quick-start) · [Docker](#-running-with-docker) · [Configuration](#%EF%B8%8F-configuration) · [Editor & Scripting](#-adventure-editor--scripting)

</div>

<br />

![Adventure Gameplay](docs/screenshots/gameplay.jpg)

<table>
  <tr>
    <td width="50%"><a href="docs/screenshots/generator.jpg"><img src="docs/screenshots/generator.jpg" alt="World Generator" /></a></td>
    <td width="50%"><a href="docs/screenshots/editor-map.jpg"><img src="docs/screenshots/editor-map.jpg" alt="Interactive Directed Map" /></a></td>
  </tr>
  <tr>
    <td align="center"><sub><b>World Generator</b> – synthesize complete adventures, lore, and Python scripts from a prompt</sub></td>
    <td align="center"><sub><b>Directed Cartography</b> – interactive topological maps with real-time pathfinding</sub></td>
  </tr>
  <tr>
    <td width="50%"><a href="docs/screenshots/editor-scenes.jpg"><img src="docs/screenshots/editor-scenes.jpg" alt="World Workbench" /></a></td>
    <td width="50%"><a href="docs/screenshots/editor-validation.jpg"><img src="docs/screenshots/editor-validation.jpg" alt="Dual-Tier AI Validation" /></a></td>
  </tr>
  <tr>
    <td align="center"><sub><b>Adventure Workbench</b> – full visual CRUD for scenes, NPCs, items, containers, and switches</sub></td>
    <td align="center"><sub><b>Dual-Tier Validation</b> – structural graph audits paired with semantic AI story critiques</sub></td>
  </tr>
</table>

<sub><i>Watch the <a href="https://youtu.be/lbAxVuU0SnQ">TaleWeaver Video Preview</a> or explore the full <a href="docs/SCREENSHOTS.md">Screenshot Guide</a>.</i></sub>

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🧠 Omniscient Gamemaster
- **Infinite Generative Worlds** – plots, quests, puzzles, and explorable scenes generated dynamically on the fly
- **Dynamic Living NPCs** – expressive multi-turn dialogue, autonomous scene movements, and individual motives
- **Strict 2-Pass Rulebook** – decoupled game loop running mathematical mechanics first, followed by atmospheric narrative prose
- **Cover Mode** – generate sequels, alternate timelines, or spinoffs from existing adventure blueprints
- **Tactical Encounters & Loot** – dedicated combat modal, locked container mechanics, item passcodes, and consumable handling

</td>
<td width="50%" valign="top">

### 🎭 Comic Feed & Cinematic Audio
- **Comic-Style Turn Feed** – dynamic speech bubbles, speaker avatars, action markers, and character staging
- **Playable Audiobook** – cinematic AI narration with emotional depth powered by Google Gemini 3.5 Flash TTS & ElevenLabs
- **Push-to-Talk Speech Input** – hands-free roleplaying with local background Whisper speech-to-text
- **In-Character Speech Shortcuts** – hold `B`, `T`, or `Shift` to automatically speak in-character (`/say `) to NPCs
- **Chronicles Timeline** – milestone-based auto-save checkpoints with instant one-click timeline rewinds

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🛠️ World-Builder & Scripting
- **In-Browser Adventure Studio** – comprehensive visual authoring for scenes, directed routes, NPCs, and loot tables
- **Sandboxed Python Event Scripts** – author deterministic event logic (`on_enter_scene`, `on_interact`, `on_turn`) in an isolated AST sandbox
- **Dual-Tier Validation Suite** – graph connectivity audits combined with semantic LLM plot-hole detection
- **One-Click AI Diagnostics** – intelligent AI repairs for broken exits, missing keys, or narrative inconsistencies
- **Dynamic Cartography** – auto-rendered hand-drawn style directed graph maps using rough.js and dagre

</td>
<td width="50%" valign="top">

### 🔐 Private & Local-First
- **Bring Your Own Keys (BYOK)** – full privacy and cost control; your prompts and stories stay on your hardware
- **Zero Lock-In Blueprints** – export and share complete adventure blueprints as standalone `.adv` or `.adz` packages
- **Local-First Database** – SQLite with asynchronous transactions and UUID-based entity models
- **Enterprise Hardening** – Fernet-encrypted keys, path traversal protection, loopback setup lockdown, and SSRF guards
- **Production Ready** – robust multi-worker container runtime via Gunicorn and Uvicorn

</td>
</tr>
</table>

---

## 🔌 Supported AI Ecosystem

TaleWeaver uses an adapter layer ([LiteLLM](https://github.com/BerriAI/litellm)) to support virtually any modern AI model, separating mechanical precision from creative narration:

| Capability | Recommended Models | Supported Providers | Notes |
|---|---|---|---|
| **World Generation** | Anthropic Opus 5.x, OpenAI 5.x, DeepSeek v4 Pro | OpenRouter, Anthropic, OpenAI, DeepSeek, Kimi | Requires deep reasoning to generate complex, valid JSON schemas |
| **Mechanics (Pass 1)** | DeepSeek Flash, GPT-6 Luna, Claude 4.5 Haiku | OpenAI, OpenRouter, Anthropic, DeepSeek | High-speed, deterministic state and inventory rule validation |
| **Narrative (Pass 2)** | DeepSeek v4 Pro, GPT-6 Luna Pro, Claude 4.5 Sonnet | OpenAI, Anthropic, OpenRouter, DeepSeek | Rich, atmospheric prose adapting to player choices and mood |
| **Text-to-Speech (TTS)** | Gemini 3.5 Flash TTS, ElevenLabs | Google Gemini, ElevenLabs | High-fidelity voice narration; feels like a live audiobook |
| **Speech-to-Text (STT)**| OpenAI Whisper (Base / Small / Medium) | Local Whisper (background thread) | Hands-free microphone input with Push-to-Talk hotkeys |
| **Visual Scene Art** | FLUX, Stable Diffusion (A1111 / Forge), Ollama | Local SD WebUI, Ollama, Cloud APIs | Contextual illustrations for scenes, items, and NPCs |

> [!TIP]
> **Cost-Effective Gaming**: Running **DeepSeek Flash** for mechanics alongside **DeepSeek v4 Pro** or **GPT-6 Luna** for narrative delivers cinematic roleplaying at pennies per hour. Pre-configured test adventures are included in `/adventures`, and community creations are available in the **[Community Adventure Repository](https://github.com/jschm42/taleweaver-adventures)**.

---

## 🚀 Quick Start

### Option A: Automatic Setup Script (Recommended)

The setup script creates a virtual environment, installs backend and frontend dependencies, runs database migrations, and initializes your environment keys.

**Linux / macOS:**
```bash
git clone https://github.com/jschm42/taleweaver.git
cd taleweaver
chmod +x setup.sh && ./setup.sh
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/jschm42/taleweaver.git
cd taleweaver
.\setup.ps1
```

---

### Option B: Manual Development Setup

**Requirements:** Python 3.10–3.13, [Poetry](https://python-poetry.org/) 2.x, Node.js 18+

```bash
# 1. Clone & install Python dependencies
git clone https://github.com/jschm42/taleweaver.git
cd taleweaver
poetry install

# 2. Configure environment & encryption keys
cp .env.example .env
poetry run python scripts/generate_fernet_key.py

# 3. Apply database migrations
poetry run alembic upgrade head

# 4. Install & build frontend
cd frontend
npm ci
npm run build
cd ..

# 5. Start TaleWeaver
poetry run taleweaver
```

Open `http://127.0.0.1:8000` in your browser. Complete the initial setup, add your API keys under **Administration**, and jump into an adventure!

---

## 🐳 Running with Docker

Deploy frontend and backend in a unified, production-grade container backed by Gunicorn and Uvicorn workers:

```bash
git clone https://github.com/jschm42/taleweaver.git
cd taleweaver

# Run the automated container bootstrapper
bash scripts/docker-setup.sh      # Windows: scripts\docker-setup.bat
```

The container maps `./data` as a persistent host volume, ensuring your SQLite database (`taleweaver.db`), logs, uploaded assets, and imported adventures persist across restarts.

---

## ⚙️ Configuration

Core server and security settings are configured in `.env` (refer to [`.env.example`](.env.example)):

| Variable | Purpose | Default / Example |
|---|---|---|
| `SECRET_KEY` | **Required** – JWT token signing key (min 32 random characters) | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENCRYPTION_KEY` | **Required** – 32-byte Fernet key for encrypting stored provider API keys | `python scripts/generate_fernet_key.py` |
| `DATA_DIR` | Directory for persistent database, session state, and uploads | `./data` |
| `ALLOWED_HOSTS` | Comma-separated domain whitelist for HTTP request validation | `localhost,127.0.0.1` |
| `ALLOW_PRIVATE_NETWORK_MODELS` | Permit outbound requests to local LLM/image endpoints (Ollama, SD) | `true` |
| `ALLOW_REMOTE_SETUP` | Allow non-loopback clients to execute initial root bootstrap | `false` |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` | Optional default provider keys (can also be configured in the UI) | Encrypted at rest |

---

## 🛠️ Adventure Editor & Scripting

TaleWeaver includes a comprehensive browser-based authoring workbench that puts you in full control of your worlds:

<details>
<summary><b>🐍 Sandboxed Python Event Scripting Engine</b></summary>

TaleWeaver executes deterministic game logic in an isolated AST interpreter sandbox (`backend/engine/scripting`), eliminating arbitrary code execution risks while enabling deep dynamic storytelling:

- **Lifecycle Hooks**: Attach custom logic to `on_enter_scene`, `on_interact`, `on_turn_start`, and `on_turn_end`.
- **State Manipulation**: Safely query and mutate scene descriptions, room exits, inventory items, NPC dialogue states, avatar hitpoints, and custom session variables.
- **Victory & Defeat Triggers**: Define custom branching conditions that evaluate player actions and story milestones.
- **In-Editor Workbench**: Test, debug, and lint event scripts directly inside the **Scripts Tab** with syntax assistance and priority scheduling.

</details>

<details>
<summary><b>🛡️ Security & Hardening Architecture</b></summary>

TaleWeaver is built with a defense-in-depth security model designed for self-hosting:

- **Strict Path Security**: All disk access runs through centralized traversal guards (`safe_data_path`, `ensure_within_data_dir`). Archive extraction (`.adz`) strips directory paths to prevent Zip-Slip vulnerabilities.
- **Fail-Closed Encryption**: Provider API keys are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256). The application strictly refuses to start if encryption keys are missing.
- **SSRF Mitigation**: User-supplied provider URLs are resolved and validated before connection to prevent internal network scanning.
- **Resource Constraints**: Image uploads are strictly capped at 10 MB with Pillow decompression bomb guards (`Pillow.MAX_IMAGE_PIXELS = 50_000_000`). Blueprints are bounded to prevent decompression bombs.
- **Loopback Lockdown**: Initial admin onboarding (`POST /api/auth/setup-root`) is restricted to loopback addresses by default.

</details>

<details>
<summary><b>🗺️ Architecture Diagrams & Turn Flow</b></summary>

Inspect the internal engine workflows through Mermaid diagrams in the repository:

- [Adventure Generation Workflow](docs/diagrams/adventure_generation.mermaid)
- [Adventure Generation Activity Flow](docs/diagrams/adventure_generation_activity.mermaid)
- [Game Session Loop Sequence](docs/diagrams/game_session_loop.mermaid)
- [Game Session Loop Activity](docs/diagrams/game_session_loop_activity.mermaid)

</details>

<details>
<summary><b>🌟 What's New in v0.6.0-beta</b></summary>

- **Comic Turn Presentation**: Reimagined UI featuring speaker avatars, expressive comic speech bubbles, and character stage rendering.
- **Sandboxed Python Scripting**: Deterministic event hooks and world script generation directly integrated into the editor and gameplay loop.
- **Dual-Tier AI & Graph Validation**: Interactive world validator identifying disconnected scene graphs and story plot holes with one-click AI repair proposals.
- **Chronicles Timeline**: Checkpoint auto-saves at major story milestones with instant state rewind capabilities.
- **Interactive Cartography**: Dynamic directed graph maps with topological pathfinding.

</details>

---

## 📜 License & Acknowledgments

- **Code**: Licensed under the [MIT License](LICENSE).
- **Adventures & Story Content**: Licensed under [CC-BY-NC 4.0](LICENSE-CC-BY-NC-4.0).
- **Fonts & Assets**: Bundled frontend typography assets and licenses are documented in `frontend/public/assets/fonts/licenses`.
