<script setup lang="ts">
import GameQuestTracker from '@/components/game/GameQuestTracker.vue'
import GameClockWidget from '@/components/game/GameClockWidget.vue'

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
}>()

const handleBack = () => {
  emit('back')
}
</script>

<template>
  <header class="bg-transparent px-4 md:px-8 pt-8 pb-4 flex flex-col lg:flex-row items-start gap-6 z-10 shrink-0 relative min-h-[110px]">
    <div class="flex items-center gap-4 z-10 min-w-0 xl:w-72 shrink-0">
      <button
        @click="handleBack"
        class="flex items-center gap-3 px-5 py-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-emerald-500/10 hover:border-emerald-500/40 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
        title="Return to Portal"
      >
        <i class="ra ra-back-arrow text-sm text-slate-100 group-hover:text-emerald-400 transition-colors"></i>
        <span class="text-xxs font-black uppercase tracking-[0.2em] text-slate-100 group-hover:text-white transition-colors">Back</span>
      </button>

      <div class="flex flex-col min-w-0">
        <h1 class="text-xl md:text-3xl font-normal text-white drop-shadow-[0_2px_15px_rgba(0,0,0,0.8)] tracking-wide whitespace-nowrap truncate adventure-title">
          {{ props.title || 'Chronicle' }}
        </h1>
        <div v-if="props.version" class="text-[10px] font-mono font-bold text-slate-500 opacity-60 uppercase tracking-widest mt-1">
          v{{ props.version }}
        </div>
      </div>
    </div>

    <div class="flex-grow w-full lg:w-auto min-w-0 flex justify-center">
      <GameQuestTracker :tracked-quest="props.trackedQuest" />
    </div>

    <div class="absolute top-8 right-4 md:right-8 lg:mt-0 z-20">
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
