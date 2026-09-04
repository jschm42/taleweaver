export interface GameCommand {
  id: string
  label: string
  description: string
  category: 'game' | 'debug'
}

export const GAME_COMMANDS: GameCommand[] = [
  { id: '/say', label: '/say <text>', description: 'Direct Speech (default)', category: 'game' },
  { id: '/sheet', label: '/sheet', description: 'Open your character sheet', category: 'game' },
  { id: '/inventory', label: '/inventory', description: 'View your items and equipment', category: 'game' },
  { id: '/map', label: '/map', description: 'View the world map', category: 'game' },
  { id: '/quests', label: '/quests', description: 'View active and completed quests', category: 'game' },
  { id: '/hint', label: '/hint', description: 'Get a hint for your next step (50 XP)', category: 'game' },
  { id: '/walkthrough', label: '/walkthrough', description: 'Open the adventure walkthrough', category: 'game' },
  { id: '/equip', label: '/equip', description: 'Equip an item from your inventory', category: 'game' },
  { id: '/unequip', label: '/unequip', description: 'Remove an equipped item', category: 'game' },
  { id: '/consume', label: '/consume', description: 'Use a consumable item', category: 'game' },
  { id: '/open', label: '/open', description: 'Open a container or door', category: 'game' },
  { id: '/read', label: '/read', description: 'Read a book, sign, or note', category: 'game' },
  // Debug Commands
  { id: '/debug on', label: '/debug on', description: 'Enable in-game debug mode & commands', category: 'debug' },
  { id: '/debug off', label: '/debug off', description: 'Disable in-game debug mode & commands', category: 'debug' },
  { id: '/debug session', label: '/debug session', description: 'Open the unified debug inspector panel', category: 'debug' },
  { id: '/debug npcs', label: '/debug npcs', description: 'Inspect all NPCs and their current stats & locations', category: 'debug' },
  { id: '/debug items', label: '/debug items', description: 'Inspect all items, states, and locations', category: 'debug' },
  { id: '/debug scenes', label: '/debug scenes', description: 'List all scenes in this session', category: 'debug' },
  { id: '/debug exits', label: '/debug exits', description: 'List all passages and lock statuses', category: 'debug' },
  { id: '/debug reveal_map', label: '/debug reveal_map', description: 'Reveal all locations on the world map', category: 'debug' },
  { id: '/debug walkthrough', label: '/debug walkthrough', description: 'Reveal adventure walkthrough for free', category: 'debug' },
  { id: '/debug unhide all', label: '/debug unhide all', description: 'Make all hidden entities in the adventure visible', category: 'debug' },
  { id: '/debug unhide', label: '/debug unhide <target>', description: 'Make a specific hidden entity visible', category: 'debug' },
  { id: '/debug heal', label: '/debug heal [npc_name] [amount]', description: 'Restore health of player or target NPC', category: 'debug' },
  { id: '/debug kill', label: '/debug kill <npc_name>', description: 'Instantly defeat an NPC', category: 'debug' },
  { id: '/debug open_exit', label: '/debug open_exit <exit_id>', description: 'Unlock a passage or door', category: 'debug' },
  { id: '/debug exp', label: '/debug exp <amount>', description: 'Grant experience points to the hero', category: 'debug' },
  { id: '/debug awards', label: '/debug awards', description: 'Instantly claim all adventure awards', category: 'debug' },
  { id: '/debug game_won', label: '/debug game_won', description: 'Trigger the adventure victory condition', category: 'debug' },
  { id: '/debug game_over', label: '/debug game_over', description: 'Trigger the game over condition', category: 'debug' },
  { id: '/debug quest_finished', label: '/debug quest_finished', description: 'Mark current quest as completed', category: 'debug' },
  { id: '/debug log on', label: '/debug log on', description: 'Enable technical debug logs in chat', category: 'debug' },
  { id: '/debug log off', label: '/debug log off', description: 'Disable technical debug logs in chat', category: 'debug' },
  { id: '/debug npc drop_items', label: '/debug npc drop_items', description: 'Force scene NPCs to drop all items', category: 'debug' },
  { id: '/debug delete_item', label: '/debug delete_item <item_key>', description: 'Remove an item from your inventory', category: 'debug' },
  { id: '/debug engine', label: '/debug engine', description: 'Display engine diagnostics and version', category: 'debug' },
  { id: '/debug win_fight', label: '/debug win_fight', description: 'Instantly win the active combat', category: 'debug' },
  { id: '/debug loose_fight', label: '/debug loose_fight', description: 'Instantly lose the active combat', category: 'debug' },
]

export function getFilteredCommands(query: string, debugEnabled: boolean): GameCommand[] {
  if (!query.startsWith('/')) return []
  const q = query.toLowerCase().slice(1).replace('/', '').trim() // support query with or without slash after first
  let list = GAME_COMMANDS

  if (!debugEnabled) {
    // If debug is off, keep game commands plus activation commands so user can discover how to enable debug
    list = list.filter(
      c => c.category !== 'debug' || c.id === '/debug on' || c.id === '/debug log on'
    )
  }

  if (!q) return list
  return list.filter(
    c => c.label.toLowerCase().includes(q) || (c.description && c.description.toLowerCase().includes(q))
  )
}
