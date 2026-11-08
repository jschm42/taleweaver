/**
 * useHoverMusicPreview — plays a library tile's start-scene music while the mouse is over it.
 *
 * One shared player for all tiles: hovering the next tile replaces the previous preview.
 * A short delay keeps a mouse that only passes over a tile from starting music, and the player's
 * in-game music settings (mute, volume; see useGameMusic) apply here too. Browsers only allow
 * audio after the first click or key press on the page, so previews stay silent until then.
 */

import { musicMuted, musicVolume } from '@/store/musicPreferences'

const START_DELAY_MS = 250
const FADE_MS = 600
const FADE_STEP_MS = 40

let audio: HTMLAudioElement | null = null
let currentUrl = ''
let startTimer: ReturnType<typeof setTimeout> | undefined
// Each element fades on its own, so a new preview never cuts off the fade-out of the last one.
const fadeTimers = new WeakMap<HTMLAudioElement, ReturnType<typeof setInterval>>()

function targetVolume(): number {
  return musicVolume.value
}

function fadeTo(el: HTMLAudioElement, target: number, onDone?: () => void): void {
  const running = fadeTimers.get(el)
  if (running) clearInterval(running)
  const steps = Math.max(1, Math.round(FADE_MS / FADE_STEP_MS))
  const delta = (target - el.volume) / steps
  let left = steps
  const timer = setInterval(() => {
    left -= 1
    el.volume = left <= 0 ? target : Math.min(1, Math.max(0, el.volume + delta))
    if (left > 0) return
    clearInterval(timer)
    fadeTimers.delete(el)
    onDone?.()
  }, FADE_STEP_MS)
  fadeTimers.set(el, timer)
}

function fadeOutCurrent(): void {
  const el = audio
  audio = null
  currentUrl = ''
  if (el) fadeTo(el, 0, () => el.pause())
}

function release(): void {
  const el = audio
  audio = null
  currentUrl = ''
  if (!el) return
  const running = fadeTimers.get(el)
  if (running) clearInterval(running)
  el.pause()
}

function start(url: string): void {
  fadeOutCurrent()
  const el = new Audio(url)
  el.loop = true
  el.volume = 0
  audio = el
  currentUrl = url
  el.play()
    .then(() => {
      if (audio === el) fadeTo(el, targetVolume())
    })
    .catch(() => {
      // Autoplay blocked (no click on the page yet) or the file is gone: stay silent.
      if (audio === el) release()
    })
}

/** Start the preview for ``url`` after a short hover delay. */
export function startHoverMusic(url: string | null | undefined): void {
  if (startTimer) clearTimeout(startTimer)
  if (!url || musicMuted.value || url === currentUrl) return
  startTimer = setTimeout(() => start(url), START_DELAY_MS)
}

/** Fade the preview out (the mouse left the tile). */
export function stopHoverMusic(): void {
  if (startTimer) clearTimeout(startTimer)
  startTimer = undefined
  fadeOutCurrent()
}
