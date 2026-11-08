import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/trackIds.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_trackIds.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { suggestTrackId, cleanTrackIdInput, trackIdError } = await import(tempFile.href)

test('ids are suggested from file names in upper case with underscores', () => {
  assert.equal(suggestTrackId('crypt theme'), 'CRYPT_THEME')
  assert.equal(suggestTrackId('Früh – Nebel!'), 'FRUH_NEBEL')
  assert.equal(suggestTrackId('crypt theme', ['CRYPT_THEME']), 'CRYPT_THEME_2')
  assert.equal(suggestTrackId('!!!'), 'TRACK')
  assert.ok(suggestTrackId('a'.repeat(40), ['A'.repeat(30)]).length <= 30)
})

test('typing keeps only allowed characters and the rules are checked', () => {
  assert.equal(cleanTrackIdInput('my-theme 2'), 'MYTHEME2')
  assert.equal(cleanTrackIdInput('x'.repeat(40)).length, 30)
  assert.equal(trackIdError('MY_THEME'), '')
  assert.match(trackIdError(''), /letters, digits/)
  assert.match(trackIdError('MY_THEME', ['MY_THEME']), /already used/)
})
