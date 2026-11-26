<script setup lang="ts">
/**
 * The scenes of one region as image tiles on the Regions page; a click opens the scene's
 * detail page. Thumbnails fall back to the original image, then to an icon.
 */
import { reactive } from 'vue'
import { MapPin } from 'lucide-vue-next'
import { getImageUrl, getOriginalImageUrl, hasRenderableImagePath } from '@/utils/game_icons'

export interface RegionSceneTile {
  id: string
  label: string
  imageUrl?: string | null
}

defineProps<{ scenes: RegionSceneTile[] }>()

const emit = defineEmits<{ (e: 'open-scene', id: string): void }>()

// Per scene: 'original' after the thumbnail failed, 'none' after the original failed too.
const fallback = reactive<Record<string, 'original' | 'none'>>({})

function imageSrc(scene: RegionSceneTile): string {
  if (!hasRenderableImagePath(scene.imageUrl) || fallback[scene.id] === 'none') return ''
  if (fallback[scene.id] === 'original') return getOriginalImageUrl(scene.imageUrl) || ''
  return getImageUrl(scene.imageUrl, { thumbnail: true })
}

function onImageError(scene: RegionSceneTile): void {
  fallback[scene.id] = fallback[scene.id] === 'original' ? 'none' : 'original'
}
</script>

<template>
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
    <button
      v-for="scene in scenes"
      :key="scene.id"
      type="button"
      class="group overflow-hidden rounded-xl border border-wb-line bg-wb-raised text-left transition-colors hover:border-wb-line-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
      @click="emit('open-scene', scene.id)"
    >
      <div class="flex aspect-[3/2] items-center justify-center bg-wb-sunken">
        <img
          v-if="imageSrc(scene)"
          :src="imageSrc(scene)"
          :alt="scene.label"
          loading="lazy"
          class="h-full w-full object-cover"
          @error="onImageError(scene)"
        />
        <MapPin v-else class="h-6 w-6 text-wb-faint" aria-hidden="true" />
      </div>
      <p class="wb-body truncate px-3 py-2 text-wb-strong">{{ scene.label }}</p>
    </button>
  </div>
</template>
