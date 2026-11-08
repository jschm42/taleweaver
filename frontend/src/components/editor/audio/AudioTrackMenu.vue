<script setup lang="ts">
/**
 * AudioTrackMenu — context menu of one library track, opened from its "⋮" button or a right
 * click on the row. Teleported and fixed, so the table's scroll container cannot clip it.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import type { AudioTrack } from '@/services/editorAudioService'

export type TrackAction = 'play' | 'edit' | 'render' | 'variant' | 'title' | 'download' | 'delete'

const props = defineProps<{
  track: AudioTrack
  x: number
  y: number
  isPlaying: boolean
  isRendering: boolean
  generationOn: boolean
  isTitle: boolean
}>()

const emit = defineEmits<{
  (e: 'action', action: TrackAction): void
  (e: 'close'): void
}>()

const MENU_WIDTH = 208
const menu = ref<HTMLElement | null>(null)
const position = ref({ left: props.x, top: props.y })

const items = computed(() => [
  { action: 'play' as const, label: props.isPlaying ? 'Stop' : 'Play', show: !!props.track.url, tone: 'hover:bg-orange-500' },
  { action: 'edit' as const, label: 'Rename / Edit Prompt', show: true, tone: 'hover:bg-blue-500' },
  {
    action: 'render' as const,
    label: props.track.url ? 'Render Again' : 'Render from Prompt',
    show: !!props.track.prompt,
    disabled: !props.generationOn || props.isRendering,
    tone: 'hover:bg-orange-500',
  },
  { action: 'variant' as const, label: 'Generate Variant…', show: true, disabled: !props.generationOn, tone: 'hover:bg-cyan-500' },
  {
    action: 'title' as const,
    label: props.isTitle ? 'Remove as Title Track' : 'Set as Title Track',
    show: true,
    tone: 'hover:bg-amber-500',
  },
  { action: 'download' as const, label: 'Download', show: !!props.track.url, tone: 'hover:bg-violet-500' },
  { action: 'delete' as const, label: 'Delete', show: true, tone: 'hover:bg-red-500' },
])

function pick(action: TrackAction): void {
  emit('action', action)
  emit('close')
}

function onDocumentDown(event: MouseEvent): void {
  if (menu.value && !menu.value.contains(event.target as Node)) emit('close')
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}

onMounted(async () => {
  document.addEventListener('mousedown', onDocumentDown)
  document.addEventListener('keydown', onKey)
  window.addEventListener('scroll', closeOnScroll, true)
  await nextTick()
  // Keep the menu inside the viewport.
  const height = menu.value?.offsetHeight ?? 0
  position.value = {
    left: Math.min(props.x, window.innerWidth - MENU_WIDTH - 8),
    top: props.y + height > window.innerHeight - 8 ? Math.max(8, props.y - height) : props.y,
  }
})

function closeOnScroll(): void {
  emit('close')
}

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentDown)
  document.removeEventListener('keydown', onKey)
  window.removeEventListener('scroll', closeOnScroll, true)
})
</script>

<template>
  <Teleport to="body">
    <div
      ref="menu"
      role="menu"
      class="fixed z-[210] w-52 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 ring-1 ring-white/5"
      :style="{ left: `${position.left}px`, top: `${position.top}px` }"
    >
      <template v-for="item in items" :key="item.action">
        <button
          v-if="item.show"
          type="button"
          role="menuitem"
          :disabled="item.disabled"
          class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:text-white transition-all disabled:opacity-40 disabled:hover:bg-transparent"
          :class="item.tone"
          @click="pick(item.action)"
        >
          {{ item.label }}
        </button>
      </template>
    </div>
  </Teleport>
</template>
