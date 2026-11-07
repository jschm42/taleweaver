import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import ts from 'typescript'

if (typeof globalThis.Audio === 'undefined') {
  globalThis.Audio = class MockAudio {
    constructor(url = '') {
      this.src = url
      this.loop = false
      this.volume = 1
      this.listeners = {}
    }
    async play() {
      return undefined
    }
    pause() {}
    removeAttribute(attr) {
      if (attr === 'src') this.src = ''
    }
    load() {}
    addEventListener(event, cb) {
      this.listeners[event] = cb
    }
  }
}

const apiDefTs = new URL('../src/utils/twScriptApiDefinitions.ts', import.meta.url)
const musicServiceTs = new URL('../src/services/musicService.ts', import.meta.url)

const apiDefJs = ts.transpileModule(readFileSync(apiDefTs, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

const musicServiceJs = ts.transpileModule(readFileSync(musicServiceTs, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

const tempApiDefFile = new URL('./__temp_sceneMusic_twScriptApiDefinitions.mjs', import.meta.url)
const tempMusicServiceFile = new URL('./__temp_sceneMusic_musicService.mjs', import.meta.url)

writeFileSync(tempApiDefFile, apiDefJs)
writeFileSync(tempMusicServiceFile, musicServiceJs)

let TW_NAMESPACES, TW_ROOT_ITEMS, musicService

try {
  const apiModule = await import(tempApiDefFile.href)
  TW_NAMESPACES = apiModule.TW_NAMESPACES
  TW_ROOT_ITEMS = apiModule.TW_ROOT_ITEMS

  const musicModule = await import(tempMusicServiceFile.href)
  musicService = musicModule.musicService
} finally {
  try { unlinkSync(tempApiDefFile) } catch {}
  try { unlinkSync(tempMusicServiceFile) } catch {}
}

test('TW_NAMESPACES includes audio and sound namespaces with expected methods', () => {
  const expectedMethods = ['play_music', 'stop_music', 'play_sound', 'play']
  for (const ns of ['audio', 'sound']) {
    assert.ok(TW_NAMESPACES[ns], `Missing namespace: ${ns}`)
    const itemNames = TW_NAMESPACES[ns].items.map((item) => item.name)
    for (const method of expectedMethods) {
      assert.ok(itemNames.includes(method), `Namespace ${ns} missing method ${method}`)
      const item = TW_NAMESPACES[ns].items.find((it) => it.name === method)
      assert.equal(item.kind, 'method')
    }
  }
})

test('TW_NAMESPACES scene namespace includes music_url property', () => {
  assert.ok(TW_NAMESPACES.scene, 'Missing scene namespace')
  const musicUrlItem = TW_NAMESPACES.scene.items.find((item) => item.name === 'music_url')
  assert.ok(musicUrlItem, 'scene namespace missing music_url')
  assert.equal(musicUrlItem.kind, 'property')
})

test('TW_ROOT_ITEMS includes audio and sound namespaces', () => {
  const rootNames = TW_ROOT_ITEMS.map((item) => item.name)
  assert.ok(rootNames.includes('audio'), 'TW_ROOT_ITEMS missing audio')
  assert.ok(rootNames.includes('sound'), 'TW_ROOT_ITEMS missing sound')
})

test('musicService has expected initial state', () => {
  assert.equal(musicService.volume.value, 0.6)
  assert.equal(musicService.isMuted.value, false)
  assert.equal(musicService.isPlaying.value, false)
})

test('musicService.setVolume clamps between 0.0 and 1.0', () => {
  musicService.setVolume(1.5)
  assert.equal(musicService.volume.value, 1.0)

  musicService.setVolume(-0.5)
  assert.equal(musicService.volume.value, 0.0)

  musicService.setVolume(0.45)
  assert.equal(musicService.volume.value, 0.45)

  musicService.setVolume(0.6)
  assert.equal(musicService.volume.value, 0.6)
})

test('musicService.toggleMute and setMuted update isMuted state', () => {
  assert.equal(musicService.isMuted.value, false)

  musicService.toggleMute()
  assert.equal(musicService.isMuted.value, true)

  musicService.toggleMute()
  assert.equal(musicService.isMuted.value, false)

  musicService.setMuted(true)
  assert.equal(musicService.isMuted.value, true)

  musicService.setMuted(false)
  assert.equal(musicService.isMuted.value, false)
})

test('musicService.handleAudioEvents dispatches play_music, stop_music, play_sound, and play without throwing', async () => {
  assert.doesNotThrow(() => {
    musicService.handleAudioEvents([
      { action: 'play_music', url: '/music/theme.mp3', loop: true, volume: 0.8 },
      { action: 'play_sound', url: '/sfx/click.mp3', volume: 0.9 },
      { action: 'play', url: '/sfx/chime.mp3', loop: false, volume: 0.7 },
      { action: 'play', url: '/music/ambient.mp3', loop: true, volume: 0.5 },
      { action: 'stop_music' },
    ])
  })
  assert.equal(musicService.isPlaying.value, false)
  assert.equal(musicService.currentUrl.value, null)
})
