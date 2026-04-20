/**
 * useApi — Thin wrapper around fetch() for TaleWeaver REST endpoints.
 *
 * All methods throw on non-2xx responses so callers can handle errors
 * with a simple try/catch.
 */
import type { CreateAdventurePayload, GameSession, AdventureImportPayload, CatalogTile } from '@/types'

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
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.text()
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
}
