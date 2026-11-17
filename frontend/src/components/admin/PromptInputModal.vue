<script setup lang="ts">
import { ref } from 'vue'
import { Plus, Sparkles } from 'lucide-vue-next'
import type { CatalogTile } from '@/types'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const props = defineProps<{
  isOpen: boolean
  data: { type: 'styles' | 'tones', item: CatalogTile, index: number } | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'generate', payload: { type: 'styles' | 'tones', item: CatalogTile, index: number, prompt: string }): void
}>()

const customPrompt = ref('')

const INSPIRATION_CHIPS = [
  'Dark Fantasy',
  'Oil Painting',
  'Cinematic Rim Lighting',
  'Moody Watercolor',
  'Gothic Cathedral',
  'Graphic Novel Ink',
  'Eerie Volumetric Fog',
  'Detailed Concept Art'
]

const addChip = (chip: string) => {
  if (!customPrompt.value.trim()) {
    customPrompt.value = chip
  } else if (!customPrompt.value.includes(chip)) {
    customPrompt.value = `${customPrompt.value.trim()}, ${chip}`
  }
}

const handleGenerate = () => {
  if (props.data && customPrompt.value.trim()) {
    emit('generate', {
      type: props.data.type,
      item: props.data.item,
      index: props.data.index,
      prompt: customPrompt.value.trim()
    })
    customPrompt.value = ''
  }
}

function handleOpenChange(open: boolean): void {
  if (!open) emit('close')
}
</script>

<template>
  <UiModal
    :open="isOpen"
    title="Generate image from prompt"
    :description="data ? `Cover image for “${data.item.name}”.` : ''"
    @update:open="handleOpenChange"
  >
    <div class="space-y-4">
      <UiField label="Image prompt" hint="Enter generates; Shift+Enter starts a new line.">
        <UiTextarea
          v-model="customPrompt"
          :rows="4"
          placeholder="e.g. A hooded wanderer above a misty crag at sunrise, moody oil painting with rim lighting"
          data-autofocus
          @keydown.enter.exact.prevent="handleGenerate"
        />
      </UiField>
      <div class="space-y-2">
        <p class="wb-label">Add a style modifier</p>
        <div class="flex flex-wrap gap-1.5">
          <UiButton v-for="chip in INSPIRATION_CHIPS" :key="chip" size="sm" variant="ghost" :icon="Plus" class="border border-wb-line" @click="addChip(chip)">
            {{ chip }}
          </UiButton>
        </div>
      </div>
    </div>
    <template #footer>
      <UiButton @click="emit('close')">Cancel</UiButton>
      <UiButton variant="ai" :icon="Sparkles" :disabled="!customPrompt.trim()" @click="handleGenerate">Generate image</UiButton>
    </template>
  </UiModal>
</template>
