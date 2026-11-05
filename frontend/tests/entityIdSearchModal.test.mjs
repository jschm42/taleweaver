import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { Buffer } from 'node:buffer'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'

const filename = new URL('../src/components/editor/EntityIdSearchModal.vue', import.meta.url)
const { descriptor } = parse(readFileSync(filename, 'utf8'))
const compiled = compileScript(descriptor, { id: 'entity-id-search-modal', inlineTemplate: true })
const source = ts.transpileModule(compiled.content, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
  .replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
  .replace(/from ['"]lucide-vue-next['"]/g, `from '${import.meta.resolve('lucide-vue-next')}'`)

const { default: EntityIdSearchModal } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
const render = async (props) => {
  const ctx = {}
  const appHtml = await renderToString(createSSRApp({ render: () => h(EntityIdSearchModal, props) }), ctx)
  const teleportHtml = ctx.teleports ? Object.values(ctx.teleports).join('') : ''
  return appHtml + teleportHtml
}

const sampleEntities = [
  { id: 'IRON_KEY', name: 'Rusted Iron Key', type: 'OBJECT', itemType: 'KEY', description: 'Opens the old dungeon cell.' },
  { id: 'HEALING_POTION', name: 'Minor Healing Potion', type: 'OBJECT', itemType: 'POTION' },
  { id: 'ELDER_THOMAS', name: 'Elder Thomas', type: 'NPC', sceneLabel: 'Village Square' },
  { id: 'MAIN_QUEST_01', name: 'The Awakening', type: 'QUEST', description: 'Find a way out of the temple.' },
  { id: 'VILLAGE_SQUARE', name: 'Village Square', type: 'SCENE' },
  { id: 'EXIT_CELL_DOOR', name: 'Heavy Oak Door', type: 'EXIT' },
  { id: 'LEVER_GATE', name: 'Rusty Wall Lever', type: 'OBJECT', itemType: 'SWITCH' },
]

test('renders modal when show is true and displays entity IDs and category counts', async () => {
  const html = await render({ show: true, entities: sampleEntities })
  assert.match(html, /Insert Game Entity ID/)
  assert.match(html, /IRON_KEY/)
  assert.match(html, /Rusted Iron Key/)
  assert.match(html, /ELDER_THOMAS/)
  assert.match(html, /Elder Thomas/)
  assert.match(html, /MAIN_QUEST_01/)
  assert.match(html, /The Awakening/)
  assert.match(html, /VILLAGE_SQUARE/)
  assert.match(html, /EXIT_CELL_DOOR/)
  assert.match(html, /LEVER_GATE/)
  assert.match(html, /7 matches/)
  assert.match(html, /Wrap in quotes/)
})

test('does not render modal content when show is false', async () => {
  const html = await render({ show: false, entities: sampleEntities })
  assert.doesNotMatch(html, /Insert Game Entity ID/)
  assert.doesNotMatch(html, /IRON_KEY/)
})

test('renders empty state message when entities list is empty', async () => {
  const html = await render({ show: true, entities: [] })
  assert.match(html, /No matching entities found/)
})

test('renders category navigation and keyboard legend', async () => {
  const html = await render({ show: true, entities: sampleEntities })
  assert.match(html, /Items/)
  assert.match(html, /NPCs/)
  assert.match(html, /Quests/)
  assert.match(html, /Scenes/)
  assert.match(html, /Exits/)
  assert.match(html, /Switches/)
  assert.match(html, /navigate/)
  assert.match(html, /insert/)
  assert.match(html, /cancel/)
})
