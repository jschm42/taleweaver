import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/services/cutsceneLibrary.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_cutsceneLibrary.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch { /* already removed */ } })
const { cutscenesOf, suggestCutsceneId, newCutscene, slideText } = await import(tempFile.href)

test('ids are upper case, ASCII and unique', () => {
  const taken = new Set(['THE_DEBT'])
  assert.equal(suggestCutsceneId('The Débt', taken), 'THE_DEBT_2')
  assert.equal(suggestCutsceneId('  ', new Set()), 'CUTSCENE')
})

test('a new cut-scene starts with one empty slide', () => {
  const cutscene = newCutscene('Intro', new Set())
  assert.equal(cutscene.id, 'INTRO')
  assert.equal(cutscene.slides.length, 1)
  assert.equal(cutscene.image_style, '')
})

test('a slide keeps several passages; the image prompt reads them all', () => {
  const [cutscene] = cutscenesOf({ cutscenes: [{ id: 'A', slides: [{ passages: ['One.', 'Two.'] }] }] })
  assert.deepEqual(cutscene.slides[0].passages, ['One.', 'Two.'])
  assert.equal(slideText(cutscene.slides[0]), 'One. Two.')
})

test('the editor payload is read defensively', () => {
  const list = cutscenesOf({ cutscenes: [{ id: 'A', slides: [{ text: 'x' }] }, null, { title: 'no id' }] })
  assert.equal(list.length, 1)
  assert.equal(list[0].slides[0].image_url, null)
  assert.ok(list[0].slides[0].id)
  assert.deepEqual(list[0].slides[0].passages, ['x'])
  assert.deepEqual(cutscenesOf(null), [])
})
