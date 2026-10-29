<script setup lang="ts">
import { ref, computed } from 'vue'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

/**
 * Square item tile of the inline prompts (workbench, unlock panel). Clicks and hover listeners
 * fall through to the root button; the default slot holds an overlay such as a remove badge.
 */
const props = defineProps<{
  item: any
  selected?: boolean
  dimmed?: boolean
  /** Larger fallback icon for tiles in a slot. */
  large?: boolean
}>()

const imageFailed = ref(false)
const imageUrl = computed(() => (imageFailed.value ? '' : getImageUrl(props.item?.image_url)))
</script>

<template>
  <button type="button" class="tw-prompt-tile" :class="{ 'is-selected': selected, 'is-dimmed': dimmed }">
    <img v-if="imageUrl" :src="imageUrl" class="w-full h-full object-cover object-top" @error="imageFailed = true" />
    <i v-else :class="['ra', large ? 'text-2xl' : 'text-xl', getItemIcon(item.item_type ?? undefined), getTypeColor(item.item_type ?? undefined)]"></i>
    <slot />
    <span class="tw-prompt-tile-caption">{{ item.name || item.id }}</span>
  </button>
</template>
