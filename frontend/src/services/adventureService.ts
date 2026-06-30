import { API_BASE, authHeaders } from '@/services/http'
import { isNpcEntity, isObjectEntity, mergeUniqueById } from '@/utils/editor_utils'

export interface Adventure {
  id: string
  title: string
  teaser?: string
  version?: string
  creator?: string
  copyright?: string
  license?: string
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
  start_scene_id?: string
}

export interface AdventureFormData {
  title: string
  teaser: string
  version: string
  creator: string
  copyright: string
  license: string
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

  async updateEditorStartScene(adventureId: string, sceneId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/start-scene`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify({ scene_id: sceneId }),
    })
    if (!res.ok) throw new Error('Failed to set start scene.')
  },

  async clearCreationError(adventureId: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify({ creation_error: null }),
    })
    if (!res.ok) throw new Error('Failed to clear creation error')
  },

  async generateTemplateField(adventureId: string, data: {
    field: string
    title?: string
    original_prompt?: string
    plot?: string
    rules?: string
    intro_text?: string
    walkthrough?: string
    completed_condition?: string
    gameover_condition?: string
    tts_director_notes?: string
  }): Promise<{ generated_text: string }> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/generate-field`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(data),
    })
    if (!res.ok) {
      const respData = await res.json()
      throw new Error(respData.detail || 'Failed to generate field.')
    }
    return res.json()
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

  async runValidation(
    adventureId: string,
    includeAi: boolean,
  ): Promise<ValidationRunResponse> {
    const res = await fetch(
      `${API_BASE}/adventures/${adventureId}/editor/validate`,
      {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({ include_ai: includeAi }),
      },
    )
    if (!res.ok) {
      const respData = await res.json().catch(() => ({}))
      throw new Error(respData.detail || 'Failed to run validation.')
    }
    return res.json()
  },

  async getLatestValidation(
    adventureId: string,
  ): Promise<PersistedValidationRun | null> {
    const res = await fetch(
      `${API_BASE}/adventures/${adventureId}/editor/validation/latest`,
      { method: 'GET', headers: authHeaders(false) },
    )
    if (!res.ok) {
      if (res.status === 404) return null
      const respData = await res.json().catch(() => ({}))
      throw new Error(respData.detail || 'Failed to load the latest validation.')
    }
    if (res.status === 204) return null
    const raw = await res.json().catch(() => null)
    if (!raw) return null
    return raw as PersistedValidationRun
  },

  async runValidationAll(adventureId: string): Promise<ValidationRunResponse> {
    return adventureService.runValidation(adventureId, true)
  },

  async runValidationStructuralOnly(
    adventureId: string,
  ): Promise<ValidationRunResponse> {
    return adventureService.runValidation(adventureId, false)
  },

  async runValidationAiOnly(
    adventureId: string,
  ): Promise<ValidationRunResponse> {
    return adventureService.runValidation(adventureId, true)
  },

  async requestAIFixSuggestions(
    adventureId: string,
    request: AIFixSuggestionsRequest,
  ): Promise<AIFixSuggestionsResponse> {
    const res = await fetch(
      `${API_BASE}/adventures/${adventureId}/editor/validate/findings/suggest-fix`,
      {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify(request),
      },
    )
    if (!res.ok) {
      const respData = await res.json().catch(() => ({}))
      throw new Error(respData.detail || 'Failed to request AI fix suggestions.')
    }
    return res.json()
  },

  async applyAIFix(
    adventureId: string,
    request: AIFixApplyRequest,
  ): Promise<AIFixApplyResponse> {
    const res = await fetch(
      `${API_BASE}/adventures/${adventureId}/editor/validate/findings/apply-fix`,
      {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify(request),
      },
    )
    if (!res.ok) {
      const respData = await res.json().catch(() => ({}))
      throw new Error(respData.detail || 'Failed to apply AI fix.')
    }
    return res.json()
  },
}

export type ValidationSeverity = 'error' | 'warn'

export interface ValidationFinding {
  severity: ValidationSeverity
  code: string
  message: string
  location?: string | null
  context?: Record<string, any> | null
}

/**
 * A finding annotated with its source (structural vs AI).
 * The backend returns these as two separate lists; the UI merges and tags them.
 */
export interface AnnotatedValidationFinding extends ValidationFinding {
  source: 'structural' | 'ai'
}

export type ValidationAiSkippedReason =
  | 'ai_not_requested'
  | 'scene_limit_exceeded'
  | 'ai_error'
  | null

export interface ValidationRunResponse {
  structural_findings: ValidationFinding[]
  ai_findings: ValidationFinding[]
  ai_skipped_reason?: ValidationAiSkippedReason
  run_at: string
}

export interface PersistedValidationRun extends ValidationRunResponse {
  structural_finding_count?: number
  ai_finding_count?: number
  error_count?: number
  warning_count?: number
}

export type FixTargetType =
  | 'scene'
  | 'object'
  | 'npc'
  | 'exit'
  | 'protagonist'
  | 'adventure'

export interface FixProposalEntityPatch {
  target_type: FixTargetType
  target_id?: string | null
  description?: string | null
  field_updates: Record<string, any>
}

export interface FixProposal {
  title: string
  summary: string
  rationale?: string | null
  patches: FixProposalEntityPatch[]
}

export interface AIFixSuggestionsRequest {
  finding_code: string
  finding_message: string
  finding_location?: string | null
  finding_context?: Record<string, any> | null
  finding_severity?: ValidationSeverity
}

export interface AIFixSuggestionsResponse {
  finding_signature: string
  proposals: FixProposal[]
  generated_at: string
  error?: string | null
}

export interface AIFixApplyRequest {
  finding_signature: string
  proposal: FixProposal
}

export interface AIFixApplyResponse {
  status: 'applied' | 'no_op' | 'partial'
  applied_targets: string[]
  message?: string | null
}
