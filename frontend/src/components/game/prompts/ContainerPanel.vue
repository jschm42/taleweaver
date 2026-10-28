<script setup lang="ts">
import { computed, ref } from 'vue'
import { Backpack, PackageOpen, ArrowDownToLine } from 'lucide-vue-next'
import { getItemIcon, getTypeColor, getImageUrl, hasRenderableImagePath } from '@/utils/game_icons'
import InlinePromptPanel from './InlinePromptPanel.vue'

/** Contents of an opened container, shown inline at the end of the story feed. */
const props = defineProps<{
  open: boolean
  title: string
  items: any[]
  imageUrl?: string | null
  busy?: boolean
}>()

const emit = defineEmits<{
  close: []
  takeAll: []
  takeItem: [item: any]
  dropToScene: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
}>()

const hasItems = computed(() => (props.items || []).length > 0)
const resolvedImageUrl = computed(() => getImageUrl(props.imageUrl) || null)

const brokenImages = ref<Record<string, boolean>>({})

function itemKey(item: any): string {
  return String(item.id || item.name || 'unknown-item')
}

function onItemImageError(item: any): void {
  brokenImages.value[itemKey(item)] = true
}

function canShowImage(item: any): boolean {
  return hasRenderableImagePath(item.image_url) && !brokenImages.value[itemKey(item)]
}

function takeItem(item: any): void {
  if (props.busy) return
  emit('itemLeave')
  emit('takeItem', item)
}
</script>

<template>
  <InlinePromptPanel
    :open="open"
    label="Container"
    :title="title"
    :image-url="resolvedImageUrl"
    :busy="busy"
    :reveal-key="title"
    @close="emit('close')"
  >
    <template #label-icon><PackageOpen class="w-3 h-3" /></template>

    <template v-if="hasItems">
      <p class="tw-prompt-hint">Click an item to take it.</p>
      <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 max-h-56 overflow-y-auto p-0.5">
        <button
          v-for="item in items"
          :key="itemKey(item)"
          type="button"
          :disabled="busy"
          class="tw-prompt-tile"
          :title="`Take ${item.name || item.id}`"
          @click="takeItem(item)"
          @mouseenter="emit('itemHover', { ...item, entity_type: 'ITEM' }, $event)"
          @mouseleave="emit('itemLeave')"
        >
          <img
            v-if="canShowImage(item)"
            :src="getImageUrl(item.image_url)"
            class="w-full h-full object-cover object-top"
            :alt="item.name || 'container item'"
            @error="onItemImageError(item)"
          />
          <i v-else :class="['ra text-2xl', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
          <span class="tw-prompt-tile-caption">{{ item.name || item.id }}</span>
        </button>
      </div>
      <div class="flex flex-wrap justify-end gap-2">
        <button type="button" class="tw-prompt-action tw-prompt-action--ghost" :disabled="busy" @click="emit('dropToScene')">
          <ArrowDownToLine class="w-4 h-4" />
          <span>Drop To Scene</span>
        </button>
        <button type="button" class="tw-prompt-action" :disabled="busy" @click="emit('takeAll')">
          <Backpack class="w-4 h-4" />
          <span>Take All</span>
        </button>
      </div>
    </template>
    <p v-else class="tw-prompt-hint">This container is empty.</p>
  </InlinePromptPanel>
</template>
