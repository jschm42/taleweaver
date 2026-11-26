<script setup lang="ts">
/**
 * One link of the world map. A built link is made of gateway exits: their travel times are
 * edited here (saved on the exits). A planned link stores its own travel time until the
 * planned region is generated. The estimate turns the map distance into a travel time.
 */
import { computed, ref, watch } from 'vue'
import { Ruler, Trash2 } from 'lucide-vue-next'
import { entityService } from '@/services/entityService'
import { useToast } from '@/composables/useToast'
import type { WorldSection } from '@/services/sectionService'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import { estimateMinutes, mapDistance, type RegionLink } from '@/components/editor/regions/regionGraph'

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  adventureId: string
  link: RegionLink | null
  sections: WorldSection[]
  sceneLabels: Record<string, string>
}>()

const emit = defineEmits<{
  (e: 'saved'): void
  (e: 'save-planned', minutes: number | null): void
  (e: 'remove-planned'): void
}>()

const toast = useToast()
const hours = ref<Record<string, string | number | null>>({})
const scale = ref<string | number | null>(1)
const saving = ref(false)

const from = computed(() => props.sections.find((s) => s.id === props.link?.from))
const to = computed(() => props.sections.find((s) => s.id === props.link?.to))
const distance = computed(() => (from.value && to.value ? mapDistance(from.value, to.value) : 0))
const keys = computed(() => (props.link?.planned ? ['planned'] : (props.link?.exits || []).map((e) => e.id)))

function toHours(minutes: number | null | undefined): number | null {
  return minutes ? Math.round((minutes / 60) * 100) / 100 : null
}

function toMinutes(value: string | number | null | undefined): number | null {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? Math.round(number * 60) : null
}

watch(open, (isOpen) => {
  if (!isOpen || !props.link) return
  hours.value = props.link.planned
    ? { planned: toHours(props.link.travelMinutes) }
    : Object.fromEntries(props.link.exits.map((e) => [e.id, toHours(e.travelMinutes)]))
})

function estimate(): void {
  const value = toHours(estimateMinutes(distance.value, Number(scale.value) || 1))
  hours.value = Object.fromEntries(keys.value.map((key) => [key, value]))
}

async function save(): Promise<void> {
  if (!props.link) return
  if (props.link.planned) {
    emit('save-planned', toMinutes(hours.value.planned))
    open.value = false
    return
  }
  saving.value = true
  try {
    for (const exit of props.link.exits) {
      const minutes = toMinutes(hours.value[exit.id])
      if (minutes === exit.travelMinutes) continue
      await entityService.saveEntityText(props.adventureId, { target_type: 'exit', target_id: exit.id, travel_minutes: minutes ?? 0 })
    }
    emit('saved')
    open.value = false
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to save the travel times.')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UiModal
    v-model:open="open"
    :title="`${from?.label || link?.from} – ${to?.label || link?.to}`"
    :description="link?.planned ? 'A planned route: its exits are created when the planned region is generated.' : 'Travel time of the exits that connect the two regions.'"
    :persistent="saving"
  >
    <div v-if="link" class="space-y-4">
      <UiField v-if="link.planned" label="Travel time (hours)">
        <UiInput v-model="hours.planned" type="number" />
      </UiField>
      <UiField
        v-for="exit in link.exits"
        v-else
        :key="exit.id"
        :label="`${sceneLabels[exit.from] || exit.from} → ${sceneLabels[exit.to] || exit.to}`"
        :hint="exit.label ? `Exit: ${exit.label}. Travel time in hours.` : 'Travel time in hours.'"
      >
        <UiInput v-model="hours[exit.id]" type="number" />
      </UiField>
      <div class="flex flex-wrap items-end gap-2 border-t border-wb-line pt-4">
        <UiField label="Hours per 10 % of the map" info="The estimate multiplies the straight-line distance on the world map by this pace. Nothing is calculated automatically: the travel time is what you set here.">
          <UiInput v-model="scale" type="number" size="sm" />
        </UiField>
        <UiButton size="sm" :icon="Ruler" @click="estimate">Estimate from map distance</UiButton>
      </div>
    </div>
    <template #footer>
      <UiButton v-if="link?.planned" variant="danger" :icon="Trash2" @click="emit('remove-planned'); open = false">Remove route</UiButton>
      <UiButton :disabled="saving" @click="open = false">Cancel</UiButton>
      <UiButton variant="primary" :loading="saving" @click="save">Save</UiButton>
    </template>
  </UiModal>
</template>
