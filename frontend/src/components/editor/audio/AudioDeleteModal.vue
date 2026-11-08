<script setup lang="ts">
/** Modal: confirm deleting a library track (its file is removed, scenes using it become silent). */
import { onBeforeUnmount, onMounted } from 'vue'
import { Trash2 } from 'lucide-vue-next'

const props = defineProps<{
  trackName: string
  /** Labels of the scenes that play this track. */
  scenes: string[]
  isDeleting: boolean
}>()

const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'confirm'): void
}>()

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape' && !props.isDeleting) emit('cancel')
}

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[210] flex items-center justify-center p-6 backdrop-blur-sm bg-black/60" @click.self="!isDeleting && emit('cancel')">
      <div class="w-full max-w-md bg-slate-900 border border-white/10 rounded-2xl p-6 space-y-4 shadow-2xl" role="alertdialog" aria-modal="true" aria-labelledby="music-delete-title">
        <div class="flex items-start gap-3">
          <div class="w-9 h-9 shrink-0 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <Trash2 class="w-4 h-4 text-red-400" />
          </div>
          <div class="space-y-1 min-w-0">
            <h4 id="music-delete-title" class="text-sm font-black text-white break-words">Delete "{{ trackName }}"?</h4>
            <p class="text-xs text-slate-400">The track and its audio file are removed from the music library. This cannot be undone.</p>
          </div>
        </div>
        <div v-if="scenes.length" class="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200">
          <p class="font-bold">{{ scenes.length }} scene(s) use this track and become silent:</p>
          <p class="mt-1 text-amber-200/80">{{ scenes.join(', ') }}</p>
        </div>
        <div class="flex justify-end gap-3">
          <button type="button" :disabled="isDeleting"
            class="px-3 py-2 text-xs font-bold border border-white/15 rounded-lg text-slate-300 hover:text-white disabled:opacity-40"
            @click="emit('cancel')">
            Cancel
          </button>
          <button type="button" :disabled="isDeleting"
            class="px-3 py-2 text-xs font-bold rounded-lg bg-red-600 hover:bg-red-500 text-white disabled:opacity-50"
            @click="emit('confirm')">
            {{ isDeleting ? 'Deleting...' : 'Delete' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
