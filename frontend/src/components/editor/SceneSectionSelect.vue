<script setup lang="ts">
// Editor select for WorldScene.section_id: the region (world section) the scene belongs to.
// Choosing a planned region makes it built. Regions are managed on the Regions page.
import { computed, ref, watch } from 'vue'
import { entityService } from '@/services/entityService'
import type { WorldSection } from '@/services/sectionService'
import { useToast } from '@/composables/useToast'
import UiField from '@/components/ui/UiField.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps<{
  adventureId: string
  sceneId: string
  value?: string | null
  sections: WorldSection[]
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const toast = useToast()
const current = ref(props.value || '')
const isSaving = ref(false)

watch(() => props.value, (value) => {
  current.value = value || ''
})

const options = computed(() => [
  { value: '', label: 'No region' },
  ...props.sections.map((s) => ({ value: s.id, label: s.status === 'built' ? s.label : `${s.label} (planned)` })),
])

async function change(next: string | number | null): Promise<void> {
  const sectionId = String(next || '')
  const previous = current.value
  current.value = sectionId
  isSaving.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: props.sceneId,
      section_id: sectionId,
    })
    emit('refresh')
  } catch (error: unknown) {
    current.value = previous
    toast.error(error instanceof Error ? error.message : 'Failed to change the region.')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <UiField v-if="sections.length" label="Region" hint="The world section this scene lies in.">
    <UiSelect :model-value="current" :options="options" :disabled="isSaving" @update:model-value="change" />
  </UiField>
</template>
