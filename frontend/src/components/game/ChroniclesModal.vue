<script setup lang="ts">
import { Clock3, History, Sparkles, X } from 'lucide-vue-next'
import type { SessionCheckpoint } from '@/types'
import { useDialogSkin } from '@/skins/dialogSkin'

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

const { activeSkin, skinStyle } = useDialogSkin()

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
  <div
    v-if="open"
    class="tw-skin tw-dialog-backdrop fixed inset-0 z-[70] flex items-center justify-center p-4"
    :data-skin="activeSkin"
    :style="skinStyle"
    @click="emit('close')"
  >
    <div class="tw-dialog w-full max-w-2xl overflow-hidden" role="dialog" aria-modal="true" aria-label="Chronicles Timeline" @click.stop>
      <div class="tw-dialog-header px-6 py-5 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <History class="w-6 h-6 shrink-0 tw-dialog-eyebrow" />
          <div>
            <h3 class="tw-dialog-title text-xl">Chronicles Timeline</h3>
            <p class="tw-muted text-xs mt-0.5">Select a checkpoint to weave time backward.</p>
          </div>
        </div>
        <button type="button" class="tw-dialog-icon-button p-2" aria-label="Close" @click="emit('close')">
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="tw-dialog-scroll px-6 py-5 space-y-3 max-h-[60vh] overflow-y-auto">
        <div v-if="loading" class="tw-dialog-slot !border-solid p-5 text-sm flex items-center gap-3">
          <span class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
          Loading timeline checkpoints...
        </div>

        <div v-else-if="!checkpoints.length" class="tw-dialog-slot p-5 text-sm">
          No checkpoints yet. Continue playing and TaleWeaver will create milestones automatically.
        </div>

        <article
          v-for="checkpoint in checkpoints"
          :key="checkpoint.id"
          class="tw-card p-4 flex flex-col gap-3"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-sm font-bold truncate">{{ checkpoint.title }}</p>
              <p class="tw-muted text-xs mt-1 flex items-center gap-2">
                <Clock3 class="w-3.5 h-3.5" />
                {{ formatCheckpointTime(checkpoint.created_at) }}
              </p>
            </div>
            <span class="tw-dialog-chip inline-flex items-center gap-1 uppercase tracking-wider">
              <Sparkles class="w-3 h-3" />
              {{ reasonBadge(checkpoint.trigger_reason) }}
            </span>
          </div>

          <div class="flex justify-end">
            <button
              type="button"
              class="tw-dialog-button"
              :disabled="restoringId === checkpoint.id"
              @click="emit('restore', checkpoint)"
            >
              {{ restoringId === checkpoint.id ? 'Weaving...' : 'Weave to this point' }}
            </button>
          </div>
        </article>
      </div>

      <div class="tw-dialog-divider px-6 py-4 border-t flex justify-end">
        <button type="button" class="tw-dialog-button tw-dialog-button--ghost" @click="emit('close')">
          Close
        </button>
      </div>
    </div>
  </div>
</template>
