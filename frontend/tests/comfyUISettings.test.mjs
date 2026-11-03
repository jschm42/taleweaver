import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import ts from 'typescript'

const filename = new URL('../src/components/admin/ComfyUISettings.vue', import.meta.url)
const { descriptor } = parse(readFileSync(filename, 'utf8'))
const compiled = compileScript(descriptor, { id: 'comfy-settings', inlineTemplate: true })
const source = ts.transpileModule(compiled.content, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 }
}).outputText.replace(/from ['"]vue['"]/g, `from '${import.meta.resolve('vue')}'`)
const { default: Settings } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
const render = props => renderToString(createSSRApp({ render: () => h(Settings, props) }))

test('renders the supplied server URL, timeout and independent workflow choices', async () => {
  const html = await render({ simple: true, advanced: true, url: 'http://my-gpu:9191/custom', timeout: 900,
    simpleWorkflow: 'sd15', advancedWorkflow: 'sdxl' })
  assert.match(html, /Experimental/)
  assert.match(html, /value="http:\/\/my-gpu:9191\/custom"/)
  assert.match(html, /value="900"/)
  assert.match(html, /Standard model workflow/)
  assert.match(html, /High-fidelity model workflow/)
  assert.equal((html.match(/<select/g) || []).length, 2)
  assert.match(html, /SD 1.5 — text to image/)
  assert.match(html, /SDXL — text to image/)
})

test('shows workflow selection only for the profiles using ComfyUI', async () => {
  const html = await render({ simple: false, advanced: true })
  assert.doesNotMatch(html, /Standard model workflow/)
  assert.match(html, /High-fidelity model workflow/)
  assert.equal((html.match(/<select/g) || []).length, 1)
})
