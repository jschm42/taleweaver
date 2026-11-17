<script setup lang="ts">
import { useEntityFormContext } from '@/composables/editor/entityFormContext'

const ef = useEntityFormContext()
</script>

<template>

  <!-- GM Status Notes / Condition -->
  <div v-if="ef.type === 'npc'" class="p-4 bg-black/30 border border-white/10 rounded-2xl space-y-2">
    <div class="flex items-center justify-between">
      <p class="text-xs font-black text-slate-200 uppercase tracking-widest flex items-center gap-1.5">
        <i class="ra ra-quill-ink text-amber-400"></i> GM Status Notes / Condition
      </p>
    </div>
    <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
      Notes or conditions evaluated by the GM to enrich narration (e.g. "is badly hurt", "is very angry, because joe does not like him").
    </p>
    <textarea
      v-model="ef.localForm.notes"
      rows="2"
      maxlength="500"
      placeholder="e.g. is badly hurt, holds a grudge against Joe..."
      class="w-full bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-amber-500 resize-none font-mono"
    ></textarea>
  </div>
</template>
