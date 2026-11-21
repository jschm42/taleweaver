<script setup lang="ts">
/**
 * Generates a catalog preview image from a prompt. The admin picks the image model (LQ = simple,
 * HQ = high fidelity) and can let the small LLM suggest a prompt from the entry's name,
 * description and instruction; the suggestion fills the field for review before generating.
 */
import { computed, ref, watch } from 'vue'
import { Plus, Sparkles, Wand2 } from 'lucide-vue-next'
import type { CatalogTile } from '@/types'
import { api } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSegmented from '@/components/ui/UiSegmented.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

type Quality = 'simple' | 'advanced'

const props = defineProps<{
  isOpen: boolean
  data: { type: 'styles' | 'tones', item: CatalogTile, index: number } | null
  /** An image is being generated: all inputs are locked and the dialog cannot be closed. */
  isGenerating?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'generate', payload: { type: 'styles' | 'tones', item: CatalogTile, index: number, prompt: string, quality: Quality }): void
}>()

const toast = useToast()
const customPrompt = ref('')
const quality = ref<Quality>('simple')
const isSuggesting = ref(false)

const QUALITY_OPTIONS: { value: Quality; label: string }[] = [
  { value: 'simple', label: 'LQ · Simple model' },
  { value: 'advanced', label: 'HQ · High-fidelity model' },
]

const INSPIRATION_CHIPS = [
  'Cinematic lighting',
  'Dramatic contrast',
  'Soft natural light',
  'Muted palette',
  'Rich saturated colors',
  'Atmospheric haze',
  'Highly detailed',
  'Single focal point',
]

watch(
  () => props.isOpen,
  (open) => {
    if (open) customPrompt.value = ''
  },
)

const addChip = (chip: string) => {
  if (!customPrompt.value.trim()) {
    customPrompt.value = chip
  } else if (!customPrompt.value.includes(chip)) {
    customPrompt.value = `${customPrompt.value.trim()}, ${chip}`
  }
}

async function suggestPrompt(): Promise<void> {
  if (!props.data || isBusy.value) return
  isSuggesting.value = true
  try {
    const { prompt, source } = await api.suggestCatalogPrompt({
      catalog_type: props.data.type,
      name: props.data.item.name,
      description: props.data.item.description || undefined,
      instruction: props.data.item.instruction || undefined,
    })
    customPrompt.value = prompt
    if (source === 'template') toast.info('The language model was not available; the built-in preview prompt was filled in.')
  } catch (err) {
    toast.error(`Prompt suggestion failed: ${(err as Error).message}`)
  } finally {
    isSuggesting.value = false
  }
}

const isBusy = computed(() => Boolean(props.isGenerating) || isSuggesting.value)

const handleGenerate = () => {
  if (isBusy.value || !props.data || !customPrompt.value.trim()) return
  emit('generate', {
    type: props.data.type,
    item: props.data.item,
    index: props.data.index,
    prompt: customPrompt.value.trim(),
    quality: quality.value,
  })
}

function handleOpenChange(open: boolean): void {
  if (!open && !props.isGenerating) emit('close')
}
</script>

<template>
  <UiModal
    :open="isOpen"
    title="Generate image from prompt"
    :description="data ? `Preview image for “${data.item.name}” (2:3).` : ''"
    :persistent="isGenerating"
    @update:open="handleOpenChange"
  >
    <div class="space-y-4" :aria-busy="isBusy">
      <UiField label="Image prompt" hint="Enter generates; Shift+Enter starts a new line.">
        <UiTextarea
          v-model="customPrompt"
          :rows="5"
          :disabled="isBusy"
          placeholder="e.g. A hooded wanderer above a misty crag at sunrise, moody oil painting with rim lighting"
          data-autofocus
          @keydown.enter.exact.prevent="handleGenerate"
        />
      </UiField>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <UiButton variant="ai" size="sm" :icon="Wand2" :loading="isSuggesting" :disabled="isBusy" @click="suggestPrompt">
          Suggest prompt
        </UiButton>
        <UiSegmented v-model="quality" :options="QUALITY_OPTIONS" label="Image quality" :disabled="isBusy" />
      </div>
      <div class="space-y-2">
        <p class="wb-label">Add a modifier</p>
        <div class="flex flex-wrap gap-1.5">
          <UiButton
            v-for="chip in INSPIRATION_CHIPS"
            :key="chip"
            size="sm"
            variant="ghost"
            :icon="Plus"
            :disabled="isBusy"
            class="border border-wb-line"
            @click="addChip(chip)"
          >
            {{ chip }}
          </UiButton>
        </div>
      </div>
    </div>
    <template #footer>
      <UiButton :disabled="isGenerating" @click="emit('close')">Cancel</UiButton>
      <UiButton variant="ai" :icon="Sparkles" :loading="isGenerating" :disabled="!customPrompt.trim() || isBusy" @click="handleGenerate">
        {{ isGenerating ? 'Generating…' : 'Generate image' }}
      </UiButton>
    </template>
  </UiModal>
</template>
