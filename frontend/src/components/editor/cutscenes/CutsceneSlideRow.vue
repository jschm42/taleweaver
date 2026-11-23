<script setup lang="ts">
/** One slide of a cut-scene: its image (opens the image dialog) and its text. */
import { ArrowDown, ArrowUp, ImagePlus, Trash2 } from 'lucide-vue-next'
import type { CutsceneDefinitionSlide } from '@/types'
import { getImageUrl } from '@/utils/game_icons'
import UiField from '@/components/ui/UiField.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

const slide = defineModel<CutsceneDefinitionSlide>({ required: true })

defineProps<{ index: number, total: number }>()

defineEmits<{
  (e: 'image'): void
  (e: 'move', delta: number): void
  (e: 'remove'): void
}>()
</script>

<template>
  <div class="flex flex-col gap-3 sm:flex-row">
    <button
      type="button"
      class="relative aspect-[16/9] w-full shrink-0 overflow-hidden rounded-md border border-wb-line bg-wb-sunken sm:w-48 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
      :aria-label="slide.image_url ? `Change the image of slide ${index + 1}` : `Add an image to slide ${index + 1}`"
      @click="$emit('image')"
    >
      <img v-if="slide.image_url" :src="getImageUrl(slide.image_url) || slide.image_url" alt="" class="absolute inset-0 h-full w-full object-cover" />
      <span v-else class="absolute inset-0 flex flex-col items-center justify-center gap-1 text-wb-muted">
        <ImagePlus class="h-5 w-5" aria-hidden="true" />
        <span class="wb-hint">Add image</span>
      </span>
    </button>
    <div class="min-w-0 flex-1">
      <UiField :label="`Slide ${index + 1}`" :count="slide.text.length" :max-length="800">
        <UiTextarea v-model="slide.text" :rows="3" placeholder="What the narrator says on this slide." />
      </UiField>
    </div>
    <div class="flex shrink-0 gap-1 sm:flex-col">
      <UiIconButton :icon="ArrowUp" label="Move up" size="sm" :disabled="index === 0" @click="$emit('move', -1)" />
      <UiIconButton :icon="ArrowDown" label="Move down" size="sm" :disabled="index === total - 1" @click="$emit('move', 1)" />
      <UiIconButton :icon="Trash2" label="Delete slide" size="sm" variant="danger" :disabled="total <= 1" @click="$emit('remove')" />
    </div>
  </div>
</template>
