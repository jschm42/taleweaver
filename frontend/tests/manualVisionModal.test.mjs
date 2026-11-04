import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'

const filename = new URL('../src/components/editor/ManualVisionModal.vue', import.meta.url)
const { descriptor } = parse(readFileSync(filename, 'utf8'))
const compiled = compileScript(descriptor, { id: 'manual-vision-modal', inlineTemplate: true })
const source = ts.transpileModule(compiled.content, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText.replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
const { default: ManualVisionModal } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
)

const defaultLimits = {
  cover: { maxBytes: 8 * 1024 * 1024, hint: 'Optimal: portrait 2:3 or landscape 16:9, max 2048x2048.' },
  protagonist: { maxBytes: 8 * 1024 * 1024, hint: 'Optimal: portrait 2:3, max 1536x2048.' },
  scene: { maxBytes: 8 * 1024 * 1024, hint: 'Optimal: landscape 16:9 / 3:2, max 2048x1536.' },
  npc: { maxBytes: 8 * 1024 * 1024, hint: 'Optimal: portrait 2:3, max 1536x2048.' },
  object: { maxBytes: 8 * 1024 * 1024, hint: 'Optimal: square 1:1, max 1536x1536.' },
}

const render = async props => {
  const ctx = {}
  const html = await renderToString(
    createSSRApp({
      render: () =>
        h(ManualVisionModal, {
          show: true,
          uploadLimits: defaultLimits,
          formatBytes: bytes => `${bytes / (1024 * 1024)}.0 MB`,
          fixNewlines: text => text || '',
          ...props,
        }),
    }),
    ctx
  )
  return (ctx.teleports && ctx.teleports.body) || html
}

test('renders compact layout with pinned header, scrollable body, and target info', async () => {
  const html = await render({
    selectedVisual: {
      kind: 'npc',
      id: 'npc_ada',
      label: 'Ada Beginning',
      description: 'Senior Python examiner in a dark brown vest.',
      hint: 'Optimal: portrait 2:3, max 1536x2048.',
      appearance: 'dark brown vest, silver wire glasses, ink-stained fingers',
    },
    visualPrompt: 'Ada examining exam papers under gaslight',
    isSuggestingPrompt: false,
    isEnhancingPrompt: false,
    isRegenerating: false,
    useAdvancedModel: false,
    applyStyle: true,
    applyAppearance: true,
    configuredStyleName: 'Victorian Oil Painting',
  })

  // Compact layout and scrolling structure
  assert.match(html, /max-h-\[90vh\]/)
  assert.match(html, /overflow-y-auto/)
  assert.match(html, /custom-scrollbar/)

  // Target header
  assert.match(html, /Manual Vision Weaver/)
  assert.match(html, /Target:.*Ada Beginning/)

  // Description
  assert.match(html, /Current description/)
  assert.match(html, /Senior Python examiner in a dark brown vest/)

  // Appearance keywords card (for NPC)
  assert.match(html, /Appearance Keywords/)
  assert.match(html, /Configured/)
  assert.match(html, /dark brown vest, silver wire glasses, ink-stained fingers/)

  // Toggles
  assert.match(html, /Apply Appearance Keywords/)
  assert.match(html, /Apply Adventure Style/)
  assert.match(html, /Apply &#39;Victorian Oil Painting&#39; style to prompt/)
  assert.match(html, /High-Quality Weaver/)

  // Buttons
  assert.match(html, /Enhance Prompt/)
  assert.match(html, /Suggest Prompt/)
  assert.match(html, /Generate Vision/)
  assert.match(html, /Discard/)
})

test('hides Enhance Prompt button when visualPrompt is empty', async () => {
  const html = await render({
    selectedVisual: {
      kind: 'npc',
      id: 'npc_dex',
      label: 'Dex Dictionary',
      description: 'Librarian with scrolls',
      hint: 'Optimal: portrait 2:3, max 1536x2048.',
    },
    visualPrompt: '',
    isSuggestingPrompt: false,
    isEnhancingPrompt: false,
    isRegenerating: false,
    useAdvancedModel: false,
  })

  assert.doesNotMatch(html, /Enhance Prompt/)
  assert.match(html, /Suggest Prompt/)
})

test('hides appearance section and appearance toggle for non-character visuals', async () => {
  const html = await render({
    selectedVisual: {
      kind: 'scene',
      id: 'scene_hall',
      label: 'The Hall of Examination',
      description: 'Vast wooden lecture hall with brass machines.',
      hint: 'Optimal: landscape 16:9 / 3:2, max 2048x1536.',
    },
    visualPrompt: 'Grand Victorian lecture hall',
    isSuggestingPrompt: false,
    isEnhancingPrompt: false,
    isRegenerating: false,
    useAdvancedModel: true,
    applyStyle: true,
  })

  // No appearance section or toggle rendered for scenes
  assert.doesNotMatch(html, /<h4[^>]*>Appearance Keywords/)
  assert.doesNotMatch(html, />Apply Appearance Keywords</)
  assert.match(html, /Apply Adventure Style/)
  assert.match(html, /High-Quality Weaver/)
})

test('displays alternative hint when applyStyle is false', async () => {
  const html = await render({
    selectedVisual: {
      kind: 'cover',
      id: 'adv_cover',
      label: 'Adventure Cover',
      description: 'Book cover scene',
      hint: 'Optimal: portrait 2:3 or landscape 16:9, max 2048x2048.',
    },
    visualPrompt: 'A glowing book in shadows',
    isSuggestingPrompt: false,
    isEnhancingPrompt: false,
    isRegenerating: false,
    useAdvancedModel: false,
    applyStyle: false,
  })

  assert.match(html, /Send prompt without adventure style to T2I model/)
})

test('reflects regenerating state with Weaving spinner and Abort action', async () => {
  const html = await render({
    selectedVisual: {
      kind: 'npc',
      id: 'npc_1',
      label: 'Test Target',
      description: 'Test target description',
      hint: 'Test hint',
    },
    visualPrompt: 'Drawing test target',
    isSuggestingPrompt: false,
    isEnhancingPrompt: false,
    isRegenerating: true,
    useAdvancedModel: false,
  })

  assert.match(html, /Weaving\.\.\./)
  assert.match(html, /Abort/)
  assert.doesNotMatch(html, /Discard/)
})
