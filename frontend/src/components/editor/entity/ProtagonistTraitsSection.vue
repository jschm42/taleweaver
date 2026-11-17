<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

const ef = useEntityFormContext()
</script>

<template>

  <!-- Protagonist Motivation & Traits -->
  <div v-if="ef.type === 'protagonist'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="space-y-3">
      <div class="flex justify-between items-center">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Motivation / Goal</label>
        <span :class="['text-xs font-bold tracking-widest', (ef.localForm.goal || '').length > 200 ? 'text-red-500' : 'text-emerald-500/50']">
          {{ (ef.localForm.goal || '').length }} / 200
        </span>
      </div>
      <ReferenceTextarea
        v-model="ef.localForm.goal"
        :maxlength="200"
        :rows="2"
        :options="ef.props.referenceOptions || []"
        class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
        placeholder="What drives the protagonist? (e.g. 'Seeks revenge for family's death')"
      />
      <button 
        v-if="ef.localForm.description"
        @click="ef.handleGenerateTraits('goal')" 
        :disabled="ef.isGenerating['goal']"
        class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50"
      >
        <i class="ra ra-crystals" :class="{ 'animate-spin': ef.isGenerating['goal'] }"></i>
        <span>Quick-Gen Goal</span>
      </button>
    </div>
    <div class="space-y-3">
      <div class="flex justify-between items-center">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Personality / Traits</label>
        <span :class="['text-xs font-bold tracking-widest', (ef.localForm.character || '').length > 200 ? 'text-red-500' : 'text-emerald-500/50']">
          {{ (ef.localForm.character || '').length }} / 200
        </span>
      </div>
      <ReferenceTextarea
        v-model="ef.localForm.character"
        :maxlength="200"
        :rows="2"
        :options="ef.props.referenceOptions || []"
        class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
        placeholder="How does the protagonist behave? (e.g. 'Sarcastic but loyal, prone to rash decisions')"
      />
      <button 
        v-if="ef.localForm.description"
        @click="ef.handleGenerateTraits('character')" 
        :disabled="ef.isGenerating['character']"
        class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50"
      >
        <i class="ra ra-crystals" :class="{ 'animate-spin': ef.isGenerating['character'] }"></i>
        <span>Quick-Gen Traits</span>
      </button>
    </div>
  </div>
</template>
