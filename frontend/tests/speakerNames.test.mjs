import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/speakerNames.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_speakerNames.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { isShortNameOf, uniqueShortNameMatch } = await import(tempFile.href)

test('a contiguous whole-word run anywhere in the name is a short name', () => {
  assert.ok(isShortNameOf('Pip Fenwick', 'Professor Pip Fenwick'))
  assert.ok(isShortNameOf('Fenwick', 'Professor Pip Fenwick'))
  assert.ok(isShortNameOf('Grimsby', 'Grimsby the Gargoyle'))
  assert.ok(isShortNameOf('Professor Pip Fenwick', 'Pip Fenwick'))
  assert.ok(isShortNameOf('Dr Holmes', 'Dr. Holmes the Elder'))
})

test('partial words, gaps and identical names are no short names', () => {
  assert.ok(!isShortNameOf('Fen', 'Professor Pip Fenwick'))
  assert.ok(!isShortNameOf('Professor Fenwick', 'Professor Pip Fenwick'))
  assert.ok(!isShortNameOf('Pip Fenwick', 'Pip Fenwick'))
  assert.ok(!isShortNameOf('', 'Pip'))
})

test('only an unambiguous candidate is returned', () => {
  const npcs = [{ name: 'Professor Pip Fenwick' }, { name: 'Lab Rat' }, { name: 'Captain Vex' }, { name: 'Captain Rook' }]
  const nameOf = (npc) => npc.name
  assert.equal(uniqueShortNameMatch('Pip Fenwick', npcs, nameOf), npcs[0])
  assert.equal(uniqueShortNameMatch('Captain', npcs, nameOf), undefined)
  assert.equal(uniqueShortNameMatch('Bram', npcs, nameOf), undefined)
})
