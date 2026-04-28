# Adventure: The Rat-Infested Cellar (RPG Mode Test)

## Story Idea
You have been tossed into the damp cellar of "The Broken Cask" tavern. The air smells of mold and stale ale. Squeaking sounds from the shadows suggest you are not alone. You need to find your gear and deal with the vermin if you want to see the daylight again.

## Tone
**Gritty & Dark:** Low visibility, dripping pipes, and the constant threat of small, sharp teeth.

## Scenes (Locations)
1. **The Damp Cellar [ID: CELLAR_01]:** A dark, cramped basement filled with rotting barrels and cobwebs.

## Characters (NPCs)
- **Giant Rats [ID: NPC_RAT_01, NPC_RAT_02]:** Aggressive, oversized rodents with red glowing eyes. They are hungry and territorial. (HP: 10, DMG: 1d4).

## Objects & Item Types

### Weapons & Combat Gear
- **Rusty Shortsword [ID: ITEM_SWORD_RUSTY, item_type: WEAPON, stat_modifier_strength: 2]:** Found leaning against a wine rack. It's chipped but still sharp enough.
- **Leather Armor [ID: ITEM_ARMOR_LEATHER, item_type: WEARABLE, wearable_slots: ["Chest"], stat_modifier_endurance: 1]:** Tucked inside an open crate.

### Consumables
- **Small Healing Potion [ID: ITEM_POTION_HEAL, item_type: CONSUMABLE]:** A vial of red liquid found in a hidden wall niche. Restores 20 HP.

### Room Interactions (Static)
- **Heavy Wine Cask [ID: OBJ_CASK, item_type: STATIC]:** A massive barrel blocking the path to the hidden niche. Requires a **Strength Check (DC 10)** to move.

## Main Quest: Exterminate and Gear Up
1. **Scavenge for Equipment:** Find the **Rusty Shortsword** and **Leather Armor** to increase your chances.
2. **The Strength Test:** Move the **Heavy Wine Cask** to reveal the healing potion.
3. **Slay the Rats:** Defeat the **Giant Rats** to clear the room.

## Test Objectives
- Verify **Inventory Management**: Picking up, equipping, and using items.
- Verify **Combat Mechanics**: Dice rolls for attacks and damage.
- Verify **Stat Modifiers**: Ensure the sword and armor correctly modify the protagonist's rolls.
- Verify **Skill Checks**: Test the Strength check for moving the cask.
