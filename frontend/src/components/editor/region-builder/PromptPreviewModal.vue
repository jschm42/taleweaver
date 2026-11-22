<script setup lang="ts">
/** The full user prompt a region build would send (advanced mode); read-only. */
import { ref, watch } from 'vue'
import { useRegionBuilderContext } from '@/composables/regionBuilder/regionBuilderContext'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

const open = defineModel<boolean>('open', { default: false })

const { loadPrompt } = useRegionBuilderContext()

const text = ref('')
const error = ref('')
const loading = ref(false)

watch(open, async (isOpen) => {
  if (!isOpen) return
  loading.value = true
  error.value = ''
  try {
    text.value = await loadPrompt()
  } catch (failure: unknown) {
    error.value = failure instanceof Error ? failure.message : 'The prompt could not be built.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <UiModal v-model:open="open" title="Region prompt" description="What the World-Builder receives, without the system prompt." size="xl">
    <div v-if="loading" class="flex justify-center py-12">
      <UiSpinner label="Building the prompt" />
    </div>
    <UiNotice v-else-if="error" tone="danger">{{ error }}</UiNotice>
    <pre v-else class="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded-md border border-wb-line bg-wb-raised p-4 wb-mono">{{ text }}</pre>
  </UiModal>
</template>
