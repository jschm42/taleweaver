# In-Game Debugging Guide

TaleWeaver provides a suite of administrative commands to help developers and testers inspect and manipulate the game state directly from the chat interface.

## Activation

To enable debug commands, you must set the following environment variable in your `.env` file:

```env
TALEWEAVER_DEBUG_ENABLED=True
```

If this is not set to `True`, all `/debug` commands will be ignored or return an error for security reasons.

## Command Syntax

All debug commands are prefixed with `/debug`.

| Command | Description |
|---------|-------------|
| `/debug engine` | Shows server diagnostics (Version, OS, Session ID, etc.). |
| `/debug scenes` | Lists all scenes in the current adventure with their IDs. |
| `/debug npcs` | Lists all NPCs with IDs and their current location. |
| `/debug items` | Lists all items (inventory and world) with IDs. |
| `/debug exits` | Lists all exits, their destinations, and lock status. |
| `/debug walkthrough` | Unlocks the walkthrough modal for free and shows it in chat. |
| `/debug game_won` | Forces the session into a "Won" state. |
| `/debug game_over` | Forces the session into a "Lost" state. |
| `/debug quest_finished` | Completes the currently active quest. |
| `/debug claim_awards` | Grants all possible awards in the adventure. |
| `/debug exp [amount]` | Grants the specified amount of XP to the avatar. |
| `/debug kill [NPC_NAME\|ID]` | Removes an NPC from the world. |
| `/debug delete_item [ITEM_KEY\|ID]` | Removes an item from the world or inventory. |
| `/debug open_exit [EXIT_ID]` | Unlocks a specific exit. |
| `/debug szene` | Shows technical details of the current scene. |
| `/debug map` | Shows summary counts of world elements. |
| `/debug log on/off` | Toggles detailed engine logging in the console. |

## Practical Examples

### 1. Unlocking the Walkthrough
If you want to check the adventure's solution without spending XP:
`user: /debug walkthrough`

### 2. Resolving Entity Conflicts
If an NPC is blocking a path and you want to remove it:
`user: /debug kill Grog the Gatekeeper`

### 3. Finding an Exit ID
If you need to force open a door but don't know the ID:
`user: /debug exits`
(Then use the ID found)
`user: /debug open_exit exit_42`

### 4. Testing Reward UI
To see how the game looks when won:
`user: /debug game_won`
