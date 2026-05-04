<script setup lang="ts">
import { computed } from 'vue'
import { getItemIcon, getImageUrl } from '@/utils/game_icons'

interface SceneHoverPayload {
  name: string
  description: string
  image_url?: string | null
}

const props = defineProps<{
  sceneId?: string | null
  sceneName?: string | null
  sceneDescription?: string | null
  sceneImage?: string | null
  showImage: (path?: string | null) => boolean
  isDebug?: boolean
}>()

const emit = defineEmits<{
  hover: [payload: SceneHoverPayload, event: MouseEvent]
  move: [event: MouseEvent]
  leave: []
  imageError: [path: string]
}>()

const hoverPayload = computed<any>(() => ({
  name: props.sceneName || 'Current Scene',
  description: props.sceneDescription || 'The current location of your adventure.',
  image_url: props.sceneImage,
  entity_type: 'SCENE'
}))
</script>

<template>
  <div class="mb-8">
    <div class="flex items-center gap-2 mb-4">
      <i class="ra ra-mountain-cave text-indigo-500"></i>
      <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-indigo-500/80">Location</h3>
    </div>
    <div
      class="relative group cursor-help overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 transition-all hover:border-indigo-500/50"
      @mouseenter="emit('hover', hoverPayload, $event)"
      @mousemove="emit('move', $event)"
      @mouseleave="emit('leave')"
    >
      <div class="aspect-video w-full relative overflow-hidden bg-slate-900 flex items-center justify-center">
        <img
          v-if="sceneImage && showImage(sceneImage)"
          :src="getImageUrl(sceneImage)"
          class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
          @error="emit('imageError', sceneImage)"
        />
        <div v-else class="w-full h-full flex items-center justify-center bg-slate-800">
          <i :class="['ra text-7xl opacity-20', getItemIcon('SCENE'), 'text-indigo-400']"></i>
        </div>
        <div class="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-slate-950 to-transparent">
          <div class="flex items-center justify-between gap-2">
            <span class="text-xs font-bold text-white uppercase tracking-wider truncate block overflow-hidden shadow-sm">{{ sceneName || 'Unknown' }}</span>
            <span v-if="isDebug && sceneId" class="text-[10px] font-mono text-indigo-300 opacity-60">ID: {{ sceneId }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

