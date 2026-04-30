---
Erzeugt: 2026-04-30
tags:
---
## Allgemein

- Beim Starten einer neuen Game-Session wird eine Kopie des Adventure-Konzepts angereichert und an dem Session-Objekt gespeichert. Diese dient dann als Spielstand. Daten die nur für die Generierung benötigt wurden (z.b. min_scenes), werden nicht an der Session gespeichert. Alle Änderungen im Spielverlauf werden dort gespeichert. Alle Informationen zum Spiel werden aus der Session entnommen. Es gibt keinerlei Zugriffe mehr auf das Manifest!
- Generierung komplett mit Unit-Tests absichern
- Game-Loop komplett mit Unit-Tests absichern
- Der Import/Export muss ebenfalls an das neue Format angepasst werden
- Keine Abwärtskompatibilität des ADV/ADZ Formats

## Adventure-Format Anpassungen

- Hinzufügen
	- plot
		- Wird während der Generierung aus dem Prompt generiert und ist eine kompakte Zusammenfassung des Adventure-Plots die gut von der KI verstanden werden kann. 
		- Kann im Editor bearbeitet werden
	- rules
		- Wird während der Generierung aus dem Prompt generiert und kann optional für das Festlegen allgemeiner Regeln verwendet werden.
		- Beispiele
			- Der Protagonist darf keinen NPC verletzten
			- Die Zuschauer dürfen den Protagonisten ausbuhen oder bejubeln (für Sitcoms)
			- Der Protagonist muss in Reimen sprechen
			- Magic requires a physical sacrifice
			- The sun never sets in this realm
	- ingame_timestamp
		- Zeitstempel, der die aktuelle In-Game Zeit repräsentiert. Diese wird in jeder Runde um den Pace erhöht. Kann aber auch vom Gamemaster, abhängig von Story, erhöht oder reduziert werden
		- In der In-Game Uhr wird dieser Zeitstempel angezeigt (wenn aktiviert)
	- completed_condition
		- Legt fest, wann der Spieler gewonnen hat
			- Kann eine weiche oder harte Regel sein
				- Beispiel
					- Der Protagonist hat das Publikum überzeugt
					- Der Protagonist hat drei Ratten erlegt
					- Alle Gegner erledigt
					- Aus dem Kerker entkommen
			- Wenn keine spezielle Regel definiert, gilt
				- RPG und Story-Modus = Alle Hauptquests erfüllt
				- Char-Modus = Keine Endbedingung
	- gameover_condtion
		- Legt fest, wann der Spieler verloren hat
			- Kann eine weiche oder harte Regel sein
				- Beispiel
					- Der Protagonist wurde im Kerker eingesperrt
					- Der Protagonist hat drei mal geflucht (Sitcom)
			- Wenn keine spezielle Regel definiert, gilt
				- RPG und Story-Modus = HP des Spielers <= 0
				- Chat-Modus = Keine Endbedingung
	- original_prompt
		- Beinhaltet den Ausgangsprompt für die Generierung des Adventures. Wird nur zur Dokumentation gespeichert und hat für das Adventure keinenen weiteren Nutzen
	- walkthrough
		- Wird während der Generierung erzeugt
		- RPG und Story-Modus
			- Beinhaltet einen Walkthrough durch das Game als Lösungshilfe und als Hilfe für den Gamemaster um den Plot besser steuern zu können
		- Chat-Modus
			- Leer
	- Änderung bei NPC
		- current_scene_id
			- Beinhaltet beim Start des Games die Startposition des NPCs. Kann sich aber im Laufe des Spiels ändern, wenn der Gamemaster den NPC durch Räume bewegt. Die aktuelle Szene wird dann hier gespeichert.
		- hp / stamina / mana
			- RPG-Modus
				- Alle drei
			- Story-Modus
				- Nur HP
			- Chat-Modus
				- Keine davon


## Frontendanpassungen

- Der aktuelle Reiter "World" wird zu "Physical"
- Im World-Editor gibt es ein neues Register "Plot"
	- Hier kann folgendes editiert werden
		- Plot
		- Rules
		- Walkthrough
		- Complete Conditions
		- Gameover Conditions
