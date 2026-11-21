import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/components/admin/catalogTransfer.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_catalogTransfer.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { mergeCatalog, parseCatalogFile, buildCatalogFile, normalizeTile } = await import(tempFile.href)

const current = [
  { id: 'noir', name: 'Noir (edited)', description: '', instruction: 'mine', image_url: null },
  { id: 'own', name: 'My style', description: '', instruction: 'x', image_url: null },
]

test('merge replaces same ids, appends new ones and keeps the others in place', () => {
  const incoming = [
    { id: 'noir', name: 'Noir', description: 'd', instruction: 'default', image_url: '/a.jpg' },
    { id: 'survival', name: 'Survival', description: '', instruction: 'y', image_url: null },
  ]
  const result = mergeCatalog(current, incoming)
  assert.deepEqual(result.items.map((i) => i.id), ['noir', 'own', 'survival'])
  assert.equal(result.items[0].instruction, 'default')
  assert.equal(result.replaced, 1)
  assert.equal(result.added, 1)
  assert.equal(current[0].instruction, 'mine')
})

test('an exported file imports again unchanged', () => {
  const file = JSON.stringify(buildCatalogFile('styles', current))
  assert.deepEqual(parseCatalogFile(file, 'styles'), current)
})

test('a plain array is accepted; entries without a name are skipped and ids are derived', () => {
  const items = parseCatalogFile(JSON.stringify([{ name: 'Rusty Gears' }, { id: 'nameless' }]), 'tones')
  assert.deepEqual(items.map((i) => i.id), ['rusty-gears'])
})

test('a file of the other catalog type is rejected', () => {
  const file = JSON.stringify(buildCatalogFile('tones', current))
  assert.throws(() => parseCatalogFile(file, 'styles'), /holds tones/)
})

test('broken JSON and empty files give readable errors', () => {
  assert.throws(() => parseCatalogFile('{', 'styles'), /not valid JSON/)
  assert.throws(() => parseCatalogFile('[]', 'styles'), /no valid entries/)
  assert.equal(normalizeTile('text'), null)
})
