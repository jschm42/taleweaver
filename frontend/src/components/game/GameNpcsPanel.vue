<script setup lang="ts">
import { getItemIcon, getImageUrl } from '@/utils/game_icons'

interface Entity {
  id: string
  name: string
  image_url?: string | null
}

const props = defineProps<{
  npcs: Entity[]
  showImage: (path?: string | null) => boolean
}>()

const emit = defineEmits<{
  hover: [entity: Entity, event: MouseEvent]
  move: [event: MouseEvent]
  leave: []
  imageError: [path: string]
}>()
</script>

<template>
  <div v-if="npcs.length > 0">
    <div class="flex items-center justify-between gap-2 mb-4">
      <div class="flex items-center gap-2">
        <i class="ra ra-venoms-trap text-cyan-500"></i>
        <h3 class="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-500/80">Population</h3>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-3 mb-8">
      <div
        v-for="ent in npcs"
        :key="ent.id"
        class="relative bg-slate-950/40 border border-slate-800/40 rounded-2xl group cursor-help transition-all hover:border-cyan-500/40 hover:bg-slate-900/50 p-2 flex flex-col items-center shadow-lg"
        @mouseenter="emit('hover', ent, $event)"
        @mousemove="emit('move', $event)"
        @mouseleave="emit('leave')"
      >
        <div class="w-16 h-16 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center shrink-0 mb-2">
          <img
            v-if="ent.image_url && showImage(ent.image_url)"
            :src="getImageUrl(ent.image_url)"
            class="w-full h-full object-cover object-top transition-transform duration-500 group-hover:scale-110"
            @error="emit('imageError', ent.image_url)"
          />
          <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/50">
            <i :class="['ra text-2xl', getItemIcon('NPC'), 'text-cyan-500/40']"></i>
          </div>
        </div>
        <span class="text-[10px] font-bold text-slate-400 group-hover:text-cyan-400 transition-colors uppercase tracking-tight truncate w-full text-center px-1 leading-tight">{{ ent.name }}</span>
      </div>
    </div>
  </div>
</template>
