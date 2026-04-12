# TaleWeaver - AI Text Adventure Wolrd Generator

Welcome to the AI Text Adventure RPG project! This is a next-generation browser-based text adventure RPG that combines the nostalgic feel of classic point-and-click and text adventures with the dynamic creativity of modern Large Language Models (LLMs).

## 1. The Vision
Instead of a static, predefined story, the AI acts as an intelligent, omniscient Gamemaster (GM). It generates worlds, puzzles, and storylines "on the fly," reacts dynamically to player decisions, and simultaneously manages a strict RPG rulebook in the background. The frontend is presented in an immersive, stylish pixel-art look.

## 2. Core Features

### AI as Gamemaster & Content Generator
* **Dynamic Generation:** Generation of complete text adventure RPGs (story plots, puzzles, explorable scenes).
* **NPCs & Dialogues:** Creation and control of NPCs, including dynamic dialogues where the AI assumes the role of the NPC in the chat.
* **Loot & Objects:** Placement of interactive objects and loot to improve character stats.
* **Challenge Ratings:** Autonomous decision-making by the GM regarding the difficulty of a player's planned action by setting a dynamic "challenge rating" (Difficulty Class).

### Persistent Game Progress & Memory
* **Memory Feature:** The AI remembers all previous conversations and actions of the player within an adventure.
* **Persistence:** Progress is permanently stored in the database, allowing sessions to be paused and resumed at any time.

### RPG Mechanics
* **Character Sheets & UI Dialog:** Players can create multiple avatars. The current state of the character can be opened via a command in a modal interface.
* **Resource Bars:** Hitpoints (HP), Stamina, and Mana (starting at 200). The AI dynamically adjusts these. HP 0 usually means Game Over.
* **Dynamic States (Status Effects):** Avatars can receive plot-dependent states (e.g., Tired, Poisoned, Enraged, Blessed) modifying base stats.
* **Randomized Action Resolution (Skill Checks):** A virtual D20 roll for risky actions (D20 + stats >= Challenge Rating) executed efficiently in the backend.
* **Individual Inventory System:** Isolated inventory for looting, dropping, and combining objects.
* **Equipment Slots:** Dedicated slots for Head, Chest, Arms, Legs, Hands, Feet, Rings (2), and Amulet.

### Hybrid Interaction
* **Natural Language Chat:** Free text input for dialogues and complex actions.
* **Slash Commands:** `/sheet`, `/pickup`, `/drop`, `/equip`, `/unequip`, `/push`, `/pull`, `/attack`, `/take`, `/combine`, `/examine`, `/map`.

### Dynamic World Mapping & Time Simulation
* **Generated Maps:** Directed graphs of scenes, visualized via Mermaid.js (using the `/map` command).
* **Heartbeat Timer:** Background time simulation for unpredictable events independent of user input.

### Media & Immersion
* Optional AI-generated images to enhance the retro pixel-art aesthetic.
* **Import/Export:** Adventures can be backed up or shared.

## 3. Architecture & Concepts

### Tenant-Ready Strategy
Although starting single-user, the database uses **UUIDv4** keys exclusively, paving the way for multi-tenancy with `O(1)` lookup complexity.

### LLM Abstraction & Secure Key Management
* **Adapter Pattern:** Using a higher-level LLM router (e.g., `litellm`) to map providers to a standardized interface.
* **Security:** API keys entered via the frontend are encrypted (AES) before being stored in the SQLite database.

### Strict Rules vs. Hallucination Engine
The `strict_rules` flag determines AI behavior:
* **Strict Mode:** Forces state modifications (HP loss, debuffs) to return "Structured Outputs" (JSON) which the backend validates.
* **Hallucination Mode:** Narrative freedom where the backend adapts to textual estimations.

## 4. Technical Details & Setup

### System Requirements
* **Python:** 3.12 (specified via `.python-version` file)
* **Node.js:** 18+ (for the Vue.js frontend MVP)
* **Package Managers:** `pip` and `npm`
* **Database:** SQLite (built-in, no separate server needed)
* **LLM Provider:** An active API key from an LLM provider (e.g., OpenAI, Anthropic, Gemini) is required for the AI Gamemaster.

### Installation & Execution

The project is split into a Python/FastAPI backend and a Vue.js frontend.

#### 1. Backend Setup
Navigate to the root or backend directory, create a virtual environment, and install dependencies:

```bash
# Create and activate a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Set up your environment variables
cp .env.example .env

# Generate a secure ENCRYPTION_KEY and follow the script's instructions
# to place the generated key into your new .env file
python scripts/generate_fernet_key.py

# Start the FastAPI server
uvicorn backend.main:app --reload
```
The backend API will typically run on `http://localhost:8000`.

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
