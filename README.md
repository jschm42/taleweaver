# AI Text Adventure RPG

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


