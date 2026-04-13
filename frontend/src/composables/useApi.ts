/**
 * useApi — Thin wrapper around fetch() for TaleWeaver REST endpoints.
 *
 * All methods throw on non-2xx responses so callers can handle errors
 * with a simple try/catch.
 */
import type { CreateAdventurePayload, GameSession } from '@/types'

const BASE = '/api'

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
}
