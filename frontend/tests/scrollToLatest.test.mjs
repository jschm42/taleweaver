import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

// Setup minimal DOM mocks for node test environment
globalThis.ResizeObserver = class {
  observe() {}
  disconnect() {}
}
globalThis.MutationObserver = class {
  observe() {}
  disconnect() {}
}
let rafCallbacks = []
globalThis.requestAnimationFrame = (cb) => {
  rafCallbacks.push(cb)
  return rafCallbacks.length
}
globalThis.cancelAnimationFrame = (id) => {
  rafCallbacks = rafCallbacks.filter((_, idx) => idx + 1 !== id)
}
function flushRaf() {
  const current = [...rafCallbacks]
  rafCallbacks = []
  current.forEach(cb => cb())
}

function loadTsModule(relativePath) {
  const fileUrl = new URL(relativePath, import.meta.url)
  const code = readFileSync(fileUrl, 'utf8')
  const transpiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText.replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
  return import(`data:text/javascript;base64,${Buffer.from(transpiled).toString('base64')}`)
}

function createMockContainer(initialProps = {}) {
  const listeners = {}
  return {
    scrollHeight: 1000,
    clientHeight: 400,
    scrollTop: 0,
    ...initialProps,
    addEventListener(name, handler) {
      listeners[name] = listeners[name] || []
      listeners[name].push(handler)
    },
    removeEventListener(name, handler) {
      if (listeners[name]) {
        listeners[name] = listeners[name].filter(h => h !== handler)
      }
    },
    dispatchEvent(name, eventObj = {}) {
      (listeners[name] || []).forEach(h => h(eventObj))
    },
    scrollTo(options) {
      this.scrollTop = options.top
    },
  }
}

test('useScrollToLatest auto-follows on initial content and allows scrolling up', async () => {
  const { ref } = await import('vue')
  const { useScrollToLatest } = await loadTsModule(
    '../src/components/game/immersive/useScrollToLatest.ts'
  )

  const containerEl = createMockContainer({ scrollHeight: 1200, clientHeight: 400, scrollTop: 0 })
  const containerRef = ref(containerEl)

  // maxFollowTop capped at 150px (e.g. latest exchange top)
  const { isFollowing, hasContentBelow, scrollToLatest } = useScrollToLatest(containerRef, {
    maxFollowTop: () => 150,
  })

  // Initially following is true
  assert.equal(isFollowing.value, true)

  // Run initial RAF measure: follow should set scrollTop to 150
  flushRaf()
  assert.equal(containerEl.scrollTop, 150)
  assert.equal(hasContentBelow.value, true)

  // 1. User scrolls UP with mouse wheel (deltaY < 0)
  containerEl.dispatchEvent('wheel', { deltaY: -100 })
  assert.equal(isFollowing.value, false, 'Wheel UP must immediately disable isFollowing')

  // Browser updates scrollTop upwards (towards 0)
  containerEl.scrollTop = 50
  containerEl.dispatchEvent('scroll')
  assert.equal(isFollowing.value, false)

  // Measure runs again (e.g. from resize or mutation)
  flushRaf()
  // MUST NOT snap back to 150 because isFollowing is false!
  assert.equal(containerEl.scrollTop, 50, 'measure must not overwrite scrollTop when reader scrolled up')

  // 2. User presses ArrowUp / PageUp
  containerEl.dispatchEvent('keydown', { key: 'ArrowUp' })
  assert.equal(isFollowing.value, false)

  // 3. User scrolls back down to the very bottom
  containerEl.scrollTop = containerEl.scrollHeight - containerEl.clientHeight // 800
  containerEl.dispatchEvent('scroll')
  assert.equal(isFollowing.value, true, 'Reaching bottom resumes isFollowing')
  flushRaf()
  assert.equal(hasContentBelow.value, false)

  // 4. User scrolls UP again via scrollbar drag (scroll event with delta < 0)
  containerEl.scrollTop = 700
  containerEl.dispatchEvent('scroll')
  assert.equal(isFollowing.value, false, 'Upward scroll delta must disable isFollowing')

  // 5. scrollToLatest resumes following
  scrollToLatest()
  assert.equal(isFollowing.value, true)
  assert.equal(containerEl.scrollTop, 1200)
})


test('scrolling to the very end pins following to the bottom until a new exchange starts', async () => {
  const { ref } = await import('vue')
  const { useScrollToLatest } = await loadTsModule(
    '../src/components/game/immersive/useScrollToLatest.ts'
  )

  const containerEl = createMockContainer({ scrollHeight: 1200, clientHeight: 400, scrollTop: 0 })
  // Smooth scrolling: the browser only gets halfway before the next measure runs.
  containerEl.scrollTo = function () {
    this.scrollTop = 100
  }
  let latestExchangeTop = 150
  const { scrollToPosition, isFollowing } = useScrollToLatest(ref(containerEl), {
    maxFollowTop: () => latestExchangeTop,
  })
  flushRaf()

  // The last spoken part asks for the very end; a measure (streaming text) interrupts the scroll.
  scrollToPosition(containerEl.scrollHeight)
  containerEl.scrollHeight = 1400
  containerEl.dispatchEvent('scroll')
  flushRaf()
  assert.equal(containerEl.scrollTop, 1000, 'pinned following goes to the real bottom, not to maxFollowTop')
  assert.equal(isFollowing.value, true)

  // A new exchange starts further down: the cap at its start applies again.
  latestExchangeTop = 1100
  containerEl.scrollHeight = 2000
  containerEl.dispatchEvent('scroll')
  flushRaf()
  assert.equal(containerEl.scrollTop, 1100, 'a new exchange ends the pin')
})
