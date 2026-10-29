/**
 * useBackendStatus — Polls the public bootstrap endpoint so public views (e.g. login)
 * can show whether the backend is reachable while it is still starting up.
 */
import { onMounted, onUnmounted, ref } from 'vue'
import { api, type BootstrapStatus } from '@/composables/useApi'

export type BackendStatus = 'checking' | 'online' | 'offline'

// Poll quickly while the backend is starting, slowly once it answers.
const OFFLINE_POLL_MS = 2000
const ONLINE_POLL_MS = 15000
const PROBE_TIMEOUT_MS = 4000

export function useBackendStatus(onOnline?: (bootstrap: BootstrapStatus | null) => void) {
  const status = ref<BackendStatus>('checking')
  let timerId: number | undefined
  let stopped = false

  async function probe(): Promise<BootstrapStatus | null> {
    try {
      return await api.getBootstrapStatus({ timeoutMs: PROBE_TIMEOUT_MS })
    } catch (err) {
      // A 4xx answer still proves the server is up; 5xx comes from the dev proxy when it is down.
      const httpStatus = (err as { status?: number } | null)?.status
      if (httpStatus !== undefined && httpStatus < 500) {
        return null
      }
      throw err
    }
  }

  async function poll() {
    const wasOnline = status.value === 'online'
    try {
      const bootstrap = await probe()
      status.value = 'online'
      if (!wasOnline) {
        onOnline?.(bootstrap)
      }
    } catch {
      status.value = 'offline'
    }
    if (stopped) {
      return
    }
    timerId = window.setTimeout(poll, status.value === 'online' ? ONLINE_POLL_MS : OFFLINE_POLL_MS)
  }

  onMounted(poll)
  onUnmounted(() => {
    stopped = true
    window.clearTimeout(timerId)
  })

  return { status }
}
