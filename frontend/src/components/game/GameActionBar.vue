<script setup lang="ts">
import { computed } from 'vue'
import { audioService } from '@/services/audioService'
import { configState } from '@/store/config'

const props = defineProps<{
  activeActionId?: string | null
  mode?: string
  disabled?: boolean
  suggestions?: string[]
}>()

const visibleSuggestions = computed(() => {
  const incoming = Array.isArray(props.suggestions) ? props.suggestions : []
  return incoming.filter(Boolean).slice(0, 3)
})

const emit = defineEmits<{
  selectAction: [actionId: string | null]
  useSuggestion: [suggestion: string]
  shuffleSuggestions: []
}>()
</script>

<template>
  <div class="flex items-center w-full p-2 bg-slate-900/80 border-t border-slate-800 backdrop-blur-md no-scrollbar shrink-0">
    <button
      :disabled="props.disabled"
      aria-label="Generate new ideas"
      title="Generate new ideas"
      class="ideas-trigger group flex items-center gap-2 px-3 mr-2 border-r border-slate-800 whitespace-nowrap rounded-lg transition-all duration-300 active:scale-95"
      :class="props.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'"
      @click="emit('shuffleSuggestions')"
    >
      <i class="ra ra-light-bulb text-amber-400 text-xs transition-transform duration-300 group-hover:scale-110"></i>
      <span class="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 group-hover:text-slate-300 transition-colors">Ideas</span>
    </button>

    <div class="flex items-center gap-2 overflow-x-auto no-scrollbar flex-grow">
      <button
        v-for="(suggestion, idx) in visibleSuggestions"
        :key="`${idx}-${suggestion}`"
        :disabled="props.disabled"
        :aria-label="`Use suggestion: ${suggestion}`"
        :title="suggestion"
        class="group relative flex items-center gap-2 px-3 py-1.5 rounded-full transition-all duration-300 active:scale-95 border text-xs font-semibold"
        :class="[
          props.disabled
            ? 'bg-slate-800/40 border-slate-700/50 opacity-40 cursor-not-allowed'
            : 'bg-slate-800/70 border-slate-700/70 text-slate-200 hover:bg-slate-700/70 hover:border-slate-500/70'
        ]"
        @click="emit('useSuggestion', suggestion)"
      >
        <span class="max-w-[22rem] truncate">{{ suggestion }}</span>
      </button>
    </div>

    <!-- Right Aligned Area -->
    <div class="ml-auto flex items-center gap-2 px-2 sm:px-4 h-full">
      <!-- TTS Controls -->
      <div v-if="configState.isTtsEnabled" class="flex items-center gap-2">
        <button
          v-show="audioService.isPlaying.value"
          @click="audioService.stop()"
          class="group relative flex items-center justify-center w-8 h-8 rounded-xl transition-all duration-300 active:scale-95 border bg-transparent border-transparent hover:bg-white/5 hover:border-white/10 animate-fade-in shrink-0"
          title="Stop Speech (SPACE)"
          aria-label="Stop speech"
        >
          <i class="ra ra-stop text-red-400 text-base group-hover:scale-110 transition-transform animate-pulse"></i>
        </button>

        <button
          @click="audioService.toggleAutoSpeech()"
          class="group relative flex items-center justify-center w-8 h-8 rounded-xl transition-all duration-300 active:scale-95 border shrink-0"
          :class="[
            audioService.autoSpeechEnabled.value
              ? 'bg-blue-500/15 border-blue-500/40 shadow-[0_0_12px_rgba(96,165,250,0.25)]'
              : 'bg-transparent border-transparent hover:bg-white/5 hover:border-white/10'
          ]"
          title="Toggle Automatic Speech"
          :aria-label="audioService.autoSpeechEnabled.value ? 'Auto Speak enabled' : 'Auto Speak disabled'"
        >
          <i :class="['ra text-base group-hover:scale-110 transition-transform', audioService.autoSpeechEnabled.value ? 'ra-microphone text-blue-400' : 'ra-microphone-mute text-slate-500']"></i>
          <div
            v-if="audioService.autoSpeechEnabled.value"
            class="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"
          ></div>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.animate-fade-in {
  animation: fadeIn 0.3s ease-out;
}

.ideas-trigger:not(:disabled):hover {
  background: rgba(251, 191, 36, 0.08);
  box-shadow: 0 0 16px -2px rgba(251, 191, 36, 0.55), inset 0 0 0 1px rgba(251, 191, 36, 0.2);
}
.ideas-trigger:not(:disabled):hover .ra-light-bulb {
  filter: drop-shadow(0 0 6px rgba(251, 191, 36, 0.8));
  color: rgb(252, 211, 77);
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateX(10px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
