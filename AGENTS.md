# 🤖 Instructions for the Coding Agent

Follow these packages **strictly in the specified order** to ensure successful implementation and avoid circular dependencies:

### Package 1: Foundation & Multi-User Database Schema
**Goal:** Establish the base architecture and the SQLite database.
* Setup the Python/FastAPI project.
* Implement the asynchronous ORM (e.g., SQLAlchemy v2).
* Create the base models with UUIDv4 as Primary Keys:
  * `User`: (Placeholder for later, initially a local default user).
  * `Avatar`: Character Sheet (Stats, HP/Stamina/Mana defaults to 200) + JSON fields for `inventory`, `equipment` (Head, Chest, Arms, Legs, Hands, Feet, Ring_1, Ring_2, Amulet), and `status_effects`.
  * `Adventure`: Title, `strict_rules` flag, heartbeat interval, optional Game Over rules.
  * `GameState`: Links User, Avatar, and Adventure; stores the current `scene_id` and in-game time.
* Create CRUD repositories for these models.

### Package 2: Security & LLM Router (Abstraction Layer)
**Goal:** Unified interface to all AI models and secure key management.
* Implement an Encryption Utility class (AES-based).
* Extend the model to store encrypted provider API keys.
* Implement the `GameMasterLLM` class with routing for Simple Tasks and Complex Tasks.

### Package 3: Core Game Engine & State Management
**Goal:** The game logic that manages the state and mediates between AI and database.
* **Command Parsers:** Action, Inventory & Equipment Parsers for slash commands routing directly to JSON updates (`O(1)` performance).
* **Stat Aggregator:** Dynamic Stat Calculation (`O(1)` performance) determining Base Stat + Equipment + Status Effects.
* **Skill-Check Engine:** A module generating D20 rolls, adding aggregated stats, and checking against the "challenge rating."
* **Rule Engine (`strict_rules`):** Pydantic JSON schemas passed to the LLM. Catch HP <= 0 conditions (Game Over).
* **Memory Management:** Sliding-window context + inject Character Sheet into system prompt.

### Package 4: API & Real-Time Communication
**Goal:** Provide interfaces for the Vue.js frontend.
* Standardized REST routes for configuration and adventure management.
* WebSocket endpoint (`/ws/adventure/{game_id}`).
* Asynchronous Heartbeat Timer to evaluate time-based logic (e.g., status-effect damage per minute).

### Package 5: Frontend MVP (Vue.js + TypeScript + Tailwind)
**Goal:** Build the graphical user interface.
* Initialize the Vue 3 (Composition API) project with Tailwind CSS.
* Create a base layout in Pixel-Art / Retro style.
* **Module Game UI:**
  * Main Chat Window.
  * Modal Dialog for the Character Sheet (`/sheet`).
  * WebSocket client integration.

### Package 6: World Mapping (Mermaid.js) & Media
**Goal:** Visual support for the text adventure logic.
* **Backend:** Graph update logic (Nodes = Scenes, Edges = Exits).
* Convert JSON map data for Mermaid.js (`O(V+E)`).
* **Frontend:** Implement the `/map` command to render.
