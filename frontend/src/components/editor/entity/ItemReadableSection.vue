<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

const ef = useEntityFormContext()
</script>

<template>

  <!-- READABLE -->
  <div v-if="ef.currentItemType === 'READABLE'" class="space-y-2">
    <div class="space-y-2">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Text Log Format</label>
      <select v-model="ef.localForm.text_log_format" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-cyan-500/50 outline-none transition-all">
        <option value="DOCUMENT">DOCUMENT</option>
        <option value="SCROLL">SCROLL</option>
        <option value="BOOK">BOOK</option>
        <option value="SIGN">SIGN</option>
      </select>
    </div>
    <div class="flex justify-between items-center">
      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Text Log Content</label>
      <span :class="['text-xs font-bold tracking-widest', (ef.localForm.text_log_content || '').length > 1000 ? 'text-red-500' : 'text-emerald-500/50']">
        {{ (ef.localForm.text_log_content || '').length }} / 1000
      </span>
    </div>
    <ReferenceTextarea
      v-model="ef.localForm.text_log_content"
      :maxlength="1000"
      :rows="3"
      :options="ef.props.referenceOptions || []"
      :class-name="['w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-y focus:border-cyan-500/50 outline-none transition-all', ef.textLogPreviewClass].join(' ')"
      placeholder="Readable note text shown to the player."
    />
    <button
      v-if="ef.localForm.name"
      @click="ef.handleGenerateTextLogContent"
      :disabled="ef.isGenerating['text_log']"
      class="w-full py-2 bg-cyan-500/5 border border-cyan-500/10 hover:bg-cyan-500/10 hover:border-cyan-500/30 rounded-xl text-[10px] font-black text-cyan-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50 mt-2"
    >
      <i class="ra ra-crystals" :class="{ 'animate-spin': ef.isGenerating['text_log'] }"></i>
      <span>Quick-Gen Text Log</span>
    </button>
  </div>
</template>
