<script setup lang="ts">
import { computed } from 'vue'
import { Feather, ImagePlus, Palette, Pencil, Plus, Sparkles, Trash2, Upload } from 'lucide-vue-next'
import type { CatalogTile } from '@/types'
import PageHeader from '@/components/workbench/PageHeader.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiMenu, { type MenuItem } from '@/components/ui/UiMenu.vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

const props = defineProps<{
  type: 'styles' | 'tones'
  catalog: CatalogTile[]
  isGeneratingItem: Record<string, boolean>
  simpleModel: string
}>()

const emit = defineEmits<{
  (e: 'addItem'): void
  (e: 'editItem', payload: { item: CatalogTile, index: number }): void
  (e: 'removeItem', index: number): void
  (e: 'generateImage', payload: { item: CatalogTile, index: number }): void
  (e: 'openPrompt', payload: { item: CatalogTile, index: number }): void
  (e: 'uploadImage', payload: { event: Event, item: CatalogTile, index: number }): void
}>()

const copy = computed(() =>
  props.type === 'styles'
    ? {
        title: 'Image styles',
        description: 'Visual styles authors can pick for the images of an adventure.',
        noun: 'style',
        icon: Palette,
      }
    : {
        title: 'Narrative tones',
        description: 'Tone presets authors can pick when an adventure is generated.',
        noun: 'tone',
        icon: Feather,
      },
)

function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

const triggerFileUpload = (index: number) => {
  const input = document.getElementById(`${props.type}-upload-${index}`) as HTMLInputElement
  input?.click()
}

const isItemGenerating = (index: number): boolean => {
  return props.isGeneratingItem[`${props.type}_${index}`] ?? false
}

function menuItems(item: CatalogTile, index: number): MenuItem[] {
  return [
    {
      label: 'Generate image',
      icon: Sparkles,
      tone: 'ai',
      disabled: isItemGenerating(index),
      onSelect: () => emit('generateImage', { item, index }),
    },
    { label: 'Generate from prompt…', icon: ImagePlus, tone: 'ai', onSelect: () => emit('openPrompt', { item, index }) },
    { label: 'Upload image', icon: Upload, onSelect: () => triggerFileUpload(index) },
    { label: 'Edit', icon: Pencil, onSelect: () => emit('editItem', { item, index }) },
    { label: 'Delete', icon: Trash2, tone: 'danger', separated: true, onSelect: () => emit('removeItem', index) },
  ]
}
</script>

<template>
  <div class="space-y-6">
    <PageHeader :title="copy.title" :description="copy.description">
      <template #actions>
        <UiButton variant="primary" :icon="Plus" @click="emit('addItem')">Add {{ copy.noun }}</UiButton>
      </template>
    </PageHeader>

    <UiEmptyState
      v-if="catalog.length === 0"
      :icon="copy.icon"
      :title="`No ${copy.noun}s yet`"
      :description="`Authors see the ${copy.noun}s of this catalog when they create an adventure.`"
    >
      <template #action>
        <UiButton variant="primary" :icon="Plus" @click="emit('addItem')">Add {{ copy.noun }}</UiButton>
      </template>
    </UiEmptyState>

    <ul v-else class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      <li
        v-for="(item, index) in catalog"
        :key="item.id + '-' + index"
        class="group rounded-xl border border-wb-line bg-wb-surface transition-colors hover:border-wb-line-strong"
      >
        <div class="relative aspect-[16/10] overflow-hidden rounded-t-xl bg-wb-raised">
          <img
            v-if="item.image_url"
            :src="item.image_url"
            :alt="item.name"
            class="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
          <div v-else class="flex h-full w-full flex-col items-center justify-center gap-1 text-wb-faint">
            <component :is="copy.icon" class="h-6 w-6" aria-hidden="true" />
            <span class="wb-hint !text-current">No image</span>
          </div>
          <input
            :id="type + '-upload-' + index"
            type="file"
            class="hidden"
            accept="image/*"
            @change="(e) => emit('uploadImage', { event: e, item, index })"
          />
          <div v-if="isItemGenerating(index)" class="absolute inset-0 flex items-center justify-center bg-black/60">
            <UiSpinner size="lg" label="Generating image" class="!text-wb-ai-text" />
          </div>
        </div>
        <div class="p-3">
          <div class="flex items-start justify-between gap-2">
            <button type="button" class="min-w-0 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent rounded-md" @click="emit('editItem', { item, index })">
              <span class="wb-label block truncate !text-wb-strong">{{ item.name }}</span>
              <span class="wb-mono block truncate text-wb-faint">{{ item.id }}</span>
            </button>
            <UiMenu :items="menuItems(item, index)" :label="`Actions for ${item.name}`" />
          </div>
          <p class="wb-hint mt-1.5 line-clamp-2 whitespace-pre-wrap">{{ fixNewlines(item.description) || 'No description.' }}</p>
        </div>
      </li>
    </ul>
  </div>
</template>
