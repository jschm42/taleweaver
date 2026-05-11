import { api } from '@/composables/useApi'
import { API_BASE, authHeaders } from '@/services/http'

export type GameDateFormat = 'DD.MM.YY' | 'MM/DD/YY' | 'YY-MM-DD'

export interface GameSettings {
  clock_24h: boolean
  date_format?: GameDateFormat
}

export interface WalkthroughData {
  available: boolean
  preview: string
  message: string
  current_xp: number
  reveal_cost: number
  hint_cost: number
  [key: string]: any
}

function getWalkthroughUnavailable(currentXp: number): WalkthroughData {
  return {
    available: false,
    preview: 'No walkthrough available for this adventure yet.',
    message: 'No walkthrough available for this adventure yet.',
    current_xp: currentXp,
    reveal_cost: 200,
    hint_cost: 50,
  }
}

export const gameViewService = {
  async fetchGameSettings(): Promise<GameSettings | null> {
    try {
      const settings = await api.getSettings()
      if (settings?.game_settings) {
        return settings.game_settings as GameSettings
      }
      return null
    } catch (error) {
      console.error('Failed to fetch game settings', error)
      return null
    }
  },

  async fetchFullWorldDebug(gameId: string): Promise<any | null> {
    try {
      const res = await fetch(`${API_BASE}/adventures/${gameId}/chat?include_full_world=true`, {
        headers: authHeaders(false),
      })
      if (!res.ok) return null
      const data = await res.json()
      return data.full_world || null
    } catch {
      return null
    }
  },

  async fetchWalkthrough(gameId: string, currentXp: number): Promise<WalkthroughData> {
    try {
      const res = await fetch(`${API_BASE}/adventures/${gameId}/walkthrough`, {
        headers: authHeaders(false),
      })
      if (!res.ok) {
        return getWalkthroughUnavailable(currentXp)
      }
      return await res.json()
    } catch (error) {
      console.error('Failed to load walkthrough', error)
      return getWalkthroughUnavailable(currentXp)
    }
  },

  async resolveGameIdFromRouteId(routeId: string): Promise<string | null> {
    try {
      const sessions = await api.listSessions()
      const direct = sessions.find((s: any) => s.game_id === routeId)
      if (direct) return routeId

      const match = sessions.find((s: any) => s.template_id === routeId || s.adventure_id === routeId)
      return match?.game_id || null
    } catch (error) {
      console.error('Failed to resolve route id to game session id', error)
      return null
    }
  },

  async ensureGameIdForRouteId(routeId: string): Promise<string | null> {
    const resolved = await this.resolveGameIdFromRouteId(routeId)
    if (resolved) return resolved

    try {
      const created = await api.startSessionForTemplate(routeId)
      return created?.game_id || null
    } catch {
      return null
    }
  },
}
