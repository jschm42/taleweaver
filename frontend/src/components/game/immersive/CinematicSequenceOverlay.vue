<script setup lang="ts">
/**
 * CinematicSequenceOverlay — Movie-style Sequence / Chapter intro banner
 *
 * Displays an atmospheric, cinematic title overlay across the story chat
 * when entering a new sequence/chapter, with gentle fade in and out.
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  activeSequence?: any | null
  adventureTitle?: string | null
}>()

const isVisible = ref(false)
const displayedSequence = ref<any | null>(null)
const lastSeenSequenceId = ref<string | null>(null)
let autoDismissTimer: number | null = null

function triggerOverlay(seq: any) {
  if (!seq || !seq.id) return

  if (autoDismissTimer !== null) {
    clearTimeout(autoDismissTimer)
    autoDismissTimer = null
  }

  displayedSequence.value = { ...seq }
  lastSeenSequenceId.value = seq.id
  isVisible.value = true

  // Auto-dismiss smoothly after 4.5 seconds
  autoDismissTimer = window.setTimeout(() => {
    dismiss()
  }, 4500)
}

function dismiss() {
  if (autoDismissTimer !== null) {
    clearTimeout(autoDismissTimer)
    autoDismissTimer = null
  }
  isVisible.value = false
}

// Watch for sequence changes
watch(
  () => props.activeSequence,
  (newSeq) => {
    if (!newSeq || !newSeq.id) return
    if (newSeq.id !== lastSeenSequenceId.value) {
      triggerOverlay(newSeq)
    }
  },
  { deep: true }
)

onMounted(() => {
  // If active sequence is already present on mount, show it after a brief initial pause
  if (props.activeSequence && props.activeSequence.id) {
    window.setTimeout(() => {
      if (props.activeSequence && props.activeSequence.id !== lastSeenSequenceId.value) {
        triggerOverlay(props.activeSequence)
      }
    }, 600)
  }
})

onBeforeUnmount(() => {
  if (autoDismissTimer !== null) {
    clearTimeout(autoDismissTimer)
  }
})
</script>

<template>
  <Transition name="cinematic-fade">
    <div
      v-if="isVisible && displayedSequence"
      class="absolute inset-0 z-[70] flex flex-col items-center justify-center p-6 select-none bg-slate-950/90 backdrop-blur-md cursor-pointer overflow-hidden"
      @click="dismiss"
    >
      <!-- Cinematic Vignette / Letterbox Lighting -->
      <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-amber-500/10 via-slate-950/60 to-slate-950/95 pointer-events-none"></div>

      <!-- Glowing Ambient Orb behind title -->
      <div class="absolute w-96 h-96 rounded-full bg-amber-400/10 blur-3xl pointer-events-none animate-pulse"></div>

      <div class="relative z-10 flex flex-col items-center text-center max-w-2xl px-6">
        <!-- Sequence Chapter Eyebrow -->
        <div class="flex items-center gap-3 mb-3">
          <div class="w-8 sm:w-16 h-[1px] bg-gradient-to-r from-transparent to-amber-400/80"></div>
          <span class="text-[11px] sm:text-xs font-mono font-bold tracking-[0.35em] uppercase text-amber-400 drop-shadow-[0_0_12px_rgba(251,191,36,0.6)]">
            <template v-if="displayedSequence.order">
              Chapter {{ displayedSequence.order }}
            </template>
            <template v-else>
              Sequence
            </template>
          </span>
          <div class="w-8 sm:w-16 h-[1px] bg-gradient-to-l from-transparent to-amber-400/80"></div>
        </div>

        <!-- Grand Cinematic Sequence Title -->
        <h1 class="text-2xl sm:text-4xl md:text-5xl font-black uppercase tracking-wider text-transparent bg-clip-text bg-gradient-to-b from-white via-slate-100 to-slate-300 drop-shadow-[0_6px_25px_rgba(0,0,0,0.95)] leading-tight cinema-title">
          {{ displayedSequence.title || displayedSequence.id }}
        </h1>

        <!-- Ornate Center Accent Divider -->
        <div class="flex items-center justify-center gap-2 my-3 sm:my-4 w-full">
          <div class="w-16 sm:w-28 h-[1px] bg-gradient-to-r from-transparent via-amber-400/50 to-transparent"></div>
          <div class="w-1.5 h-1.5 rotate-45 bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]"></div>
          <div class="w-16 sm:w-28 h-[1px] bg-gradient-to-r from-transparent via-amber-400/50 to-transparent"></div>
        </div>

        <!-- Optional Description / Tagline -->
        <p
          v-if="displayedSequence.description"
          class="text-xs sm:text-sm text-slate-300/90 font-serif italic max-w-md sm:max-w-lg leading-relaxed text-center drop-shadow px-2"
        >
          {{ displayedSequence.description }}
        </p>

        <!-- Subtle Skip Hint -->
        <span class="text-[9px] uppercase tracking-[0.25em] text-slate-500/70 font-semibold mt-6 transition-opacity hover:text-slate-300">
          Click anywhere to continue
        </span>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Cinematic smooth enter and leave transitions */
.cinematic-fade-enter-active {
  transition: opacity 0.8s cubic-bezier(0.16, 1, 0.3, 1), transform 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.cinematic-fade-leave-active {
  transition: opacity 1s cubic-bezier(0.16, 1, 0.3, 1), transform 1s cubic-bezier(0.16, 1, 0.3, 1);
}

.cinematic-fade-enter-from {
  opacity: 0;
  transform: scale(0.96);
}

.cinematic-fade-leave-to {
  opacity: 0;
  transform: scale(1.02);
}

/* Subtle letter-spacing expansion on title reveal */
.cinema-title {
  animation: title-breathe 4.5s ease-out forwards;
}

@keyframes title-breathe {
  0% {
    letter-spacing: 0.05em;
  }
  100% {
    letter-spacing: 0.12em;
  }
}
</style>
