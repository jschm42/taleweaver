import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/components/editor/regions/regionExits.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_regionExits.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { sceneRegionMap, exitTargetRegion } = await import(tempFile.href)

const regions = sceneRegionMap(
  [
    { id: 'DOCK', section_id: 'HARBOR' },
    { id: 'PIER', section_id: 'HARBOR' },
    { id: 'PASS', section_id: 'PEAKS' },
    { id: 'SHED', section_id: null },
  ],
  [{ id: 'HARBOR', label: 'Harbor' }, { id: 'PEAKS', label: 'Peaks' }],
)

test('an exit inside one region leads nowhere new', () => {
  assert.equal(exitTargetRegion('DOCK', 'PIER', regions, 'HARBOR'), null)
})

test('an exit into another region names the region outside the open one', () => {
  assert.equal(exitTargetRegion('DOCK', 'PASS', regions, 'HARBOR'), 'Peaks')
  // Drawn the other way round (bidirectional exit stored from the far side).
  assert.equal(exitTargetRegion('PASS', 'DOCK', regions, 'HARBOR'), 'Peaks')
})

test('scenes without a region count as their own region', () => {
  assert.equal(exitTargetRegion('SHED', 'DOCK', regions, null), 'Harbor')
  assert.equal(regions.SHED.label, 'No region')
})

test('without an open region the target end is named', () => {
  assert.equal(exitTargetRegion('PASS', 'DOCK', regions, undefined), 'Harbor')
  assert.equal(exitTargetRegion('PASS', 'DOCK', undefined, 'HARBOR'), null)
})
