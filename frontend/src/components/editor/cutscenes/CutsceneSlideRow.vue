<script setup lang="ts">
/**
 * One slide of a cut-scene: its image (opens the image dialog) and its text passages. Several
 * passages are shown one after another over the same picture (e.g. a short dialogue).
 */
import { ArrowDown, ArrowUp, ImagePlus, Plus, Trash2, X } from 'lucide-vue-next'
import { MAX_PASSAGES } from '@/services/cutsceneService'
import type { CutsceneDefinitionSlide } from '@/types'
import { getImageUrl } from '@/utils/game_icons'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const MAX_PASSAGE_CHARS = 800

const slide = defineModel<CutsceneDefinitionSlide>({ required: true })

defineProps<{ index: number, total: number }>()

defineEmits<{
  (e: 'image'): void
  (e: 'move', delta: number): void
  (e: 'remove'): void
}>()

function addPassage(): void {
  if (slide.value.passages.length < MAX_PASSAGES) slide.value.passages.push('')
}

function removePassage(position: number): void {
  if (slide.value.passages.length > 1) slide.value.passages.splice(position, 1)
}

function passageLabel(slideIndex: number, position: number): string {
  return slide.value.passages.length > 1 ? `Slide ${slideIndex + 1} · passage ${position + 1}` : `Slide ${slideIndex + 1}`
}
</script>

<template>
  <div class="flex flex-col gap-3 sm:flex-row">
    <button
      type="button"
      class="relative aspect-[16/9] w-full shrink-0 self-start overflow-hidden rounded-md border border-wb-line bg-wb-sunken sm:w-48 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
      :aria-label="slide.image_url ? `Change the image of slide ${index + 1}` : `Add an image to slide ${index + 1}`"
      @click="$emit('image')"
    >
      <img v-if="slide.image_url" :src="getImageUrl(slide.image_url) || slide.image_url" alt="" class="absolute inset-0 h-full w-full object-cover" />
      <span v-else class="absolute inset-0 flex flex-col items-center justify-center gap-1 text-wb-muted">
        <ImagePlus class="h-5 w-5" aria-hidden="true" />
        <span class="wb-hint">Add image</span>
      </span>
    </button>
    <div class="min-w-0 flex-1 space-y-3">
      <div v-for="(_, position) in slide.passages" :key="position" class="flex items-start gap-2">
        <UiField class="min-w-0 flex-1" :label="passageLabel(index, position)" :count="slide.passages[position].length" :max-length="MAX_PASSAGE_CHARS">
          <UiTextarea
            v-model="slide.passages[position]"
            :rows="2"
            :placeholder="position === 0 ? 'What the narrator says on this slide.' : 'Shown after the passage above, over the same picture.'"
          />
        </UiField>
        <UiIconButton
          v-if="slide.passages.length > 1"
          class="mt-6"
          :icon="X"
          :label="`Remove passage ${position + 1}`"
          size="sm"
          @click="removePassage(position)"
        />
      </div>
      <UiButton :icon="Plus" size="sm" variant="ghost" :disabled="slide.passages.length >= MAX_PASSAGES" @click="addPassage">
        Add passage
      </UiButton>
    </div>
    <div class="flex shrink-0 gap-1 sm:flex-col">
      <UiIconButton :icon="ArrowUp" label="Move up" size="sm" :disabled="index === 0" @click="$emit('move', -1)" />
      <UiIconButton :icon="ArrowDown" label="Move down" size="sm" :disabled="index === total - 1" @click="$emit('move', 1)" />
      <UiIconButton :icon="Trash2" label="Delete slide" size="sm" variant="danger" :disabled="total <= 1" @click="$emit('remove')" />
    </div>
  </div>
</template>
