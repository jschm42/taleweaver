import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const apiDefTs = new URL('../src/utils/twScriptApiDefinitions.ts', import.meta.url)
const autoCompTs = new URL('../src/utils/scriptAutocomplete.ts', import.meta.url)

// Transpile TS files to temporary .mjs for native ESM imports
const apiDefJs = ts.transpileModule(readFileSync(apiDefTs, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

const autoCompJs = ts.transpileModule(readFileSync(autoCompTs, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
  .replace('./twScriptApiDefinitions', './__temp_twScriptApiDefinitions.mjs')
  .replace('./cdnScriptLoader', './__temp_cdnScriptLoaderMock.mjs')

const tempApiDefFile = new URL('./__temp_twScriptApiDefinitions.mjs', import.meta.url)
const tempCdnMockFile = new URL('./__temp_cdnScriptLoaderMock.mjs', import.meta.url)
const tempAutoCompFile = new URL('./__temp_scriptAutocomplete.mjs', import.meta.url)

writeFileSync(tempApiDefFile, apiDefJs)
writeFileSync(tempCdnMockFile, 'export async function ensureCodeMirrorHintLoaded() { return true }\n')
writeFileSync(tempAutoCompFile, autoCompJs)

let TW_NAMESPACES, TW_ROOT_ITEMS, PROXY_ITEMS, resolveCompletionsForLine, twScriptHint

try {
  const apiModule = await import(tempApiDefFile.href)
  TW_NAMESPACES = apiModule.TW_NAMESPACES
  TW_ROOT_ITEMS = apiModule.TW_ROOT_ITEMS
  PROXY_ITEMS = apiModule.PROXY_ITEMS

  const autoModule = await import(tempAutoCompFile.href)
  resolveCompletionsForLine = autoModule.resolveCompletionsForLine
  twScriptHint = autoModule.twScriptHint
} finally {
  try { unlinkSync(tempApiDefFile) } catch {}
  try { unlinkSync(tempCdnMockFile) } catch {}
  try { unlinkSync(tempAutoCompFile) } catch {}
}

test('TW_NAMESPACES covers all primary scripting engine domains', () => {
  const expectedNamespaces = [
    'player',
    'scene',
    'exits',
    'npcs',
    'objects',
    'items',
    'switches',
    'vars',
    'flags',
    'story',
    'dialog',
    'time',
    'game',
    'quests',
    'awards',
    'sequences',
    'dice',
    'memories',
    'llm',
    'json',
    'log',
    'console',
  ]

  for (const ns of expectedNamespaces) {
    assert.ok(TW_NAMESPACES[ns], `Missing namespace: ${ns}`)
    assert.ok(Array.isArray(TW_NAMESPACES[ns].items), `Namespace ${ns} has no items array`)
    assert.ok(TW_NAMESPACES[ns].items.length > 0, `Namespace ${ns} items is empty`)
  }
})

test('TW_ROOT_ITEMS contains shortcuts and sub-namespaces', () => {
  const names = TW_ROOT_ITEMS.map((it) => it.name)
  assert.ok(names.includes('story'))
  assert.ok(names.includes('player'))
  assert.ok(names.includes('narrate'))
  assert.ok(names.includes('direct'))
  assert.ok(names.includes('system'))
  assert.ok(names.includes('switch'))
  assert.ok(names.includes('save'))
  assert.ok(names.includes('debug'))
})

test('resolveCompletionsForLine resolves tw. root items', () => {
  const result = resolveCompletionsForLine('tw.')
  assert.equal(result.queryPrefix, '')
  assert.ok(result.items.length >= 20)
  assert.ok(result.items.some((it) => it.name === 'story'))
  assert.ok(result.items.some((it) => it.name === 'player'))
})

test('resolveCompletionsForLine resolves tw.story methods with query prefix', () => {
  const result = resolveCompletionsForLine('tw.story.nar')
  assert.equal(result.queryPrefix, 'nar')
  assert.ok(result.items.some((it) => it.name === 'narrate'))
  assert.ok(result.items.some((it) => it.name === 'narrate_raw'))
})

test('resolveCompletionsForLine resolves tw.player properties and methods', () => {
  const result = resolveCompletionsForLine('tw.player.')
  assert.equal(result.queryPrefix, '')
  assert.ok(result.items.some((it) => it.name === 'hp'))
  assert.ok(result.items.some((it) => it.name === 'inventory'))
  assert.ok(result.items.some((it) => it.name === 'heal'))
  assert.ok(result.items.some((it) => it.name === 'damage'))
  assert.ok(result.items.some((it) => it.name === 'has_item'))
})

test('resolveCompletionsForLine resolves chained proxy methods', () => {
  const npcResult = resolveCompletionsForLine('tw.npcs.get("GUARD").')
  assert.equal(npcResult.queryPrefix, '')
  assert.ok(npcResult.items.some((it) => it.name === 'say'))
  assert.ok(npcResult.items.some((it) => it.name === 'attack'))

  const switchResult = resolveCompletionsForLine('tw.switch("LEVER").')
  assert.equal(switchResult.queryPrefix, '')
  assert.ok(switchResult.items.some((it) => it.name === 'flip'))
  assert.ok(switchResult.items.some((it) => it.name === 'is_state'))
})

test('twScriptHint produces properly formatted CodeMirror completions', () => {
  const mockCm = {
    getCursor: () => ({ line: 0, ch: 9 }),
    getLine: () => 'tw.story.',
  }

  const hintResult = twScriptHint(mockCm)
  assert.ok(hintResult)
  assert.equal(hintResult.from.line, 0)
  assert.equal(hintResult.from.ch, 9)
  assert.ok(hintResult.list.length > 0)

  const narrateEntry = hintResult.list.find((e) => e.text === 'narrate')
  assert.ok(narrateEntry)
  assert.equal(narrateEntry.item.kind, 'method')
  assert.ok(typeof narrateEntry.render === 'function')
  assert.ok(typeof narrateEntry.hint === 'function')
})
