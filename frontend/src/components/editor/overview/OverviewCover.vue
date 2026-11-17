<script setup lang="ts">
import { computed } from 'vue'
import { Download, ImagePlus, RefreshCw, Upload, WandSparkles } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import UiButton from '@/components/ui/UiButton.vue'
import UiMenu, { type MenuItem } from '@/components/ui/UiMenu.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

/** Cover image of the adventure with its image actions. */
const editor = useEditor()

const cover = computed(() => editor.debugData?.adventure ?? null)
const coverId = computed((): string => String(cover.value?.id ?? ''))
const title = computed((): string => String(cover.value?.title || 'adventure'))
const isBusy = computed(() => Boolean(editor.isQuickGenerating[`cover_${coverId.value}`] || editor.isBatchGenerating.cover))

const menuItems = computed((): MenuItem[] => [
  { label: 'Regenerate with a prompt', icon: WandSparkles, tone: 'ai', onSelect: () => editor.openRegenerateDialog('cover', coverId.value, title.value) },
  { label: 'Upload an image', icon: Upload, onSelect: () => editor.openUploadPicker('cover', coverId.value, title.value) },
  ...(cover.value?.image_url
    ? [{ label: 'Download', icon: Download, onSelect: () => editor.downloadVisualAsset(cover.value.image_url, `${title.value}_cover`) }]
    : []),
])
</script>

<template>
  <div v-if="cover" class="mx-auto w-full max-w-56 space-y-2 lg:max-w-none">
    <div class="flex items-center justify-between gap-2">
      <p class="wb-label">Cover</p>
      <UiMenu :items="menuItems" label="Cover actions" />
    </div>
    <div class="relative aspect-[2/3] overflow-hidden rounded-xl border border-wb-line bg-wb-raised">
      <img v-if="cover.image_url" :src="cover.image_url" :alt="`Cover of ${title}`" class="h-full w-full object-cover" />
      <div v-else class="flex h-full flex-col items-center justify-center gap-2 text-wb-faint">
        <ImagePlus class="h-8 w-8" aria-hidden="true" />
        <span class="wb-hint">No cover yet</span>
      </div>
      <div v-if="isBusy" class="absolute inset-0 flex items-center justify-center bg-black/60">
        <UiSpinner label="Generating the cover" />
      </div>
    </div>
    <UiButton variant="ai" size="sm" block :icon="RefreshCw" :loading="isBusy" @click="editor.quickRegenerateVisual('cover', coverId)">
      {{ cover.image_url ? 'Regenerate cover' : 'Generate cover' }}
    </UiButton>
  </div>
</template>
