import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/composables/createAdventure/createAdventureForm.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_createAdventureForm.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { defaultForm, applySimpleDefaults, deriveTitle, buildCreatePayload, applySurprisePreset, applyCoverSource } =
  await import(tempFile.href)

const catalogs = {
  styles: [{ id: 'film-noir', name: 'Film Noir', instruction: 'noir' }],
  tones: [{ id: 'horror', name: 'Horror', instruction: 'dread' }],
}

test('the payload carries full catalog entries and drops combat damage outside RPG mode', () => {
  const form = { ...defaultForm(), storyIdea: '  A haunted lighthouse  ', selected_style_id: 'film-noir', selected_tone_id: 'horror' }
  form.can_damage_npcs = true
  const payload = buildCreatePayload(form, catalogs, null, 'id-1')
  assert.equal(payload.id, 'id-1')
  assert.equal(payload.original_prompt, 'A haunted lighthouse')
  assert.deepEqual(payload.selected_image_styles, [catalogs.styles[0]])
  assert.deepEqual(payload.selected_tone, catalogs.tones[0])
  assert.equal(payload.can_damage_npcs, false)
  assert.equal(payload.time_config, null)
  assert.equal(payload.cover_source_adventure_id, undefined)
})

test('manual calendar time becomes a time_config and sets the pacing', () => {
  const form = { ...defaultForm(), time_auto: false, time_config: { start_time: '21:30', pacing_minutes: 10 } }
  const payload = buildCreatePayload(form, catalogs, null, 'x')
  assert.equal(payload.time_config.time_system, 'calendar')
  assert.equal(payload.time_config.start_time, '21:30')
  assert.equal(payload.time_per_turn, 10)
})

test('cover mode adds the source and its options', () => {
  const payload = buildCreatePayload(defaultForm(), catalogs, { id: 'src', title: 'Old Tale' }, 'x')
  assert.equal(payload.cover_source_adventure_id, 'src')
  assert.equal(payload.cover_source_adventure_name, 'Old Tale')
  assert.equal(payload.cover_similarity_percent, 50)
})

test('simple defaults reset limits, media and the builder mode', () => {
  const form = { ...defaultForm(), min_scenes: 4, max_scenes: 9, generate_npc_images: false, generation_strictness: 'strict', time_auto: false }
  applySimpleDefaults(form)
  assert.equal(form.min_scenes, null)
  assert.equal(form.max_scenes, null)
  assert.equal(form.generate_npc_images, true)
  assert.equal(form.generation_strictness, 'creative')
  assert.equal(form.time_auto, true)
})

test('the title falls back to the first words of the idea without blueprint tags', () => {
  assert.equal(deriveTitle('[World] The frozen observatory wakes up tonight. More text'), 'The frozen observatory wakes up')
  assert.equal(deriveTitle('   '), 'A New Adventure')
})

test('a surprise preset matches catalog names and switches time to manual', () => {
  const form = defaultForm()
  applySurprisePreset(form, { title: 'Fog', selected_style: 'film noir', selected_tone: 'HORROR', time_system: 'units', units_per_turn: 3, min_scenes: 4 }, catalogs)
  assert.equal(form.selected_style_id, 'film-noir')
  assert.equal(form.selected_tone_id, 'horror')
  assert.equal(form.time_auto, false)
  assert.equal(form.time_config.units_per_turn, 3)
  assert.equal(form.min_scenes, 4)
})

test('a cover source prefills only empty fields and maps the legacy strict mode', () => {
  const form = { ...defaultForm(), title: 'Keep me' }
  applyCoverSource(form, {
    title: 'Origin',
    original_prompt: 'An old idea',
    selected_image_styles: [{ id: 'film-noir' }],
    selected_tone: '{"id":"horror"}',
    rule_enforcement_mode: 'strict',
  })
  assert.equal(form.title, 'Keep me')
  assert.equal(form.storyIdea, 'An old idea')
  assert.equal(form.selected_style_id, 'film-noir')
  assert.equal(form.selected_tone_id, 'horror')
  assert.equal(form.rule_enforcement_mode, 'rpg')
})
