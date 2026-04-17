# Adventure: Kitchen Crisis - The Sitcom Edition

## Story Idea
"The Miller Family Meltdown." It's 18:00 on a Tuesday. Grandma is coming for dinner in one hour, and the household is a disaster zone. A laugh track punctuates every failure. You play as the "Last Sane Person" (or the biggest chaos agent) trying to get the legendary Casserole ready while managing a cast of eccentric family members and a very persistent neighbor.

## Tone
**90s Sitcom / Absurd Comedy:** Bright colors, high stakes over trivial things, and frequent "Oh you!" moments. Every action should feel like a scene transition. Use snappy English dialogue.

## Scenes (Locations)
1. **The Modern Kitchen [ID: MODERN_KITCHEN]:** The heart of the chaos. Cluttered, bright, and smells like impending burnt cheese.
2. **The Living Room [ID: LIVING_ROOM]:** Dominated by a massive TV and a sofa that swallows small objects.
3. **The Hallway [ID: HALLWAY]:** A narrow transition zone where the 'Wall of Honor' hangs.
4. **The Master Bedroom [ID: MASTER_BEDROOM]:** A strictly forbidden zone containing the 'heavy-duty stuff'.
5. **The Mystery Basement [ID: MYSTERY_BASEMENT, is_hidden: true]:** A dark abyss that requires a key.

## Characters (NPCs)
- **Dad Arthur [ID: DAD_ARTHUR]:** (NPC) Wearing a Hawaiian shirt and trying to "fix" the sink with a banana.
- **Mom Beatrice [ID: MOM_BEATRICE]:** (NPC) Trying to close a billion-dollar deal while holding a laundry basket.
- **Grumpy Grandpa Joe [ID: GRAMPS_JOE]:** (NPC) Complaining about the "lack of grit" in modern furniture.
- **Neighbor Kevin [ID: NEIGHBOR_KEVIN]:** (NPC) Periodically bursts through the back door asking to "borrow" or "sample" things.
- **Mittens the Cat [ID: CAT_MITTENS]:** (NPC) A chaotic orange cat (ANIMAL, MOVABLE) that weaves between everyone's legs.
- **Gloop the Goldfish [ID: GOLDFISH_GLOOP]:** (NPC) Staring judgmentally from a bowl (ANIMAL, STATIONARY) on the counter.

## Objects & Item Types (English)

### Consumables
- **Forbidden Casserole [ID: CASSEROLE, item_type: CONSUMABLE]:** Mom's prize possession.
- **Extra-Strength Espresso [ID: ESPRESSO, item_type: CONSUMABLE]:** Liquid energy.

### Weapons & Tools
- **The Golden Spatula [ID: GOLDEN_SPATULA, item_type: WEAPON]:** Good for flipping burgers or neighbor suppression.
- **Leaky WD-40 [ID: WD40, item_type: TOOL]:** Used to fix the Squeaky Floor.

### Wearables
- **Dad's Lucky Power Tie [ID: POWER_TIE, item_type: WEARABLE, wearable_slots: ["Neck"]]:** Increases Charisma.
- **Furry Rabbit Slippers [ID: RABBIT_SLIPPERS, item_type: WEARABLE, wearable_slots: ["Feet"]]:** Grants Stealth.

### Keys & Readables
- **The Basement Key [ID: BASEMENT_KEY, item_type: KEY, is_hidden: true]:** Hidden behind the 'Wedding Photo' in the Hallway.
- **The Secret Diary [ID: SECRET_DIARY, item_type: READABLE]:** Contains deep family secrets.

### Combinables
- **Electronic Remote [ID: TV_REMOTE, item_type: COMBINABLE]:** Dead without batteries.
- **AA Batteries [ID: AA_BATTERIES, item_type: COMBINABLE, is_hidden: true]:** Hidden in the Sofa.

## Main Quest: The Remote Hack
1. Search the **Sofa** to discover the **AA Batteries**.
2. **COMBINE** the **Electronic Remote** with the **AA Batteries**.
3. Use the **Remote** on the **TV** to distract Grandpa Joe.
