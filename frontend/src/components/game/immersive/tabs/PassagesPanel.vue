<script setup lang="ts">
/**
 * PassagesPanel — Exits of the current scene as picture tiles: the target scene's image
 * once it was visited, a "?" while it is still unexplored.
 * The image fills the whole tile under a gradient that darkens towards the text. A tile shows
 * the exit's label (it names the passage, e.g. "an old rusty gate"), with "→ Target" below once
 * the target was visited; unexplored targets are not named on the tile. Only locked exits carry a
 * badge. Hovering opens the shared game popup with the label, the target image and what is known.
 */
import { ref } from 'vue'
import { DoorOpen, Lock, ArrowRight } from 'lucide-vue-next'
import { getImageUrl } from '@/utils/game_icons'
import { exitOwnLabel } from '@/utils/exitLabel'

const props = defineProps<{
  sceneExits: any[]
  currentSceneName?: string | null
  isEvaluating?: boolean
  /** Narrow column layout (scene sidebar): small two-per-row tiles, no hint or origin text. */
  compact?: boolean
}>()

const emit = defineEmits<{
  traverseExit: [exit: any]
  /** Hover popup (shared game tooltip): label, target image and what is known. */
  exitHover: [entity: any, event: MouseEvent]
  exitLeave: []
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

/** The exit's label; legacy exits without one read "Passage" until the target is known. */
function tileLabel(exit: any): string {
  return exitOwnLabel(exit.label) || (exit.target_known ? '' : 'Passage')
}

/** The entity the shared hover popup shows: the label as title, the target once it is known. */
function hoverEntity(exit: any) {
  const known = Boolean(exit.target_known)
  return {
    id: exit.id,
    entity_type: 'EXIT',
    name: tileLabel(exit) || targetName(exit) || 'Exit',
    description: known ? `Leads to ${targetName(exit)}.` : 'Where this leads is still unknown.',
    image_url: known ? exit.target_image_url : null,
    is_locked: Boolean(exit.is_locked),
    lock_description: exit.lock_description || '',
  }
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
    <p v-if="!props.compact" class="tw-muted text-xs leading-relaxed">Choose a route to leave this place. Locked passages need a key or a solution first.</p>

    <div class="grid" :class="props.compact ? 'grid-cols-2 gap-2' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3'">
      <button
        v-for="exit in props.sceneExits"
        :key="exit.id || exit.label"
        type="button"
        class="tw-card tw-card--interactive tw-passage group flex flex-col justify-end overflow-hidden text-left"
        :class="{ 'is-locked': exit.is_locked, 'is-compact': props.compact, 'opacity-50 pointer-events-none': props.isEvaluating }"
        :disabled="props.isEvaluating"
        :aria-label="tileLabel(exit) || targetName(exit) || 'Exit'"
        @click="emit('traverseExit', exit)"
        @mouseenter="emit('exitHover', hoverEntity(exit), $event)"
        @mouseleave="emit('exitLeave')"
      >
        <!-- The target scene's image fills the whole tile; a gradient darkens it towards the text. -->
        <span class="tw-passage-media" aria-hidden="true">
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
          <span v-else class="tw-passage-unknown">?</span>
        </span>
        <span class="tw-passage-shade" aria-hidden="true"></span>

        <!-- Only a locked exit carries a badge; open exits need no marker. -->
        <span v-if="exit.is_locked" class="tw-passage-badge is-locked">
          <Lock class="w-3 h-3" />
          Locked
        </span>

        <span class="tw-passage-text flex flex-col gap-0.5 min-w-0" :class="props.compact ? 'px-2 py-1.5' : 'px-3 py-2.5'">
          <!-- The label names the passage; "→ Target" follows only once the target was visited.
               Legacy exits without a label show the target alone, or "Passage" while unexplored. -->
          <span v-if="tileLabel(exit)" class="tw-passage-label block font-bold truncate" :class="props.compact ? 'text-xs' : 'text-sm'">{{ tileLabel(exit) }}</span>
          <span
            v-if="exit.target_known"
            class="flex items-center gap-1 min-w-0"
            :class="tileLabel(exit) ? 'tw-passage-target text-[11px] font-semibold' : ['tw-passage-label font-bold', props.compact ? 'text-xs' : 'text-sm']"
          >
            <ArrowRight class="shrink-0 opacity-80" :class="props.compact ? 'w-3 h-3' : 'w-3.5 h-3.5'" aria-hidden="true" />
            <span class="truncate">{{ targetName(exit) || 'Exit' }}</span>
          </span>
          <span v-if="!exit.target_known" class="sr-only">(unexplored)</span>
        </span>
      </button>
    </div>
  </div>
</template>
