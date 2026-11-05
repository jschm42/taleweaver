import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

// Transpile the TS modules under test to temporary .mjs files (aliases rewritten to the temp files).
const modules = {
  messageKeys: ['../src/composables/messageKeys.ts', {}],
  silentCommands: ['../src/composables/silentCommands.ts', {}],
  historyWindow: [
    '../src/composables/historyWindow.ts',
    {
      '@/composables/messageKeys': './__temp_messageKeys.mjs',
      '@/composables/silentCommands': './__temp_silentCommands.mjs',
    },
  ],
  storyDividers: ['../src/components/game/immersive/storyDividers.ts', {}],
}

const tempFiles = []
const loaded = {}
for (const [name, [path, aliases]] of Object.entries(modules)) {
  let js = ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText
  for (const [from, to] of Object.entries(aliases)) js = js.replaceAll(`'${from}'`, `'${to}'`)
  const file = new URL(`./__temp_${name}.mjs`, import.meta.url)
  writeFileSync(file, js)
  tempFiles.push(file)
}
try {
  loaded.historyWindow = await import(new URL('./__temp_historyWindow.mjs', import.meta.url).href)
  loaded.storyDividers = await import(new URL('./__temp_storyDividers.mjs', import.meta.url).href)
} finally {
  after(() => tempFiles.forEach((f) => { try { unlinkSync(f) } catch {} }))
}

const { mergeNewestWindow, prependOlderPage } = loaded.historyWindow
const { dividerBefore } = loaded.storyDividers

const msg = (id, extra = {}) => ({ id, role: 'system', content: `m-${id}`, _key: `k-${id}`, ...extra })

test('a reloaded newest window keeps the older pages it connects to', () => {
  const shown = [msg('1'), msg('2'), msg('3'), msg('4')]
  const reloaded = [msg('3', { _key: undefined }), msg('4', { _key: undefined }), msg('5', { _key: undefined })]

  const { messages, keptOlder } = mergeNewestWindow(shown, reloaded)

  assert.equal(keptOlder, true)
  assert.deepEqual(messages.map((m) => m.id), ['1', '2', '3', '4', '5'])
  assert.equal(messages[2]._key, 'k-3', 'shown messages keep their render key')
})

test('a reloaded window that does not connect replaces the shown messages', () => {
  const shown = [msg('1'), msg('2')]
  const { messages, keptOlder } = mergeNewestWindow(shown, [msg('8'), msg('9')])

  assert.equal(keptOlder, false)
  assert.deepEqual(messages.map((m) => m.id), ['8', '9'])
})

test('an older page goes in front without duplicates', () => {
  const shown = [msg('3'), msg('4')]
  const merged = prependOlderPage(shown, [msg('1'), msg('2'), msg('3')])

  assert.deepEqual(merged.map((m) => m.id), ['1', '2', '3', '4'])
  assert.ok(merged[0]._key && merged[0]._key !== merged[1]._key)
})

const page = (sceneKey) => ({ index: 0, sceneKey, exchanges: [], systemMessages: [] })
const nodes = { HALL: { label: 'Conversation Hall' }, LAB: { label: 'Switch Lab' } }
const titles = { SEQ_2: 'Social Dynamics' }

test('dividers mark scene and chapter changes', () => {
  assert.equal(dividerBefore(undefined, page('HALL|SEQ_1'), nodes, titles), null)
  assert.equal(dividerBefore(page('HALL|SEQ_1'), page('HALL|SEQ_1'), nodes, titles), null)
  assert.deepEqual(dividerBefore(page('HALL|SEQ_1'), page('LAB|SEQ_1'), nodes, titles), {
    scene: 'Switch Lab',
    chapter: null,
  })
  assert.deepEqual(dividerBefore(page('HALL|SEQ_1'), page('HALL|SEQ_2'), nodes, titles), {
    scene: null,
    chapter: 'Social Dynamics',
  })
  assert.deepEqual(dividerBefore(page('HALL|SEQ_2'), page('LAB|SEQ_3'), nodes, titles), {
    scene: 'Switch Lab',
    chapter: 'New chapter',
  })
})

test('legacy pages without scene info get a plain divider', () => {
  assert.deepEqual(dividerBefore(page(null), page(null), nodes, titles), { scene: null, chapter: null })
})
