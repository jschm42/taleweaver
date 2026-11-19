import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

function loadTsModule(relativePath) {
  const code = readFileSync(new URL(relativePath, import.meta.url), 'utf8')
  const transpiled = ts.transpileModule(code, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(transpiled).toString('base64')}`)
}

const { speechRevealTarget, REVEAL_MARGIN_PX } = await loadTsModule(
  '../src/components/game/immersive/speechRevealTarget.ts',
)

// A feed showing 0..500 of 2000 px.
const base = { scrollTop: 0, viewHeight: 500, scrollHeight: 2000, isLast: false }

test('a bubble already in view does not scroll', () => {
  assert.equal(speechRevealTarget({ ...base, bubbleTop: 100, bubbleBottom: 300 }), null)
})

test('a bubble below the view is scrolled up until it is fully visible', () => {
  const target = speechRevealTarget({ ...base, bubbleTop: 450, bubbleBottom: 650 })
  assert.equal(target, 650 + REVEAL_MARGIN_PX - 500)
})

test('a bubble taller than the view is shown from its top', () => {
  const target = speechRevealTarget({ ...base, bubbleTop: 700, bubbleBottom: 1400 })
  assert.equal(target, 700 - REVEAL_MARGIN_PX)
})

test('a bubble above the view is scrolled down to', () => {
  const target = speechRevealTarget({ ...base, scrollTop: 800, bubbleTop: 600, bubbleBottom: 700 })
  assert.equal(target, 600 - REVEAL_MARGIN_PX)
})

test('the last bubble scrolls to the very bottom', () => {
  const target = speechRevealTarget({ ...base, bubbleTop: 100, bubbleBottom: 300, isLast: true })
  assert.equal(target, 2000)
})
