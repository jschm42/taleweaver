export interface ChatMessage {
  id?: string
  role: 'user' | 'assistant' | 'system' | 'thought' | 'license_info'
  content: string
  timestamp: Date
  itemIds?: string[]
  /** Scene/sequence the message belongs to; the story feed shows one page per scene/sequence. */
  scene_id?: string | null
  sequence_id?: string | null
}

/** Character sheet snapshot pushed by the server after every action. */
export interface CharacterSheet {
  name: string
  adventure_title?: string | null
  adventure_version?: string | null
  creator?: string | null
  copyright?: string | null
  license?: string | null
  license_url?: string | null
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
  in_game_time: number  // minutes or units elapsed in-game
  start_datetime?: string | null
  time_system?: 'calendar' | 'units' | 'relative' | string
  time_config?: Record<string, any> | null
  time_per_turn?: number
  max_time_per_turn?: number | null
  current_scene?: string | null
  scene_id?: string | null
  rule_enforcement_mode?: 'rpg' | 'story' | 'chat'
  adventure_tone?: string | { id?: string; name?: string } | null
  /** Author-defined dialog skin (validated server-side). */
  ui_theme?: { skin?: string | null; accent?: string | null } | null
  is_debug_enabled?: boolean
  debug_mode?: boolean
  special_actions?: SpecialAttack[]
  unlocked_actions?: string[]
  agent_active?: boolean
  agent_monkey_mode?: boolean
  agent_allow_walkthrough?: boolean
  agent_step_by_step?: boolean
  agent_personality?: string
  agent_custom_personality?: string
  max_memory_turns?: number
  enable_history_compression?: boolean
  narration_style?: 'terse' | 'dialogue' | 'balanced' | 'rich' | 'epic' | string
  /** Dialog skin the player picked for this session; "auto" follows the adventure. */
  ui_skin?: string | null
  compressed_history?: any
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

export type SpecialCategory = 'MAGIC' | 'MELEE' | 'RANGED' | 'SOCIAL' | 'OTHER'
export type CombatStat =
  | 'hp' | 'mana' | 'stamina'
  | 'strength' | 'dexterity' | 'intelligence' | 'wisdom' | 'charisma' | 'armor_class'
export type SuccessStat = 'strength' | 'dexterity' | 'intelligence' | 'wisdom' | 'charisma'

/** One stat change of a special attack, e.g. `{ target: 'target', stat: 'hp', amount: '-2d6' }`. */
export interface SpecialEffect {
  target: 'target' | 'self'
  stat: CombatStat
  amount: string
}

/** Special attack definition as stored on the protagonist (stats) or an NPC (metadata_json). */
export interface SpecialAttack {
  id: string
  name: string
  description?: string
  action_type: 'ATTACK' | 'HEAL' | 'UTILITY'
  category?: SpecialCategory | null
  cost_type?: 'mana' | 'stamina' | null
  cost?: number | null
  mana_cost?: number
  success_stat?: SuccessStat | null
  difficulty?: number | null
  effects?: SpecialEffect[]
  damage_type?: 'FIXED' | 'ROLLED' | null
  damage_value?: string | null
  outcome_description?: string | null
  is_locked?: boolean
  unlock_condition_type?: 'READ_ITEM' | 'FIND_ITEM' | null
  unlock_condition_target?: string | null
  unlock_required_item_id?: string | null
  unlock_required_scene_id?: string | null
  unlock_required_defeated_npc_id?: string | null
  unlock_guard_expression?: string | null
  unlock_text?: string | null
  on_success_script?: string | null
  on_success_text?: string | null
  on_failure_script?: string | null
  on_failure_text?: string | null
}

/** Special attack as normalized by the combat engine (always has cost, category and effects). */
export interface NormalizedSpecialAttack extends SpecialAttack {
  category: SpecialCategory
  cost_type: 'mana' | 'stamina'
  cost: number
  success_stat: SuccessStat
  effects: SpecialEffect[]
  targets_enemy: boolean
  locked?: boolean
  has_unlock_guard?: boolean
}

export interface AppliedEffect {
  entity: string
  name?: string
  stat: CombatStat
  delta: number
  roll?: string
}

/** Structured payload attached to combat log entries; drives the arena animations. */
export interface CombatEventData {
  kind:
    | 'attack' | 'special' | 'initiative' | 'turn' | 'rest' | 'consume' | 'run'
    | 'event' | 'engage' | 'defeat' | 'fled' | 'victory' | 'game_over'
  actor?: string | null
  target?: string | null
  entity?: string
  label?: string
  action_name?: string
  category?: SpecialCategory
  stat?: string
  rolled?: boolean
  d20?: number
  modifier?: number
  total?: number
  dc?: number
  success?: boolean
  crit?: boolean
  fumble?: boolean
  cost?: { type: 'mana' | 'stamina'; amount: number }
  effects?: AppliedEffect[]
  order?: InitiativeEntry[]
  round?: number
  xp?: number
}

export interface CombatLogEntry {
  round: number
  type: string
  text: string
  timestamp?: string
  data?: CombatEventData
}

export interface InitiativeEntry {
  id: string
  name: string
  roll: number
  bonus: number
  total: number
}

export interface CombatantState {
  id: string
  name: string
  image_url?: string | null
  hp: number
  max_hp?: number
  stamina?: number
  max_stamina?: number
  mana?: number
  max_mana?: number
  ac?: number
  stats?: Partial<Record<SuccessStat, number>>
  modifiers?: Partial<Record<CombatStat, number>>
}

export interface CombatEnemyState extends CombatantState {
  armor_mod?: number
  dexterity_mod?: number
  inventory?: InventoryItem[]
  engaged?: boolean
  defeated?: boolean
  fled?: boolean
  special_actions?: NormalizedSpecialAttack[]
}

export interface CombatPlayerState extends CombatantState {
  special_actions?: NormalizedSpecialAttack[]
}

export interface CombatState {
  active: boolean
  round: number
  turn: 'player' | 'enemy'
  active_actor?: string | null
  player: CombatPlayerState
  /** Current target (kept for single-enemy consumers). */
  enemy: CombatEnemyState
  enemies?: CombatEnemyState[]
  target_id?: string | null
  initiative?: InitiativeEntry[]
  turn_index?: number
  xp_gained?: number
  loot_pending?: boolean
  loot_items?: InventoryItem[]
  outcome?: string | null
  status_note?: string | null
  log?: CombatLogEntry[]
}

/** One answer of a script-opened choice dialog; `index` is the author-defined option position. */
export interface DialogOption {
  index: number
  label: string
}

/** Choice dialog opened by a script (`tw.dialog.choose`) that awaits the player's answer. */
export interface PendingDialog {
  id: string
  prompt: string
  speaker?: string | null
  options: DialogOption[]
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
  /** Title of the session's active sequence (chapter); null when the adventure has none. */
  current_sequence_name?: string | null
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
  /** When the player last opened this session; falls back to created_at when missing. */
  last_played_at?: string | null
  status?: 'active' | 'archived' | 'completed' | 'game_over' | null
  status_note?: string | null
  copied_from_id?: string | null
  max_memory_turns?: number
  enable_history_compression?: boolean
  narration_style?: 'terse' | 'dialogue' | 'balanced' | 'rich' | 'epic' | string
  is_legacy_format?: boolean
  rule_enforcement_mode?: 'rpg' | 'story' | 'chat' | string
  selected_image_styles?: CatalogTile[] | any[]
  selected_tone?: CatalogTile | string | null
}

export interface WorldMemory {
  description: string
  emotion?: 'positive' | 'negative' | 'neutral'
  scope?: 'local' | 'global'
  npc_id?: string
  scene_id?: string
  [key: string]: unknown
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
  creator?: string | null
  copyright?: string | null
  license?: string | null
  license_url?: string | null
  image_url: string | null
  is_ready: boolean
  creation_status?: string | null
  creation_error?: string | null
  selected_tone?: CatalogTile | string | null
  selected_image_styles?: CatalogTile[] | any[]
  rule_enforcement_mode?: 'rpg' | 'story' | 'chat' | string
  progress?: number
  quest_count?: number
  completed_quest_count?: number
  active_game_id?: string | null
  has_active_session?: boolean
  /** Last time the session behind active_game_id was opened. */
  last_played_at?: string | null
  is_paused?: boolean
  scene_id?: string | null
  current_scene_name?: string | null
  cover_source_adventure_id?: string | null
  cover_source_adventure_name?: string | null
  has_update?: boolean
  available_version?: string | null
  has_sequences?: boolean
  is_legacy_format?: boolean
  can_start?: boolean
}

/** Payload for creating a new adventure. */
export interface CreateAdventurePayload {
  id?: string
  title: string
  context?: string
  version?: string
  creator?: string | null
  copyright?: string | null
  license?: string | null
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
  scripts_generation_enabled?: boolean
  min_containers?: number | null
  max_containers?: number | null
  text_log_generation_enabled?: boolean
  min_text_logs?: number | null
  max_text_logs?: number | null
  clock_enabled?: boolean
  heartbeat_enabled?: boolean
  automatic_cover_generation?: boolean
  time_system?: 'calendar' | 'units' | 'relative' | string
  time_config?: Record<string, any> | null
  time_per_turn?: number
  pacing_minutes?: number
  max_time_per_turn?: number | null
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
  skip_generation?: boolean
  max_memory_turns?: number
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

export interface BlueprintIssue {
  line: number
  message: string
  severity: 'error' | 'warning'
}

export interface BlueprintValidationResult {
  has_tags: boolean
  errors: BlueprintIssue[]
  warnings: BlueprintIssue[]
  counts: Record<string, number>
}

export interface GeneratorSurprisePresetPayload {
  available_tones?: string[]
  available_styles?: string[]
  language?: string
}

export interface GeneratorSurprisePresetResponse {
  title: string
  story_idea: string
  selected_tone?: string | null
  selected_style?: string | null
  rule_enforcement_mode: 'rpg' | 'story' | 'chat'
  generate_scene_images: boolean
  generate_npc_images: boolean
  generate_item_images: boolean
  clock_enabled: boolean
  time_system: 'calendar' | 'units'
  day_label: string
  initial_day: number
  start_time: string
  time_format: '24h' | '12h'
  pacing_minutes: number
  unit_name: string
  initial_units: number
  units_per_turn: number
  min_scenes?: number | null
  max_scenes?: number | null
  min_quests?: number | null
  max_quests?: number | null
}

/** Minimal import payload type for .ADV files (frontend-side). */
export interface AdventureImportPayload {
  version: string
  creator?: string
  copyright?: string
  license?: string
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
  max_memory_turns?: number
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
  tier: 'bronze' | 'silver' | 'gold' | 'negative'
  requirement: string
  is_earned?: boolean
}

export interface EarnedAward extends Award {
  adventure_id: string
  adventure_title: string
  session_id: string
  earned_at: string
}


/** A voice from the curated ElevenLabs voice list (backend/core/elevenlabs_voices.json). */
export interface TtsVoice {
  id: string
  name: string
  gender: string | null
  age: string
  accent: string
  description: string
  good_for: string[]
}

export interface TtsVoiceList {
  provider: string
  /** Only ElevenLabs gives characters their own voices; Gemini uses the narrator voice. */
  supports_npc_voices: boolean
  voices: TtsVoice[]
}
