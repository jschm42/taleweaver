<script setup lang="ts">
/**
 * PassagesPanel — Exits of the current scene as picture tiles: the target scene's image
 * once it was visited, a "?" while it is still unexplored.
 */
import { ref } from 'vue'
import { DoorOpen, Lock, ArrowRight } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  sceneExits: any[]
  currentSceneName?: string | null
  isEvaluating?: boolean
}>()

const emit = defineEmits<{
  traverseExit: [exit: any]
}>()

/** Image fallbacks per scene image URL: thumbnail → full image → no image. */
const imageFallbacks = ref(new Map<string, 'full' | 'broken'>())

function formatSceneTitle(name?: string | null): string {
  if (!name) return ''
  const trimmed = String(name).trim()
  if (trimmed.includes('_') || trimmed.includes('-') || /^[A-Z0-9\s_-]+$/.test(trimmed)) {
    return trimmed
      .replace(/[_-]+/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }
  return trimmed
}

function targetName(exit: any): string {
  return exit.target_scene_name || formatSceneTitle(exit.target_scene_id)
}

function targetImage(exit: any): string | null {
  const url = exit.target_known ? exit.target_image_url : null
  if (!url) return null
  const fallback = imageFallbacks.value.get(url)
  if (fallback === 'broken') return null
  return getImageUrl(url, { thumbnail: fallback !== 'full' }) || null
}

function onImageError(exit: any) {
  const url = exit.target_image_url
  const next = imageFallbacks.value.get(url) === 'full' ? 'broken' : 'full'
  imageFallbacks.value = new Map(imageFallbacks.value).set(url, next)
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="flex items-center justify-between">
      <h3 class="tw-panel-title">Passages & Exits</h3>
      <span class="tw-muted text-[11px] font-bold">
        {{ props.sceneExits.length }} {{ props.sceneExits.length === 1 ? 'route' : 'routes' }}
      </span>
    </div>
    <p class="tw-muted text-xs leading-relaxed">Choose a route to leave this place. Locked passages need a key or a solution first.</p>

    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      <button
        v-for="exit in props.sceneExits"
        :key="exit.id || exit.label"
        type="button"
        class="tw-card tw-card--interactive tw-passage group flex flex-col overflow-hidden text-left"
        :class="{ 'is-locked': exit.is_locked, 'opacity-50 pointer-events-none': props.isEvaluating }"
        :disabled="props.isEvaluating"
        :title="exit.target_known ? targetName(exit) : 'Unexplored'"
        @click="emit('traverseExit', exit)"
      >
        <span class="tw-passage-media">
          <img
            v-if="targetImage(exit)"
            :src="targetImage(exit)!"
            :alt="targetName(exit)"
            class="tw-passage-image"
            loading="lazy"
            @error="onImageError(exit)"
          />
          <span v-else-if="exit.target_known" class="tw-passage-unknown">
            <DoorOpen class="w-8 h-8" />
          </span>
          <span v-else class="tw-passage-unknown" aria-label="Unexplored">?</span>

          <span class="tw-passage-badge" :class="exit.is_locked ? 'is-locked' : 'is-open'">
            <Lock v-if="exit.is_locked" class="w-3 h-3" />
            <DoorOpen v-else class="w-3 h-3" />
            {{ exit.is_locked ? 'Locked' : 'Open' }}
          </span>
        </span>

        <span class="flex flex-col gap-0.5 min-w-0 px-3 py-2.5">
          <span class="tw-passage-label block text-sm font-bold truncate">{{ exit.label || 'Exit' }}</span>
          <span v-if="exit.target_scene_name || exit.target_scene_id" class="tw-muted flex items-center gap-1 text-[11px] min-w-0">
            <span class="truncate">{{ props.currentSceneName || 'Here' }}</span>
            <ArrowRight class="w-3 h-3 shrink-0" />
            <span class="truncate font-semibold">{{ targetName(exit) }}</span>
          </span>
        </span>
      </button>
    </div>
  </div>
</template>
