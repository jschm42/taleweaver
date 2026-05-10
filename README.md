# TaleWeaver - AI Text Adventure World Generator (v0.1.0-beta)

> [!IMPORTANT]
> **TaleWeaver is currently in active development.**
> As this is an early beta release, you may encounter unexpected behavior, bugs, or creative "hallucinations" from the AI Gamemaster. We are constantly refining the engine and **contributions, bug reports, and feedback are highly welcome!**

Welcome to the AI Text Adventure RPG project! This is a next-generation browser-based text adventure RPG that combines the nostalgic feel of classic point-and-click and text adventures with the dynamic creativity of modern Large Language Models (LLMs).

> [!TIP]
> **Roleplay for the best experience!** TaleWeaver works best when you fully immerse yourself in the role of the protagonist. Instead of just giving commands, try to describe your actions and thoughts in character. The AI Gamemaster will react much more dynamically and build a richer narrative if you "play along" with the story's themes and your character's traits.

## 📸 Gallery

<p align="center">
  <img src="docs/screenshots/portal.png" width="800" alt="Adventure Portal Placeholder">
  <br><em><b>Adventure Portal</b> - Manage your stories and explore new worlds.</em>
</p>

<p align="center">
  <img src="docs/screenshots/generator.png" width="800" alt="Game Builder Placeholder">
  <br><em><b>World Generator</b> - AI-driven world building and story generation.</em>
</p>

<p align="center">
  <img src="docs/screenshots/gameplay.png" width="800" alt="In-Game Gameplay Placeholder">
  <br><em><b>In-Game</b> - Immersive text adventure gameplay with dynamic AI interaction.</em>
</p>

## 🚀 First Steps

To get started with your first adventure, follow these simple steps:

1.  **Configure LLM**: Navigate to **Administration** and provide an API key for your preferred provider (OpenAI, Anthropic, Gemini, or local Ollama). This is required for the AI Gamemaster.
2.  **Explore the Library**: Browse the **Library** for pre-seeded adventures or imported blueprints.
3.  **Generate a World**: If you want something unique, use the **World Generator** to create a completely new setting from a simple prompt in your preferred language (e.g., German, French, Italian).
4.  **Begin Journey**: Select your adventure and click **Begin Journey** to start playing! (Your hero's stats and appearance are automatically initialized from the adventure's protagonist definition).

> [!TIP]
> You can find several pre-made test adventures in the `/adventures` directory of this repository. Use the **Import** button in the **Library** to load them and start playing immediately!

## 🧠 LLM Recommendations

For the best experience, we recommend using high-tier models, especially for **World Generation** and **Strict Mechanics**.

| Task | Recommended Models | Notes |
| :--- | :--- | :--- |
| **World Generation** | **GPT-5**, **Claude 4.5 Opus**, **Gemini 3 Pro** | Requires strong reasoning to generate complex, valid JSON manifests. |
| **Mechanics (Pass 1)** | **GPT-5-mini**, **Claude 4.5 Sonnet** | Best for following strict RPG rules and state modifications. |
| **Narrative (Pass 2)** | **Claude 4.5 Sonnet**, **GPT-5** | These models provide the most immersive and atmospheric prose.

[!WARNING]
Use providers with a good latency for the world generation to avoid long wait times. 

> [!WARNING]
> **Small / Preview Models:** Models like `Gemini 1.5 Flash` or `GPT-4o-mini` are excellent for quick chat responses but may occasionally struggle with the complex, deep JSON schemas required for generating entire worlds. If world generation fails repeatedly, try a more powerful "Pro" or "Sonnet" class model.

## 1. The Vision

Instead of a static, predefined story, the AI acts as an intelligent, omniscient Gamemaster (GM). It generates worlds, puzzles, and storylines "on the fly," reacts dynamically to player decisions, and simultaneously manages a strict RPG rulebook in the background. The frontend is presented in an immersive, stylish pixel-art look.

## 2. Core Features

