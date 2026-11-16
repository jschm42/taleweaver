import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/services/browserTts.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_browserTts.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { cleanForBrowserSpeech, splitIntoChunks, pickVoice } = await import(tempFile.href)

const voice = (name, lang) => ({ name, lang })
const VOICES = [
  voice('Microsoft Katja Online (Natural) - German', 'de-DE'),
  voice('Microsoft Hedda - German', 'de-DE'),
  voice('Google Deutsch', 'de-DE'),
  voice('Microsoft Zira - English', 'en-US'),
]

test('vocal tags and markdown emphasis are not read aloud', () => {
  assert.equal(cleanForBrowserSpeech('[whispers] Come *closer*, <sigh> friend.'), 'Come closer, friend.')
})

test('text is read in sentence chunks that stay below the length limit', () => {
  const text = 'First sentence. Second one! ' + 'word '.repeat(80) + 'End?'
  const chunks = splitIntoChunks(text, 60)
  assert.ok(chunks.length > 3)
  assert.ok(chunks.every(chunk => chunk.length <= 60))
  assert.equal(chunks[0], 'First sentence. Second one!')
  assert.ok(chunks.at(-1).endsWith('End?'))
})

test('the narrator gets the best voice of the language (neural first)', () => {
  assert.equal(pickVoice(VOICES, undefined, 'de').name, 'Microsoft Katja Online (Natural) - German')
})

test('characters get a stable voice other than the narrator voice', () => {
  const narrator = pickVoice(VOICES, undefined, 'de')
  const innkeeper = pickVoice(VOICES, 'Innkeeper', 'de')
  assert.notEqual(innkeeper.name, narrator.name)
  assert.equal(pickVoice(VOICES, 'innkeeper', 'de').name, innkeeper.name)
  assert.ok(innkeeper.lang.startsWith('de'))
})

test('without a voice for the language any voice is used', () => {
  assert.equal(pickVoice(VOICES, undefined, 'fr').name, 'Microsoft Katja Online (Natural) - German')
  assert.equal(pickVoice([], 'Anyone', 'de'), null)
})

test('the chosen narrator voice wins, also across languages', () => {
  const chosen = { narrator: 'Microsoft Zira - English', characters: [] }
  assert.equal(pickVoice(VOICES, undefined, 'de', chosen).name, 'Microsoft Zira - English')
})

test('characters only use the chosen character voices this browser has', () => {
  const chosen = { narrator: '', characters: ['Microsoft Hedda - German', 'Missing Voice'] }
  for (const key of ['Innkeeper', 'Guard', 'Witch', 'Bran']) {
    assert.equal(pickVoice(VOICES, key, 'de', chosen).name, 'Microsoft Hedda - German')
  }
})

test('without any chosen voice in this browser the automatic choice is used', () => {
  const chosen = { narrator: 'Gone', characters: ['Gone too'] }
  assert.equal(pickVoice(VOICES, undefined, 'de', chosen).name, 'Microsoft Katja Online (Natural) - German')
  assert.ok(pickVoice(VOICES, 'Innkeeper', 'de', chosen).lang.startsWith('de'))
})
