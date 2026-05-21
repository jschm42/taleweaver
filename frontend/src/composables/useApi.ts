/**
 * useApi — Thin wrapper around fetch() for TaleWeaver REST endpoints.
 *
 * All methods throw on non-2xx responses so callers can handle errors
 * with a simple try/catch.
 */
import type {
  CreateAdventurePayload,
  GameSession,
  AdventureImportPayload,
  CatalogTile,
  AdventureTemplateSummary,
  StoryIdeaSuggestionPayload,
  StoryIdeaSuggestionResponse,
} from '@/types'
import { authState } from '@/store/auth'
import { configState } from '@/store/config'

interface SettingsResponse {
  app_version?: string
  keys: Record<string, { masked: string; is_env: boolean }>
  llm_settings: Record<string, unknown>
  t2i_settings: Record<string, unknown>
  game_settings: Record<string, unknown>
  is_llm_configured: boolean
  is_t2i_configured: boolean
  image_styles_catalog: CatalogTile[]
  tone_catalog: CatalogTile[]
  tts_settings: Record<string, unknown>
}

// Use absolute backend URL during local development to avoid proxy/cache timing
// issues (Vite already proxies `/api` to the backend, but in some dev setups
// the relative proxy can lead to empty responses on initial load). In
// production we keep the relative `/api` base so the server can serve the
// frontend and backend from the same origin.
const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  
  if (!(init?.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  
  if (authState.token) {
    headers.set('Authorization', `Bearer ${authState.token}`)
  }

  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      headers,
    })
    
    // If we get here, the server at least responded
    configState.isBackendReachable = true
    configState.lastErrorMessage = ''

    if (!res.ok) {
      const bodyText = await res.text()
      let detail = bodyText
      try {
        const parsed = JSON.parse(bodyText)
        if (parsed && typeof parsed.detail === 'string') {
          // If the JSON contains more than just the detail (e.g. conflict_info),
          // keep the full JSON string so the caller can parse it.
          if (Object.keys(parsed).length > 1) {
            detail = bodyText
          } else {
            detail = parsed.detail
          }
        }
      } catch {
        // Keep plain-text fallback when response is not JSON.
      }
      if (res.status === 401 && authState.isAuthenticated) {
         // Token might have expired
         window.dispatchEvent(new CustomEvent('auth-unauthorized'))
      }
      
      // If it's a 500 error, we might want to flag it as a backend issue too
      if (res.status >= 500) {
        configState.isBackendReachable = false
        configState.lastErrorMessage = `Server Error (${res.status}): ${detail}`
      }

      throw new Error(`API ${res.status}: ${detail}`)
    }
    // 204 No Content has no body
    if (res.status === 204) return undefined as T
    return res.json() as Promise<T>
  } catch (err: any) {
    // If it's not already an API error (thrown above), it's likely a network error
    if (!(err.message.startsWith('API '))) {
      configState.isBackendReachable = false
      configState.lastErrorMessage = err.message || 'Network Error'
    }
    throw err
  }
}

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const headers = new Headers(init?.headers)
  
  if (authState.token) {
    headers.set('Authorization', `Bearer ${authState.token}`)
  }

  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      headers,
    })
    
    configState.isBackendReachable = true
    configState.lastErrorMessage = ''

    if (!res.ok) {
      const bodyText = await res.text()
      let detail = bodyText
      try {
        const parsed = JSON.parse(bodyText)
        if (parsed && typeof parsed.detail === 'string') {
          detail = parsed.detail
        }
      } catch {
        // Keep plain-text fallback when response is not JSON.
      }
      if (res.status === 401 && authState.isAuthenticated) {
         window.dispatchEvent(new CustomEvent('auth-unauthorized'))
      }
      
      if (res.status >= 500) {
        configState.isBackendReachable = false
        configState.lastErrorMessage = `Server Error (${res.status}): ${detail}`
      }

      throw new Error(`API ${res.status}: ${detail}`)
    }
    return res.blob()
  } catch (err: any) {
    if (!(err.message.startsWith('API '))) {
      configState.isBackendReachable = false
      configState.lastErrorMessage = err.message || 'Network Error'
    }
    throw err
  }
}

