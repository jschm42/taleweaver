<script setup lang="ts">
import { computed } from 'vue'
import bronzeTrophy from '@/assets/svg/bronze-award-trophy.svg'
import silverTrophy from '@/assets/svg/silver-award-trophy.svg'
import goldTrophy from '@/assets/svg/gold-award-trophy.svg'

const props = defineProps<{
  adventure: any
}>()

const awards = computed<any[]>(() => {
  const raw = props.adventure?.awards
  if (Array.isArray(raw)) return raw
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
})

function getAwardIcon(tier: string) {
  const t = (tier || '').toLowerCase()
  if (t === 'gold') return goldTrophy
  if (t === 'silver') return silverTrophy
  return bronzeTrophy
}
</script>

<template>
  <section class="space-y-6 animate-page-in">
    <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Achievements & Awards ({{ awards.length }})</h3>
    <p v-if="awards.length === 0" class="text-xs text-slate-500 uppercase tracking-widest">No awards generated for this adventure yet.</p>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="award in awards" :key="'award_' + (award.key || award.title)" class="bg-slate-900/40 border border-white/5 rounded-2xl p-5 hover:border-emerald-500/20 transition-all group flex items-start gap-4">
        <div :class="[
          'w-12 h-12 rounded-xl flex items-center justify-center border shrink-0',
          award.tier === 'gold' ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' :
          award.tier === 'silver' ? 'bg-slate-300/10 border-slate-300/20 text-slate-300' :
          'bg-orange-700/10 border-orange-700/20 text-orange-700'
        ]">
          <img :src="getAwardIcon(award.tier)" class="w-8 h-8 object-contain" alt="Trophy" />
        </div>
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <h4 class="text-sm font-black text-white uppercase tracking-tight">{{ award.title }}</h4>
            <span :class="[
              'text-xs font-black uppercase px-1.5 py-0.5 rounded border',
              award.tier === 'gold' ? 'bg-amber-500/20 border-amber-500/30 text-amber-500' :
              award.tier === 'silver' ? 'bg-slate-300/20 border-slate-300/30 text-slate-300' :
              'bg-orange-700/20 border-orange-700/30 text-orange-700'
            ]">{{ award.tier }}</span>
          </div>
          <p class="text-xs text-slate-400 leading-relaxed">{{ award.description }}</p>
          <p class="text-xs text-slate-500 italic mt-1">Requirement: {{ award.requirement }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
