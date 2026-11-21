<script setup lang="ts">
/**
 * A new connection between two regions. Two built regions are connected by a real exit
 * between one scene of each (a gateway exit with a travel time). With a planned region the
 * connection is a planned route; its exit is created when that region is generated.
 */
import { computed, ref, watch } from 'vue'
import { entityService } from '@/services/entityService'
import { useToast } from '@/composables/useToast'
import type { WorldSection } from '@/services/sectionService'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { estimateMinutes, mapDistance } from '@/components/editor/regions/regionGraph'

interface SceneOption {
  id: string
  label: string
  sectionId: string | null
}

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  adventureId: string
  from: WorldSection | null
  to: WorldSection | null
  scenes: SceneOption[]
}>()

const emit = defineEmits<{
  (e: 'saved'): void
  (e: 'plan', minutes: number | null): void
}>()

const toast = useToast()
const fromScene = ref<string | number | null>('')
const toScene = ref<string | number | null>('')
const label = ref<string | number | null>('')
const twoWay = ref(true)
const hours = ref<string | number | null>(null)
const saving = ref(false)

const planned = computed(() => props.from?.status !== 'built' || props.to?.status !== 'built')
const optionsOf = (sectionId?: string) =>
  props.scenes.filter((s) => s.sectionId === sectionId).map((s) => ({ value: s.id, label: s.label }))
const fromOptions = computed(() => optionsOf(props.from?.id))
const toOptions = computed(() => optionsOf(props.to?.id))

watch(open, (isOpen) => {
  if (!isOpen || !props.from || !props.to) return
  fromScene.value = fromOptions.value[0]?.value || ''
  toScene.value = toOptions.value[0]?.value || ''
  label.value = `the road to ${props.to.label}`
  const minutes = estimateMinutes(mapDistance(props.from, props.to), 1)
  hours.value = Math.round((minutes / 60) * 100) / 100
})

function minutes(): number | null {
  const value = Number(hours.value)
  return Number.isFinite(value) && value > 0 ? Math.round(value * 60) : null
}

async function save(): Promise<void> {
  if (planned.value) {
    emit('plan', minutes())
    open.value = false
    return
  }
  if (!fromScene.value || !toScene.value || !String(label.value).trim()) {
    toast.warn('Choose both scenes and name the way.')
    return
  }
  saving.value = true
  try {
    await entityService.createExit(props.adventureId, {
      from_scene_id: String(fromScene.value),
      to_scene_id: String(toScene.value),
      label: String(label.value).trim(),
      exit_type: twoWay.value ? 'bidirectional' : 'one_way',
      travel_minutes: minutes(),
    })
    emit('saved')
    open.value = false
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to create the exit.')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UiModal
    v-model:open="open"
    :title="`Connect ${from?.label} and ${to?.label}`"
    :description="planned ? 'A planned route: the exit is created when the planned region is generated.' : 'Creates an exit between a scene of each region.'"
    :persistent="saving"
  >
    <div class="space-y-4">
      <template v-if="!planned">
        <div class="grid gap-4 md:grid-cols-2">
          <UiField :label="`Scene in ${from?.label}`">
            <UiSelect v-model="fromScene" :options="fromOptions" />
          </UiField>
          <UiField :label="`Scene in ${to?.label}`">
            <UiSelect v-model="toScene" :options="toOptions" />
          </UiField>
        </div>
        <UiField label="Name of the way" hint="Names the passage itself, e.g. 'the mountain road'.">
          <UiInput v-model="label" />
        </UiField>
        <UiCheckbox v-model="twoWay" label="Two-way" description="The player can walk back the same way." />
      </template>
      <UiField label="Travel time (hours)" hint="Suggested from the map distance; change it as you like.">
        <UiInput v-model="hours" type="number" />
      </UiField>
    </div>
    <template #footer>
      <UiButton :disabled="saving" @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :loading="saving" @click="save">{{ planned ? 'Add route' : 'Create exit' }}</UiButton>
    </template>
  </UiModal>
</template>
