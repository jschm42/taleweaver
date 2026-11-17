import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { loadSfc } from './helpers/loadSfc.mjs'

const Settings = await loadSfc('../src/components/admin/ComfyUISettings.vue', import.meta.url)
const render = props => renderToString(createSSRApp({ render: () => h(Settings, props) }))

test('renders the supplied server URL, timeout and independent workflow choices', async () => {
  const html = await render({ simple: true, advanced: true, url: 'http://my-gpu:9191/custom', timeout: 900,
    simpleWorkflow: 'sd15', advancedWorkflow: 'sdxl' })
  assert.match(html, /Experimental/)
  assert.match(html, /value="http:\/\/my-gpu:9191\/custom"/)
  assert.match(html, /value="900"/)
  assert.match(html, /Workflow for the standard model/)
  assert.match(html, /Workflow for the high-fidelity model/)
  assert.equal((html.match(/<select/g) || []).length, 2)
  assert.match(html, /SD 1.5 – text to image/)
  assert.match(html, /SDXL – text to image/)
})

test('shows workflow selection only for the profiles using ComfyUI', async () => {
  const html = await render({ simple: false, advanced: true })
  assert.doesNotMatch(html, /Workflow for the standard model/)
  assert.match(html, /Workflow for the high-fidelity model/)
  assert.equal((html.match(/<select/g) || []).length, 1)
})
