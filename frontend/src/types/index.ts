/** A single chat message displayed in the chat window. */
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
}

/** Character sheet snapshot pushed by the server after every action. */
export interface CharacterSheet {
  name: string
  hp: number
  stamina: number
  mana: number
  stats: Record<string, number>
  inventory: InventoryItem[]
  equipment: Record<string, InventoryItem | null>
  status_effects: string[]
}

export interface InventoryItem {
  name: string
  stat_modifiers?: Record<string, number>
  [key: string]: unknown
}

/** Summary of a game session returned by GET /api/adventures. */
export interface GameSession {
  game_id: string
  adventure_id: string
  avatar_id: string
  scene_id: string
  in_game_time: number
  is_paused: boolean
}

/** Payload for creating a new adventure. */
export interface CreateAdventurePayload {
  title: string
  avatar_name: string
  strict_rules?: boolean
  heartbeat_enabled?: boolean
  heartbeat_interval?: number
}

/** WebSocket message types received from the server. */
export type WsIncoming =
  | { role: 'assistant' | 'system'; content: string }
  | { type: 'sheet_update'; data: CharacterSheet }
  | { type: 'game_over'; reason: string }
