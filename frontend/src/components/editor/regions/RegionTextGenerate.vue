<script setup lang="ts">
/**
 * "Generate" for a region's description or brief: the World-Builder writes it from the
 * adventure's plot, the region's other fields and the other regions. The text goes into the
 * Regions page draft, so the author reviews it and saves or discards it with the save bar.
 */
import { ref } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import { sectionService, type WorldSection } from '@/services/sectionService'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps<{
  adventureId: string
  field: 'description' | 'brief'
  section: WorldSection
  sections: WorldSection[]
}>()

const emit = defineEmits<{ (e: 'generated', text: string): void }>()

const toast = useToast()
const busy = ref(false)

async function generate(): Promise<void> {
  busy.value = true
  try {
    const text = await sectionService.generateSectionText(props.adventureId, props.field, props.section.id, props.sections)
    if (text) emit('generated', text)
    else toast.warn(`The World-Builder returned no ${props.field}.`)
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : `Failed to write the ${props.field}.`)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex justify-end">
    <UiButton variant="ai" size="sm" :icon="Sparkles" :loading="busy" @click="generate">
      {{ section[field].trim() ? 'Regenerate' : 'Generate' }}
    </UiButton>
  </div>
</template>
