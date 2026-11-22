import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/composables/regionBuilder/regionBuilderForm.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_regionBuilderForm.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const {
  formFor, applySimpleDefaults, buildPayload, setContextOn, setAllContext, formatTokens, DEFAULT_CONTEXT,
} = await import(tempFile.href)

const region = { label: 'Peaks', description: 'Cold.', brief: '  Dwarven ruins.  ' }

test('a region without stored settings starts in simple mode with all context on', () => {
  const form = formFor(region)
  assert.equal(form.mode, 'simple')
  assert.equal(form.size, 'medium')
  assert.deepEqual(form.context, DEFAULT_CONTEXT)
  const payload = buildPayload(form)
  assert.equal(payload.brief, 'Dwarven ruins.')
  assert.equal(payload.options.min_scenes, 6)
  assert.equal(payload.options.max_scenes, 10)
})

test('stored settings reopen the builder the way it was left', () => {
  const form = formFor({
    ...region,
    generation_settings: {
      mode: 'advanced',
      context: { scenes: 'full', npcs: 'off', walkthroughs: false, bogus: 'x' },
      options: { min_items: 3, max_items: null, award_generation_enabled: false, generation_strictness: 'loose' },
    },
  })
  assert.equal(form.mode, 'advanced')
  assert.equal(form.context.scenes, 'full')
  assert.equal(form.context.npcs, 'off')
  assert.equal(form.context.walkthroughs, false)
  assert.equal(form.options.min_items, 3)
  assert.equal(form.options.award_generation_enabled, false)
  assert.equal(form.options.generation_strictness, 'creative')
  assert.equal(buildPayload(form).options.min_items, 3)
})

test('simple mode keeps on and off but resets details and counts', () => {
  const form = formFor(region)
  form.mode = 'advanced'
  form.context.scenes = 'full'
  setContextOn(form, 'plot', false)
  form.options.max_quests = 4
  form.mode = 'simple'
  applySimpleDefaults(form)
  assert.equal(form.context.scenes, 'compact')
  assert.equal(form.context.plot, 'off')
  assert.equal(form.options.max_quests, null)
})

test('all off and all on switch every context option', () => {
  const form = formFor(region)
  setAllContext(form, false)
  assert.ok(Object.entries(form.context).every(([key, value]) => key === 'walkthroughs' || value === 'off'))
  setAllContext(form, true)
  assert.equal(form.context.items, 'compact')
})

test('token labels are short estimates', () => {
  assert.equal(formatTokens(840), '≈ 840 tokens')
  assert.equal(formatTokens(1234), '≈ 1.2k tokens')
  assert.equal(formatTokens(48210), '≈ 48k tokens')
})
