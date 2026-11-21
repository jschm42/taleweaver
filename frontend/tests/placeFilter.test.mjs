import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/components/editor/filters/placeFilter.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_placeFilter.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { usePlaceFilter, groupsByScene, sectionMapOf, NO_REGION, ELSEWHERE } = await import(tempFile.href)

const scenes = [
  { id: 'gate', name: 'City Gate', section_id: 'city' },
  { id: 'market', name: 'Market', section_id: 'city' },
  { id: 'cave', name: 'Cave', section_id: 'wilds' },
  { id: 'void', name: 'Void', section_id: null },
]
const sections = [{ id: 'city', label: 'City' }, { id: 'wilds', label: 'Wilds' }]
const items = [
  { current_scene_id: 'GATE' },
  { current_scene_id: 'market' },
  { current_scene_id: 'market' },
  { current_scene_id: 'cave' },
  { current_scene_id: 'void' },
  { current_scene_id: null },
]

let counter = 0
function makeFilter() {
  counter += 1
  return usePlaceFilter({
    memoryKey: () => `test:${counter}`,
    sections: () => sections,
    sectionOfScene: () => sectionMapOf(scenes),
    groups: () => groupsByScene(items, scenes),
  })
}

test('groups entries per scene case-insensitively; unknown scenes go to the elsewhere group', () => {
  const groups = groupsByScene(items, scenes)
  assert.deepEqual(groups.map((g) => [g.label, g.count]), [['City Gate', 1], ['Market', 2], ['Cave', 1], ['Void', 1], ['Unassigned / elsewhere', 1]])
  assert.equal(groups.at(-1).sceneId, null)
})

test('region options count the entries of each region', () => {
  const filter = makeFilter()
  assert.deepEqual(filter.regionOptions.value.map((o) => o.label), ['All regions (6)', 'City (3)', 'Wilds (1)', 'No region (1)'])
})

test('a region keeps only its scenes, and the scene options narrow to that region', () => {
  const filter = makeFilter()
  filter.setRegion('city')
  assert.equal(filter.matches('gate'), true)
  assert.equal(filter.matches('cave'), false)
  assert.equal(filter.matches(null), false)
  assert.deepEqual(filter.sceneOptions.value.map((o) => o.value), ['', 'GATE', 'MARKET'])
})

test('no region keeps scenes without a region, all regions also keeps unknown scenes', () => {
  const filter = makeFilter()
  filter.setRegion(NO_REGION)
  assert.equal(filter.matches('void'), true)
  assert.equal(filter.matches('gate'), false)
  filter.clear()
  assert.equal(filter.matches(null), true)
  assert.equal(filter.isActive.value, false)
})

test('a scene filter keeps one scene; the elsewhere group is selectable too', () => {
  const filter = makeFilter()
  filter.setScene('MARKET')
  assert.equal(filter.matches('market'), true)
  assert.equal(filter.matches('gate'), false)
  filter.setScene(ELSEWHERE)
  assert.equal(filter.matches(null), true)
  assert.equal(filter.matches('void'), false)
})
