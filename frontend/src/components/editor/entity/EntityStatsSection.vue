<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'

const ef = useEntityFormContext()
</script>

<template>

  <div class="space-y-3">
    <div class="flex justify-between items-center">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Entity Name <span class="text-red-400">*</span></label>
      <span :class="['text-xs font-bold tracking-widest', (ef.localForm.name || '').length > 50 ? 'text-red-500' : 'text-emerald-500/50']">
        {{ (ef.localForm.name || '').length }} / 50
      </span>
    </div>
    <input v-model="ef.localForm.name" maxlength="50" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-xl font-bold text-white focus:border-emerald-500 outline-none transition-all shadow-inner" />

  <!-- Stats Inputs -->
  <div v-if="['protagonist', 'npc'].includes(ef.type) && ef.props.ruleEnforcementMode !== 'chat'" class="grid grid-cols-3 gap-4">
    <div class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Health (HP)</label>
      <input 
        v-model.number="ef.localForm.hp" 
        type="number" 
        min="0"
        max="999"
        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-red-500/50 outline-none transition-all"
        :class="{ 'border-red-500 text-red-500': ef.localForm.hp < 0 || ef.localForm.hp > 999 }"
      />
    </div>
    <div class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Stamina (STM)</label>
      <input 
        v-model.number="ef.localForm.stamina" 
        type="number" 
        min="0"
        max="999"
        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-emerald-500/50 outline-none transition-all"
        :class="{ 'border-red-500 text-red-500': ef.localForm.stamina < 0 || ef.localForm.stamina > 999 }"
      />
    </div>
    <div v-if="ef.props.ruleEnforcementMode === 'rpg'" class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Mana (MAN)</label>
      <input 
        v-model.number="ef.localForm.mana" 
        type="number" 
        min="0"
        max="999"
        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-blue-500/50 outline-none transition-all"
        :class="{ 'border-red-500 text-red-500': ef.localForm.mana < 0 || ef.localForm.mana > 999 }"
      />
    </div>
  </div>
  </div>
</template>
