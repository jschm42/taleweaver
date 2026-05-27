<script setup lang="ts">
import { AlertTriangle, X } from 'lucide-vue-next'
import type { SessionCheckpoint } from '@/types'

const props = defineProps<{
  open: boolean
  checkpoint: SessionCheckpoint | null
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm'): void
}>()

const formatTimestamp = (iso: string | undefined): string => {
  if (!iso) return 'Unknown time'
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return 'Unknown time'
  return dt.toLocaleString()
}
</script>

<template>
  <div
    v-if="props.open"
    class="fixed inset-0 z-[90] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
    @click="emit('close')"
  >
    <div class="w-full max-w-lg rounded-2xl border border-rose-500/25 bg-slate-900 shadow-2xl overflow-hidden" @click.stop>
      <div class="px-6 py-5 border-b border-white/10 flex items-start justify-between gap-4">
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 rounded-full border border-rose-400/40 bg-rose-500/15 flex items-center justify-center shrink-0 mt-0.5">
            <AlertTriangle class="w-5 h-5 text-rose-300" />
          </div>
          <div>
            <h3 class="text-lg font-black text-white">Confirm Timeline Restore</h3>
            <p class="text-xs text-slate-400 mt-1">This will permanently remove all events after the selected checkpoint.</p>
          </div>
        </div>

        <button class="text-slate-400 hover:text-white transition-colors" :disabled="props.busy" @click="emit('close')">
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="px-6 py-5 space-y-3">
        <div class="rounded-xl border border-rose-300/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          Warning: Weaving a new timeline will permanently overwrite your current future.
        </div>

        <div v-if="props.checkpoint" class="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
          <p class="text-xs text-slate-400 uppercase tracking-wider">Selected checkpoint</p>
          <p class="text-sm font-bold text-amber-300 mt-1">{{ props.checkpoint.title }}</p>
          <p class="text-xs text-slate-400 mt-1">{{ formatTimestamp(props.checkpoint.created_at) }}</p>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-white/10 flex items-center justify-end gap-3">
        <button
          class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors disabled:opacity-50"
          :disabled="props.busy"
          @click="emit('close')"
        >
          Cancel
        </button>
        <button
          class="px-4 py-2 rounded-lg bg-rose-500 text-white text-sm font-black uppercase tracking-wider hover:bg-rose-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="props.busy"
          @click="emit('confirm')"
        >
          {{ props.busy ? 'Weaving...' : 'Yes, restore timeline' }}
        </button>
      </div>
    </div>
  </div>
</template>