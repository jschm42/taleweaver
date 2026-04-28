<script setup lang="ts">
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

interface Entity {
  id: string
  name: string
  item_type?: string | null
   image_url?: string | null
   is_portable?: boolean
 }

const props = defineProps<{
  items: Entity[]
  showImage: (path?: string | null) => boolean
}>()

const emit = defineEmits<{
  hover: [entity: Entity, event: MouseEvent]
  move: [event: MouseEvent]
  leave: []
  imageError: [path: string]
  takeDirect: [entity: Entity]
}>()
</script>

<template>
  <div v-if="items.length > 0">
    <div class="flex items-center justify-between gap-2 mb-4">
      <div class="flex items-center gap-2">
        <i class="ra ra-locked-fortress text-amber-500"></i>
        <h3 class="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-500/80">Discovery</h3>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-3">
      <div
        v-for="ent in items"
        :key="ent.id"
        class="relative bg-slate-950/40 border border-slate-800/40 rounded-2xl group transition-all hover:border-amber-500/40 hover:bg-slate-900/50 p-2 flex flex-col items-center shadow-lg"
        :class="ent.is_portable !== false ? 'cursor-pointer' : 'cursor-help'"
        @mouseenter="emit('hover', ent, $event)"
        @mousemove="emit('move', $event)"
        @mouseleave="emit('leave')"
        @click="ent.is_portable !== false ? emit('takeDirect', ent) : null"
      >
        <div class="w-12 h-12 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center shrink-0 mb-2">
          <img
            v-if="ent.image_url && showImage(ent.image_url)"
            :src="getImageUrl(ent.image_url)"
            class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
            @error="emit('imageError', ent.image_url)"
          />
          <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/50">
            <i :class="['ra text-xl', getItemIcon(ent.item_type), getTypeColor(ent.item_type)]"></i>
          </div>
        </div>
        <span class="text-[9px] font-bold text-slate-400 group-hover:text-amber-400 transition-colors uppercase tracking-tight truncate w-full text-center px-1 leading-tight">{{ ent.name }}</span>
      </div>
    </div>
  </div>
</template>
