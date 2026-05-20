<script setup lang="ts">
defineProps<{
  adventure: any
}>()
</script>

<template>
  <section v-if="adventure?.quests?.length" class="space-y-6 animate-page-in">
    <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Quest Log ({{ adventure.quests.length }})</h3>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="quest in adventure.quests" :key="'quest_' + quest.id" class="bg-slate-900/40 border border-white/5 rounded-2xl p-4 hover:border-emerald-500/20 transition-all group">
        <div class="flex items-start justify-between mb-2">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
              <i :class="[quest.is_main ? 'ra ra-trophy text-emerald-400' : 'ra ra-scroll-unfurled text-slate-400']"></i>
            </div>
            <div>
              <h4 class="text-sm font-bold text-white">{{ quest.title }}</h4>
              <span class="text-xs text-slate-500 uppercase tracking-widest">{{ quest.is_main ? 'Main Quest' : 'Side Quest' }}</span>
            </div>
          </div>
          <span class="px-2 py-0.5 rounded bg-black/40 text-xs font-black text-emerald-500 uppercase border border-emerald-500/20">{{ quest.exp_reward }} XP</span>
        </div>
        <p class="text-xs text-slate-400 leading-relaxed line-clamp-2 mb-3">{{ quest.description }}</p>
        <div class="flex items-center gap-2">
          <div class="flex-grow h-1 bg-black/40 rounded-full overflow-hidden">
            <div class="h-full bg-emerald-500/40" :style="{ width: quest.status === 'completed' ? '100%' : '0%' }"></div>
          </div>
          <span class="text-xs font-black uppercase tracking-tighter" :class="quest.status === 'completed' ? 'text-emerald-500' : 'text-slate-600'">{{ quest.status }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
