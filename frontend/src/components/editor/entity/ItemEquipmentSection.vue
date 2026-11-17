<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import WeaponCombatSettings from '@/components/editor/WeaponCombatSettings.vue'

const ef = useEntityFormContext()
</script>

<template>

  <!-- WEAPON: damage, cost, attack roll and on-hit effects -->
  <WeaponCombatSettings v-if="ef.currentItemType === 'WEAPON' && ef.localForm.weapon_config" v-model="ef.localForm.weapon_config" />

  <!-- WEAPON / WEARABLE: Wearable Slots -->
  <div v-if="['WEAPON', 'WEARABLE'].includes(ef.currentItemType)" class="space-y-2">
    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Wearable Slots</label>
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
      <label
        v-for="slot in ['Head', 'Neck', 'Chest', 'Hands', 'Legs', 'Feet', 'MainHand', 'OffHand', 'Finger', 'Wrist', 'Back', 'Waist']"
        :key="slot"
        :class="[
          'flex items-center gap-2 p-2 rounded-lg border transition-all select-none',
          ef.localForm.wearable_slots_input.includes(slot)
            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
            : 'border-white/5 bg-black/20 text-slate-500',
          ef.localForm.is_wearable_slots_fixed
            ? 'cursor-not-allowed' + (ef.localForm.wearable_slots_input.includes(slot) ? '' : ' opacity-40')
            : 'cursor-pointer hover:bg-sky-500/10 hover:border-sky-500/20'
        ]"
      >
        <div class="relative flex items-center">
          <input
            type="checkbox"
            :value="slot"
            :checked="ef.localForm.wearable_slots_input.includes(slot)"
            :disabled="ef.localForm.is_wearable_slots_fixed"
            @change="(e: Event) => {
              const checked = (e.target as HTMLInputElement).checked
              if (checked) {
                ef.localForm.wearable_slots_input = [...ef.localForm.wearable_slots_input, slot]
              } else {
                ef.localForm.wearable_slots_input = ef.localForm.wearable_slots_input.filter((s: string) => s !== slot)
              }
            }"
            class="w-4 h-4 rounded border-white/20 bg-black/40 text-emerald-500 focus:ring-emerald-500/40 focus:ring-1 disabled:opacity-80"
          />
        </div>
        <span class="text-[10px] font-bold uppercase tracking-widest transition-colors" :class="ef.localForm.wearable_slots_input.includes(slot) ? 'text-emerald-300' : 'text-slate-400'">{{ slot }}</span>
      </label>
    </div>
  </div>
</template>
