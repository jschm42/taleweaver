<script setup lang="ts">
import { Clock3, History, Sparkles, X } from 'lucide-vue-next'
import type { SessionCheckpoint } from '@/types'

const props = defineProps<{
  open: boolean
  checkpoints: SessionCheckpoint[]
  loading?: boolean
  restoringId?: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'restore', checkpoint: SessionCheckpoint): void
}>()

function formatCheckpointTime(iso: string): string {
  if (!iso) return 'Unknown time'
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return 'Unknown time'
  return dt.toLocaleString()
}

function reasonBadge(reason: SessionCheckpoint['trigger_reason']): string {
  if (reason === 'SCENE_CHANGE') return 'Scene change'
  if (reason === 'QUEST_UPDATE') return 'Quest update'
  return 'Award granted'
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[70] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" @click="emit('close')">
    <div class="w-full max-w-2xl rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden" @click.stop>
      <div class="px-6 py-5 border-b border-white/10 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-sky-500/20 border border-sky-500/40 flex items-center justify-center shrink-0">
            <History class="w-5 h-5 text-sky-300" />
          </div>
          <div>
            <h3 class="text-lg font-black text-white">Chronicles Timeline</h3>
            <p class="text-xs text-slate-400">Select a checkpoint to weave time backward.</p>
          </div>
        </div>
        <button class="text-slate-400 hover:text-white transition-colors" @click="emit('close')">
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="px-6 py-5 space-y-3 max-h-[60vh] overflow-y-auto custom-scrollbar">
        <div v-if="loading" class="rounded-xl border border-white/10 bg-white/5 p-5 text-sm text-slate-300 flex items-center gap-3">
          <span class="w-4 h-4 border-2 border-slate-300/30 border-t-slate-300 rounded-full animate-spin"></span>
          Loading timeline checkpoints...
        </div>

        <div v-else-if="!checkpoints.length" class="rounded-xl border border-white/10 bg-white/5 p-5 text-sm text-slate-300">
          No checkpoints yet. Continue playing and TaleWeaver will create milestones automatically.
        </div>

        <article
          v-for="checkpoint in checkpoints"
          :key="checkpoint.id"
          class="rounded-xl border border-slate-700/70 bg-slate-800/60 p-4 flex flex-col gap-3"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-sm font-bold text-amber-300 truncate">{{ checkpoint.title }}</p>
              <p class="text-xs text-slate-400 mt-1 flex items-center gap-2">
                <Clock3 class="w-3.5 h-3.5" />
                {{ formatCheckpointTime(checkpoint.created_at) }}
              </p>
            </div>
            <span class="inline-flex items-center gap-1 rounded-full border border-sky-400/30 bg-sky-500/10 px-2.5 py-1 text-[10px] font-black uppercase tracking-wider text-sky-300">
              <Sparkles class="w-3 h-3" />
              {{ reasonBadge(checkpoint.trigger_reason) }}
            </span>
          </div>

          <div class="flex justify-end">
            <button
              class="px-4 py-2 rounded-lg bg-sky-500 text-slate-950 text-xs font-black uppercase tracking-wider hover:bg-sky-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="restoringId === checkpoint.id"
              @click="emit('restore', checkpoint)"
            >
              {{ restoringId === checkpoint.id ? 'Weaving...' : 'Weave to this point' }}
            </button>
          </div>
        </article>
      </div>

      <div class="px-6 py-4 border-t border-white/10 flex justify-end">
        <button class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors" @click="emit('close')">
          Close
        </button>
      </div>
    </div>
  </div>
</template>
