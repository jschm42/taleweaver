<script setup lang="ts">
/**
 * SceneTransitionOverlay — Atmospheric scene transition curtain
 *
 * Displays a cinematic loading veil with rotating compass rose, destination banner,
 * and fantasy shimmer effect when traversing between scenes.
 */
import { Compass, Sparkles } from 'lucide-vue-next'

const props = defineProps<{
  active: boolean
  targetSceneName?: string | null
  exitLabel?: string | null
  statusText?: string | null
}>()
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
      class="absolute inset-0 z-40 flex flex-col items-center justify-center p-6 select-none bg-slate-950/90 backdrop-blur-xl bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-slate-900/80 via-slate-950/95 to-slate-950"
    >
      <!-- Ambient Glow Orb -->
      <div class="absolute w-72 h-72 rounded-full bg-amber-500/10 blur-3xl pointer-events-none animate-pulse"></div>

      <!-- Center Mystic Compass / Wayfinder Emblem -->
      <div class="relative flex items-center justify-center mb-6">
        <!-- Outer rotating rune ring -->
        <div class="w-24 h-24 sm:w-28 sm:h-28 rounded-full border border-dashed border-amber-400/40 animate-spin-slow"></div>

        <!-- Middle glowing ring -->
        <div class="absolute w-18 h-18 sm:w-20 sm:h-20 rounded-full border border-amber-500/60 bg-amber-950/30 shadow-[0_0_30px_rgba(251,191,36,0.25)] backdrop-blur-sm flex items-center justify-center">
          <Compass class="w-8 h-8 sm:w-9 sm:h-9 text-amber-400 animate-compass-breath drop-shadow-[0_0_12px_rgba(251,191,36,0.6)]" />
        </div>

        <!-- Floating Sparkles -->
        <Sparkles class="absolute -top-1 -right-1 w-4 h-4 text-amber-300 animate-pulse" />
        <Sparkles class="absolute -bottom-2 -left-2 w-3.5 h-3.5 text-amber-400/70 animate-pulse delay-300" />
      </div>

      <!-- Destination Information -->
      <div class="flex flex-col items-center text-center max-w-md px-4 z-10">
        <span class="text-[10px] sm:text-xs font-black uppercase tracking-[0.25em] text-amber-400/90 mb-1.5 flex items-center gap-1.5">
          <span>Traveling to</span>
        </span>

        <h2 class="text-xl sm:text-2xl font-black text-white tracking-tight drop-shadow-md">
          {{ formatSceneTitle(props.targetSceneName) || 'New Location' }}
        </h2>

        <p class="text-xs sm:text-sm text-slate-400 italic mt-2">
          <template v-if="props.exitLabel">
            Passing through <span class="text-amber-200/90 font-semibold not-italic">"{{ props.exitLabel }}"</span>...
          </template>
          <template v-else>
            The path unfolds into the unknown...
          </template>
        </p>

        <!-- Shimmering Progress Bar -->
        <div class="w-44 sm:w-60 h-1 bg-slate-800/80 rounded-full overflow-hidden mt-6 relative border border-white/5">
          <div class="absolute inset-0 bg-gradient-to-r from-transparent via-amber-400 to-transparent w-full animate-shimmer-sweep"></div>
        </div>

        <!-- Subtext / Status Note -->
        <span class="text-[10px] uppercase font-bold text-slate-500 tracking-widest mt-3">
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

/* Custom animations */
@keyframes spinSlow {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin-slow {
  animation: spinSlow 18s linear infinite;
}

@keyframes compassBreath {
  0%, 100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.08);
  }
}

.animate-compass-breath {
  animation: compassBreath 2.8s ease-in-out infinite;
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
</style>
