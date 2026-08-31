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
  { id: '/debug session', label: '/debug session', description: 'Open the debug inspector', category: 'debug' },
  { id: '/debug reveal_map', label: '/debug reveal_map', description: 'Reveal all locations on the map', category: 'debug' },
  { id: '/debug walkthrough', label: '/debug walkthrough', description: 'Reveal walkthrough for free', category: 'debug' },
  { id: '/debug log on', label: '/debug log on', description: 'Enable technical debug logs', category: 'debug' },
  { id: '/debug log off', label: '/debug log off', description: 'Disable technical debug logs', category: 'debug' },
  { id: '/debug on', label: '/debug on', description: 'Enable in-game debug commands & logs', category: 'debug' },
  { id: '/debug off', label: '/debug off', description: 'Disable in-game debug commands & logs', category: 'debug' },
  { id: '/debug npc drop_items', label: '/debug npc drop_items', description: 'Force all scene NPCs to drop all items', category: 'debug' },
  { id: '/debug item dynamic on', label: '/debug item dynamic on', description: 'Allow GM to generate items dynamically', category: 'debug' },
  { id: '/debug item dynamic off', label: '/debug item dynamic off', description: 'Restrict GM to pre-defined items only', category: 'debug' }
]

export function getFilteredCommands(query: string, debugEnabled: boolean): GameCommand[] {
  if (!query.startsWith('/')) return []
  const q = query.toLowerCase().slice(1).replace('/', '') // support query with or without slash after first
  let list = GAME_COMMANDS
  if (!debugEnabled) {
    list = list.filter(c => c.category !== 'debug')
  }
  
  if (!q) return list
  return list.filter(c => c.label.toLowerCase().includes(q) || (c.description && c.description.toLowerCase().includes(q)))
}
