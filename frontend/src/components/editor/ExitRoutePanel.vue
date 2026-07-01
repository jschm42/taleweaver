<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  entityService,
  type EntityEditData,
} from '@/services/entityService'
import { notificationService } from '@/services/notificationService'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import { ArrowLeft } from 'lucide-vue-next'

const props = defineProps<{
  adventureId: string
  exitId: string
  debugData: any
  referenceOptions: any[]
  isSaving: boolean
  isDeletingRouteAsset: boolean
  returnTabLabel?: string
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'request-delete-exit', exitId: string): void
  (e: 'back'): void
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
  code_to_unlock: '',
  item_to_unlock: '',
  rule_to_unlock: '',
})

watch(
  () => routeExitDetails.value,
  (exitData) => {
    if (!exitData) {
      exitEditForm.value = {
        label: '',
        lock_description: '',
        exit_type: 'one_way',
        code_to_unlock: '',
        item_to_unlock: '',
        rule_to_unlock: '',
      }
      return
    }
    exitEditForm.value = {
      label: String(exitData.label || ''),
      lock_description: String(exitData.lock_description || ''),
      exit_type: String(exitData.exit_type || 'one_way').toLowerCase() === 'bidirectional' ? 'bidirectional' : 'one_way',
      code_to_unlock: String(exitData.code_to_unlock || ''),
      item_to_unlock: String(exitData.item_to_unlock || ''),
      rule_to_unlock: String(exitData.rule_to_unlock || ''),
    }
  },
  { immediate: true }
)

const itemReferenceOptions = computed(() => {
  const source = props.referenceOptions || []
  return source
    .filter((option) => String(option.type || '').toUpperCase() === 'OBJECT')
    .map((option) => ({
      ...option,
      name: option.name || option.id || '',
    }))
})

const hasGate = computed(() => {
  return Boolean(
    (exitEditForm.value.code_to_unlock || '').trim()
    || (exitEditForm.value.item_to_unlock || '').trim()
    || (exitEditForm.value.rule_to_unlock || '').trim()
  )
})

const isFormInvalid = computed(() => {
  const labelText = (exitEditForm.value.label || '').trim()
  if (!labelText || labelText.length > 100) return true
  if ((exitEditForm.value.lock_description || '').length > 255) return true
  if ((exitEditForm.value.code_to_unlock || '').length > 32) return true
  if ((exitEditForm.value.rule_to_unlock || '').length > 500) return true
  if (hasGate.value && !(exitEditForm.value.lock_description || '').trim()) return true
  return false
})

const localIsSaving = ref(false)

async function saveRouteExit() {
  const exit = routeExitDetails.value
  if (!exit) return
  if (isFormInvalid.value) return

  const trimmedLabel = exitEditForm.value.label.trim()
  const trimmedLockDesc = exitEditForm.value.lock_description.trim()
  const rawCode = exitEditForm.value.code_to_unlock
  const rawItem = exitEditForm.value.item_to_unlock
  const rawRule = exitEditForm.value.rule_to_unlock

  const payload: EntityEditData = {
    target_type: 'exit',
    target_id: String(exit.id),
    name: trimmedLabel,
    description: trimmedLockDesc,
    exit_type: exitEditForm.value.exit_type,
    code_to_unlock: rawCode,
    item_to_unlock: rawItem,
    rule_to_unlock: rawRule,
    locked: Boolean(rawCode || rawItem || rawRule),
  }

  localIsSaving.value = true
  try {
    await entityService.saveEntityText(props.adventureId, payload)
    notificationService.add('Exit updated.', 'success')
    emit('refresh')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update exit.', 'error')
  } finally {
    localIsSaving.value = false
  }
}
</script>

