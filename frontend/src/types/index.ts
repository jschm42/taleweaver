/** A single chat message displayed in the chat window. */
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
}

/** Character sheet snapshot pushed by the server after every action. */
export interface CharacterSheet {
  name: string
  role?: string | null
  description?: string | null
  profile_image?: string | null
  hp: number
  stamina: number
  mana: number
  stats: Record<string, number>
  inventory: InventoryItem[]
  equipment: Record<string, InventoryItem | null>
  status_effects: string[]
  in_game_time: number  // minutes elapsed in-game
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
  id?: string
  title: string
  context?: string
  image_url?: string | null
  strict_rules?: boolean
  generate_npc_images?: boolean
  generate_item_images?: boolean
  heartbeat_enabled?: boolean
}

/** WebSocket message types received from the server. */
export type WsIncoming =
  | { role: 'assistant' | 'system'; content: string }
  | { type: 'sheet_update'; data: CharacterSheet }
  | { type: 'game_over'; reason: string }
  | { type: 'map_update'; mermaid: string }
  | { type: 'image_update'; url: string }
