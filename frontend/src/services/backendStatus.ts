/**
 * backendStatus — tracks whether the backend is reachable and tells the UI.
 *
 * Without this, a stopped backend looks like a frozen frontend: requests just fail or time out
 * while the player is still logged in. `installBackendWatch()` wraps `window.fetch` once, so every
 * API call (apiFetch and plain fetch alike) is observed:
 *
 * - a network error, a timeout, or a 500/502/503/504 for an `/api` request starts a health probe
 *   (`GET /api/health`); only a failed probe marks the backend offline, so an ordinary server
 *   error does not trigger the banner (a dev proxy answers 500/502 when the backend is down);
 * - a probe that fails fast (connection refused, proxy 502/503/504) means "down"; a probe that only
 *   times out means "slow": the request may just be queued behind the browser's per-host connection
 *   limit (audio, images, streamed narration) or hit a busy worker. Slow probes are retried quickly
 *   and only `SLOW_ROUNDS_BEFORE_OFFLINE` slow rounds in a row raise the banner;
 * - while offline, the probe repeats with backoff; the first answer marks it online again and
 *   dispatches `BACKEND_ONLINE_EVENT`, so views can reload their data;
 * - while online and the tab is visible, a slow heartbeat catches an outage during idle time.
 */
import { reactive } from 'vue'

export const BACKEND_ONLINE_EVENT = 'taleweaver:backend-online'

const HEALTH_URL = '/api/health'
const PROBE_TIMEOUT_MS = 10000
const RETRY_DELAYS_MS = [2000, 4000, 8000, 10000]
const SLOW_RETRY_MS = 5000
const SLOW_ROUNDS_BEFORE_OFFLINE = 3
const HEARTBEAT_MS = 30000
const RESTORED_NOTICE_MS = 3500
const SUSPICIOUS_STATUS = new Set([500, 502, 503, 504])

export const backendStatus = reactive({
  online: true,
  checking: false,
  /** When the backend was first found unreachable (for "offline since"). */
  offlineSince: null as number | null,
  /** Epoch ms of the next automatic retry while offline. */
  nextRetryAt: null as number | null,
  /** True for a few seconds after the connection came back. */
  justRestored: false,
})

let originalFetch: typeof window.fetch | null = null
let probing: Promise<void> | null = null
let retryTimer: ReturnType<typeof setTimeout> | undefined
let heartbeatTimer: ReturnType<typeof setInterval> | undefined
let restoredTimer: ReturnType<typeof setTimeout> | undefined
let failedProbes = 0
let slowRounds = 0
let inFlightCount = 0

export function getInFlightCount(): number {
  return inFlightCount
}

function isApiRequest(input: RequestInfo | URL): boolean {
  const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
  try {
    const url = new URL(raw, window.location.href)
    return url.origin === window.location.origin && url.pathname.startsWith('/api/') && url.pathname !== HEALTH_URL
  } catch {
    return false
  }
}

export function markOnline(): void {
  if (retryTimer) clearTimeout(retryTimer)
  retryTimer = undefined
  failedProbes = 0
  slowRounds = 0
  backendStatus.nextRetryAt = null
  if (backendStatus.online) return
  backendStatus.online = true
  backendStatus.offlineSince = null
  backendStatus.justRestored = true
  if (restoredTimer) clearTimeout(restoredTimer)
  restoredTimer = setTimeout(() => {
    backendStatus.justRestored = false
  }, RESTORED_NOTICE_MS)
  window.dispatchEvent(new Event(BACKEND_ONLINE_EVENT))
}

function markOffline(): void {
  if (backendStatus.online) {
    backendStatus.online = false
    backendStatus.offlineSince = Date.now()
    backendStatus.justRestored = false
  }
  const delay = RETRY_DELAYS_MS[Math.min(failedProbes, RETRY_DELAYS_MS.length - 1)]
  failedProbes += 1
  backendStatus.nextRetryAt = Date.now() + delay
  if (retryTimer) clearTimeout(retryTimer)
  retryTimer = setTimeout(() => void probeBackend(), delay)
}

type ProbeResult = 'ok' | 'down' | 'slow'

