<script setup lang="ts">
import { ref } from 'vue'
import { Download, Loader2 } from 'lucide-vue-next'
import { sessionDebugExportService } from '@/services/sessionDebugExportService'
import { useNotifications } from '@/composables/useNotifications'

/**
 * Download button of the debug inspector: without `entityId` it downloads every image of
 * the session as a ZIP; with it, that NPC or item as a .twe bundle (like the editor export).
 */
const props = withDefaults(defineProps<{
  gameId: string
  entityId?: string
  label?: string
  compact?: boolean
}>(), {
  entityId: '',
  label: '',
  compact: false,
})

const { addNotification } = useNotifications()
const busy = ref(false)

async function run(): Promise<void> {
  if (busy.value || !props.gameId) return
  busy.value = true
  try {
    if (props.entityId) {
      await sessionDebugExportService.exportSessionEntity(props.gameId, props.entityId)
    } else {
      await sessionDebugExportService.downloadSessionImages(props.gameId)
    }
  } catch (err) {
    addNotification(err instanceof Error ? err.message : 'Download failed.', 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <button
    type="button"
    :disabled="busy || !gameId"
    :title="entityId ? `Export ${entityId} as .twe (importable in the editor)` : 'Download all scene, NPC and item images as ZIP'"
    class="inline-flex items-center gap-1.5 rounded-lg border border-slate-700/70 bg-slate-800/70 text-slate-300 hover:bg-cyan-600 hover:text-white hover:border-cyan-400 transition-all disabled:opacity-50 cursor-pointer"
    :class="compact ? 'p-1' : 'px-3 py-1.5 text-xs font-bold uppercase tracking-wider'"
    @click.stop="run"
  >
    <Loader2 v-if="busy" :class="compact ? 'w-3.5 h-3.5' : 'w-4 h-4'" class="animate-spin" />
    <Download v-else :class="compact ? 'w-3.5 h-3.5' : 'w-4 h-4'" />
    <span v-if="label">{{ label }}</span>
  </button>
</template>
