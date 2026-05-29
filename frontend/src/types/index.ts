export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'thought'
  content: string
  timestamp: Date
  itemIds?: string[]
}

/** Character sheet snapshot pushed by the server after every action. */
export interface CharacterSheet {
  name: string
  adventure_title?: string | null
  adventure_version?: string | null
  adventure_id?: string | null
  role?: string | null
  description?: string | null
  profile_image?: string | null
  hp: number
  max_hp?: number
  stamina: number
  max_stamina?: number
  mana: number
  max_mana?: number
  exp: number
  strength: number
  intelligence: number
  wisdom: number
  dexterity: number
  charisma: number
  armor_class: number
  stats: Record<string, number>
  inventory: InventoryItem[]
  equipment: Record<string, InventoryItem | null>
  status_effects: string[]
  in_game_time: number  // minutes elapsed in-game
  start_datetime?: string | null
  current_scene?: string | null
  scene_id?: string | null
  rule_enforcement_mode?: 'rpg' | 'story' | 'chat'
  adventure_tone?: string | null
  is_debug_enabled?: boolean
  debug_mode?: boolean
  agent_active?: boolean
  agent_monkey_mode?: boolean
}

export interface InventoryItem {
  name: string
  id?: string
  image_url?: string | null
  item_type?: string
  hp?: number
  max_hp?: number
  stamina?: number
  max_stamina?: number
  mana?: number
  max_mana?: number
  stat_modifiers?: Record<string, number>
  [key: string]: unknown
}

export interface CombatLogEntry {
  round: number
  type: string
  text: string
  timestamp?: string
}

export interface CombatState {
  active: boolean
  round: number
  turn: 'player' | 'enemy'
  player: {
    name: string
    image_url?: string | null
    hp: number
    max_hp?: number
    ac?: number
  }
  enemy: {
    id: string
    name: string
    image_url?: string | null
    hp: number
    max_hp?: number
    armor_mod?: number
    dexterity_mod?: number
    inventory?: InventoryItem[]
  }
  loot_pending?: boolean
  loot_items?: InventoryItem[]
  outcome?: string | null
  status_note?: string | null
  log?: CombatLogEntry[]
}

export interface MapNode {
  id: string
  label: string
  description?: string
  image_url?: string | null
  [key: string]: unknown
}

export interface MapEdge {
  from: string
  to: string
  label?: string
  is_locked?: boolean
  [key: string]: unknown
}

export interface WorldMapData {
  nodes: Record<string, MapNode>
  edges: MapEdge[]
  current_scene_id: string | null
}

/** Summary of a game session returned by GET /api/adventures. */
export interface GameSession {
  game_id: string
  template_id?: string
  adventure_id: string
  avatar_id: string
  profile_image?: string | null
  adventure_title: string
  adventure_version?: string | null
  image_url: string | null
  scene_id: string
  current_scene_name?: string | null
  in_game_time: number
  is_paused: boolean
  is_ready: boolean
  creation_status?: string | null
  creation_error?: string | null
  progress?: number
  quest_count?: number
  completed_quest_count?: number
  award_count?: number
  earned_award_count?: number
  created_at?: string
  status?: 'active' | 'archived' | 'completed' | 'game_over' | null
  status_note?: string | null
  copied_from_id?: string | null
}

export interface SessionCheckpoint {
  id: string
  session_id: string
  message_index: number
  trigger_reason: 'SCENE_CHANGE' | 'QUEST_UPDATE' | 'AWARD_GRANTED'
  title: string
  created_at: string
}

export interface RestoreCheckpointResult {
  status: 'restored'
  checkpoint_id: string
  deleted_messages: number
}

export interface AdventureTemplateSummary {
  template_id: string
  title: string
  teaser?: string | null
  version?: string | null
  image_url: string | null
  is_ready: boolean
  creation_status?: string | null
  creation_error?: string | null
  selected_tone?: CatalogTile | string | null
  progress?: number
  quest_count?: number
  completed_quest_count?: number
  active_game_id?: string | null
  has_active_session?: boolean
  is_paused?: boolean
  scene_id?: string | null
  current_scene_name?: string | null
  cover_source_adventure_id?: string | null
  cover_source_adventure_name?: string | null
}

/** Payload for creating a new adventure. */
export interface CreateAdventurePayload {
  id?: string
  title: string
  context?: string
  version?: string
  image_url?: string | null
  strict_rules?: boolean
  rule_enforcement_mode?: 'rpg' | 'story' | 'chat'
  generate_npc_images?: boolean
  generate_item_images?: boolean
  generate_scene_images?: boolean
  automatic_npc_voice_assignment?: boolean
  selected_image_styles?: CatalogTile[]
  selected_tone?: CatalogTile | string | null
  min_scenes?: number | null
  max_scenes?: number | null
  min_items?: number | null
  max_items?: number | null
  container_generation_enabled?: boolean
  min_containers?: number | null
  max_containers?: number | null
  text_log_generation_enabled?: boolean
  min_text_logs?: number | null
  max_text_logs?: number | null
  clock_enabled?: boolean
  heartbeat_enabled?: boolean
  automatic_cover_generation?: boolean
  time_per_turn?: number
  pacing_minutes?: number
  pacing?: Record<string, unknown>
  original_manifest?: Record<string, unknown>
  award_generation_enabled?: boolean
  min_awards?: number
  max_awards?: number
  allow_dynamic_items?: boolean
  can_damage_npcs?: boolean
  npcs_can_damage_protagonist?: boolean
  cover_source_adventure_id?: string
  cover_source_adventure_name?: string
  cover_similarity_percent?: number
  allow_reuse_source_assets?: boolean
}

export interface CatalogTile {
  id: string
  name: string
  description?: string
  instruction?: string
  image_url?: string | null
}

export interface StoryIdeaSuggestionPayload {
  title?: string
  story_idea?: string
  selected_tone?: CatalogTile | null
  rule_enforcement_mode?: 'rpg' | 'story' | 'chat'
  language?: string
}

export interface StoryIdeaSuggestionResponse {
  title: string
  story_idea: string
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
  | { role: 'assistant' | 'system' | 'thought'; content: string }
  | { type: 'sheet_update'; data: CharacterSheet }
  | { type: 'game_over'; reason: string }
  | { type: 'map_update'; map_data?: WorldMapData }
  | { type: 'image_update'; url: string }

export interface Award {
  key: string
  title: string
  description: string
  tier: 'bronze' | 'silver' | 'gold'
  requirement: string
  is_earned?: boolean
}

export interface EarnedAward extends Award {
  adventure_id: string
  adventure_title: string
  session_id: string
  earned_at: string
}

