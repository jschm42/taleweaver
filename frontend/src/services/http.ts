import { authState } from '@/store/auth'

export const API_BASE = '/api'

export function authHeaders(includeJson = false): Record<string, string> {
  const headers: Record<string, string> = {}
  if (includeJson) {
    headers['Content-Type'] = 'application/json'
  }
  if (authState.token) {
    headers.Authorization = `Bearer ${authState.token}`
  }
  return headers
}
