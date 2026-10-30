<script setup lang="ts">
import { computed } from 'vue'
import { Brain } from 'lucide-vue-next'
import { getItemIcon, getTypeColor } from '@/utils/game_icons'

/** A badge in the top-left corner of the tile. */
export interface ItemTileBadge {
  label: string
  class: string
}

/** One item card of the Items tab, with its context menu. */
const props = defineProps<{
  obj: any
  /** Border colour class of the card. */
  accentClass: string
  /** Hover colour class of the menu button. */
  menuHoverClass?: string
  badges?: ItemTileBadge[]
  hasScript?: boolean
  /** Entity passed to the hover tooltip; defaults to a plain item. */
  hoverEntity?: any
  /** Image, generation and upload actions; off for items that never get an image (CONSTRUCTABLE). */
  imageActions?: boolean
  /** Offer "Move to Scene…" (off for CONSTRUCTABLE items, which never appear in the world). */
  movable?: boolean
  showStatsDot?: boolean
  imageUrl?: string
  isGenerating?: boolean
  menuOpen?: boolean
}>()

const emit = defineEmits<{
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'open-text-edit', ...args: any[]): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'handle-hover', entity: any, event: MouseEvent): void
  (e: 'clear-hover'): void
  (e: 'request-change-item-type', itemId: string, name: string, currentItemType: string): void
  (e: 'request-move-item-to-scene', itemId: string, name: string, currentSceneId: string): void
  (e: 'request-delete-item', itemId: string, name: string): void
  (e: 'export-entity', kind: 'item', id: string, label: string): void
}>()

const hoverPayload = computed(() => props.hoverEntity || {
  id: props.obj.id,
  name: props.obj.name,
  description: props.obj.description,
  image_url: props.obj.image_url,
  type: 'ITEM',
  stats: props.obj.stats,
})

const menuItemClass = 'w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:text-white transition-all'
</script>

<template>
  <div
    @mouseenter="emit('handle-hover', hoverPayload, $event)"
    @mouseleave="emit('clear-hover')"
    :class="[
      'relative group aspect-square bg-slate-900 border rounded-xl shadow-lg transition-all overflow-visible',
      accentClass,
      menuOpen ? 'z-[180]' : 'z-0',
    ]"
  >
    <div class="absolute inset-0 rounded-xl overflow-hidden">
      <!-- Items without image actions (CONSTRUCTABLE) always show their type icon, even if an old image is stored. -->
      <img v-if="imageActions && imageUrl" :src="imageUrl" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
      <div v-else-if="!imageActions" class="absolute inset-0 flex items-center justify-center pb-6">
        <i :class="['ra text-4xl opacity-70', getItemIcon(obj.item_type ?? undefined), getTypeColor(obj.item_type ?? undefined)]"></i>
      </div>
      <div v-if="isGenerating" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
        <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
      </div>
      <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
      <div class="absolute top-2 left-2 flex items-center gap-1 z-10">
        <div v-for="badge in badges || []" :key="badge.label" :class="['px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border', badge.class]">{{ badge.label }}</div>
        <div
          v-if="hasScript"
          class="p-1 rounded-full border border-purple-500/50 bg-purple-950/80 text-purple-300 shadow-md flex items-center justify-center backdrop-blur-sm"
          title="Contains custom event script(s)"
        >
          <Brain class="w-3 h-3 text-purple-400" />
        </div>
      </div>
      <div class="absolute bottom-0 left-0 right-0 p-2">
        <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
        <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
        <div v-if="showStatsDot" class="flex gap-1 mt-1">
          <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.5)]"></div>
        </div>
      </div>
    </div>

    <div class="absolute top-1.5 right-1.5 z-40">
      <button @click="emit('toggle-menu', obj.id, $event)" :class="['w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white transition-all shadow-lg group/dots', menuHoverClass || 'hover:bg-emerald-500']">
        <div class="flex flex-col gap-0.5">
          <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
          <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
          <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
        </div>
      </button>
      <div v-if="menuOpen" class="absolute right-0 mt-1 w-56 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[200] animate-fade-in ring-1 ring-white/5">
        <template v-if="imageActions">
          <button @click="emit('quick-regen', 'object', obj.id)" :class="[menuItemClass, 'hover:bg-emerald-500']">Quick Regen</button>
          <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" :class="[menuItemClass, 'hover:bg-cyan-500']">Regen (Prompt)</button>
          <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" :class="[menuItemClass, 'hover:bg-amber-500']">Upload Image</button>
          <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'object'}_image`)" :class="[menuItemClass, 'hover:bg-violet-500']">Download Image</button>
        </template>
        <button @click="emit('open-text-edit', 'object', obj.id, obj.name, (obj.description || ''))" :class="[menuItemClass, 'hover:bg-blue-500']">Edit Details</button>
        <div class="my-1 border-t border-white/5"></div>
        <button @click="emit('request-change-item-type', obj.id, obj.name, obj.item_type || 'DEFAULT')" :class="[menuItemClass, 'hover:bg-amber-500']">Change Type…</button>
        <button v-if="movable" @click="emit('request-move-item-to-scene', obj.id, obj.name, obj.current_scene_id || '')" :class="[menuItemClass, 'hover:bg-sky-500']">Move to Scene…</button>
        <button @click="emit('export-entity', 'item', obj.id, obj.name)" :class="[menuItemClass, 'hover:bg-teal-500']">Export (.twe)</button>
        <button @click="emit('request-delete-item', obj.id, obj.name)" :class="[menuItemClass, 'hover:bg-red-500']">Delete</button>
      </div>
    </div>
  </div>
</template>
