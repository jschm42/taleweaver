import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

// Transpile comicPages.ts to a temporary .mjs file (its only import is a type).
const tempFile = new URL('./__temp_comicPagesEnding.mjs', import.meta.url)
const js = ts.transpileModule(readFileSync(new URL('../src/composables/comicPages.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { buildComicPages } = await import(tempFile.href)

const parsers = {
  parseUser: (msg) => ({ isDialogue: false, speechText: msg.content }),
  parseAssistant: (content) => ({ narration: content, dialogues: [] }),
}

const msg = (role, content) => ({ role, content, timestamp: new Date(), scene_id: 'KITCHEN', sequence_id: 'SEQ_5' })
const ending = (outcome) => msg('adventure_ending', JSON.stringify({ outcome, reason: 'The end.' }))

test('the ending card follows the epilogue exchange', () => {
  // Arrange
  const messages = [msg('user', 'Face Grandma'), msg('assistant', 'Grandma gasps.'), msg('assistant', 'Epilogue.'), ending('won')]

  // Act
  const [page] = buildComicPages(messages, parsers)

  // Assert
  assert.equal(page.exchanges.length, 2)
  assert.equal(page.endings.length, 1)
  assert.equal(page.endings[0].afterExchange, 2)
  assert.equal(JSON.parse(page.endings[0].message.content).outcome, 'won')
})

test('play after a win continues below the card', () => {
  // Arrange
  const messages = [msg('assistant', 'Epilogue.'), ending('won'), msg('user', 'look around'), msg('assistant', 'The kitchen is quiet.')]

  // Act
  const [page] = buildComicPages(messages, parsers)

  // Assert
  assert.equal(page.exchanges.length, 2)
  assert.equal(page.endings[0].afterExchange, 1)
  assert.equal(page.exchanges[1].userMessage.content, 'look around')
})

test('a page with only an ending card is kept', () => {
  // Act
  const pages = buildComicPages([ending('lost')], parsers)

  // Assert
  assert.equal(pages.length, 1)
  assert.equal(pages[0].endings[0].afterExchange, 0)
})
