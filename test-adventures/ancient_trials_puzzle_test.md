# Adventure: Trials of the Ancients (Puzzle Test)

## Story Idea
You stand before the Temple of Trials. To reach the Inner Sanctum and its legendary treasures, you must prove your wisdom by solving the riddles of the silent guardians.

## Tone
**Mystical & Ancient:** Dust motes dancing in shafts of light, ancient stone carvings, and an eerie silence that weighs heavy on the ears.

## Scenes (Locations)
1. **Temple Entrance [ID: TEMPLE_ENTRANCE]:** A grand doorway flanked by two massive stone statues.
2. **Hall of Wisdom [ID: ROOM_PUZZLE]:** A chamber with a circular floor pattern and a pedestal in the center.
3. **Inner Sanctum [ID: ROOM_TREASURE]:** The final room, filled with ancient relics. (Initially locked).

## Objects & Item Types
- **The Sun Gem [ID: ITEM_KEY_SUN, item_type: KEY]:** A glowing amber gemstone that fits into the pedestal.
- **Riddle Pedestal [ID: OBJ_PEDESTAL, item_type: STATIC]:** A stone pillar in the Hall of Wisdom that asks a riddle.
- **The Sealed Door [ID: EXIT_HALL_TO_TREASURE, item_type: EXIT]:** A heavy stone slab blocking the way to the Inner Sanctum. (**is_locked: true**).

## Main Quest: The Path of Wisdom
1. **Enter the Temple:** Find a way past the entrance statues.
2. **Solve the Riddle:** Interact with the **Riddle Pedestal** in the Hall of Wisdom. Solving the riddle grants the **Sun Gem**.
3. **Unlock the Sanctum:** Use the **Sun Gem** on the **Sealed Door** to unlock the path.

## Test Objectives
- Verify **Navigation Control**: Testing locked exits and movement restrictions.
- Verify **Item Keys**: Using specific items to change the state of an exit.
- Verify **Puzzle Logic**: Handling riddles and state changes in the world (e.g., an item appearing after an action).
- Verify **Exit Updates**: Ensuring `updated_exits` correctly unlocks the door.
