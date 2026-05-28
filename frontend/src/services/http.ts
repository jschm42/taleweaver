import { authState } from '@/store/auth'

export const API_BASE = '/api'
const DEFAULT_API_TIMEOUT_MS = 15000

export function authHeaders(includeJson = false): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  }
  if (includeJson) {
    headers['Content-Type'] = 'application/json'
  }
  if (authState.token) {
    headers.Authorization = `Bearer ${authState.token}`
  }
  return headers
}

export interface ApiFetchInit extends RequestInit {
  timeoutMs?: number
  includeJson?: boolean
}

export function buildApiUrl(path: string): string {
  return path.startsWith('/') ? `${API_BASE}${path}` : `${API_BASE}/${path}`
}

export async function apiFetch(path: string, init: ApiFetchInit = {}): Promise<Response> {
  const {
    timeoutMs = DEFAULT_API_TIMEOUT_MS,
    includeJson = false,
    headers: incomingHeaders,
    signal,
    cache,
    ...rest
  } = init

  const mergedHeaders = new Headers(authHeaders(includeJson))
  const callerHeaders = new Headers(incomingHeaders)
  callerHeaders.forEach((value, key) => mergedHeaders.set(key, value))

  const controller = new AbortController()
  if (signal) {
    if (signal.aborted) {
      controller.abort(signal.reason)
    } else {
      signal.addEventListener('abort', () => controller.abort(signal.reason), { once: true })
    }
  }

  const timeoutId = window.setTimeout(() => controller.abort('request-timeout'), timeoutMs)
  try {
    return await fetch(buildApiUrl(path), {
      ...rest,
      headers: mergedHeaders,
      signal: controller.signal,
      credentials: 'same-origin',
      cache: cache ?? 'no-store',
    })
  } finally {
    clearTimeout(timeoutId)
  }
}