- Die Chat-Eingabe für Änderungen wandert in einen eigenen Reiter "Rebuild"
- Im Asset Register gibt es folgende Änderungen
	- RPG-Mode
		- Die Stats der NPCs mit HP, Stamina, Mana werden an der Popup-Kachel angezeigt (wie in-game)
		- Die Stats an den Items werden an der Popup-Kachel angezeigt (win in-game)
	- Story-Mode
		- Die Stats der NPCs mit HP werden an der Popup-Kachel angezeigt (wie in-game)
		- Die Stats an den Items werden an der Popup-Kachel angezeigt (wie in-game)
	- Chat-Mode
		- Es werden keine Stats an NPCs oder Items angezeigt

# Neues Game-Turn Konzept

## Context-Injection

### ALL Modes

#### World & Time
| Attribute           | Source        | Description                                                                          |
| :------------------ | :------------ | :----------------------------------------------------------------------------------- |
| `CURRENT GAME TIME` | Session State | Current in-game time formatted as `Day X, HH:MM`.                                    |
| quests_json         | Session State | A list of all quests (Main and Side) with their current `status` (active/completed). |
| awards_json         | Session State | A list of all earnable awards and their specific requirements.                       |
| plot                | Session State | The generated plot                                                                   |
| rules               | Session State | The generated rules                                                                  |
| walkthrough         | Session State | The generated walkthrough                                                            |
| tone                | Session State | The configured tone (the actual prompt, not the key!)                                |
|                     |               |                                                                                      |
#### Location Context (`location_context`)
| Attribute         | Source      | Description                                                                                                                             |     |
| :---------------- | :---------- | :-------------------------------------------------------------------------------------------------------------------------------------- | --- |
| `NAME`            | WorldScene  | Label of the current location.                                                                                                          |     |
| `ID`              | WorldScene  | Unique identifier for internal logic.                                                                                                   |     |
| `DESCRIPTION`     | WorldScene  | The static narrative description of the scene.                                                                                          |     |
| `PRESENT NPCs`    | WorldEntity | List of NPCs in the scene with HP (RPG + Story), Stamina (RPG), Mana (RPG), and `spatial_position`.                                     |     |
| `OTHER NPCs`      | WorldEntity | List of NPCs NOT IN PRESENT SCENE with their current_scene_id with HP (RPG + Story), Stamina (RPG), Mana (RPG), and `spatial_position`. |     |
| `OBJECTS`         | WorldEntity | List of interactable objects with their `spatial_position`.                                                                             |     |
| `AVAILABLE EXITS` | WorldExit   | List of exits with `label`, destination `ID`, and lock status (including `lock_description`).                                           |     |

### RPG-Mode

#### Character Sheet (`sheet_json`)
| Attribute        | Source             | Description                                                                                   |
| :--------------- | :----------------- | :-------------------------------------------------------------------------------------------- |
| `name`           | Avatar             | The protagonist's name.                                                                       |
| `role`           | Avatar             | The character class or narrative role (e.g., "Rogue", "Scholar").                             |
| `description`    | Avatar             | Background story and physical description.                                                    |
| `hp`             | Avatar             | Current resource value.                                                                       |
| stamina          | Avatar             | Current resource value.                                                                       |
| mana             | Avatar             | Current resource value.                                                                       |
| `stats`          | Avatar + Equipment | Aggregated Core Attributes: Strength, Dexterity, Intelligence, Wisdom, Charisma, Armor Class. |
| `equipment`      | Avatar             | Currently equipped items and their slots.                                                     |
| `inventory`      | Avatar             | All items carried by the player.                                                              |
| `status_effects` | Avatar             | Active conditions (e.g., "Poisoned", "Resting").                                              |

------

### Story-Mode

#### Character Sheet (`sheet_json`)
| Attribute        | Source | Description                                                       |
| :--------------- | :----- | :---------------------------------------------------------------- |
| `name`           | Avatar | The protagonist's name.                                           |
| `role`           | Avatar | The character class or narrative role (e.g., "Rogue", "Scholar"). |
| `description`    | Avatar | Background story and physical description.                        |
| `hp`             | Avatar | Current resource values.                                          |
| `equipment`      | Avatar | Currently equipped items and their slots.                         |
| `inventory`      | Avatar | All items carried by the player.                                  |
| `status_effects` | Avatar | Active conditions (e.g., "Poisoned", "Resting").                  |
|                  |        |                                                                   |

