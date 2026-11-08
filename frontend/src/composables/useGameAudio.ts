/**
 * useGameAudio — plays the script audio of a session (`tw.audio`, `audio` field of GET /chat).
 *
 * The server decides what should play; this composable only follows it: it cross-fades to a
 * new track once its file is rendered, keeps the previous track while the next one is still
 * generating, and fades out on `tw.audio.stop()`. Mute and volume belong to the player
 * (store/audioPreferences, also set in the in-game settings) and apply at once when changed.
 *
 * Looping tracks are not looped by the audio element: shortly before the end a second copy
 * starts and the two cross-fade, because generated clips rarely have a seamless loop point.
 */
import { computed, onBeforeUnmount, watch, type ComputedRef, type Ref } from 'vue'
import type { AudioSnapshot } from '@/types'
import { audioMuted, audioVolume, setAudioVolume } from '@/store/audioPreferences'

const FADE_STEP_MS = 50
const STOP_FADE_SECONDS = 2
/** Cross-fade at the loop point; tracks shorter than three times this loop natively. */
const LOOP_OVERLAP_SECONDS = 1.5
const UNLOCK_EVENTS = ['pointerdown', 'keydown'] as const

interface Channel {
  audio: HTMLAudioElement
  url: string
  loop: boolean
  /** True once the next loop copy took over (only one hand-off per channel). */
  handedOff?: boolean
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

export interface GameAudioControls {
  muted: Ref<boolean>
  playerVolume: Ref<number>
  hasAudio: ComputedRef<boolean>
  isGenerating: ComputedRef<boolean>
  lastError: ComputedRef<string>
  toggleMuted: () => void
  setVolume: (value: number) => void
  stopAll: () => void
}

export function useGameAudio(audio: Ref<AudioSnapshot | null>): GameAudioControls {
  const muted = audioMuted
  const playerVolume = audioVolume
  let current: Channel | null = null
  let unlockPending = false

  /** True when the session has audio (script, scene or theme); the toggle is shown only then. */
  const hasAudio = computed(() => !!audio.value)
  const isGenerating = computed(() => audio.value?.now?.status === 'pending')
  const lastError = computed(() => audio.value?.now?.error || '')

  const targetVolume = (): number => (muted.value ? 0 : playerVolume.value * (audio.value?.volume ?? 1))

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

  function handOffLoop(channel: Channel): void {
    const el = channel.audio
    const duration = el.duration
    if (channel !== current || channel.handedOff || !channel.loop) return
    if (!Number.isFinite(duration) || duration < LOOP_OVERLAP_SECONDS * 3) return
    if (duration - el.currentTime > LOOP_OVERLAP_SECONDS) return
    channel.handedOff = true
    const next = openChannel(channel.url, true)
    current = next
    if (!muted.value) startChannel(next, LOOP_OVERLAP_SECONDS)
    fade(channel, 0, LOOP_OVERLAP_SECONDS, () => release(channel))
  }

  function openChannel(url: string, loop: boolean): Channel {
    const audio = new Audio(url)
    audio.volume = 0
    const channel: Channel = { audio, url, loop }
    audio.addEventListener('loadedmetadata', () => {
      // Short clips cannot overlap themselves; let the element loop them.
      audio.loop = loop && audio.duration < LOOP_OVERLAP_SECONDS * 3
    })
    audio.addEventListener('timeupdate', () => handOffLoop(channel))
    return channel
  }

  function follow(snapshot: AudioSnapshot | null): void {
    const now = snapshot?.now ?? null
    if (!now) {
      fadeOutCurrent(STOP_FADE_SECONDS)
      return
    }
    // Still generating or failed: keep whatever plays now.
    if (now.status !== 'ready' || !now.url) return
    if (current?.url === now.url) {
      current.loop = now.loop
      if (!muted.value) fade(current, targetVolume(), 0.5)
      return
    }
    fadeOutCurrent(now.fade)
    current = openChannel(now.url, now.loop)
    if (!muted.value) startChannel(current, now.fade)
  }

  function applyMuted(): void {
    if (!current) return
    if (muted.value) {
      const channel = current
      fade(channel, 0, 0.8, () => channel.audio.pause())
      return
    }
    startChannel(current, 1)
  }

  function toggleMuted(): void {
    muted.value = !muted.value
  }

  function setVolume(value: number): void {
    setAudioVolume(value)
  }

  // Mute and volume may also change in the in-game settings.
  watch(muted, applyMuted)
  watch(playerVolume, () => {
    if (current && !muted.value && !current.timer) current.audio.volume = targetVolume()
  })

  watch(
    () => [audio.value?.rev, audio.value?.now?.status, audio.value?.now?.url],
    () => follow(audio.value),
    { immediate: true },
  )

  function stopAll(): void {
    removeUnlock()
    if (current) release(current)
    current = null
  }

  onBeforeUnmount(stopAll)

  return { muted, playerVolume, hasAudio, isGenerating, lastError, toggleMuted, setVolume, stopAll }
}
