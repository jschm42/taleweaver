import { test, after, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

// Minimal browser globals for the watcher.
const events = []
let healthy = true
let healthSlow = false
let apiStatus = 200
let pendingApiPromise = null
globalThis.window = {
  location: { href: 'http://localhost:5173/game', origin: 'http://localhost:5173' },
  addEventListener: () => {},
  dispatchEvent: (event) => events.push(event.type),
  fetch: async (input, init) => {
    if (init?.signal?.aborted) throw new DOMException('The operation was aborted.', 'AbortError')
    const url = String(input)
    if (url.endsWith('/api/health')) {
      // Simulates the probe's own timeout firing (request queued or worker busy).
      if (healthSlow) throw new DOMException('The operation was aborted.', 'AbortError')
      if (!healthy) throw new TypeError('Failed to fetch')
      return new Response(JSON.stringify({ status: 'ok' }), { status: 200 })
    }
    if (pendingApiPromise) {
      await pendingApiPromise
    }
    return new Response('{}', { status: apiStatus })
  },
}
globalThis.document = { visibilityState: 'hidden', createElement: () => ({}) }

const source = readFileSync(new URL('../src/services/backendStatus.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_backendStatus.mjs', import.meta.url)
writeFileSync(tempFile, js)
const { backendStatus, installBackendWatch, uninstallBackendWatch, probeBackend, getInFlightCount, BACKEND_ONLINE_EVENT } =
  await import(tempFile.href)
installBackendWatch()
after(() => {
  uninstallBackendWatch()
  try { unlinkSync(tempFile) } catch {}
})

beforeEach(() => {
  events.length = 0
})

test('a failing request with an unreachable backend marks it offline', async () => {
  healthy = false
  apiStatus = 502
  await window.fetch('/api/adventures/x/chat')
  await probeBackend()
  assert.equal(backendStatus.online, false)
  assert.ok(backendStatus.offlineSince)
  assert.ok(backendStatus.nextRetryAt)
})

test('the next answer brings it back and announces it', async () => {
  healthy = true
  apiStatus = 200
  await probeBackend()
  assert.equal(backendStatus.online, true)
  assert.equal(backendStatus.justRestored, true)
  assert.deepEqual(events, [BACKEND_ONLINE_EVENT])
})

test('a plain server error with a healthy backend is not an outage', async () => {
  healthy = true
  apiStatus = 500
  await window.fetch('/api/settings')
  await probeBackend()
  assert.equal(backendStatus.online, true)
})

test('requests the page cancelled itself are ignored', async () => {
  healthy = false
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(window.fetch('/api/x', { signal: controller.signal }))
  // No health probe was started for the cancelled request.
  assert.equal(backendStatus.checking, false)
  assert.equal(backendStatus.online, true)
  healthy = true
})

test('active in-flight requests prevent false-positive offline marking while probe is delayed', async () => {
  assert.equal(backendStatus.online, true)
  healthy = false
  apiStatus = 200

  let finishInFlightRequest
  pendingApiPromise = new Promise((resolve) => {
    finishInFlightRequest = resolve
  })

  // Start an in-flight API request that is taking longer
  const fetchPromise = window.fetch('/api/adventures/slow/chat')

  // In-flight count should be 1
  assert.equal(getInFlightCount(), 1)

  // A background probe triggers while the request is in flight and health check fails
  await probeBackend()

  // Must NOT mark the backend offline because an API request is actively in flight
  assert.equal(backendStatus.online, true)

  // Finish the in-flight request
  finishInFlightRequest()
  pendingApiPromise = null
  await fetchPromise
  assert.equal(getInFlightCount(), 0)
  healthy = true
})

test('a health probe that only times out does not raise the banner at once', async () => {
  assert.equal(backendStatus.online, true)
  healthSlow = true
  await probeBackend()
  assert.equal(backendStatus.online, true)
  await probeBackend()
  assert.equal(backendStatus.online, true)

  healthSlow = false
  await probeBackend()
  assert.equal(backendStatus.online, true)
  assert.deepEqual(events, [])
})

test('several slow rounds in a row mark the backend offline', async () => {
  healthSlow = true
  await probeBackend()
  await probeBackend()
  await probeBackend()
  assert.equal(backendStatus.online, false)

  healthSlow = false
  await probeBackend()
  assert.equal(backendStatus.online, true)
})
