<script setup lang="ts">
/**
 * CutsceneOverlay — a cut-scene (chapter intro or `tw.cutscene.play`) over the whole play view.
 *
 * Slides (image + text) follow each other like the travel curtain's cinematic veil: the image
 * drifts slowly (Ken Burns), the text sits in a letterboxed caption. Colors and fonts follow
 * the active dialog skin (--tw-overlay-* tokens, src/skins/overlays.css). Holding the mouse
 * button or Space skips the current slide, Escape the whole cut-scene. Timing and speech:
 * composables/useCutsceneSlides.ts. Spec: docs/specs/cutscenes.md.
 */
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useCutsceneSlides } from '@/composables/useCutsceneSlides'
import type { Cutscene } from '@/types'

const props = defineProps<{
  cutscene: Cutscene | null
  /** Read the slide texts aloud (the player's auto-speech setting). */
  autoSpeech: boolean
  /** Dialog skin (`data-skin`) and accent style: the overlay is rendered outside the skinned root. */
  skin?: string
  skinStyle?: Record<string, string>
}>()

const emit = defineEmits<{ finished: [] }>()

const slides = useCutsceneSlides(() => props.autoSpeech, () => emit('finished'))
const { index, holdProgress } = slides

const current = computed(() => props.cutscene?.slides[index.value] ?? null)
const total = computed(() => props.cutscene?.slides.length ?? 0)
// SVG ring around the skip hint: full circumference 2πr with r = 10.
const RING = 2 * Math.PI * 10
const ringOffset = computed(() => RING * (1 - holdProgress.value))

watch(
  () => props.cutscene?.token,
  (token) => {
    slides.stop()
    if (token && props.cutscene) slides.start(props.cutscene)
  },
  { immediate: true },
)

function onKeyDown(event: KeyboardEvent): void {
  if (!props.cutscene) return
  if (event.key === 'Escape') {
    event.preventDefault()
    slides.skipAll()
    return
  }
  if (event.code !== 'Space') return
  event.preventDefault()
  if (!event.repeat) slides.beginHold()
}

function onKeyUp(event: KeyboardEvent): void {
  if (event.code === 'Space') slides.endHold()
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown, true)
  window.addEventListener('keyup', onKeyUp, true)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown, true)
  window.removeEventListener('keyup', onKeyUp, true)
})
</script>

