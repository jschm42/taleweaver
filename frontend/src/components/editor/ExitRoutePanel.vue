<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { entityService } from '@/services/entityService'
import { notificationService } from '@/services/notificationService'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

const props = defineProps<{
  adventureId: string
  exitId: string
  debugData: any
  referenceOptions: any[]
  isSaving: boolean
  isDeletingRouteAsset: boolean
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'request-delete-exit', exitId: string): void
}>()

const routeExitDetails = computed<any | null>(() => {
  const exitId = String(props.exitId || '').trim()
  const exits = Array.isArray(props.debugData?.exits) ? props.debugData.exits : []
  if (!exitId) return null
  return exits.find((worldExit: any) => String(worldExit.id) === exitId) || null
})

const exitEditForm = ref({
  label: '',
  lock_description: '',
  exit_type: 'one_way' as 'one_way' | 'bidirectional',
})

watch(
  () => routeExitDetails.value,
  (exitData) => {
    if (!exitData) {
      exitEditForm.value = {
        label: '',
        lock_description: '',
        exit_type: 'one_way',
      }
      return
    }
    exitEditForm.value = {
      label: String(exitData.label || ''),
      lock_description: String(exitData.lock_description || ''),
      exit_type: String(exitData.exit_type || 'one_way').toLowerCase() === 'bidirectional' ? 'bidirectional' : 'one_way',
    }
  },
  { immediate: true }
)

const localIsSaving = ref(false)

async function saveRouteExit() {
  const exit = routeExitDetails.value
  if (!exit) return
  if (!exitEditForm.value.label.trim()) {
    notificationService.add('Exit label is required.', 'error')
    return
  }
  localIsSaving.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'exit',
      target_id: String(exit.id),
      name: exitEditForm.value.label.trim(),
      description: exitEditForm.value.lock_description.trim(),
      exit_type: exitEditForm.value.exit_type,
    })
    emit('refresh')
    notificationService.add('Exit updated.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update exit.', 'error')
  } finally {
    localIsSaving.value = false
  }
}
</script>

<template>
  <section class="bg-slate-900/40 border border-white/10 rounded-2xl p-5 space-y-4">
    <div class="flex items-start justify-between gap-4">
      <div>
        <p class="text-xs uppercase tracking-widest text-emerald-300">Exit Route</p>
        <h3 class="text-lg font-bold text-white">{{ routeExitDetails?.label || routeExitDetails?.id || exitId }}</h3>
        <p class="text-sm text-slate-300 mt-1">
          {{ routeExitDetails?.from_scene_id }} -> {{ routeExitDetails?.to_scene_id }}
        </p>
      </div>
      <button
        class="px-3 py-2 text-xs font-bold rounded-lg border border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50"
        :disabled="isDeletingRouteAsset"
        @click="emit('request-delete-exit', exitId)"
      >
        Delete Exit
      </button>
    </div>

    <div class="grid md:grid-cols-2 gap-3 text-slate-200">
      <label class="text-xs text-slate-300 space-y-1">
        <span>Label</span>
        <input v-model="exitEditForm.label" class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white" />
      </label>
      <label class="text-xs text-slate-300 space-y-1">
        <span>Type</span>
        <select v-model="exitEditForm.exit_type" class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white">
          <option value="one_way">one_way</option>
          <option value="bidirectional">bidirectional</option>
        </select>
      </label>
    </div>

    <label class="text-xs text-slate-300 space-y-1 block">
      <span>Lock Description</span>
      <ReferenceTextarea
        v-model="exitEditForm.lock_description"
        :rows="3"
        :options="referenceOptions"
        class-name="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white"
      />
    </label>

    <div class="flex justify-end">
      <button class="px-3 py-2 text-xs font-bold rounded bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50" :disabled="localIsSaving || isSaving" @click="saveRouteExit">
        Save Exit
      </button>
    </div>
  </section>
</template>
