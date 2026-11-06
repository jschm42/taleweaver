<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Volume2, VolumeX } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    src: string
    /** Target volume (0..1) after the fade-in. */
    volume?: number
  }>(),
  { volume: 0.35 },
)

const MUTED_KEY = 'login_music_muted'
const FADE_MS = 2500
const FADE_STEP_MS = 50
const UNLOCK_EVENTS = ['pointerdown', 'keydown'] as const

const muted = ref(readMuted())
let audio: HTMLAudioElement | undefined
let fadeTimer: ReturnType<typeof setInterval> | undefined

function readMuted(): boolean {
  try {
    return localStorage.getItem(MUTED_KEY) === '1'
  } catch {
    return false
  }
}

function writeMuted(value: boolean) {
  try {
    localStorage.setItem(MUTED_KEY, value ? '1' : '0')
  } catch {
    // Storage blocked: the choice just lasts for this page view.
  }
}

function fadeTo(target: number, onDone?: () => void) {
  if (!audio) return
  if (fadeTimer) clearInterval(fadeTimer)
  const el = audio
  const step = ((target - el.volume) * FADE_STEP_MS) / FADE_MS
  fadeTimer = setInterval(() => {
    const next = el.volume + step
    const reached = step >= 0 ? next >= target : next <= target
    el.volume = reached ? target : Math.min(1, Math.max(0, next))
    if (!reached) return
    clearInterval(fadeTimer)
    fadeTimer = undefined
    onDone?.()
  }, FADE_STEP_MS)
}

function removeUnlockListeners() {
  UNLOCK_EVENTS.forEach((evt) => window.removeEventListener(evt, startPlayback))
}

async function startPlayback() {
  if (!audio || muted.value || !audio.paused) return
  try {
    await audio.play()
    removeUnlockListeners()
    fadeTo(props.volume)
  } catch {
    // Autoplay blocked until the user interacts with the page; the unlock listeners retry.
  }
}

function toggleMuted() {
  muted.value = !muted.value
  writeMuted(muted.value)
  if (!audio) return
  if (muted.value) {
    fadeTo(0, () => audio?.pause())
    return
  }
  startPlayback()
}

onMounted(() => {
  audio = new Audio(props.src)
  audio.loop = true
  audio.volume = 0
  UNLOCK_EVENTS.forEach((evt) => window.addEventListener(evt, startPlayback))
  startPlayback()
})

onBeforeUnmount(() => {
  removeUnlockListeners()
  if (fadeTimer) clearInterval(fadeTimer)
  audio?.pause()
  audio = undefined
})
</script>

<template>
  <button
    type="button"
    class="absolute top-4 right-4 z-20 p-2.5 rounded-full border border-white/10 bg-black/40 text-slate-400 hover:text-aether-primary hover:border-aether-primary/30 transition-colors"
    :title="muted ? 'Play background music' : 'Mute background music'"
    :aria-label="muted ? 'Play background music' : 'Mute background music'"
    :aria-pressed="!muted"
    @click.stop="toggleMuted"
  >
    <VolumeX v-if="muted" class="w-4 h-4" />
    <Volume2 v-else class="w-4 h-4" />
  </button>
</template>