### AI as Gamemaster & Content Generator
* **Dynamic Generation:** Generation of complete text adventure RPGs (story plots, puzzles, explorable scenes) in any supported language.
* **NPCs & Dialogues:** Creation and control of NPCs, including dynamic dialogues where the AI assumes the role of the NPC in the chat.
* **Loot & Objects:** Placement of interactive objects and loot to improve character stats.
* **Challenge Ratings:** Autonomous decision-making by the GM regarding the difficulty of a player's planned action by setting a dynamic "challenge rating" (Difficulty Class).
* **Style & Tone Catalog:** Fully customizable world generation. Define your own visual styles and narrative tones in the Administration panel, complete with AI-generated previews.

### Persistent Game Progress & Memory
* **Memory Feature:** The AI remembers all previous conversations and actions of the player within an adventure.
* **Persistence:** Progress is permanently stored in the database, allowing sessions to be paused and resumed at any time.

### RPG Mechanics
* **Character Sheets & In-Game Stats:** The protagonist's state (stats, inventory, equipment) is automatically initialized from the adventure template. The current state can be viewed in-game via a command or modal interface.
* **Resource Bars:** Hitpoints (HP), Stamina, and Mana (starting at 200). The AI dynamically adjusts these. HP 0 usually means Game Over.
* **Dynamic States (Status Effects):** Avatars can receive plot-dependent states (e.g., Tired, Poisoned, Enraged, Blessed) modifying base stats.
* **Randomized Action Resolution (Skill Checks):** A virtual D20 roll for risky actions (D20 + stats >= Challenge Rating) executed efficiently in the backend.
* **Individual Inventory System:** Isolated inventory for looting, dropping, and combining objects.
* **Equipment Slots:** Dedicated slots for Head, Chest, Arms, Legs, Hands, Feet, Rings (2), and Amulet.
  
### 🐟 Bable Fish Multilingualism
* **Multilingual Generation:** Generate entirely new adventures in your chosen language (German, Italian, French, etc.) from the start.
* **In-Game Translation:** Switch languages dynamically during gameplay using the "Bable Fish" toggle to translate narration and NPC dialogue.
* **User Preferences:** Set a global default language in your profile that follows you across all adventures and sessions.
* **Voice & Narration (TTS):** Immersive audio experience powered by **Google Gemini 1.5 Flash (TTS)** and **ElevenLabs**. The AI Gamemaster narrates the story with cinematic quality, including support for vocal tags and director notes for dramatic pacing.

### Hybrid Interaction
* **Natural Language Chat:** Free text input for dialogues and complex actions.
* **Slash Commands:** `/sheet`, `/pickup`, `/drop`, `/equip`, `/unequip`, `/push`, `/pull`, `/attack`, `/take`, `/combine`, `/examine`, `/map`.

### Dynamic World Mapping
* **Generated Maps:** Directed graphs of scenes, visualized via Mermaid.js (using the `/map` command).

### Media & Immersion
* Optional AI-generated images to enhance the retro pixel-art aesthetic.
* **Import/Export:** Adventures can be backed up or shared.

## 3. Architecture & Concepts

### Tenant-Ready Strategy
Although starting single-user, the database uses **UUIDv4** keys exclusively, paving the way for multi-tenancy with `O(1)` lookup complexity.

### LLM Abstraction & Secure Key Management
* **Adapter Pattern:** Using a higher-level LLM router (e.g., `litellm`) to map providers to a standardized interface.
* **Security:** API keys entered via the frontend are encrypted (AES) before being stored in the SQLite database.

## 4. Workflows & Internal Logic

For a deeper look into the backend processes, check out the Mermaid diagrams in the `docs/diagrams` folder:
* [Adventure Generation Workflow](docs/diagrams/adventure_generation.mermaid) ([Activity Diagram](docs/diagrams/adventure_generation_activity.mermaid))
* [Game Session Loop Sequence](docs/diagrams/game_session_loop.mermaid) ([Activity Diagram](docs/diagrams/game_session_loop_activity.mermaid))

### 🐳 Running with Docker (Recommended)

The easiest way to get TaleWeaver up and running is using Docker. This method packages both the frontend and backend into a single container and handles all dependencies automatically.

#### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed and running.
- [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop).

#### Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/jschm42/taleweaver.git
    cd taleweaver
    ```

2.  **Run the setup script:**
    -   **Linux/macOS:** `bash scripts/docker-setup.sh`
    -   **Windows:** `scripts\docker-setup.bat`

3.  **Configure Environment:**
    The setup script will create a `.env` file from `.env.example`. Open it and set your `ENCRYPTION_KEY`. (You can generate one using `python scripts/generate_fernet_key.py` or use any persistent 32-byte base64 string).

4.  **Access the App:**
    Open your browser and go to `http://localhost:8000`.

#### Persistence & Data
The Docker setup uses a **bind mount** to the `./data` directory on your host machine. This ensures that:
- Your SQLite database (`taleweaver.db`) and all game progress persist between restarts.
- Generated character images and logs are saved on your host.
- The bundled adventures in `/adventures` are automatically imported on the first start.

#### Updating
To update to the latest version and rebuild the container:
```bash
bash scripts/docker-update.sh
```

### 🛠️ Manual Development Setup

If you prefer to run the components separately for development:

#### System Requirements
- **Python:** 3.12 (specified via `.python-version` file)
- **Node.js:** 18+ (for the Vue.js frontend MVP)
- **Package Managers:** `pip` and `npm`
- **Database:** SQLite (built-in, no separate server needed)
- **LLM Provider:** An active API key from an LLM provider (e.g., OpenAI, Anthropic, Gemini) is required for the AI Gamemaster.

### Installation & Execution

The project is split into a Python/FastAPI backend and a Vue.js frontend.

#### 1. Backend Setup
Navigate to the project root directory, create a virtual environment, and install dependencies:

```bash
# Create and activate a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install requirements
python -m pip install -r requirements.txt

# Set up your environment variables
cp .env.example .env

# Generate a secure ENCRYPTION_KEY and follow the script's instructions
# to place the generated key into your new .env file
python scripts/generate_fernet_key.py

# Apply database migrations
python -m alembic upgrade head

# If a previous migration crashed and left temp tables behind, clean and retry:
# python -c "import sqlite3; c=sqlite3.connect('taleweaver.db'); c.execute('DROP TABLE IF EXISTS _alembic_tmp_adventures'); c.execute('DROP TABLE IF EXISTS _alembic_tmp_users'); c.execute('DROP TABLE IF EXISTS _alembic_tmp_avatars'); c.commit(); c.close()"
# python -m alembic upgrade head

# Start the FastAPI server (uses BACKEND_PORT from .env)
python -m backend.main
```

Important: Run this command from the project root. Running it from inside the backend directory causes import errors like ModuleNotFoundError: No module named backend.

If you see SQLite errors such as no such column after model changes, recreate the local database file taleweaver.db (or run your migration flow) so the schema matches the current models.

The backend API will run on the port configured in `.env` (default: `http://localhost:8000`).
The frontend will run on the port configured in `.env` (default: `http://localhost:5173`).

#### Windows Quick Start (PowerShell)

If you want a copy-paste setup for Windows PowerShell from the project root:

```powershell
# Backend terminal
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m backend.main
```

```powershell
# Frontend terminal
cd frontend
npm install
npm run dev
```

#### 2. Frontend Setup
Navigate to the frontend directory to set up the Vue.js interface:

```bash
cd frontend

# Install UI dependencies
npm install

# Start the development server
npm run dev
```
The frontend will typically run on `http://localhost:5173`.

#### 3. First Launch
Once both servers are running, open the frontend URL in your browser. You will be prompted in the settings/configuration UI to provide your LLM API key. This key is encrypted using AES and stored safely in your local SQLite database before you can start generating your first adventure.

### Local Ollama Image Generation (Experimental)

TaleWeaver supports local image generation through Ollama as an additional `Visuals` provider.

1. Install and run Ollama.
2. Pull an image model, for example:

```bash
ollama pull x/flux2-klein
```