<template>
  <section class="bg-slate-900/40 border border-white/10 rounded-2xl p-5 space-y-4">
    <div class="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
      <button
        class="flex items-center gap-2 px-3 py-1.5 text-xs font-black uppercase tracking-[0.15em] rounded-lg border border-white/10 bg-slate-900/40 text-slate-300 hover:text-white hover:bg-white/5 transition-all"
        @click="emit('back')"
      >
        <ArrowLeft class="w-4 h-4" />
        Back to {{ props.returnTabLabel || 'Map' }}
      </button>
      <button
        class="px-3 py-2 text-xs font-bold rounded-lg border border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50"
        :disabled="isDeletingRouteAsset"
        @click="emit('request-delete-exit', exitId)"
      >
        Delete Exit
      </button>
    </div>

    <div>
      <p class="text-xs uppercase tracking-widest text-emerald-300">Exit Route</p>
      <h3 class="text-lg font-bold text-white">{{ routeExitDetails?.label || 'Exit' }}</h3>
      <p class="text-sm text-slate-300 mt-1">
        {{ routeExitDetails?.from_scene_id }} -> {{ routeExitDetails?.to_scene_id }}
      </p>
    </div>

    <div class="grid md:grid-cols-2 gap-3 text-slate-200">
      <label class="text-xs text-slate-300 space-y-1">
        <div class="flex justify-between items-center">
          <span>Label <span class="text-red-400">*</span></span>
          <span :class="['text-[10px] font-mono', (exitEditForm.label || '').length > 100 || !(exitEditForm.label || '').trim() ? 'text-red-500 font-bold' : 'text-emerald-500/40']">
            {{ (exitEditForm.label || '').length }} / 100
          </span>
        </div>
        <input v-model="exitEditForm.label" maxlength="100" class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white focus:border-emerald-500 outline-none" />
      </label>
      <label class="text-xs text-slate-300 space-y-1">
        <span>Type</span>
        <select v-model="exitEditForm.exit_type" class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white focus:border-emerald-500 outline-none">
          <option value="one_way">one_way</option>
          <option value="bidirectional">bidirectional</option>
        </select>
      </label>
    </div>

    <label class="text-xs text-slate-300 space-y-1 block">
      <div class="flex justify-between items-center">
        <span>Lock Description<span v-if="hasGate" class="text-red-400"> *</span></span>
        <span :class="['text-[10px] font-mono', (exitEditForm.lock_description || '').length > 255 ? 'text-red-500 font-bold' : 'text-emerald-500/40']">
          {{ (exitEditForm.lock_description || '').length }} / 255
        </span>
      </div>
      <ReferenceTextarea
        v-model="exitEditForm.lock_description"
        :rows="3"
        :options="referenceOptions"
        :maxlength="255"
        class-name="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white focus:border-emerald-500 outline-none"
      />
    </label>

    <div class="grid md:grid-cols-2 gap-3 text-slate-200">
      <label class="text-xs text-slate-300 space-y-1">
        <div class="flex justify-between items-center">
          <span>Code To Unlock</span>
          <span :class="['text-[10px] font-mono', (exitEditForm.code_to_unlock || '').length > 32 ? 'text-red-500 font-bold' : 'text-emerald-500/40']">
            {{ (exitEditForm.code_to_unlock || '').length }} / 32
          </span>
        </div>
        <input v-model="exitEditForm.code_to_unlock" maxlength="32" class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white focus:border-emerald-500 outline-none" placeholder="e.g. 1234 or WORD" />
      </label>
      <label class="text-xs text-slate-300 space-y-1">
        <span>Item ID To Unlock</span>
        <EntityReferenceCombobox
          v-model="exitEditForm.item_to_unlock"
          :options="itemReferenceOptions"
          placeholder="Select key item reference"
          :enable-search="true"
        />
      </label>
    </div>

    <label class="text-xs text-slate-300 space-y-1 block">
      <div class="flex justify-between items-center">
        <span>Rule To Unlock (Narrative Requirement)</span>
        <span :class="['text-[10px] font-mono', (exitEditForm.rule_to_unlock || '').length > 500 ? 'text-red-500 font-bold' : 'text-emerald-500/40']">
          {{ (exitEditForm.rule_to_unlock || '').length }} / 500
        </span>
      </div>
      <input v-model="exitEditForm.rule_to_unlock" maxlength="500" class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white focus:border-emerald-500 outline-none" placeholder="e.g. Protagonist defeats NPC_2" />
    </label>

    <div class="flex justify-end">
      <button class="px-3 py-2 text-xs font-bold rounded bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50" :disabled="localIsSaving || isSaving || isFormInvalid" @click="saveRouteExit">
        Save Exit
      </button>
    </div>
  </section>
</template>
