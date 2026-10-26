<script setup lang="ts">
/**
 * SpeechControls — Pause/continue, skip the current line, or stop reading aloud.
 * Shown only while speech is playing or being prepared (auto-speech or a bubble's Audio button).
 */
import { computed } from 'vue'
import { Pause, Play, SkipForward, Square } from 'lucide-vue-next'
import { audioService } from '@/services/audioService'

const isActive = computed(() => audioService.isPlaying.value)
const isPaused = computed(() => audioService.isPaused.value)
</script>

<template>
  <Transition
    enter-from-class="opacity-0 translate-y-2"
    leave-to-class="opacity-0 translate-y-2"
    enter-active-class="transition duration-200"
    leave-active-class="transition duration-150"
  >
    <div
      v-if="isActive"
      class="flex items-center gap-1 rounded-full border border-slate-700/70 bg-slate-950/90 p-1 shadow-xl backdrop-blur-md"
      role="group"
      aria-label="Speech playback"
    >
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-200 hover:bg-white/10 transition-colors"
        :title="isPaused ? 'Continue reading aloud' : 'Pause reading aloud'"
        :aria-pressed="isPaused"
        @click="audioService.togglePause()"
      >
        <Play v-if="isPaused" class="h-3.5 w-3.5" />
        <Pause v-else class="h-3.5 w-3.5" />
        <span>{{ isPaused ? 'Continue' : 'Pause' }}</span>
      </button>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-200 hover:bg-white/10 transition-colors"
        title="Skip to the next line"
        @click="audioService.skip()"
      >
        <SkipForward class="h-3.5 w-3.5" />
        <span>Skip</span>
      </button>
      <button
        type="button"
        class="flex items-center rounded-full p-1.5 text-slate-400 hover:bg-white/10 hover:text-red-300 transition-colors"
        title="Stop reading aloud"
        aria-label="Stop reading aloud"
        @click="audioService.stop()"
      >
        <Square class="h-3.5 w-3.5" />
      </button>
    </div>
  </Transition>
</template>
