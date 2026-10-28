<script setup lang="ts">
import { ref, computed } from 'vue'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

/** Inventory item row inside an inline prompt; the default slot holds its action button. */
const props = defineProps<{
  item: any
}>()

const imageFailed = ref(false)
const imageUrl = computed(() => (imageFailed.value ? '' : getImageUrl(props.item?.image_url)))
</script>

<template>
  <div class="tw-prompt-item">
    <div class="tw-prompt-item-thumb">
      <img v-if="imageUrl" :src="imageUrl" class="w-full h-full object-cover object-top" @error="imageFailed = true" />
      <i v-else :class="['ra text-lg', getItemIcon(item.item_type ?? undefined), getTypeColor(item.item_type ?? undefined)]"></i>
    </div>
    <div class="flex-1 min-w-0">
      <p class="tw-prompt-item-name">{{ item.name || item.id }}</p>
      <p class="tw-prompt-hint line-clamp-2">{{ item.description || 'A special item carried in your inventory.' }}</p>
    </div>
    <slot />
  </div>
</template>
