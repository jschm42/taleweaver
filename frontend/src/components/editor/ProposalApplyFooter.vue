<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-vue-next'

const props = defineProps<{
  hasBackupConfirmed: boolean
  applying: boolean
  canApply: boolean
  applyLabel: string
}>()

const emit = defineEmits<{
  (e: 'toggle-backup', value: boolean): void
  (e: 'cancel'): void
  (e: 'apply'): void
}>()
</script>

<template>
  <div class="px-6 py-4 border-t border-white/10 space-y-3 shrink-0 bg-slate-950/50">
    <label class="flex items-start gap-3 text-xs text-slate-200 leading-relaxed cursor-pointer select-none">
      <input
        type="checkbox"
        class="mt-0.5 accent-rose-500 cursor-pointer"
        :checked="props.hasBackupConfirmed"
        @change="emit('toggle-backup', ($event.target as HTMLInputElement).checked)"
      />
      <span>
        <span class="font-black text-rose-200">Important &mdash;</span>
        I have made a copy of this adventure (or accept the risk that AI edits will overwrite
        my current data). The engine does not auto-rollback these changes.
      </span>
    </label>

    <div class="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 flex items-start gap-2 text-[11px] text-amber-100">
      <AlertTriangle class="w-4 h-4 text-amber-300 shrink-0 mt-0.5" />
      <p class="leading-relaxed">
        AI-generated changes can be subtly wrong. We strongly recommend exporting the
        adventure (<code class="font-mono">.adv</code>) before applying any of these patches.
      </p>
    </div>

    <div class="flex items-center justify-end gap-3">
      <button
        type="button"
        class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors disabled:opacity-50"
        :disabled="props.applying"
        @click="emit('cancel')"
      >
        Cancel
      </button>
      <button
        type="button"
        class="px-5 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-black uppercase tracking-wider transition-colors disabled:bg-slate-700 disabled:cursor-not-allowed flex items-center gap-2"
        :disabled="!props.canApply"
        @click="emit('apply')"
      >
        <Loader2 v-if="props.applying" class="w-4 h-4 animate-spin" />
        <CheckCircle2 v-else class="w-4 h-4" />
        <span>{{ props.applying ? 'Applying…' : props.applyLabel }}</span>
      </button>
    </div>
  </div>
</template>
