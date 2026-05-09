<script setup lang="ts">
import { ref, computed } from 'vue'
import { audioService } from '@/services/audioService'
import { configState } from '@/store/config'

interface Action {
  id: string
  label: string
  icon: string
  color: string
}

const actions: Action[] = [
  { id: 'talk', label: 'Talk', icon: 'ra-speech-bubbles', color: 'text-blue-400' },
  { id: 'inspect', label: 'Inspect', icon: 'ra-scroll-unfurled', color: 'text-cyan-400' },
  { id: 'take', label: 'Take', icon: 'ra-hand', color: 'text-amber-400' },
  { id: 'attack', label: 'Attack', icon: 'ra-sword', color: 'text-red-400' },
  { id: 'push', label: 'Push', icon: 'ra-cog', color: 'text-slate-400' },
  { id: 'pull', label: 'Pull', icon: 'ra-tread', color: 'text-slate-400' },
]

const props = defineProps<{
  activeActionId?: string | null
  mode?: string
  disabled?: boolean
}>()

const filteredActions = computed(() => {
  return actions.filter(a => {
    if (a.id === 'attack') return props.mode === 'rpg'
    return true
  })
})

const emit = defineEmits<{
  selectAction: [actionId: string | null]
}>()

function toggleAction(id: string) {
  if (props.disabled) return
  if (props.activeActionId === id) {
    emit('selectAction', null)
  } else {
    emit('selectAction', id)
  }
}
</script>

<template>
  <div class="flex items-center w-full p-2 bg-slate-900/80 border-t border-slate-800 backdrop-blur-md no-scrollbar shrink-0">
    <div class="flex items-center gap-2 px-3 mr-2 border-r border-slate-800">
      <i class="ra ra-gear text-slate-500 text-xs"></i>
      <span class="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500 whitespace-nowrap">Actions</span>
    </div>
    <div class="flex items-center gap-2 overflow-x-auto no-scrollbar flex-grow">
      <button
        v-for="action in filteredActions"
        :key="action.id"
        :disabled="props.disabled"
        class="group relative flex items-center gap-2 px-4 py-2 rounded-xl transition-all duration-300 active:scale-95 border"
        :class="[
          props.disabled
            ? 'bg-slate-800/40 border-slate-700/50 opacity-40 cursor-not-allowed'
            : activeActionId === action.id 
            ? 'bg-white/10 border-white/20 shadow-[0_0_15px_rgba(255,255,255,0.1)]' 
            : 'bg-transparent border-transparent hover:bg-white/5 hover:border-white/10'
        ]"
        @click="toggleAction(action.id)"
      >
        <i :class="['ra', action.icon, action.color, 'text-base group-hover:scale-110 transition-transform']"></i>
        <span class="text-xs font-bold text-slate-300 group-hover:text-white uppercase tracking-tight">{{ action.label }}</span>
        
        <!-- Active Indicator -->
        <div 
          v-if="activeActionId === action.id" 
          class="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"
        ></div>
      </button>
    </div>

    <!-- Right Aligned Area -->
    <div class="ml-auto flex items-center gap-6 px-4 h-full">
      <!-- Selection Instructions -->
      <div v-if="activeActionId && !props.disabled" class="flex items-center gap-3 animate-fade-in border-r border-slate-800 pr-6 mr-2">
        <div class="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20">
          <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></div>
          <span class="text-[10px] font-bold text-emerald-400 uppercase tracking-widest whitespace-nowrap">Select Target...</span>
        </div>
        <button 
          @click="emit('selectAction', null)"
          class="text-slate-500 hover:text-white transition-colors"
          title="Cancel Action"
        >
          <i class="ra ra-cancel text-xs"></i>
        </button>
      </div>

      <!-- TTS Controls -->
      <div v-if="configState.isTtsEnabled" class="flex items-center gap-2">
        <button 
          v-show="audioService.isPlaying.value"
          @click="audioService.stop()"
          class="group relative flex items-center gap-2 px-4 py-2 rounded-xl transition-all duration-300 active:scale-95 border bg-transparent border-transparent hover:bg-white/5 hover:border-white/10 animate-fade-in shrink-0"
          title="Stop Speech (SPACE)"
        >
          <i class="ra ra-stop text-red-400 text-base group-hover:scale-110 transition-transform animate-pulse"></i>
          <span class="text-xs font-bold text-slate-300 group-hover:text-white uppercase tracking-tight">Stop</span>
        </button>

        <button 
          @click="audioService.toggleAutoSpeech()"
          class="group relative flex items-center gap-2 px-4 py-2 rounded-xl transition-all duration-300 active:scale-95 border shrink-0"
          :class="[
            audioService.autoSpeechEnabled.value 
              ? 'bg-white/10 border-white/20 shadow-[0_0_15px_rgba(255,255,255,0.1)]' 
              : 'bg-transparent border-transparent hover:bg-white/5 hover:border-white/10'
          ]"
          title="Toggle Automatic Speech"
        >
          <i :class="['ra text-base group-hover:scale-110 transition-transform', audioService.autoSpeechEnabled.value ? 'ra-microphone text-blue-400' : 'ra-microphone-mute text-slate-500']"></i>
          <span class="text-xs font-bold text-slate-300 group-hover:text-white uppercase tracking-tight">Auto Speak</span>
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
@keyframes fadeIn {
  from { opacity: 0; transform: translateX(10px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
