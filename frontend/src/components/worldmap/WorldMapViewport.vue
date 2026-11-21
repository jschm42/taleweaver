<script setup lang="ts">
/**
 * WorldMapViewport — the zoomable, pannable world map canvas shared by the editor's and the
 * players' world map. It draws the map tiles (AdventureTemplate.world_map_layout: a grid of
 * 16:9 images) and places the slotted content (routes, region markers) in percent of the
 * whole map. Mouse wheel zooms towards the cursor, dragging the background pans; the
 * consumer renders its own controls with the slot props (`zoom`, `zoomIn`, `zoomOut`, `fit`).
 * Styling is neutral so both the Workbench and the play-view skins can use it.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { MapLayout } from '@/types'
import { getImageUrl } from '@/utils/game_icons'

const props = defineProps<{ layout?: MapLayout | null }>()

const MIN_ZOOM = 0.2
const MAX_ZOOM = 6

const viewport = ref<HTMLDivElement | null>(null)
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const panning = ref<{ x: number; y: number } | null>(null)

const cols = computed(() => Math.max(1, props.layout?.cols || 1))
const rows = computed(() => Math.max(1, props.layout?.rows || 1))
const tiles = computed(() => props.layout?.tiles || [])

/** Zoom at which the whole map fits into the viewport. */
function fitZoom(): number {
  const el = viewport.value
  if (!el || !el.clientWidth) return 1
  const canvasHeight = el.clientWidth * (rows.value * 9) / (cols.value * 16)
  return Math.min(1, el.clientHeight / canvasHeight)
}

function fit(): void {
  zoom.value = fitZoom()
  const el = viewport.value
  if (!el) return
  const canvasHeight = el.clientWidth * (rows.value * 9) / (cols.value * 16) * zoom.value
  offset.value = { x: (el.clientWidth * (1 - zoom.value)) / 2, y: Math.max(0, (el.clientHeight - canvasHeight) / 2) }
}

function zoomAt(next: number, clientX?: number, clientY?: number): void {
  const el = viewport.value
  const clamped = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next))
  if (!el) {
    zoom.value = clamped
    return
  }
  const rect = el.getBoundingClientRect()
  const px = (clientX ?? rect.left + rect.width / 2) - rect.left
  const py = (clientY ?? rect.top + rect.height / 2) - rect.top
  const ratio = clamped / zoom.value
  offset.value = { x: px - (px - offset.value.x) * ratio, y: py - (py - offset.value.y) * ratio }
  zoom.value = clamped
}

const zoomIn = (): void => zoomAt(zoom.value * 1.25)
const zoomOut = (): void => zoomAt(zoom.value / 1.25)

function onWheel(event: WheelEvent): void {
  event.preventDefault()
  zoomAt(zoom.value * (event.deltaY < 0 ? 1.12 : 1 / 1.12), event.clientX, event.clientY)
}

function onPointerDown(event: PointerEvent): void {
  // Markers and route chips are buttons: they handle their own clicks and drags.
  if ((event.target as HTMLElement).closest('button')) return
  panning.value = { x: event.clientX - offset.value.x, y: event.clientY - offset.value.y }
  viewport.value?.setPointerCapture(event.pointerId)
}

function onPointerMove(event: PointerEvent): void {
  if (!panning.value) return
  offset.value = { x: event.clientX - panning.value.x, y: event.clientY - panning.value.y }
}

function stopPan(): void {
  panning.value = null
}

let resizeObserver: ResizeObserver | null = null
onMounted(() => {
  void nextTick(fit)
  if (viewport.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => fit())
    resizeObserver.observe(viewport.value)
  }
})
onBeforeUnmount(() => resizeObserver?.disconnect())
watch(() => [cols.value, rows.value], () => void nextTick(fit))

const canvasStyle = computed(() => ({
  aspectRatio: `${cols.value * 16} / ${rows.value * 9}`,
  transform: `translate(${offset.value.x}px, ${offset.value.y}px) scale(${zoom.value})`,
}))

function tileStyle(col: number, row: number): Record<string, string> {
  return {
    left: `${(col / cols.value) * 100}%`,
    top: `${(row / rows.value) * 100}%`,
    width: `${100 / cols.value}%`,
    height: `${100 / rows.value}%`,
  }
}
</script>

<template>
  <div
    ref="viewport"
    class="relative w-full h-full overflow-hidden select-none touch-none"
    :class="panning ? 'cursor-grabbing' : 'cursor-grab'"
    @wheel="onWheel"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="stopPan"
    @pointercancel="stopPan"
  >
    <div class="absolute left-0 top-0 w-full origin-top-left" :style="canvasStyle" data-world-canvas>
      <img
        v-for="tile in tiles"
        :key="`${tile.col}-${tile.row}`"
        :src="getImageUrl(tile.url) || tile.url"
        alt=""
        draggable="false"
        class="absolute object-cover pointer-events-none"
        :style="tileStyle(tile.col, tile.row)"
      />
      <slot :zoom="zoom" />
    </div>
    <slot name="controls" :zoom="zoom" :zoom-in="zoomIn" :zoom-out="zoomOut" :fit="fit" />
  </div>
</template>
