<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

const ef = useEntityFormContext()
</script>

<template>

  <!-- Hidden state & Reveal rule for Objects -->
  <div v-if="ef.currentItemType !== 'CONSTRUCTABLE'" class="space-y-4 border-t border-white/5 pt-4">
    <div class="flex items-center justify-between">
      <div class="space-y-1 pr-4">
        <p class="text-xs font-black text-slate-200 uppercase tracking-widest">Start Hidden</p>
        <p class="text-[10px] text-slate-500 uppercase tracking-tighter">When enabled, the player must explicitly search the scene or fulfill a condition before discovering this item.</p>
      </div>
      <button
        type="button"
        @click="ef.localForm.is_hidden = !ef.localForm.is_hidden"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', ef.localForm.is_hidden ? 'bg-emerald-600' : 'bg-slate-700']"
      >
        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', ef.localForm.is_hidden ? 'translate-x-6' : 'translate-x-0']"></div>
      </button>
    </div>

    <div v-if="ef.localForm.is_hidden" class="space-y-3 pt-2">
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Spatial Position</label>
        <input
          v-model="ef.localForm.spatial_position"
          type="text"
          maxlength="255"
          placeholder="e.g. Under the couch cushions, inside the locked desk drawer"
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:border-emerald-500 outline-none transition-all shadow-inner"
        />
        <span class="block text-[10px] text-slate-500 leading-normal">
          Free-text location hint used by the GM when describing the room.
        </span>
      </div>

      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Reveal Rule</label>
          <span class="text-[10px] font-mono text-slate-500 tracking-widest">{{ (ef.localForm.reveal_rule || '').length }} / 500</span>
        </div>
        <ReferenceTextarea
          v-model="ef.localForm.reveal_rule"
          :options="ef.props.referenceOptions || []"
          :rows="2"
          :maxlength="500"
          placeholder="e.g. player inspects the couch, player opens the junk drawer"
          class-name="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:border-emerald-500 outline-none transition-all resize-none shadow-inner"
        />
        <span class="block text-[10px] text-slate-500 leading-normal">
          Specific action or event that triggers this item to reveal in the room. Leave empty for default search reveal. Enter <code class="text-slate-400">script</code> to let only scripts (or crafting / another item's reveal) reveal it.
        </span>
      </div>
    </div>

    <!-- Switches reveal things through their transitions, outcomes and scripts. -->
    <div v-if="ef.currentItemType !== 'SWITCH'" class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Reveals Item</label>
      <EntityReferenceCombobox
        v-model="ef.localForm.reveals_item_id"
        :options="ef.itemReferenceOptions"
        placeholder="Optional — a hidden item this one reveals"
        search-placeholder="Search object items by id or name"
        :enable-search="true"
      />
      <span class="block text-[10px] text-slate-500 leading-normal">
        When this item is opened, searched or otherwise changed, the chosen hidden item is revealed. Leave empty to reveal nothing.
      </span>
    </div>
  </div>
  <div v-else class="p-3 bg-violet-500/10 border border-violet-500/20 rounded-xl">
    <p class="text-xs text-violet-300 font-bold leading-relaxed">
      CONSTRUCTABLE items are meta items: they never appear in the game, so they need no description, appearance, position, hidden flag, reveal rule, portability or pickup/drop triggers.
    </p>
  </div>
</template>
