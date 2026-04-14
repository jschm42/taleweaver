# Adventure: Escape from the Concrete Tomb

## Story Idea
You wake up on a cold, damp concrete floor. Your head throbs. You are in a small, windowless cellar. The air is stale. A heavy steel door provides the only exit, but it is locked from the outside. Above the door, a crackling intercom speaker occasionally hums with static. You have no idea how you got here, but a mysterious voice keeps whispering instructions—or riddles—through the speaker.

## Tone
**Claustrophobic & Industrial:** Dark, gritty, and mysterious. The sound of flickering fluorescent lights and dripping water. The voice is calm, almost surgical, but carries an underlying threat.

## Scenes (Locations)
1. **The Locked Cellar [ID: CELLAR_MAIN]:** A 4x4 meter concrete room. There is a rusted cot in one corner and an old workbench in the other. A heavy steel door dominates the north wall. Above it is the intercom speaker.

## Characters (NPCs)
- **The Monitor [ID: NPC_VOICE]:** A voice coming through the speaker. It sounds distorted but controlled. It refers to you as "Subject 42" and seems to be observing your progress through hidden cameras.

## Objects & Item Types

### Tools & Combination Items
- **Length of Copper Wire [ID: ITEM_WIRE, item_type: COMBINABLE]:** A stiff but bendable piece of wiring found under the cot.
- **Rusted Pliers [ID: ITEM_PLIERS, item_type: TOOL]:** Found on the edge of the workbench. They are stiff but functional.
- **Improvised Bypass Tool [ID: ITEM_BYPASS, item_type: KEY, is_hidden: true, combination_ingredients: ["ITEM_WIRE", "ITEM_PLIERS"]]:** The result of using the pliers to bend the wire into a specific shape. This is the only way to trigger the electronic release of the door.

### Room Interactions (Static)
- **Heavy Steel Door [ID: OBJ_DOOR, item_type: STATIC]:** A massive door with an electronic keypad that is missing its buttons. It has an exposed circuit slot where a tool could be inserted.
- **Crackling Intercom [ID: OBJ_SPEAKER, item_type: STATIC]:** Mounted high on the wall. It's the source of the Monitor's voice.
- **Old Workbench [ID: OBJ_BENCH, item_type: STATIC]:** Bolted to the floor. It holds the pliers and some scattered, useless bolts.

### Other Items
- **Damp Blanket [ID: ITEM_BLANKET, item_type: WEARABLE, wearable_slots: ["Chest"]]:** Smells of mildew but provides some warmth.

## Main Quest: Break the Silence
1. **Find the Components:** Salvage the **Copper Wire** from the cot and the **Pliers** from the workbench.
2. **The Voice's Riddle:** Interact with the **Intercom** to hear the Monitor's hint about "bending the will of the machine."
3. **Craft the Tool:** Use the **Pliers** on the **Copper Wire** in your inventory to combine them into the **Bypasser**.
4. **The Great Escape:** Use the **Bypasser** on the **Steel Door**'s exposed circuits to force the lock open.
