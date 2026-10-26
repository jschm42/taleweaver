<script setup lang="ts">
/**
 * SheetInventoryPanel — Backpack grid of the character sheet.
 */
import type { InventoryItem } from '@/types'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'
import { isInteractable, isReadableItem, useBrokenImages } from './sheetItems'

const SLOT_COUNT = 24

const props = defineProps<{
  items: InventoryItem[]
  isDebug?: boolean
}>()

const emit = defineEmits<{
  activate: [item: any]
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  itemContextmenu: [item: any, event: MouseEvent]
}>()

const { showImage, handleImageError } = useBrokenImages()

const itemAt = (idx: number): any => props.items[idx - 1]
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="flex items-center justify-between gap-2 mb-3 sm:mb-4 shrink-0">
      <h4 class="tw-panel-title tw-muted">Backpack Contents</h4>
      <div class="tw-muted text-xxs sm:text-xs font-mono font-bold">
        <span class="tw-dialog-eyebrow">{{ props.items.length }}</span> / {{ SLOT_COUNT }} slots used
      </div>
    </div>

    <div class="grid grid-cols-4 sm:grid-cols-6 gap-2 sm:gap-3.5">
      <div
        v-for="idx in SLOT_COUNT"
        :key="idx"
        class="aspect-square flex items-center justify-center transition-all relative group"
        :class="[
          itemAt(idx) ? 'tw-card tw-dialog-slot-filled' : 'tw-dialog-slot',
          itemAt(idx) ? (isInteractable(itemAt(idx)) ? 'cursor-pointer active:scale-95' : 'cursor-help') : ''
        ]"
        @click="itemAt(idx) && emit('activate', itemAt(idx))"
        @mouseenter="itemAt(idx) && emit('itemHover', { ...itemAt(idx), entity_type: 'ITEM' }, $event)"
        @mouseleave="emit('itemLeave')"
        @contextmenu.prevent="itemAt(idx) && emit('itemContextmenu', { ...itemAt(idx), entity_type: 'ITEM' }, $event)"
      >
        <template v-if="itemAt(idx)">
          <!-- READ/NOTE tag -->
          <div
            v-if="isReadableItem(itemAt(idx))"
            class="absolute top-1 left-1 z-20 px-1 rounded text-[7px] sm:text-[8px] font-black tracking-wide border leading-none"
            :class="Boolean(itemAt(idx).is_read) ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' : 'bg-amber-500/20 text-amber-200 border-amber-500/40'"
          >
            {{ Boolean(itemAt(idx).is_read) ? 'READ' : 'NOTE' }}
          </div>

          <div v-if="showImage(itemAt(idx).image_url)" class="w-full h-full p-1.5 sm:p-2">
            <img
              :src="getImageUrl(itemAt(idx).image_url)"
              class="w-full h-full object-cover object-top rounded-lg transition-transform group-hover:scale-105"
              @error="handleImageError(itemAt(idx).image_url)"
            />
          </div>
          <i
            v-else
            :class="['ra text-2xl sm:text-3xl transition-transform group-hover:scale-110', getItemIcon(itemAt(idx).item_type), getTypeColor(itemAt(idx).item_type)]"
          ></i>

          <div v-if="props.isDebug" class="absolute bottom-1 right-1 px-1 bg-black/75 rounded text-[7px] font-mono text-amber-300 opacity-70">
            {{ itemAt(idx).id || itemAt(idx).key }}
          </div>
        </template>

        <div v-else class="text-[10px] font-mono opacity-40 select-none">
          {{ idx }}
        </div>
      </div>
    </div>

    <div class="tw-dialog-divider tw-muted mt-4 pt-3 border-t flex items-center justify-between text-xxs flex-wrap gap-2">
      <span>💡 Click item to equip, consume, open, or read.</span>
      <span>Right-click or hold for actions.</span>
    </div>
  </div>
</template>

<style scoped>
.ra { font-family: 'rpgawesome' !important; display: inline-block; line-height: 1; text-align: center; }
</style>
