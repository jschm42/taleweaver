import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/autoSpeakQueue.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_autoSpeakQueue.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { currentTurnAssistantMessages, unspokenTurnMessages } = await import(tempFile.href)

const drama = [
  { role: 'assistant', content: 'Earlier turn narration.' },
  { role: 'user', content: '/give_items Tina | Pink Glitter Energy Drink' },
  { role: 'system', content: 'You give Pink Glitter Energy Drink to Tina.' },
  { role: 'assistant', content: 'Tina: "OMG, Pink Glitter Zero!"' },
  { role: 'assistant', content: 'Tina: "MOOOOM! HELP!"' },
  { role: 'assistant', content: 'Tina storms down the stairs.' },
  { role: 'system', content: '[DEBUG: Trigger fired] on_receive_item on TINA', is_debug: true },
  { role: 'assistant', content: 'Jack looks around the hallway.' },
]

test('all GM messages after the last player message belong to the turn, oldest first', () => {
  const turn = currentTurnAssistantMessages(drama).map(({ index }) => index)
  assert.deepEqual(turn, [3, 4, 5, 7])
})

test('only messages not spoken yet are returned', () => {
  const spoken = new Set([7])
  const pending = unspokenTurnMessages(drama, (_message, index) => spoken.has(index))
  assert.deepEqual(pending.map(({ index }) => index), [3, 4, 5])
})

test('debug lines and empty messages are never read', () => {
  const turn = currentTurnAssistantMessages([
    { role: 'user', content: 'look' },
    { role: 'assistant', content: '   ' },
    { role: 'assistant', content: 'debug', is_debug: true },
  ])
  assert.deepEqual(turn, [])
})
