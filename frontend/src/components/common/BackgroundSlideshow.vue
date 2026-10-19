<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = withDefaults(
  defineProps<{
    images: string[]
    /** Time each image stays visible (ms) before the next crossfade starts. */
    interval?: number
  }>(),
  { interval: 5000 },
)

const FADE_MS = 2000
// Max pan offset in % — must stay below (minScale - 1) / 2 so edges never show
const MAX_PAN = 3.5

const activeIndex = ref(0)
const leavingIndex = ref(-1)
const motions = ref<Record<string, string>[]>([])
let timer: ReturnType<typeof setInterval> | undefined

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min)
}

function randomMotion(): Record<string, string> {
  const pan = () => `${randomBetween(-MAX_PAN, MAX_PAN).toFixed(2)}%`
  const zoomIn = Math.random() < 0.5
  const [s0, s1] = zoomIn ? [1.1, 1.16] : [1.16, 1.1]
  return {
    '--x0': pan(),
    '--y0': pan(),
    '--x1': pan(),
    '--y1': pan(),
    '--s0': String(s0),
    '--s1': String(s1),
  }
}

function advance() {
  if (document.hidden) return
  const next = (activeIndex.value + 1) % props.images.length
  motions.value[next] = randomMotion()
  leavingIndex.value = activeIndex.value
  activeIndex.value = next
}

onMounted(() => {
  // Preload so the first crossfade never reveals a half-loaded image
  props.images.forEach((src) => {
    const img = new Image()
    img.src = src
  })
  motions.value = props.images.map(randomMotion)
  if (props.images.length < 2) return
  timer = setInterval(advance, props.interval)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div
    class="slideshow"
    aria-hidden="true"
    :style="{ '--slide-duration': `${interval + FADE_MS}ms`, '--fade-duration': `${FADE_MS}ms` }"
  >
    <div
      v-for="(src, i) in images"
      :key="src"
      class="slide"
      :class="{ active: i === activeIndex, leaving: i === leavingIndex }"
      :style="[{ backgroundImage: `url('${src}')` }, motions[i]]"
    ></div>
    <!-- Dimming layers: light overall darkening plus a vignette toward the edges -->
    <div class="dim"></div>
  </div>
</template>

<style scoped>
.slideshow {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.slide {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0;
  filter: saturate(0.9) brightness(0.75);
  transition: opacity var(--fade-duration) ease-in-out;
  will-change: opacity, transform;
}

.slide.active {
  opacity: 1;
}

/* Same animation on active and leaving, so the drift keeps running through the fade-out */
.slide.active,
.slide.leaving {
  animation: drift var(--slide-duration) linear forwards;
}

@keyframes drift {
  from {
    transform: translate(var(--x0), var(--y0)) scale(var(--s0));
  }
  to {
    transform: translate(var(--x1), var(--y1)) scale(var(--s1));
  }
}

.dim {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at center, rgba(2, 6, 12, 0.15) 0%, rgba(2, 6, 12, 0.6) 75%, rgba(2, 6, 12, 0.9) 100%),
    linear-gradient(to bottom, rgba(2, 6, 12, 0.2), rgba(2, 6, 12, 0.5));
}

@media (prefers-reduced-motion: reduce) {
  .slide.active,
  .slide.leaving {
    animation: none;
    transform: scale(1.1);
  }
}
</style>
