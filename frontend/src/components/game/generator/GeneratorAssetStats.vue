<script setup lang="ts">
import { BarChart3 } from 'lucide-vue-next'

export interface AssetStatDetail {
  generated: number
  reused: number
}

export interface AssetStatsMap {
  cover: AssetStatDetail
  protagonist: AssetStatDetail
  scene: AssetStatDetail
  npc: AssetStatDetail
  item: AssetStatDetail
}

const props = defineProps<{
  assetStats: AssetStatsMap
  totalStats: { generated: number; reused: number }
  isReady: boolean
}>()
</script>

<template>
  <div class="mt-4 sm:mt-6 p-4 sm:p-5 rounded-2xl border border-cyan-500/20 bg-cyan-500/5 backdrop-blur-md flex flex-col gap-3.5 sm:gap-4 self-center w-full max-w-[95%] sm:max-w-[90%] shadow-[0_0_20px_rgba(6,182,212,0.05)] animate-fade-in">
    <!-- Summary Header -->
    <div class="flex items-center justify-between border-b border-white/10 pb-3">
      <div class="flex items-center gap-2">
        <BarChart3 class="w-4 h-4 text-cyan-400 shrink-0" />
        <h4 class="text-xs font-black text-white uppercase tracking-widest">Generation Summary</h4>
      </div>
      <span
        class="text-[10px] font-black uppercase tracking-widest px-2.5 py-0.5 rounded border"
        :class="props.isReady ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border-rose-500/30'"
      >
        {{ props.isReady ? 'Success' : 'Flawed / Cancelled' }}
      </span>
    </div>

    <!-- Asset Cards Grid -->
    <div class="grid grid-cols-2 xs:grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-3">
      <!-- Cover -->
      <div class="flex flex-col items-center p-2.5 sm:p-3 rounded-xl bg-black/40 border border-white/5 text-center">
        <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 sm:mb-2">Cover</span>
        <div class="flex flex-col gap-1 w-full text-[9px] font-black">
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
            <span>Created</span>
            <span>{{ props.assetStats.cover.generated }}</span>
          </div>
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
            <span>Reused</span>
            <span>{{ props.assetStats.cover.reused }}</span>
          </div>
        </div>
      </div>

      <!-- Protagonist / Hero -->
      <div class="flex flex-col items-center p-2.5 sm:p-3 rounded-xl bg-black/40 border border-white/5 text-center">
        <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 sm:mb-2">Hero</span>
        <div class="flex flex-col gap-1 w-full text-[9px] font-black">
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
            <span>Created</span>
            <span>{{ props.assetStats.protagonist.generated }}</span>
          </div>
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
            <span>Reused</span>
            <span>{{ props.assetStats.protagonist.reused }}</span>
          </div>
        </div>
      </div>

      <!-- Scenes -->
      <div class="flex flex-col items-center p-2.5 sm:p-3 rounded-xl bg-black/40 border border-white/5 text-center">
        <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 sm:mb-2">Scenes</span>
        <div class="flex flex-col gap-1 w-full text-[9px] font-black">
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
            <span>Created</span>
            <span>{{ props.assetStats.scene.generated }}</span>
          </div>
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
            <span>Reused</span>
            <span>{{ props.assetStats.scene.reused }}</span>
          </div>
        </div>
      </div>

      <!-- NPCs -->
      <div class="flex flex-col items-center p-2.5 sm:p-3 rounded-xl bg-black/40 border border-white/5 text-center">
        <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 sm:mb-2">NPCs</span>
        <div class="flex flex-col gap-1 w-full text-[9px] font-black">
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
            <span>Created</span>
            <span>{{ props.assetStats.npc.generated }}</span>
          </div>
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
            <span>Reused</span>
            <span>{{ props.assetStats.npc.reused }}</span>
          </div>
        </div>
      </div>

      <!-- Items -->
      <div class="flex flex-col items-center p-2.5 sm:p-3 rounded-xl bg-black/40 border border-white/5 text-center col-span-2 xs:col-span-1">
        <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 sm:mb-2">Items</span>
        <div class="flex flex-col gap-1 w-full text-[9px] font-black">
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400">
            <span>Created</span>
            <span>{{ props.assetStats.item.generated }}</span>
          </div>
          <div class="flex justify-between px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">
            <span>Reused</span>
            <span>{{ props.assetStats.item.reused }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Totals Summary Bar -->
    <div class="flex flex-wrap justify-between items-center text-[10px] font-bold text-slate-400 uppercase tracking-widest border-t border-white/10 pt-3 gap-2">
      <div class="flex items-center gap-3 sm:gap-4">
        <span>Created: <span class="text-cyan-400 font-black">{{ props.totalStats.generated }}</span></span>
        <span>Reused: <span class="text-purple-400 font-black">{{ props.totalStats.reused }}</span></span>
      </div>
      <div class="text-slate-400">
        Total Assets: <span class="text-white font-black">{{ props.totalStats.generated + props.totalStats.reused }}</span>
      </div>
    </div>
  </div>
</template>
