<script setup lang="ts">
/**
 * SceneTransitionOverlay — Atmospheric scene transition curtain
 *
 * Displays a cinematic loading veil with destination banner and shimmer effect when traversing between scenes. When the destination
 * scene has an image, it is revealed behind the veil with a slow Ken Burns drift
 * and layered gradient vignettes. Colors and fonts follow the active dialog skin
 * (--tw-overlay-* tokens, see src/skins/overlays.css).
 */
import { ref, watch } from 'vue'

const props = defineProps<{
  active: boolean
  targetSceneName?: string | null
  exitLabel?: string | null
  statusText?: string | null
  backgroundImageUrl?: string | null
}>()

const imageLoaded = ref(false)
const imageFailed = ref(false)

watch(
  () => props.backgroundImageUrl,
  () => {
    imageLoaded.value = false
    imageFailed.value = false
  },
)

function formatSceneTitle(name?: string | null): string {
  if (!name) return ''
  const trimmed = String(name).trim()
  if (trimmed.includes('_') || trimmed.includes('-') || /^[A-Z0-9\s_-]+$/.test(trimmed)) {
    return trimmed
      .replace(/[_-]+/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, c => c.toUpperCase())
  }
  return trimmed
}
</script>

<template>
  <Transition name="scene-veil">
    <div
      v-if="props.active"
      class="tw-overlay fixed inset-0 z-[60] flex flex-col items-center justify-center p-6 select-none overflow-hidden"
    >
      <!-- Destination Scene Backdrop -->
      <div class="absolute inset-0 pointer-events-none">
        <img
          v-if="props.backgroundImageUrl && !imageFailed"
          :src="props.backgroundImageUrl"
          alt=""
          class="scene-backdrop absolute inset-0 w-full h-full object-cover object-center"
          :class="{ 'is-loaded': imageLoaded }"
          @load="imageLoaded = true"
          @error="imageFailed = true"
        />

        <!-- Base radial veil (also the fallback when no image is available) -->
        <div class="tw-overlay-veil absolute inset-0"></div>

        <!-- Cinematic letterbox gradients (top & bottom) -->
        <div class="tw-overlay-letterbox absolute inset-0"></div>

        <!-- Warm/cool color wash for a magical tint -->
        <div class="tw-overlay-wash absolute inset-0"></div>
        <div class="tw-overlay-texture absolute inset-0"></div>

        <!-- Drifting light sweep -->
        <div class="absolute inset-0 light-sweep mix-blend-screen"></div>

        <!-- Soft edge vignette -->
        <div class="tw-overlay-vignette absolute inset-0"></div>
      </div>

      <!-- Ambient Glow Orb -->
      <div class="tw-overlay-glow absolute w-72 h-72 rounded-full blur-3xl pointer-events-none animate-pulse"></div>

      <!-- Destination Information -->
      <div class="flex flex-col items-center text-center max-w-md px-4 z-10">
        <span class="tw-overlay-eyebrow text-[10px] sm:text-xs font-black uppercase tracking-[0.25em] mb-1.5 flex items-center gap-1.5">
          <span>Traveling to</span>
        </span>

        <h2 class="tw-overlay-title text-xl sm:text-3xl font-black tracking-wide">
          {{ formatSceneTitle(props.targetSceneName) || 'New Location' }}
        </h2>

        <p class="tw-overlay-muted text-xs sm:text-sm italic mt-2 drop-shadow-[0_1px_6px_rgba(0,0,0,0.9)]">
          <template v-if="props.exitLabel">
            Passing through <span class="tw-overlay-highlight font-semibold not-italic">"{{ props.exitLabel }}"</span>...
          </template>
          <template v-else>
            The path unfolds into the unknown...
          </template>
        </p>

        <!-- Shimmering Progress Bar -->
        <div class="tw-overlay-progress w-44 sm:w-60 h-1 rounded-full overflow-hidden mt-6 relative">
          <div class="tw-overlay-progress-bar absolute inset-0 w-full animate-shimmer-sweep"></div>
        </div>

        <!-- Subtext / Status Note -->
        <span class="tw-overlay-muted text-[10px] uppercase font-bold tracking-widest mt-3 drop-shadow-[0_1px_4px_rgba(0,0,0,0.9)]">
          {{ props.statusText || 'Weaving scene narrative...' }}
        </span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Smooth scene curtain fade */
.scene-veil-enter-active {
  transition: opacity 0.3s ease-out, transform 0.3s ease-out;
}
.scene-veil-leave-active {
  transition: opacity 0.45s ease-in, transform 0.45s ease-in;
}
.scene-veil-enter-from {
  opacity: 0;
  transform: scale(1.02);
}
.scene-veil-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

/* Destination backdrop: blurred & dim until loaded, then sharpens and drifts */
.scene-backdrop {
  opacity: 0;
  filter: blur(18px) saturate(0.6) brightness(0.5);
  transform: scale(1.15);
  transition:
    opacity 1.2s ease-out,
    filter 1.8s ease-out;
}

.scene-backdrop.is-loaded {
  opacity: 0.85;
  filter: blur(1.5px) var(--tw-overlay-image-filter);
  animation: kenBurns 14s ease-out forwards;
}

@keyframes kenBurns {
  from {
    transform: scale(1.15) translate3d(1.5%, 1%, 0);
  }
  to {
    transform: scale(1.03) translate3d(-1%, -0.5%, 0);
  }
}

.light-sweep {
  background: linear-gradient(
    115deg,
    transparent 30%,
    rgba(253, 230, 138, 0.08) 45%,
    rgba(253, 230, 138, 0.16) 50%,
    rgba(253, 230, 138, 0.08) 55%,
    transparent 70%
  );
  background-size: 250% 100%;
  animation: lightSweep 6s ease-in-out infinite;
}

@keyframes lightSweep {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@keyframes shimmerSweep {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.animate-shimmer-sweep {
  animation: shimmerSweep 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@media (prefers-reduced-motion: reduce) {
  .scene-backdrop.is-loaded,
  .light-sweep {
    animation: none;
  }
}
</style>
