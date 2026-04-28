<script setup lang="ts">
const props = defineProps<{
  trackedQuest?: any
}>()
</script>

<template>
  <div class="w-full max-w-5xl mx-auto px-4">
    <transition name="fade">
      <div v-if="props.trackedQuest" class="animate-fade-in pointer-events-none w-full">
        <div :class="['quest-panel-header glassmorphism flex items-start gap-3 md:gap-4 px-3 py-2 md:px-5 md:py-4 rounded-xl md:rounded-2xl border border-white/5 pointer-events-auto shadow-2xl', props.trackedQuest.status === 'completed' ? 'opacity-60' : '']">
          <div class="w-8 h-8 md:w-10 md:h-10 flex items-center justify-center bg-indigo-500/10 rounded-lg md:rounded-xl border border-indigo-500/20 text-indigo-400 shrink-0 mt-0.5 shadow-inner">
            <i :class="['ra text-xs md:text-sm', props.trackedQuest.status === 'completed' ? 'ra-check' : 'ra-scroll']"></i>
          </div>
          <div class="flex-grow min-w-0">
            <div class="flex items-center justify-between mb-0.5 md:mb-1">
              <div :class="['text-xs md:text-sm font-black text-white uppercase tracking-tight truncate', props.trackedQuest.status === 'completed' ? 'line-through text-slate-400' : '']">
                {{ props.trackedQuest.title }}
              </div>
              <div class="shrink-0 text-right ml-2 md:ml-4">
                <span v-if="props.trackedQuest.status === 'completed'" class="text-[8px] md:text-[9px] font-black uppercase tracking-[0.2em] text-emerald-400 bg-emerald-400/10 px-1.5 md:px-2 py-0.5 rounded">Completed</span>
                <span v-else class="text-[8px] md:text-[10px] font-black text-indigo-400 tabular-nums uppercase tracking-widest">{{ props.trackedQuest.exp_reward }} XP</span>
              </div>
            </div>
            <div :class="['text-[10px] md:text-xs text-slate-400 leading-relaxed line-clamp-2 md:line-clamp-3', props.trackedQuest.status === 'completed' ? 'line-through text-slate-500' : '']">
              {{ props.trackedQuest.description }}
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.quest-panel-header {
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
