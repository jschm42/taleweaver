import { reactive, ref } from 'vue'

export interface User {
  id: string
  username: string
  role: string
  profile_image_url?: string | null
  bio?: string | null
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
