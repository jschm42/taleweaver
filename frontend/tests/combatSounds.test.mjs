import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'

const source = readFileSync(new URL('../src/components/game/combat/combatSounds.ts', import.meta.url), 'utf8')
const soundDir = new URL('../public/assets/audio/combat/', import.meta.url)
const readme = readFileSync(new URL('README.md', soundDir), 'utf8')

const block = source.slice(source.indexOf('COMBAT_SOUND_FILES = {'), source.indexOf('} as const'))
const files = [...block.matchAll(/'([a-z_]+\.mp3)'/g)].map((m) => m[1])

test('every combat sound has a file to replace', () => {
  assert.ok(files.length > 20, 'sound registry was not parsed')
  for (const file of files) {
    assert.ok(existsSync(new URL(file, soundDir)), `missing ${file} in public/assets/audio/combat`)
  }
})

test('the folder holds no sound the game never plays', () => {
  const onDisk = readdirSync(soundDir).filter((name) => name.endsWith('.mp3'))
  assert.deepEqual(onDisk.sort(), [...files].sort())
})

test('the README lists every combat sound', () => {
  for (const file of files) {
    assert.ok(readme.includes(`\`${file}\``), `README.md does not describe ${file}`)
  }
})
