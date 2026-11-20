<script setup lang="ts">
import { computed, ref } from 'vue'
import { Download, RefreshCw, Upload, User, WandSparkles } from 'lucide-vue-next'
import EditorImageLightbox from '@/components/editor/EditorImageLightbox.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiMenu, { type MenuItem } from '@/components/ui/UiMenu.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'
import type { ProtagonistData } from './protagonistTypes'

/** Portrait of the protagonist with its image actions; a click shows it in full size. */
const props = defineProps<{ protagonist: ProtagonistData; isGenerating: boolean; visualsCacheVersion: number }>()
const emit = defineEmits<{
  'quick-regen': []
  'open-regen-dialog': []
  'open-upload-picker': []
  'download-asset': []
}>()

const enlarged = ref<string | null>(null)

const imageUrl = computed(() =>
  props.protagonist.profile_image ? `${props.protagonist.profile_image}?v=${props.visualsCacheVersion}` : '',
)

const menuItems = computed((): MenuItem[] => [
  { label: 'Regenerate with a prompt', icon: WandSparkles, tone: 'ai', onSelect: () => emit('open-regen-dialog') },
  { label: 'Upload a portrait', icon: Upload, onSelect: () => emit('open-upload-picker') },
  ...(imageUrl.value ? [{ label: 'Download', icon: Download, onSelect: () => emit('download-asset') }] : []),
])
</script>

<template>
  <div class="mx-auto w-full max-w-56 shrink-0 space-y-2 md:mx-0">
    <div class="flex items-center justify-between gap-2">
      <p class="wb-label">Portrait</p>
      <UiMenu :items="menuItems" label="Portrait actions" />
    </div>
    <div class="relative aspect-[3/4] overflow-hidden rounded-xl border border-wb-line bg-wb-raised">
      <button
        v-if="imageUrl"
        type="button"
        class="h-full w-full cursor-zoom-in focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
        aria-label="View the portrait in full size"
        @click="enlarged = imageUrl"
      >
        <img :src="imageUrl" :alt="`Portrait of ${protagonist.name || 'the protagonist'}`" class="h-full w-full object-cover" />
      </button>
      <div v-else class="flex h-full flex-col items-center justify-center gap-2 text-wb-faint">
        <User class="h-8 w-8" aria-hidden="true" />
        <span class="wb-hint">No portrait yet</span>
      </div>
      <div v-if="isGenerating" class="absolute inset-0 flex items-center justify-center bg-black/60">
        <UiSpinner label="Generating the portrait" />
      </div>
    </div>
    <UiButton variant="ai" size="sm" block :icon="RefreshCw" :loading="isGenerating" @click="emit('quick-regen')">
      {{ imageUrl ? 'Regenerate portrait' : 'Generate portrait' }}
    </UiButton>
    <EditorImageLightbox :image-url="enlarged" @close="enlarged = null" />
  </div>
</template>
