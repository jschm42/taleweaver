<script setup lang="ts">
/**
 * DiscoveriesPanel — Objects found in the current scene as large icon tiles.
 */
import { ref, computed } from 'vue'
import { Hand } from 'lucide-vue-next'
import { getItemIcon, getTypeColor, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  items: any[]
  isEvaluating?: boolean
  /** Narrow column layout (scene sidebar): small three-per-row tiles, no hint or type text. */
  compact?: boolean
}>()

const emit = defineEmits<{
  itemClick: [item: any]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  itemContextmenu: [item: any, event: MouseEvent]
  takeDirect: [item: any]
}>()

const TAKE_ALL_INTERVAL_MS = 250

const isTakingAll = ref(false)
const thumbFailed = ref<Record<string, boolean>>({})
const brokenImages = ref<Record<string, boolean>>({})
const loadedImages = ref<Record<string, boolean>>({})

const portableItems = computed(() => props.items.filter((item: any) => item.is_portable !== false))
const canTakeAll = computed(() => portableItems.value.length > 1 && !props.isEvaluating && !isTakingAll.value)

function imageUrl(path: string): string {
  return thumbFailed.value[path] ? getOriginalImageUrl(path) : getImageUrl(path, { thumbnail: true })
}

function onImageError(path: string) {
  if (!thumbFailed.value[path]) {
    thumbFailed.value[path] = true
    return
  }
  brokenImages.value[path] = true
}

function onImageLoad(path: string) {
  loadedImages.value[path] = true
}

function isImageLoading(item: any): boolean {
  return hasImage(item) && !loadedImages.value[item.image_url]
}

function hasImage(item: any): boolean {
  return Boolean(item.image_url) && !brokenImages.value[item.image_url]
}

function typeLabel(item: any): string {
  return String(item.item_type || 'Object').toLowerCase()
}

async function takeAll() {
  if (!canTakeAll.value) {
    return
  }
  isTakingAll.value = true
  try {
    for (const item of portableItems.value) {
      emit('takeDirect', item)
      await new Promise((resolve) => setTimeout(resolve, TAKE_ALL_INTERVAL_MS))
    }
  } finally {
    isTakingAll.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between gap-3">
      <h3 class="tw-panel-title">Room Discoveries</h3>
      <button
        v-if="canTakeAll"
        type="button"
        class="px-2.5 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 text-[11px] font-bold flex items-center gap-1.5 transition-all active:scale-95 cursor-pointer"
        title="Collect all portable items into your inventory"
        @click="takeAll"
      >
        <Hand class="w-3.5 h-3.5" />
        Take All ({{ portableItems.length }})
      </button>
    </div>
    <p v-if="!props.compact" class="tw-muted text-xs leading-relaxed">
      Click an object to look at it, right-click for more actions, or use the hand to pick it up.
    </p>

    <div class="grid" :class="props.compact ? 'grid-cols-3 gap-2' : 'grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3'">
      <div
        v-for="item in props.items"
        :key="item.id"
        class="tw-card tw-card--interactive group relative flex flex-col items-center text-center"
        :class="props.compact ? 'gap-1 p-1.5 pt-2' : 'gap-2 p-3 pt-4'"
        role="button"
        tabindex="0"
        :aria-label="`Examine ${item.name}`"
        @click="emit('itemClick', item)"
        @keydown.enter="emit('itemClick', item)"
        @mouseenter="emit('itemHover', item, $event)"
        @mouseleave="emit('itemLeave')"
        @contextmenu.prevent="emit('itemContextmenu', item, $event)"
      >
        <button
          v-if="item.is_portable !== false"
          type="button"
          class="absolute z-10 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/35 border border-emerald-500/40 text-emerald-500 hover:scale-110 transition-all cursor-pointer disabled:opacity-40"
          :class="props.compact ? 'top-1 right-1 p-1' : 'top-2 right-2 p-1.5'"
          :disabled="props.isEvaluating"
          :aria-label="`Take ${item.name}`"
          title="Take item"
          @click.stop="emit('takeDirect', item)"
        >
          <Hand :class="props.compact ? 'w-3 h-3' : 'w-3.5 h-3.5'" />
        </button>

        <div
          class="relative rounded-xl overflow-hidden bg-slate-950/90 border border-white/10 flex items-center justify-center shrink-0 shadow-inner group-hover:scale-105 transition-transform"
          :class="props.compact ? 'w-14 h-14' : 'w-20 h-20 sm:w-24 sm:h-24'"
        >
          <span v-if="isImageLoading(item)" class="tw-image-spinner" role="status" aria-label="Loading image"></span>
          <img
            v-if="hasImage(item)"
            :src="imageUrl(item.image_url)"
            :alt="item.name"
            decoding="async"
            class="w-full h-full object-cover transition-opacity duration-300"
            :class="isImageLoading(item) ? 'opacity-0' : 'opacity-100'"
            @load="onImageLoad(item.image_url)"
            @error="onImageError(item.image_url)"
          />
          <i v-else :class="['ra', props.compact ? 'text-3xl' : 'text-4xl sm:text-5xl', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
        </div>

        <p class="font-bold leading-snug line-clamp-2" :class="props.compact ? 'text-[11px]' : 'text-xs'">{{ item.name }}</p>
        <p v-if="!props.compact" class="tw-muted text-[10px] uppercase tracking-wider">{{ typeLabel(item) }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}
</style>
