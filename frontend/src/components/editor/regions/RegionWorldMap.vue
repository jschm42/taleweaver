<script setup lang="ts">
/**
 * The world map of the editor: regions at their map position over the map tiles, and the
 * links between them (solid: exits connect them, dashed: planned). Each link has a chip with
 * its travel time that opens it. Zoom with the wheel or the buttons, drag the background to
 * pan. In `edit` mode regions can be dragged; in `navigate` mode a click opens the region.
 * While `connectFrom` is not null, the next region click completes a new connection.
 */
import { computed, ref } from 'vue'
import { Maximize2, ZoomIn, ZoomOut } from 'lucide-vue-next'
import type { MapLayout } from '@/types'
import type { WorldSection } from '@/services/sectionService'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import WorldMapViewport from '@/components/worldmap/WorldMapViewport.vue'
import { formatTravel, type RegionLink } from '@/components/editor/regions/regionGraph'

const props = withDefaults(
  defineProps<{
    sections: WorldSection[]
    links: RegionLink[]
    selectedId: string | null
    sceneCounts: Record<string, number>
    layout?: MapLayout | null
    mode?: 'edit' | 'navigate'
    connectFrom?: string | null
  }>(),
  { layout: null, mode: 'edit', connectFrom: null },
)

const emit = defineEmits<{
  (e: 'region-click', id: string): void
  (e: 'link-click', link: RegionLink): void
  (e: 'move', id: string, x: number, y: number): void
}>()

const dragging = ref<{ id: string; canvas: HTMLElement } | null>(null)
const moved = ref(false)

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
  moved.value = false
  if (props.mode !== 'edit' || props.connectFrom !== null) return
  const canvas = (event.currentTarget as HTMLElement).closest('[data-world-canvas]') as HTMLElement | null
  if (!canvas) return
  dragging.value = { id, canvas }
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}

function onDrag(event: PointerEvent): void {
  if (!dragging.value) return
  // The canvas rect already includes zoom and pan, so percent of it is percent of the map.
  const rect = dragging.value.canvas.getBoundingClientRect()
  moved.value = true
  emit('move', dragging.value.id, clamp(((event.clientX - rect.left) / rect.width) * 100), clamp(((event.clientY - rect.top) / rect.height) * 100))
}

function stopDrag(): void {
  dragging.value = null
}

function click(id: string): void {
  if (!moved.value) emit('region-click', id)
  moved.value = false
}

function linkText(link: RegionLink): string {
  return formatTravel(link.travelMinutes) || 'no time'
}

/** Markers keep their size on screen at every zoom. */
function counterScale(zoom: number): Record<string, string> {
  return { transform: `translate(-50%, -50%) scale(${1 / zoom})` }
}
</script>

<template>
  <div class="relative w-full aspect-[16/9] rounded-xl border border-wb-line bg-wb-sunken overflow-hidden">
    <WorldMapViewport :layout="layout">
      <template #default="{ zoom }">
        <svg class="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <template v-for="{ link, a, b } in lines" :key="`${link.from}-${link.to}`">
            <!-- Dark casing first, so the line stays visible on any map image. -->
            <line :x1="a.map_x" :y1="a.map_y" :x2="b.map_x" :y2="b.map_y" class="stroke-wb-canvas" stroke-width="6" stroke-linecap="round" vector-effect="non-scaling-stroke" />
            <line
              :x1="a.map_x"
              :y1="a.map_y"
              :x2="b.map_x"
              :y2="b.map_y"
              :class="link.planned ? 'stroke-wb-muted' : 'stroke-wb-accent'"
              stroke-width="3"
              stroke-linecap="round"
              :stroke-dasharray="link.planned ? '6 5' : undefined"
              vector-effect="non-scaling-stroke"
            />
          </template>
        </svg>
        <button
          v-for="{ link, a, b } in lines"
          :key="`t-${link.from}-${link.to}`"
          type="button"
          :aria-label="`Route ${a.label} to ${b.label}: ${linkText(link)}`"
          class="absolute rounded-md border border-wb-line-strong bg-wb-surface px-1.5 py-0.5 wb-hint text-wb-strong whitespace-nowrap hover:bg-wb-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent"
          :style="{ left: `${(a.map_x + b.map_x) / 2}%`, top: `${(a.map_y + b.map_y) / 2}%`, ...counterScale(zoom) }"
          @click="emit('link-click', link)"
        >
          {{ linkText(link) }}
        </button>
        <button
          v-for="section in sections"
          :key="section.id"
          type="button"
          :aria-label="mode === 'navigate' ? `Open region ${section.label}` : `Region ${section.label}, drag to move`"
          :class="[
            'absolute flex flex-col items-center gap-1 rounded-md px-2 py-1',
            mode === 'edit' && connectFrom === null ? 'cursor-grab' : 'cursor-pointer',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
          ]"
          :style="{ left: `${section.map_x}%`, top: `${section.map_y}%`, ...counterScale(zoom) }"
          @pointerdown="startDrag($event, section.id)"
          @pointermove="onDrag"
          @pointerup="stopDrag"
          @pointercancel="stopDrag"
          @click="click(section.id)"
        >
          <span
            :class="[
              'w-4 h-4 rounded-full border-2 border-wb-canvas',
              section.status === 'built' ? 'bg-wb-accent' : 'bg-wb-muted',
              (connectFrom && connectFrom === section.id) || selectedId === section.id ? 'ring-2 ring-wb-accent ring-offset-2 ring-offset-wb-canvas' : '',
            ]"
          />
          <!-- Solid chip: the name stays readable on any map image. -->
          <span class="rounded-md border border-wb-line-strong bg-wb-surface px-2 py-0.5 text-center">
            <span class="wb-label text-wb-strong whitespace-nowrap block">{{ section.label }}</span>
            <span class="wb-hint whitespace-nowrap block">
              {{ section.status === 'built' ? `${sceneCounts[section.id] || 0} scenes` : 'Planned' }}
            </span>
          </span>
        </button>
      </template>
      <template #controls="{ zoomIn, zoomOut, fit }">
        <div class="absolute right-2 top-2 flex gap-1 rounded-md border border-wb-line bg-wb-surface p-1">
          <UiIconButton :icon="ZoomIn" label="Zoom in" size="sm" @click="zoomIn" />
          <UiIconButton :icon="ZoomOut" label="Zoom out" size="sm" @click="zoomOut" />
          <UiIconButton :icon="Maximize2" label="Show the whole map" size="sm" @click="fit" />
        </div>
      </template>
    </WorldMapViewport>
  </div>
</template>
