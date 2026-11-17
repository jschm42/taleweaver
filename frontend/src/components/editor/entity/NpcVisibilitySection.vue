<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

const ef = useEntityFormContext()
</script>

<template>

  <!-- NPC Hidden State & Reveal Condition -->
  <div v-if="ef.type === 'npc'" class="p-4 bg-black/30 border border-white/10 rounded-2xl space-y-4">
    <div class="flex items-center justify-between">
      <div class="space-y-1 pr-4">
        <p class="text-xs font-black text-slate-200 uppercase tracking-widest">Start Hidden</p>
        <p class="text-[10px] text-slate-500 uppercase tracking-tighter">If enabled, this NPC starts hidden and will only appear when discovered or when speaking.</p>
      </div>
      <button
        type="button"
        @click="ef.localForm.is_hidden = !ef.localForm.is_hidden"
        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', ef.localForm.is_hidden ? 'bg-emerald-600' : 'bg-slate-700']"
      >
        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', ef.localForm.is_hidden ? 'translate-x-6' : 'translate-x-0']"></div>
      </button>
    </div>

    <div v-if="ef.localForm.is_hidden" class="space-y-3 pt-2 border-t border-white/5">
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Spatial Position</label>
        <input
          v-model="ef.localForm.spatial_position"
          type="text"
          maxlength="255"
          placeholder="e.g. Hiding in the cellar behind the wine barrels"
          class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:border-emerald-500 outline-none transition-all shadow-inner"
        />
        <span class="block text-[10px] text-slate-500 leading-normal">
          Location hint used by the narrator when describing the scene.
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
          placeholder="e.g. When the protagonist inspects the wine rack or calls out the secret passphrase."
          class-name="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:border-emerald-500 outline-none transition-all resize-none shadow-inner"
        />
        <span class="block text-[10px] text-slate-500 leading-normal">
          GM narration rule that triggers this NPC to be revealed. Leave empty for default scene search reveal. Enter <code class="text-slate-400">script</code> to let only scripts reveal it (the GM never discovers it).
        </span>
      </div>
    </div>
  </div>
</template>