3. In the frontend `Configuration -> Visuals` section:
	- Set `Image Provider` to `Ollama (Local, Experimental)`.
	- Set `Simple Image Model` and `Advanced Image Model` (default recommendation: `x/flux2-klein`).
	- Set `Ollama URL` (default: `http://localhost:11434`).
	- Optionally set `width`, `height`, `steps`, `seed`, and `negative_prompt`.

Notes:
- No cloud API key is required for local Ollama image generation.
- TaleWeaver first tries image generation via LiteLLM integration and falls back to direct Ollama HTTP calls when needed.

## 6. Automated Adventure Import

TaleWeaver features an automated pipeline to seed the database with adventures or import shared content on startup.

### Supported Formats
* **`.adv` (JSON):** Adventure blueprint as plain JSON (no bundled assets).
* **`.adz` (ZIP):** "Adventure Zip" containing the same blueprint JSON as `adventure.adv` plus optional bundled assets in `assets/`.

Both formats use the same top-level blueprint structure and must include format metadata:
* `format`: `taleweaver.adz`
* `version`: currently `1.0`

### Format Versioning
* Every exported file is versioned.
* On import, the backend validates `format` and `version`.
* If a file version is below the minimum supported version, import is rejected with an explicit error (HTTP 400), e.g.:
	* `Import version 0.9 is too old. Minimum supported version is 1.0.`

### Watch Directories
The backend monitors three specific directories relative to the project root:

1.  **`adventures/`**: Bundled adventures that are **committed to the repository**. This is the primary location for core adventures that should be available on every installation. Files are **never deleted**.
2.  **`data/presets/adventures/`**: Local presets or examples. This folder is ignored by git. Files are **never deleted**.
3.  **`data/imports/adventures/`**: For manual "drop-in" imports. Files in this folder are **automatically deleted** once successfully imported to keep the workspace clean.

### How it Works
* The import process runs every time the FastAPI backend starts.
* **One-Time Seed:** Adventures in the root `adventures/` folder are only imported if the database is currently empty (e.g., first start or after a reset). This allows users to delete bundled adventures from the UI without them reappearing on every restart.
* **Deduplication:** For other folders, the system checks the adventure title. If an adventure with the same title already exists, the import is skipped.
* **Asset Handling:** For `.adz` files, assets are automatically extracted and remapped to the local storage, ensuring images are available immediately.

### Portal Import/Export
* In the portal adventure card menu, each adventure can be exported as both `.adv` and `.adz`.
* The portal import action accepts both `.adv` and `.adz`:
	* Use `.adv` when you only need the blueprint JSON.
	* Use `.adz` when you also want to include packaged assets.

## 7. Credits & Assets

* **AI & LLM:** Image generation is powered by **FLUX.1 [schnell]** and **FLUX.2 [klein]** by [Black Forest Labs](https://blackforestlabs.ai/). Multi-provider LLM abstraction is handled via [LiteLLM](https://github.com/BerriAI/litellm).
* **Voice & TTS:** Cinematic narration provided by **Google Gemini 1.5 Flash (TTS)** and **ElevenLabs**.
* **Mapping:** Dynamic world maps are rendered using [Mermaid.js](https://mermaid.js.org/).
* **Visual Assets:** Special thanks to [Recraft.ai](https://www.recraft.ai) for the high-quality vector graphics and SVG assets, and [DiceBear](https://www.dicebear.com/) for the procedural user avatars.
* **Icons:** RPG-specific iconography provided by [RPG-Awesome](https://nagoshiashumari.github.io/Rpg-Awesome/) and system icons by [Lucide](https://lucide.dev/).
* **Typography:** Retro pixel-art and fantasy aesthetics powered by the **Press Start 2P**, **Acme**, and **Orbitron** fonts from [Google Fonts](https://fonts.google.com/) (SIL Open Font License).

## 8. License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

AI-generated content (images and text) produced by this application is subject to the terms of the respective model providers. For **Black Forest Labs FLUX.1 [schnell]** and **FLUX.2 [klein]**, commercial use is permitted under the Apache 2.0 license. Please be aware that the copyrightability of AI-generated content is subject to legal interpretation in your local jurisdiction.
