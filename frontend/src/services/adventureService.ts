import { API_BASE, authHeaders } from '@/services/http'
import { isNpcEntity, isObjectEntity, mergeUniqueById } from '@/utils/editor_utils'

export interface Adventure {
  id: string
  title: string
  teaser?: string
  version?: string
  original_prompt?: string
  rule_enforcement_mode: 'rpg' | 'story' | 'chat'
  time_per_turn: number
  min_scenes: number | null
  max_scenes: number | null
  min_items?: number | null
  max_items?: number | null
  container_generation_enabled?: boolean
  min_containers?: number | null
  max_containers?: number | null
  text_log_generation_enabled?: boolean
  min_text_logs?: number | null
  max_text_logs?: number | null
  awards?: any[]
  allow_dynamic_items: boolean
  can_damage_npcs: boolean
  npcs_can_damage_protagonist: boolean
  plot?: string
  rules?: string
  intro_text?: string
  walkthrough?: string
  completed_condition?: string
  gameover_condition?: string
  tts_director_notes?: string
  selected_image_styles?: any[]
  selected_tone?: any
  is_adventure_generator?: boolean
  creation_error?: string
  image_url?: string
  cover_source_adventure_id?: string | null
  cover_source_adventure_name?: string | null
  cover_similarity_percent?: number
  allow_reuse_source_assets?: boolean
}

export interface AdventureFormData {
  title: string
  teaser: string
  version: string
  original_prompt: string
  rule_enforcement_mode: 'rpg' | 'story' | 'chat'
  time_per_turn: number
  min_scenes: number | null
  max_scenes: number | null
  min_items: number | null
  max_items: number | null
  container_generation_enabled: boolean
  min_containers: number | null
  max_containers: number | null
  text_log_generation_enabled: boolean
  min_text_logs: number | null
  max_text_logs: number | null
  awards: any[]
  allow_dynamic_items: boolean
  can_damage_npcs: boolean
  npcs_can_damage_protagonist: boolean
  plot: string
  rules: string
  intro_text: string
  walkthrough: string
  completed_condition: string
  gameover_condition: string
  tts_director_notes: string
  selected_style_id: string
  selected_tone_id: string
  is_adventure_generator: boolean
  cover_source_adventure_id?: string
  cover_source_adventure_name?: string
  cover_similarity_percent?: number
  allow_reuse_source_assets?: boolean
}

export interface CatalogData {
  image_styles_catalog: any[]
  tone_catalog: any[]
  tts_settings?: {
    voice_catalog?: any[]
    voice_list?: string[]
  }
}

export interface DebugPayload {
  adventure?: Adventure
  protagonist?: any
  npcs?: any[]
  objects?: any[]
  scenes?: any[]
  entities_all?: any[]
}

/**
 * Service for adventure data operations and API calls
 */
export const adventureService = {
  async fetchAdventure(adventureId: string): Promise<Adventure> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}`, {
      headers: authHeaders(false),
    })
    if (!res.ok) throw new Error('Failed to load adventure configuration.')
    return res.json()
  },

  async fetchDebugInfo(adventureId: string): Promise<DebugPayload> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/assets`, {
      headers: authHeaders(false),
    })
    if (!res.ok) {
      throw new Error('Failed to load world assets/debug data.')
    }
    return res.json()
  },

  async fetchCatalogs(): Promise<CatalogData> {
    const res = await fetch(`${API_BASE}/settings`, {
      headers: authHeaders(false),
    })
    if (!res.ok) throw new Error('Failed to fetch catalogs')
    return res.json()
  },

  async updateAdventure(adventureId: string, data: Partial<AdventureFormData>): Promise<Adventure> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify(data),
    })
    if (!res.ok) throw new Error('Failed to save changes.')
    return res.json()
  },

  async clearCreationError(adventureId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify({ creation_error: null }),
    })
    if (!res.ok) throw new Error('Failed to clear creation error')
  },

  normalizeDebugPayload(raw: any): DebugPayload {
    if (!raw || typeof raw !== 'object') return raw
    const payload = { ...raw }
    const allEntities = Array.isArray(raw.entities_all) ? raw.entities_all : []
    if (allEntities.length === 0) return payload

    const inferredNpcs = allEntities.filter((entity: any) => isNpcEntity(entity))
    const inferredObjects = allEntities.filter((entity: any) => isObjectEntity(entity))

    payload.npcs = mergeUniqueById(
      Array.isArray(raw.npcs) ? raw.npcs : [],
      inferredNpcs
    )
    payload.objects = mergeUniqueById(
      Array.isArray(raw.objects) ? raw.objects : [],
      inferredObjects
    )
    return payload
  },
}