export const api = {
  /** Manually trigger import of example adventures (samples). */
  importExamples(): Promise<{ status: string; message: string }> {
    return request('/adventures/import-examples', { method: 'POST' })
  },

  /** Manually restore default adventures. */
  reimportDefaults(): Promise<{ status: string; message: string }> {
    return request('/adventures/reimport-defaults', { method: 'POST' })
  },

  /** Check for conflicts before restoring defaults. */
  checkDefaults(): Promise<{ available_imports: Array<{ title: string; origin_id?: string; already_exists: boolean }> }> {
    return request('/adventures/check-defaults', { method: 'GET' })
  },

  /** Check for conflicts before importing examples. */
  checkExamples(): Promise<{ available_imports: Array<{ title: string; origin_id?: string; already_exists: boolean }> }> {
    return request('/adventures/check-examples', { method: 'GET' })
  },

  /** Lists all game sessions. */
  listAdventures(): Promise<GameSession[]> {
    return request<GameSession[]>('/adventures/sessions')
  },

  /** Lists all game sessions (explicit endpoint). */
  listSessions(): Promise<GameSession[]> {
    return request<GameSession[]>('/adventures/sessions')
  },

  /** Lists all adventure templates for management. */
  listAdventureTemplates(): Promise<AdventureTemplateSummary[]> {
    return request<AdventureTemplateSummary[]>('/adventures/templates')
  },

  /** Starts (or reuses) a session for a template. */
  startSessionForTemplate(templateId: string): Promise<{ game_id: string; template_id: string; adventure_id: string; avatar_id: string }> {
    return request(`/adventures/${templateId}/sessions/start`, { method: 'POST' })
  },

  /** Deletes one game session but keeps the template. */
  deleteSession(gameId: string): Promise<{ status: string; game_id: string }> {
    return request(`/adventures/sessions/${gameId}`, { method: 'DELETE' })
  },

  /** Creates a copy of an existing session. */
  copySession(gameId: string): Promise<{ game_id: string }> {
    return request(`/adventures/sessions/${gameId}/copy`, { method: 'POST' })
  },

  /** Pauses a session via template-scoped route. */
  pauseSession(templateId: string): Promise<{ status: string; game_id: string }> {
    return request(`/adventures/${templateId}/pause`, { method: 'POST' })
  },

  /** Resumes a session via template-scoped route. */
  resumeSession(templateId: string): Promise<{ status: string; game_id: string }> {
    return request(`/adventures/${templateId}/resume`, { method: 'POST' })
  },

  /** Hard-resets a session via template-scoped route. */
  resetSession(templateId: string): Promise<{ status: string; message: string }> {
    return request(`/adventures/${templateId}/reset`, { method: 'POST' })
  },

  /** Marks one readable text log as read within a session. */
  markTextLogRead(gameId: string, entityId: string): Promise<{ status: string; entity_id: string; is_read: boolean }> {
    return request(`/adventures/${gameId}/text-logs/${encodeURIComponent(entityId)}/read`, { method: 'POST' })
  },

  /** Attempts to unlock one container with a submitted access code. */
  unlockContainerWithCode(gameId: string, entityId: string, code: string): Promise<{ status: string; entity_id: string; locked: boolean }> {
    return request(`/adventures/${gameId}/containers/${encodeURIComponent(entityId)}/unlock-code`, {
      method: 'POST',
      body: JSON.stringify({ code }),
    })
  },

  /** @deprecated Use listSessions() instead. */
  listGameSessions(): Promise<GameSession[]> {
    return request<GameSession[]>('/adventures/')
  },

  /** Creates a new adventure and returns the generated IDs. */
  createAdventure(payload: CreateAdventurePayload): Promise<{ game_id: string; adventure_id: string; avatar_id: string }> {
    return request('/adventures/', { method: 'POST', body: JSON.stringify(payload) })
  },

  /** Generates or improves title and story idea from user input. */
  suggestStoryIdea(payload: StoryIdeaSuggestionPayload): Promise<StoryIdeaSuggestionResponse> {
    return request('/adventures/story-idea/suggest', { method: 'POST', body: JSON.stringify(payload) })
  },

  /** Returns a single adventure template details by ID. */
  getAdventure(templateId: string): Promise<any> {
    return request(`/adventures/${templateId}`)
  },

  /** Import an adventure JSON payload (parsed .adv) and open creation flow on the server. */
  importAdventure(payload: AdventureImportPayload): Promise<{ game_id: string; adventure_id: string; avatar_id: string }> {
    return request('/adventures/import', { method: 'POST', body: JSON.stringify(payload) })
  },

  /** Deletes an adventure by its ID. */
  deleteAdventure(adventureId: string): Promise<void> {
    return request(`/adventures/${adventureId}`, { method: 'DELETE' })
  },

  /** Saves an encrypted API key for a provider. */
  saveApiKey(provider: string, apiKey: string): Promise<{ status: string; message: string }> {
    return request('/settings/keys', {
      method: 'POST',
      body: JSON.stringify({ provider, api_key: apiKey }),
    })
  },

  /** Deletes an encrypted API key for a provider. */
  deleteApiKey(provider: string): Promise<{ status: string; message: string }> {
    return request(`/settings/keys/${provider}`, { method: 'DELETE' })
  },

  /** Retrieves full settings payload including generation catalogs. */
  getSettings(): Promise<SettingsResponse> {
    return request('/settings')
  },

  /** Saves admin-managed image style catalog. */
  saveImageStylesCatalog(items: CatalogTile[]): Promise<{ status: string; message: string }> {
    return request('/settings/image-styles', {
      method: 'POST',
      body: JSON.stringify({ items }),
    })
  },

  /** Saves admin-managed tone catalog. */
  saveToneCatalog(items: CatalogTile[]): Promise<{ status: string; message: string }> {
    return request('/settings/tones', {
      method: 'POST',
      body: JSON.stringify({ items }),
    })
  },

  /** Returns the URL for exporting an adventure as ADZ. */
  exportAdzUrl(adventureId: string): string {
    return `${BASE}/adventures/${adventureId}/export/adz`
  },

  /** Returns the URL for exporting an adventure as ADV (JSON blueprint). */
  exportAdvUrl(adventureId: string): string {
    return `${BASE}/adventures/${adventureId}/export/adv`
  },

  /** Downloads the adventure as ADZ (ZIP) bundle. */
  downloadAdventureAdz(adventureId: string): Promise<Blob> {
    return requestBlob(`/adventures/${adventureId}/export/adz`)
  },

  /** Downloads the adventure as ADV (JSON) manifest. */
  downloadAdventureAdv(adventureId: string): Promise<any> {
    return request(`/adventures/${adventureId}/export/adv`)
  },

  /** Import an ADZ file via FormData. */
  async importAdz(file: File, overwrite: boolean = false): Promise<{ status: string; adventure_id: string }> {
    const formData = new FormData()
    formData.append('file', file)

    const url = `/adventures/import/adz${overwrite ? '?overwrite=true' : ''}`
    return request(url, {
      method: 'POST',
      body: formData,
    })
  },

  /** Import an ADV blueprint file via FormData. */
  async importAdv(file: File, overwrite: boolean = false): Promise<{ status: string; adventure_id: string }> {
    const formData = new FormData()
    formData.append('file', file)

    const url = `/adventures/import/adv${overwrite ? '?overwrite=true' : ''}`
    return request(url, {
      method: 'POST',
      body: formData,
    })
  },

  /** Retrieves the generation status and potential errors for an adventure. */
  getAdventureStatus(adventureId: string): Promise<{ status: string; is_ready: boolean; error?: string }> {
    return request(`/adventures/${adventureId}/status`)
  },

  /** Cancels an active adventure generation. */
  cancelAdventure(adventureId: string): Promise<{ status: string }> {
    return request(`/adventures/${adventureId}/cancel`, { method: 'POST' })
  },

  /** Admin Settings */
  saveLlmSettings(payload: any): Promise<any> {
    return request('/settings/llm', { method: 'POST', body: JSON.stringify(payload) })
  },

  saveT2iSettings(payload: any): Promise<any> {
    return request('/settings/t2i', { method: 'POST', body: JSON.stringify(payload) })
  },

  saveGameSettings(payload: any): Promise<any> {
    return request('/settings/game', { method: 'POST', body: JSON.stringify(payload) })
  },

  saveTTSSettings(payload: any): Promise<any> {
    return request('/settings/tts', { method: 'POST', body: JSON.stringify(payload) })
  },

  generateTTS(payload: { text: string; scene_description?: string; adventure_id?: string; session_id?: string; title?: string; scene_name?: string; tone?: string; voice_override?: string; speaker_voices?: Record<string, string>; director_notes?: string }): Promise<{ audio_url: string }> {
    return request('/tts/generate', { method: 'POST', body: JSON.stringify(payload) })
  },

  testTTS(): Promise<{ status: string; audio_url?: string; message?: string }> {
    return request('/tts/test-connection', { method: 'POST' })
  },

  getElevenLabsModels(): Promise<Array<{ model_id: string, name: string }>> {
    return request('/settings/tts/elevenlabs-models', { method: 'GET' })
  },

  /** Testing */
  testLlm(payload: any): Promise<any> {
    return request('/settings/test-llm', { method: 'POST', body: JSON.stringify(payload) })
  },

  testVision(payload: any): Promise<any> {
    return request('/settings/test-vision', { method: 'POST', body: JSON.stringify(payload) })
  },

  /** Catalog */
  generateCatalogImage(payload: any): Promise<any> {
    return request('/settings/catalog/generate', { method: 'POST', body: JSON.stringify(payload) })
  },

  async uploadCatalogImage(formData: FormData): Promise<any> {
    const res = await fetch(`${BASE}/settings/catalog/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authState.token}` },
      body: formData,
    })
    if (!res.ok) throw new Error('Upload failed')
    return res.json()
  },

  /** --- AUTH & USER MGMT --- **/

  login(username: string, password: string): Promise<{ access_token: string; token_type: string }> {
    const params = new URLSearchParams()
    params.append('username', username)
    params.append('password', password)
    return request('/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: params
    })
  },

  getMe(): Promise<any> {
    return request('/auth/me')
  },

  getBootstrapStatus(): Promise<{ has_admin: boolean; has_users: boolean }> {
    return request('/auth/bootstrap-status')
  },

  setupRootAdmin(payload: any): Promise<any> {
    return request('/auth/setup-root', { method: 'POST', body: JSON.stringify(payload) })
  },

  listUsers(): Promise<any[]> {
    return request('/users')
  },

  createUser(payload: any): Promise<any> {
    return request('/users', { method: 'POST', body: JSON.stringify(payload) })
  },

  updateUser(userId: string, payload: any): Promise<any> {
    return request(`/users/${userId}`, { method: 'PUT', body: JSON.stringify(payload) })
  },

  deleteUser(userId: string): Promise<void> {
    return request(`/users/${userId}`, { method: 'DELETE' })
  },

  async uploadProfileImage(file: File): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const response = await request('/users/me/profile-image', {
        method: 'POST',
        body: formData
      })
      return response
    } catch (error) {
      console.error('API uploadProfileImage error:', error)
      throw error
    }
  },

  updateMyBio(bio: string): Promise<any> {
    return request('/users/me/bio', {
      method: 'PUT',
      body: JSON.stringify({ bio })
    })
  },

  generateMyBio(): Promise<{ bio: string }> {
    return request('/users/me/bio/generate', { method: 'POST' })
  },

  async generateMyProfileImage(bio?: string): Promise<any> {
    const body = bio !== undefined ? JSON.stringify({ bio }) : undefined
    
    try {
      const response = await request('/users/me/profile-image/generate', { method: 'POST', body })
      return response
    } catch (error) {
      console.error('API generateMyProfileImage error:', error)
      throw error
    }
  },

  /** Updates a session note or status. */
  updateSession(gameId: string, payload: { status?: string | null; status_note?: string | null }): Promise<GameSession> {
    return request(`/adventures/sessions/${gameId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  /** Downloads the session as ADS (ZIP) bundle. */
  downloadSessionAds(gameId: string): Promise<Blob> {
    return requestBlob(`/adventures/sessions/${gameId}/export`)
  },

  /** Imports a session from ADS ZIP file. */
  async importSession(file: File): Promise<{ status: string; game_id: string; message: string }> {
    const formData = new FormData()
    formData.append('file', file)
    return request('/adventures/sessions/import', {
      method: 'POST',
      body: formData,
    })
  }
}

