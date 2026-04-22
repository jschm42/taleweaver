/**
 * useApi — Thin wrapper around fetch() for TaleWeaver REST endpoints.
 *
 * All methods throw on non-2xx responses so callers can handle errors
 * with a simple try/catch.
 */
import type { CreateAdventurePayload, GameSession, AdventureImportPayload, CatalogTile } from '@/types'
import { authState } from '@/store/auth'

interface SettingsResponse {
  keys: Record<string, string>
  llm_settings: Record<string, unknown>
  t2i_settings: Record<string, unknown>
  image_styles_catalog: CatalogTile[]
  tone_catalog: CatalogTile[]
}

// Use absolute backend URL during local development to avoid proxy/cache timing
// issues (Vite already proxies `/api` to the backend, but in some dev setups
// the relative proxy can lead to empty responses on initial load). In
// production we keep the relative `/api` base so the server can serve the
// frontend and backend from the same origin.
const BASE = import.meta.env.DEV ? 'http://localhost:8000/api' : '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { ...init?.headers }
  
  if (!(init?.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  
  if (authState.token) {
    headers['Authorization'] = `Bearer ${authState.token}`
  }

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
  })
  if (!res.ok) {
    const detail = await res.text()
    if (res.status === 401 && authState.isAuthenticated) {
       // Token might have expired
       window.dispatchEvent(new CustomEvent('auth-unauthorized'))
    }
    throw new Error(`API ${res.status}: ${detail}`)
  }
  // 204 No Content has no body
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  /** Lists all game sessions. */
  listAdventures(): Promise<GameSession[]> {
    return request<GameSession[]>('/adventures')
  },

  /** Creates a new adventure and returns the generated IDs. */
  createAdventure(payload: CreateAdventurePayload): Promise<{ game_id: string; adventure_id: string; avatar_id: string }> {
    return request('/adventures', { method: 'POST', body: JSON.stringify(payload) })
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

  /** Import an ADZ file via FormData. */
  async importAdz(file: File): Promise<{ status: string; adventure_id: string }> {
    const formData = new FormData()
    formData.append('file', file)
    
    const res = await fetch(`${BASE}/adventures/import/adz`, {
      method: 'POST',
      body: formData,
    })
    
    if (!res.ok) {
      const detail = await res.text()
      throw new Error(`ADZ Import ${res.status}: ${detail}`)
    }
    return res.json()
  },

  /** Retrieves the generation status and potential errors for an adventure. */
  getAdventureStatus(adventureId: string): Promise<{ status: string; is_ready: boolean; error?: string }> {
    return request(`/adventures/${adventureId}/status`)
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

  uploadProfileImage(file: File): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)
    return request('/users/me/profile-image', {
      method: 'POST',
      body: formData
    })
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

  generateMyProfileImage(bio?: string): Promise<any> {
    const body = bio !== undefined ? JSON.stringify({ bio }) : undefined
    return request('/users/me/profile-image/generate', { method: 'POST', body })
  }
}
