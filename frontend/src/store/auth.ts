import { reactive } from 'vue'

export interface User {
  id: string
  username: string
  role: string
  profile_image_url?: string | null
  bio?: string | null
  default_language?: string | null
  earned_awards?: any[] | null
  game_log?: any[] | null
  adventure_count?: number
}

export const authState = reactive({
  user: null as User | null,
  token: localStorage.getItem('access_token') || null,
  isAuthenticated: false,
  isInitialized: false
})

export function setToken(token: string) {
  authState.token = token
  localStorage.setItem('access_token', token)
}

export function clearAuth() {
  authState.user = null
  authState.token = null
  authState.isAuthenticated = false
  localStorage.removeItem('access_token')
}

export async function refreshUser() {
  if (!authState.token) return
  
  const BASE = '/api'
  try {
    const res = await fetch(`${BASE}/auth/me`, {
      headers: {
        'Authorization': `Bearer ${authState.token}`
      }
    })
    if (res.ok) {
      const userData = await res.json()
      authState.user = userData
      authState.isAuthenticated = true
    } else if (res.status === 401) {
      clearAuth()
    }
  } catch (error) {
    console.error('Failed to refresh user:', error)
  } finally {
    authState.isInitialized = true
  }
}

