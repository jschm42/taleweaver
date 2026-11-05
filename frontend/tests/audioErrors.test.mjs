import { test, after } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/services/audioErrors.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText
const tempFile = new URL('./__temp_audioErrors.mjs', import.meta.url)
writeFileSync(tempFile, js)
after(() => { try { unlinkSync(tempFile) } catch {} })
const { describePlaybackError, CONNECTION_LOST_MESSAGE, AUTOPLAY_BLOCKED_MESSAGE } = await import(tempFile.href)

test('browser network errors become one readable message', () => {
  for (const raw of [
    'Failed to fetch',
    'NetworkError when attempting to fetch resource.',
    'Load failed',
    'Audio stream failed - code:2 msg:network',
  ]) {
    assert.equal(describePlaybackError(raw), CONNECTION_LOST_MESSAGE, raw)
  }
})

test('autoplay blocks keep their hint', () => {
  assert.equal(describePlaybackError('NotAllowedError: play() failed'), AUTOPLAY_BLOCKED_MESSAGE)
})

test('provider errors are shown as they are', () => {
  const raw = 'TTS Provider error: quota exceeded'
  assert.equal(describePlaybackError(raw), raw)
  assert.equal(describePlaybackError('Audio stream failed - code:20 msg:x'), 'Audio stream failed - code:20 msg:x')
})
