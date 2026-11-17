<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'

const ef = useEntityFormContext()
</script>

<template>

  <!-- NPC Loot / Inventory -->
  <div v-if="ef.type === 'npc'" class="p-4 bg-black/30 border border-white/10 rounded-2xl space-y-3">
    <div class="flex items-center gap-2">
      <i class="ra ra-gem text-amber-400 text-sm"></i>
      <p class="text-xs font-black text-slate-200 uppercase tracking-widest">Loot / Inventory</p>
    </div>
    <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
      Items this NPC carries. Dropped as loot when the NPC is defeated in combat.
    </p>
    <div class="space-y-2">
      <div
        v-for="(_item, idx) in ef.localForm.inventory_input"
        :key="idx"
        class="flex items-center gap-2"
      >
        <EntityReferenceCombobox
          v-model="ef.localForm.inventory_input[idx]"
          :options="ef.itemReferenceOptions"
          placeholder="Select loot item"
          :enable-search="true"
        />
        <button
          type="button"
          @click="ef.localForm.inventory_input = ef.localForm.inventory_input.filter((_: string, i: number) => i !== idx)"
          class="shrink-0 px-2 py-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 text-[10px] font-bold uppercase tracking-widest transition-all"
        >
          <i class="ra ra-cancel"></i>
        </button>
      </div>
      <button
        type="button"
        @click="ef.localForm.inventory_input = [...(ef.localForm.inventory_input || []), '']"
        class="w-full py-2 bg-amber-500/5 border border-amber-500/10 hover:bg-amber-500/10 hover:border-amber-500/30 rounded-xl text-[10px] font-black text-amber-400 uppercase tracking-widest transition-all flex items-center justify-center gap-1.5"
      >
        <i class="ra ra-gem text-xs"></i> Add Loot Item
      </button>
    </div>
    <p v-if="!ef.localForm.inventory_input || ef.localForm.inventory_input.length === 0" class="text-[10px] text-slate-600 italic">
      No loot configured. The NPC drops nothing on defeat.
    </p>
  </div>
</template>
