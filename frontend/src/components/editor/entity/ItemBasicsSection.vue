<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import { Lock } from 'lucide-vue-next'
import { Star } from 'lucide-vue-next'

const ef = useEntityFormContext()
</script>

<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Item Type</label>
      <select
        v-if="!ef.localForm.is_item_type_fixed"
        v-model="ef.localForm.item_type"
        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold uppercase tracking-widest focus:border-emerald-500/50 outline-none transition-all"
      >
        <option value="DEFAULT">DEFAULT</option>
        <option value="CONSUMABLE">CONSUMABLE</option>
        <option value="WEARABLE">WEARABLE</option>
        <option value="WEAPON">WEAPON</option>
        <option value="CONSTRUCTABLE">CONSTRUCTABLE</option>
        <option value="READABLE">READABLE</option>
        <option value="CONTAINER">CONTAINER</option>
        <option value="CONTAINER_SWITCH">CONTAINER_SWITCH</option>
        <option value="SWITCH">SWITCH</option>
      </select>
      <input
        v-else
        :value="String(ef.localForm.item_type || '').toUpperCase()"
        disabled
        class="w-full bg-black/30 border border-white/5 rounded-xl px-4 py-2 text-slate-300 font-bold uppercase tracking-widest cursor-not-allowed"
      />
    </div>
    <!-- Recipes are never picked up: no Portable toggle (empty cell keeps the grid). -->
    <div v-if="ef.isRecipe"></div>
    <div v-else-if="ef.currentItemType !== 'WEARABLE'" class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Portable</label>
      <button
        type="button"
        @click="ef.localForm.is_portable = !ef.localForm.is_portable"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', ef.localForm.is_portable ? 'bg-emerald-600' : 'bg-slate-700']"
      >
        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', ef.localForm.is_portable ? 'translate-x-6' : 'translate-x-0']"></div>
      </button>
    </div>
    <div v-else class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Portable</label>
      <div class="w-full bg-black/30 border border-white/5 rounded-xl px-4 py-2 text-slate-400 font-bold uppercase tracking-widest">
        TRUE (Fixed)
      </div>
    </div>
  </div>



  <!-- Locked (Cannot Be Taken) for regular items -->
  <div v-if="!['CONTAINER', 'CONTAINER_SWITCH', 'SWITCH', 'CONSTRUCTABLE'].includes(ef.currentItemType)" class="p-3 bg-black/20 border border-white/10 rounded-xl">
    <div class="flex items-center justify-between">
      <div class="space-y-1 pr-4">
        <p class="text-xs font-black text-slate-200 uppercase tracking-widest flex items-center gap-1.5">
          <Lock class="w-3.5 h-3.5 text-amber-400" /> Locked (Cannot Be Taken)
        </p>
        <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
          If enabled, this item is visible and inspectable (in the scene or inside a container) but cannot be picked up until unlocked by a script (<code class="text-amber-400">tw.objects.unlock('ID')</code>).
        </p>
      </div>
      <button
        type="button"
        @click="ef.localForm.locked = !ef.localForm.locked"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1 shrink-0', ef.localForm.locked ? 'bg-amber-600' : 'bg-slate-700']"
      >
        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', ef.localForm.locked ? 'translate-x-6' : 'translate-x-0']"></div>
      </button>
    </div>
  </div>

  <!-- Quest item: can never be given to NPCs or taken away by the Game Master -->
  <div v-if="ef.currentItemType !== 'CONSTRUCTABLE'" class="p-3 bg-black/20 border border-white/10 rounded-xl">
    <div class="flex items-center justify-between">
      <div class="space-y-1 pr-4">
        <p class="text-xs font-black text-slate-200 uppercase tracking-widest flex items-center gap-1.5">
          <Star class="w-3.5 h-3.5 text-yellow-400" /> Quest Item
        </p>
        <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
          The story depends on it: the player can never give it to an NPC or companion, and the Game Master cannot take it away. Shown with a gold frame in-game. Scripts can still move it (e.g. <code class="text-yellow-400">tw.player.transfer_item('ID', 'NPC_ID')</code> for a hand-in).
        </p>
      </div>
      <button
        type="button"
        @click="ef.localForm.quest_item = !ef.localForm.quest_item"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1 shrink-0', ef.localForm.quest_item ? 'bg-yellow-600' : 'bg-slate-700']"
      >
        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', ef.localForm.quest_item ? 'translate-x-6' : 'translate-x-0']"></div>
      </button>
    </div>
  </div>
</template>
