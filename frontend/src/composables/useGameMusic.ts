/**
 * useGameMusic — plays the script music of a session (`tw.music`, `music` field of GET /chat).
 *
 * The server decides what should play; this composable only follows it: it cross-fades to a
 * new track once its file is rendered, keeps the previous track while the next one is still
 * generating, and fades out on `tw.music.stop()`. Mute and volume belong to the player and are
 * kept in localStorage.
 */
import { computed, onBeforeUnmount, ref, watch, type ComputedRef, type Ref } from 'vue'
import type { MusicSnapshot } from '@/types'

const MUTED_KEY = 'game_music_muted'
const VOLUME_KEY = 'game_music_volume'
const DEFAULT_VOLUME = 0.4
const FADE_STEP_MS = 50
const STOP_FADE_SECONDS = 2
const UNLOCK_EVENTS = ['pointerdown', 'keydown'] as const

function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStored(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Storage blocked: the choice lasts for this page view only.
  }
}

interface Channel {
  audio: HTMLAudioElement
  url: string
  timer?: ReturnType<typeof setInterval>
}

function fade(channel: Channel, target: number, seconds: number, onDone?: () => void): void {
  if (channel.timer) clearInterval(channel.timer)
  const el = channel.audio
  const steps = Math.max(1, Math.round((seconds * 1000) / FADE_STEP_MS))
  const delta = (target - el.volume) / steps
  let left = steps
  channel.timer = setInterval(() => {
    left -= 1
    el.volume = left <= 0 ? target : Math.min(1, Math.max(0, el.volume + delta))
    if (left > 0) return
    clearInterval(channel.timer)
    channel.timer = undefined
    onDone?.()
  }, FADE_STEP_MS)
}

function release(channel: Channel): void {
  if (channel.timer) clearInterval(channel.timer)
  channel.audio.pause()
  channel.audio.src = ''
}

export interface GameMusicControls {
  muted: Ref<boolean>
  playerVolume: Ref<number>
  hasMusic: ComputedRef<boolean>
  isGenerating: ComputedRef<boolean>
  lastError: ComputedRef<string>
  toggleMuted: () => void
  setVolume: (value: number) => void
  stopAll: () => void
}

export function useGameMusic(music: Ref<MusicSnapshot | null>): GameMusicControls {
  const muted = ref(readStored(MUTED_KEY) === '1')
  const playerVolume = ref(Number(readStored(VOLUME_KEY) ?? DEFAULT_VOLUME) || DEFAULT_VOLUME)
  let current: Channel | null = null
  let unlockPending = false

  /** True once the session ever asked for music; the toggle is shown only then. */
  const hasMusic = computed(() => !!music.value?.enabled)
  const isGenerating = computed(() => music.value?.now?.status === 'pending')
  const lastError = computed(() => music.value?.now?.error || '')

  const targetVolume = (): number => (muted.value ? 0 : playerVolume.value * (music.value?.volume ?? 1))

  function removeUnlock(): void {
    UNLOCK_EVENTS.forEach((evt) => window.removeEventListener(evt, retryPlayback))
    unlockPending = false
  }

  async function startChannel(channel: Channel, seconds: number): Promise<void> {
    try {
      await channel.audio.play()
      removeUnlock()
      fade(channel, targetVolume(), seconds)
    } catch {
      // Autoplay is blocked until the player interacts with the page.
      if (unlockPending) return
      unlockPending = true
      UNLOCK_EVENTS.forEach((evt) => window.addEventListener(evt, retryPlayback))
    }
  }

  function retryPlayback(): void {
    if (current && current.audio.paused && !muted.value) startChannel(current, 1)
  }

  function fadeOutCurrent(seconds: number): void {
    const old = current
    current = null
    if (!old) return
    fade(old, 0, seconds, () => release(old))
  }

  function follow(snapshot: MusicSnapshot | null): void {
    const now = snapshot?.enabled ? snapshot.now : null
    if (!now) {
      fadeOutCurrent(STOP_FADE_SECONDS)
      return
    }
    // Still generating or failed: keep whatever plays now.
    if (now.status !== 'ready' || !now.url) return
    if (current?.url === now.url) {
      current.audio.loop = now.loop
      if (!muted.value) fade(current, targetVolume(), 0.5)
      return
    }
    fadeOutCurrent(now.fade)
    const audio = new Audio(now.url)
    audio.loop = now.loop
    audio.volume = 0
    current = { audio, url: now.url }
    if (!muted.value) startChannel(current, now.fade)
  }

  function toggleMuted(): void {
    muted.value = !muted.value
    writeStored(MUTED_KEY, muted.value ? '1' : '0')
    if (!current) return
    if (muted.value) {
      const channel = current
      fade(channel, 0, 0.8, () => channel.audio.pause())
      return
    }
    startChannel(current, 1)
  }

  function setVolume(value: number): void {
    playerVolume.value = Math.min(1, Math.max(0, value))
    writeStored(VOLUME_KEY, String(playerVolume.value))
    if (current && !muted.value) current.audio.volume = targetVolume()
  }

  watch(
    () => [music.value?.rev, music.value?.now?.status, music.value?.now?.url, music.value?.enabled],
    () => follow(music.value),
    { immediate: true },
  )

  function stopAll(): void {
    removeUnlock()
    if (current) release(current)
    current = null
  }

  onBeforeUnmount(stopAll)

  return { muted, playerVolume, hasMusic, isGenerating, lastError, toggleMuted, setVolume, stopAll }
}