---

### Chat-Mode

#### Character Sheet (`sheet_json`)
| Attribute     | Source | Description                                                       |
| :------------ | :----- | :---------------------------------------------------------------- |
| `name`        | Avatar | The protagonist's name.                                           |
| `role`        | Avatar | The character class or narrative role (e.g., "Rogue", "Scholar"). |
| `description` | Avatar | Background story and physical description.                        |

------


## Tool-Calls

### RPG-Modus

### LLM "Tool Calls" (Structured Output)
The LLM responds with a structured `GameEvent` object. It "calls" game logic by setting these fields:

| Field                                        | Effect                                                                  |
| :------------------------------------------- | :---------------------------------------------------------------------- |
| `hp_change`, `stamina_change`, `mana_change` | Modifies player resources (positive or negative).                       |
| `new_inventory_items`                        | Grants the player new items (with full stats/descriptions).             |
| `new_status_effects`                         | Applies conditions like "Burning" or "Blessed".                         |
| `new_scene_id`                               | **Navigation**: Moves the player to a different location ID.            |
| `requested_skill_checks`                     | **Dice Roll**: Triggers a check (e.g., "Strength DC 15 to break door"). |
| `updated_entities`                           | Updates NPC/Object HP, name, description, or position.                  |
| `moved_entities`                             | Moves an NPC or Object to a different scene or position.                |
| `updated_exits`                              | Locks or unlocks doors/paths.                                           |
| `completed_quest_ids`                        | Marks specific quests as finished.                                      |
| `earned_award_keys`                          | Grants achievements to the player.                                      |
| `extra_time_minutes`                         | Adds duration to the current turn (e.g., "Climbing takes 10 mins").     |
| `game_over` / `game_completed`               | Ends the session with a specific `status_note`.                         |
|                                              |                                                                         |

### Story-Modus

### LLM "Tool Calls" (Structured Output)
The LLM responds with a structured `GameEvent` object. It "calls" game logic by setting these fields:

| Field                                        | Effect                                                                  |
| :------------------------------------------- | :---------------------------------------------------------------------- |
| `hp_change`, `stamina_change`, `mana_change` | Modifies player resources (positive or negative).                       |
| `new_inventory_items`                        | Grants the player new items (with full stats/descriptions).             |
| `new_status_effects`                         | Applies conditions like "Burning" or "Blessed".                         |
| `new_scene_id`                               | **Navigation**: Moves the player to a different location ID.            |
| `updated_entities`                           | Updates NPC/Object HP, name, description, or position.                  |
| `moved_entities`                             | Moves an NPC or Object to a different scene or position.                |
| `updated_exits`                              | Locks or unlocks doors/paths.                                           |
| `completed_quest_ids`                        | Marks specific quests as finished.                                      |
| `earned_award_keys`                          | Grants achievements to the player.                                      |
| `extra_time_minutes`                         | Adds duration to the current turn (e.g., "Climbing takes 10 mins").     |
| `game_over` / `game_completed`               | Ends the session with a specific `status_note`.                         |
|                                              |                                                                         |

### Chat-Modus

### LLM "Tool Calls" (Structured Output)
The LLM responds with a structured `GameEvent` object. It "calls" game logic by setting these fields:

| Field                                        | Effect                                                              |
| :------------------------------------------- | :------------------------------------------------------------------ |
| `new_inventory_items`                        | Grants the player new items (with full stats/descriptions).         |
| `new_scene_id`                               | **Navigation**: Moves the player to a different location ID.        |
| `updated_entities`                           | Updates NPC/Object HP, name, description, or position.              |
| `moved_entities`                             | Moves an NPC or Object to a different scene or position.            |
| `updated_exits`                              | Locks or unlocks doors/paths.                                       |
| `completed_quest_ids`                        | Marks specific quests as finished.                                  |
| `earned_award_keys`                          | Grants achievements to the player.                                  |
| `extra_time_minutes`                         | Adds duration to the current turn (e.g., "Climbing takes 10 mins"). |
| `game_over` / `game_completed`               | Ends the session with a specific `status_note`.                     |
|                                              |                                                                     |
