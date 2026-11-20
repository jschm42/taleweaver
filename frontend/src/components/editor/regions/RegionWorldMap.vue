<script setup lang="ts">
/**
 * The world map of the editor: regions at their map position, links between them (solid: an
 * exit connects them, dashed: planned). Regions can be dragged to a new position.
 */
import { computed, ref } from 'vue'
import type { WorldSection } from '@/services/sectionService'
import { formatTravel, type RegionLink } from '@/components/editor/regions/regionGraph'

const props = defineProps<{
  sections: WorldSection[]
  links: RegionLink[]
  selectedId: string | null
  sceneCounts: Record<string, number>
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'move', id: string, x: number, y: number): void
}>()

const board = ref<HTMLDivElement | null>(null)
const dragging = ref<string | null>(null)

const byId = computed(() => new Map(props.sections.map((s) => [s.id, s])))

const lines = computed(() =>
  props.links
    .map((link) => ({ link, a: byId.value.get(link.from), b: byId.value.get(link.to) }))
    .filter((entry): entry is { link: RegionLink; a: WorldSection; b: WorldSection } => Boolean(entry.a && entry.b)),
)

function clamp(value: number): number {
  return Math.round(Math.min(100, Math.max(0, value)) * 10) / 10
}

function startDrag(event: PointerEvent, id: string): void {
  dragging.value = id
  emit('select', id)
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}

function onDrag(event: PointerEvent): void {
  if (!dragging.value || !board.value) return
  const rect = board.value.getBoundingClientRect()
  const x = clamp(((event.clientX - rect.left) / rect.width) * 100)
  const y = clamp(((event.clientY - rect.top) / rect.height) * 100)
  emit('move', dragging.value, x, y)
}

function stopDrag(): void {
  dragging.value = null
}
</script>

<template>
  <div
    ref="board"
    class="relative w-full aspect-[16/9] rounded-xl border border-wb-line bg-wb-sunken overflow-hidden select-none touch-none"
    @pointermove="onDrag"
    @pointerup="stopDrag"
    @pointercancel="stopDrag"
  >
    <svg class="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <line
        v-for="{ link, a, b } in lines"
        :key="`${link.from}-${link.to}`"
        :x1="a.map_x"
        :y1="a.map_y"
        :x2="b.map_x"
        :y2="b.map_y"
        :class="link.planned ? 'stroke-wb-muted' : 'stroke-wb-accent'"
        stroke-width="0.4"
        :stroke-dasharray="link.planned ? '1.5 1' : undefined"
        vector-effect="non-scaling-stroke"
      />
    </svg>
    <span
      v-for="{ link, a, b } in lines.filter((entry) => entry.link.travelMinutes)"
      :key="`t-${link.from}-${link.to}`"
      class="absolute -translate-x-1/2 -translate-y-1/2 wb-hint pointer-events-none"
      :style="{ left: `${(a.map_x + b.map_x) / 2}%`, top: `${(a.map_y + b.map_y) / 2}%` }"
    >{{ formatTravel(link.travelMinutes) }}</span>
    <button
      v-for="section in sections"
      :key="section.id"
      type="button"
      :aria-label="`Region ${section.label}, drag to move`"
      :class="[
        'absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-1 rounded-md px-2 py-1 cursor-grab',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
        selectedId === section.id ? 'bg-wb-accent-soft' : 'hover:bg-wb-raised',
      ]"
      :style="{ left: `${section.map_x}%`, top: `${section.map_y}%` }"
      @pointerdown="startDrag($event, section.id)"
      @click="emit('select', section.id)"
    >
      <span
        :class="[
          'w-3 h-3 rounded-full border-2',
          section.status === 'built' ? 'bg-wb-accent border-wb-accent' : 'bg-wb-surface border-wb-muted border-dashed',
        ]"
      />
      <span class="wb-label text-wb-strong whitespace-nowrap">{{ section.label }}</span>
      <span class="wb-hint whitespace-nowrap">
        {{ section.status === 'built' ? `${sceneCounts[section.id] || 0} scenes` : 'Planned' }}
      </span>
    </button>
  </div>
</template>
