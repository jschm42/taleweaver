<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'

const ef = useEntityFormContext()
</script>

<template>

  <!-- CONSUMABLE: Effects -->
  <div v-if="ef.currentItemType === 'CONSUMABLE'" class="space-y-4">
    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Stat Effects When Consumed</label>
    <div class="grid grid-cols-3 gap-4">
      <div class="space-y-2">
        <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Health (HP)</label>
        <input
          v-model.number="ef.localForm.effects_hp"
          type="number"
          min="-999"
          max="999"
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-red-500/50 outline-none transition-all"
        />
      </div>
      <div class="space-y-2">
        <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Stamina</label>
        <input
          v-model.number="ef.localForm.effects_stamina"
          type="number"
          min="-999"
          max="999"
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-emerald-500/50 outline-none transition-all"
        />
      </div>
      <div class="space-y-2">
        <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Mana</label>
        <input
          v-model.number="ef.localForm.effects_mana"
          type="number"
          min="-999"
          max="999"
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-blue-500/50 outline-none transition-all"
        />
      </div>
    </div>
    <p class="text-[10px] text-slate-500 uppercase tracking-wider">Positive values restore stats, negative values drain them.</p>
  </div>
</template>
