import { reactive } from 'vue'
import { apiFetch } from '@/services/http'

const ACCESS_TOKEN_KEY = 'access_token'

function loadAccessToken(): string | null {
  const sessionToken = sessionStorage.getItem(ACCESS_TOKEN_KEY)
  if (sessionToken) {
    return sessionToken
  }

  const persistentToken = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (persistentToken) {
    return persistentToken
  }

  return null
}

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
  total_xp?: number
}

export const authState = reactive({
  user: null as User | null,
  token: loadAccessToken(),
  isAuthenticated: false,
  isInitialized: false
})

export function setToken(token: string, rememberMe: boolean = false) {
  authState.token = token
  if (rememberMe || localStorage.getItem(ACCESS_TOKEN_KEY)) {
    localStorage.setItem(ACCESS_TOKEN_KEY, token)
  } else {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
  }
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token)
}

export function clearAuth() {
  authState.user = null
  authState.token = null
  authState.isAuthenticated = false
  sessionStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(ACCESS_TOKEN_KEY)
}

export async function refreshUser() {
  if (!authState.token) return

  try {
    const res = await apiFetch('/auth/me', {
      method: 'GET',
      timeoutMs: 12000,
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

