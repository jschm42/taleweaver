import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/speakerLabel.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_speakerLabel.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { canBeSpeakerName } = await import(tempFile.href)

test('times and numbers before a colon are not speakers', () => {
  assert.equal(canBeSpeakerName('16'), false) // "16:30 sharp: Kevin is here"
  assert.equal(canBeSpeakerName('3'), false)
  assert.equal(canBeSpeakerName(' 12 '), false)
})

test('names with letters are speakers, also with digits or umlauts', () => {
  assert.equal(canBeSpeakerName('Tina'), true)
  assert.equal(canBeSpeakerName('R2-D2'), true)
  assert.equal(canBeSpeakerName('Jürgen'), true)
})

test('a colon between two digits is a time, not a speaker separator', () => {
  assert.equal(canBeSpeakerName('The clock struck 18', '00 in Suburban Sabotage'), false)
  assert.equal(canBeSpeakerName('Agent 47', '"Target acquired."'), true)
  assert.equal(canBeSpeakerName('Agent 47', ''), true)
})
