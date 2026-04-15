export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  itemIds?: string[]
}

/** Character sheet snapshot pushed by the server after every action. */
export interface CharacterSheet {
  name: string
  adventure_title?: string | null
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
  start_datetime?: string | null
  current_scene?: string | null
  scene_id?: string | null
}

export interface InventoryItem {
  name: string
  image_url?: string | null
  item_type?: string
  stat_modifiers?: Record<string, number>
  [key: string]: unknown
}

/** Summary of a game session returned by GET /api/adventures. */
export interface GameSession {
  game_id: string
  adventure_id: string
  avatar_id: string
  adventure_title: string
  image_url: string | null
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
  generate_scene_images?: boolean
  heartbeat_enabled?: boolean
  automatic_cover_generation?: boolean
  time_per_turn?: number
  pacing?: Record<string, unknown>
  original_manifest?: Record<string, unknown>
}

/** Minimal import payload type for .ADV files (frontend-side). */
export interface AdventureImportPayload {
  version: string
  id?: string
  title: string
  subtitle?: string
  description?: string
  story_idea?: string
  tone?: string
  image_style?: string
  // optional lists are free-form on the frontend
  characters?: any[]
  scenes?: any[]
  items?: any[]
  objects?: any[]
  protagonist?: any
  pacing?: {
    scene_length?: 'short' | 'normal' | 'long'
    event_frequency?: 'low' | 'normal' | 'high'
    notes?: string
  }
  time_per_turn?: number
  start_date?: string
  start_time?: string
  start_datetime?: string
  metadata?: Record<string, unknown>
  generate_npc_images?: boolean
  generate_item_images?: boolean
  automatic_cover_generation?: boolean
}

/** WebSocket message types received from the server. */
export type WsIncoming =
  | { role: 'assistant' | 'system'; content: string }
  | { type: 'sheet_update'; data: CharacterSheet }
  | { type: 'game_over'; reason: string }
  | { type: 'map_update'; mermaid: string }
  | { type: 'image_update'; url: string }