<template>
  <Transition name="cutscene-fade">
    <div
      v-if="props.cutscene"
      class="tw-skin tw-overlay fixed inset-0 z-[70] select-none overflow-hidden cursor-pointer"
      :data-skin="props.skin"
      :style="props.skinStyle"
      role="dialog"
      aria-modal="true"
      :aria-label="props.cutscene.title || 'Cut-scene'"
      @pointerdown="slides.beginHold"
      @pointerup="slides.endHold"
      @pointerleave="slides.endHold"
      @pointercancel="slides.endHold"
      @contextmenu.prevent
    >
      <!-- Slide image (cross-fades between slides) -->
      <Transition name="cutscene-slide">
        <div :key="current?.id ?? index" class="absolute inset-0 pointer-events-none">
          <img
            v-if="current?.image_url"
            :src="current.image_url"
            alt=""
            class="cutscene-image absolute inset-0 w-full h-full object-cover object-center"
          />
          <div v-else class="tw-overlay-veil absolute inset-0"></div>
        </div>
      </Transition>

      <div class="tw-overlay-wash absolute inset-0 pointer-events-none"></div>
      <div class="tw-overlay-texture absolute inset-0 pointer-events-none"></div>
      <div class="cutscene-letterbox absolute inset-0 pointer-events-none"></div>

      <!-- Title (first slide) -->
      <Transition name="cutscene-caption">
        <div
          v-if="index === 0 && props.cutscene.title"
          class="absolute top-[8vh] inset-x-0 flex flex-col items-center gap-2 px-6 pointer-events-none"
        >
          <span class="tw-overlay-rule h-px w-40 sm:w-64"></span>
          <h2 class="tw-overlay-title tw-overlay-title--chapter text-2xl sm:text-4xl tracking-wide text-center">
            {{ props.cutscene.title }}
          </h2>
          <span class="tw-overlay-rule h-px w-40 sm:w-64"></span>
        </div>
      </Transition>

      <!-- Caption -->
      <div class="absolute inset-x-0 bottom-0 flex flex-col items-center px-6 pb-[7vh] pointer-events-none">
        <Transition name="cutscene-caption" mode="out-in">
          <p
            v-if="current?.text"
            :key="current.id"
            class="cutscene-text max-w-3xl text-center text-base sm:text-xl leading-relaxed whitespace-pre-line"
          >
            {{ current.text }}
          </p>
        </Transition>

        <div v-if="total > 1" class="mt-5 flex items-center gap-2" aria-hidden="true">
          <span
            v-for="n in total"
            :key="n"
            class="cutscene-dot h-1.5 rounded-full transition-all duration-500"
            :class="n - 1 === index ? 'w-6 is-current' : 'w-1.5'"
          ></span>
        </div>
      </div>

      <!-- Skip hint with hold progress ring -->
      <div class="absolute right-4 bottom-4 sm:right-6 sm:bottom-6 flex items-center gap-2 pointer-events-none">
        <span class="tw-overlay-muted text-[11px] sm:text-xs">Hold Space or mouse to skip · Esc ends</span>
        <svg class="w-6 h-6 -rotate-90" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10" class="cutscene-ring-track" fill="none" stroke-width="2" />
          <circle
            cx="12"
            cy="12"
            r="10"
            class="cutscene-ring"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            :stroke-dasharray="RING"
            :stroke-dashoffset="ringOffset"
          />
        </svg>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.cutscene-fade-enter-active { transition: opacity 0.6s ease-out; }
.cutscene-fade-leave-active { transition: opacity 0.8s ease-in; }
.cutscene-fade-enter-from,
.cutscene-fade-leave-to { opacity: 0; }

.cutscene-slide-enter-active,
.cutscene-slide-leave-active { transition: opacity 1.1s ease; }
.cutscene-slide-enter-from,
.cutscene-slide-leave-to { opacity: 0; }

.cutscene-caption-enter-active { transition: opacity 0.7s ease-out 0.25s, transform 0.7s ease-out 0.25s; }
.cutscene-caption-leave-active { transition: opacity 0.35s ease-in; }
.cutscene-caption-enter-from { opacity: 0; transform: translateY(8px); }
.cutscene-caption-leave-to { opacity: 0; }

/* The slide image is the content here: only lightly dimmed, unlike the travel backdrop. */
.cutscene-image {
  filter: saturate(1.05) brightness(0.92);
  animation: cutsceneDrift 18s ease-out forwards;
}

@keyframes cutsceneDrift {
  from { transform: scale(1.12) translate3d(1.2%, 0.8%, 0); }
  to { transform: scale(1.02) translate3d(-0.8%, -0.4%, 0); }
}

.cutscene-letterbox {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--tw-overlay-bg) 85%, transparent),
    transparent 22%,
    transparent 52%,
    color-mix(in srgb, var(--tw-overlay-bg) 92%, transparent) 88%
  );
}

.cutscene-text {
  color: var(--tw-overlay-ink);
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.95);
}

.cutscene-dot { background: color-mix(in srgb, var(--tw-overlay-muted) 45%, transparent); }
.cutscene-dot.is-current { background: var(--tw-overlay-accent); }

.cutscene-ring-track { stroke: color-mix(in srgb, var(--tw-overlay-muted) 35%, transparent); }
.cutscene-ring { stroke: var(--tw-overlay-accent); }

@media (prefers-reduced-motion: reduce) {
  .cutscene-image { animation: none; }
}
</style>
