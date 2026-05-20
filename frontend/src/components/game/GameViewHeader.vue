<script setup lang="ts">
import GameQuestTracker from '@/components/game/GameQuestTracker.vue'
import GameClockWidget from '@/components/game/GameClockWidget.vue'
import { FileText } from 'lucide-vue-next'

const props = defineProps<{
  title?: string | null
  version?: string | null
  trackedQuest?: any
  gameTime: { dateShort: string; time: string } | null
  clockTick: boolean
  debugMode?: boolean
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'edit-note'): void
}>()

const handleBack = () => {
  emit('back')
}
</script>

<template>
  <header class="bg-transparent px-4 md:px-8 pt-8 pb-4 flex flex-col lg:flex-row items-start justify-between gap-6 z-10 shrink-0 relative min-h-[110px]">
    <div class="flex flex-col items-start gap-2 z-10 min-w-0 shrink-0 lg:w-1/4">
      <div class="flex items-center gap-2">
        <button
          @click="handleBack"
          class="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-emerald-500/10 hover:border-emerald-500/40 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
          title="Return to Portal"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5 text-slate-100 group-hover:text-emerald-400 transition-colors">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
        </button>

        <button
          v-if="props.title"
          @click="emit('edit-note')"
          class="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-amber-500/10 hover:border-amber-500/40 text-amber-400/80 hover:text-amber-400 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
          title="Edit Session Note"
        >
          <FileText class="w-5 h-5" />
        </button>
      </div>

      <div class="flex flex-col min-w-0">
        <h1 class="text-xl md:text-3xl font-normal text-white drop-shadow-[0_2px_15px_rgba(0,0,0,0.8)] tracking-wide adventure-title">
          {{ props.title || 'Chronicle' }}
        </h1>
        <div v-if="props.version" class="text-[10px] font-mono font-bold text-slate-500 opacity-60 uppercase tracking-widest mt-1">
          v{{ props.version }}
        </div>
      </div>
    </div>

    <div class="flex-grow w-full lg:w-2/4 min-w-0 flex justify-center">
      <GameQuestTracker :tracked-quest="props.trackedQuest" />
    </div>

    <div class="z-20 shrink-0 lg:w-1/4 flex justify-end">
      <GameClockWidget :game-time="props.gameTime" :clock-tick="props.clockTick" />
    </div>

    <div v-if="props.debugMode" class="absolute top-24 left-1/2 -translate-x-1/2 z-[100] px-4 py-1 bg-rose-600/80 backdrop-blur-md border border-rose-400/50 rounded-full text-[10px] font-black text-white uppercase tracking-[0.2em] animate-pulse shadow-lg">
      Debug Protocol Active
    </div>
  </header>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Acme&display=swap');

.adventure-title {
  font-family: 'Acme', sans-serif;
}
</style>
