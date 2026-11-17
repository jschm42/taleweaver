<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import AppearanceField from '@/components/editor/AppearanceField.vue'

const ef = useEntityFormContext()
</script>

<template>

  <div v-if="!ef.isRecipe" class="space-y-3">
    <div class="flex justify-between items-center">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Description / Biography <span class="text-red-400">*</span></label>
      <span :class="['text-xs font-bold tracking-widest', (ef.localForm.description || '').length > 1000 ? 'text-red-500' : 'text-emerald-500/50']">
        {{ (ef.localForm.description || '').length }} / 1000
      </span>
    </div>
    <ReferenceTextarea
      v-model="ef.localForm.description"
      :maxlength="1000"
      :rows="ef.type === 'object' ? 3 : 4"
      :options="ef.props.referenceOptions || []"
      :class-name="['w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner', ef.type === 'object' ? 'text-sm' : 'text-base'].join(' ')"
    />
    <button 
      v-if="['npc', 'protagonist'].includes(ef.type) && ef.localForm.name && ef.localForm.goal && ef.localForm.character"
      type="button"
      @click="ef.handleGenerateBiography" 
      :disabled="ef.isGenerating['biography']"
      class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50 mt-2"
    >
      <i class="ra ra-crystals" :class="{ 'animate-spin': ef.isGenerating['biography'] }"></i>
      <span>Quick-Gen Biography</span>
    </button>
    <button 
      v-if="ef.type === 'object' && ef.localForm.name"
      type="button"
      @click="ef.handleGenerateDescription" 
      :disabled="ef.isGenerating['description']"
      class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50 mt-2"
    >
      <i class="ra ra-crystals" :class="{ 'animate-spin': ef.isGenerating['description'] }"></i>
      <span>Quick-Gen Description</span>
    </button>
  </div>

  <AppearanceField
    v-if="['cover', 'protagonist', 'npc', 'object'].includes(ef.type) && !ef.isRecipe"
    v-model="ef.localForm.appearance"
    :target-type="ef.type"
  />
</template>
