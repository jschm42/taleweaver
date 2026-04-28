# Adventure: Market Day in Oakhaven (Story Mode Test)

## Story Idea
It's a sunny day in Oakhaven, but Merchant Alex is in a panic. His precious signet ring has gone missing. You suspect the local beggar, Thom, might have seen something, but getting him to talk will require either a silver tongue or a full stomach.

## Tone
**Bright & Lively:** A bustling town square with colorful stalls, the smell of fresh bread, and the murmur of many voices.

## Scenes (Locations)
1. **Market Square [ID: MARKET_SQUARE]:** The heart of the town, filled with merchants and shoppers.
2. **The Whistling Pig Inn [ID: INN_WHISTLING_PIG]:** A cozy tavern where locals gather to gossip.
3. **Back Alley [ID: STREET_BACKALLEY]:** A narrow, shadowed passage behind the market.

## Characters (NPCs)
- **Merchant Alex [ID: NPC_ALEX]:** A nervous trader who lost his ring. He is willing to pay well for its return.
- **Beggar Thom [ID: NPC_THOM]:** A scruffy man living in the back alley. He knows more than he lets on.
- **Innkeeper Bella [ID: NPC_BELLA]:** A sharp-witted woman who knows everyone's business.

## Objects & Item Types
- **Alex's Signet Ring [ID: ITEM_SIGNET_RING, item_type: QUEST_ITEM]:** A gold ring with a crest. Currently in Thom's possession.
- **Bowl of Hearty Stew [ID: ITEM_STEW, item_type: CONSUMABLE]:** Can be bought from Bella at the inn.

## Main Quest: The Lost Signet
1. **The Investigation:** Talk to **Merchant Alex** to accept the quest.
2. **Gather Intel:** Visit the **Whistling Pig Inn** and ask **Bella** about suspicious activity.
3. **The Confrontation:** Find **Thom** in the **Back Alley**. Use a **Charisma Check (DC 12)** to convince him to talk, or give him a **Bowl of Hearty Stew**.
4. **The Reward:** Return the ring to **Alex**.

## Awards
- **Honest Soul [KEY: AWARD_HONEST_SOUL, tier: "silver"]:** Awarded for returning the ring without asking for extra payment.

## Test Objectives
- Verify **NPC Interactions**: Handling conversations with multiple NPCs.
- Verify **Quest Progression**: Moving from "open" to "completed".
- Verify **Award Triggering**: Ensuring the award is granted upon completion.
- Verify **Social Mechanics**: Using Charisma checks or item bribes to progress.