function isTimeout(error: unknown): boolean {
  const name = (error as { name?: string } | null)?.name
  return name === 'AbortError' || name === 'TimeoutError'
}

async function probeOnce(fetcher: typeof window.fetch): Promise<ProbeResult> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)
  try {
    const response = await fetcher(HEALTH_URL, { cache: 'no-store', signal: controller.signal })
    const body = response.ok ? await response.json().catch(() => null) : null
    return body?.status === 'ok' ? 'ok' : 'down'
  } catch (error) {
    // Only our own timer aborts the probe, so an abort is a timeout, not a refused connection.
    return isTimeout(error) ? 'slow' : 'down'
  } finally {
    clearTimeout(timer)
  }
}

/** A probe that only timed out: retry soon, and give up only after several slow rounds. */
function handleSlowProbe(): void {
  slowRounds += 1
  if (!backendStatus.online || slowRounds >= SLOW_ROUNDS_BEFORE_OFFLINE) {
    markOffline()
    return
  }
  if (retryTimer) clearTimeout(retryTimer)
  retryTimer = setTimeout(() => void probeBackend(), SLOW_RETRY_MS)
}

async function runProbe(): Promise<void> {
  const fetcher = originalFetch ?? window.fetch.bind(window)
  backendStatus.checking = true

  try {
    let result = await probeOnce(fetcher)
    // When currently marked online, confirm with an immediate second probe before alarming the player.
    if (result !== 'ok' && backendStatus.online) {
      result = await probeOnce(fetcher)
    }
    if (result === 'ok') {
      markOnline()
      return
    }

    // If an API request is actively in flight, the backend is working on it.
    // A slow or delayed health check while processing a heavy turn/generation must not raise a false offline alarm.
    if (inFlightCount > 0) {
      return
    }

    if (result === 'slow') {
      handleSlowProbe()
      return
    }
    markOffline()
  } finally {
    backendStatus.checking = false
  }
}

/** Check the backend now (one probe at a time). */
export function probeBackend(): Promise<void> {
  if (!probing) {
    probing = runProbe().finally(() => {
      probing = null
    })
  }
  return probing
}

function observe(input: RequestInfo | URL, outcome: Response | unknown): void {
  if (!isApiRequest(input)) return
  if (outcome instanceof Response) {
    if (SUSPICIOUS_STATUS.has(outcome.status)) void probeBackend()
    else markOnline()
    return
  }
  // Rejected fetch: network error, timeout or abort. The probe tells which.
  void probeBackend()
}

/** Install the fetch observer and the heartbeat. Call once before mounting the app. */
export function installBackendWatch(): void {
  if (originalFetch) return
  originalFetch = window.fetch.bind(window)
  const base = originalFetch
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const isApi = isApiRequest(input)
    if (isApi) {
      inFlightCount++
    }
    try {
      const response = await base(input, init)
      observe(input, response)
      return response
    } catch (error: any) {
      // A request the page cancelled itself says nothing about the backend.
      const isAbort =
        error?.name === 'AbortError' ||
        (error instanceof DOMException && error.name === 'AbortError')
      const isClientCancel = isAbort && init?.signal?.reason !== 'request-timeout'
      if (!isClientCancel) {
        observe(input, error)
      }
      throw error
    } finally {
      if (isApi) {
        inFlightCount = Math.max(0, inFlightCount - 1)
      }
    }
  }
  heartbeatTimer = setInterval(() => {
    if (backendStatus.online && document.visibilityState === 'visible' && inFlightCount === 0) {
      void probeBackend()
    }
  }, HEARTBEAT_MS)
  window.addEventListener('online', () => void probeBackend())
}

/** For tests: restore the original fetch and stop timers. */
export function uninstallBackendWatch(): void {
  if (originalFetch) window.fetch = originalFetch
  originalFetch = null
  inFlightCount = 0
  slowRounds = 0
  if (heartbeatTimer) clearInterval(heartbeatTimer)
  if (retryTimer) clearTimeout(retryTimer)
  if (restoredTimer) clearTimeout(restoredTimer)
}
