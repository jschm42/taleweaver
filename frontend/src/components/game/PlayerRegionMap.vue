<script setup lang="ts">
/**
 * PlayerRegionMap — the world map of the play view: the regions the player discovered at their
 * map position over the map tiles and the known routes between them. A click on a region opens
 * its scenes; the current region is highlighted, regions only seen behind a revealed exit are
 * drawn faint. Wheel or buttons zoom, dragging the background pans.
 * Data: GET /map (sections, section_links, current_section_id, world_map_layout).
 */
import { computed } from 'vue'
import { Maximize2, ZoomIn, ZoomOut } from 'lucide-vue-next'
import type { MapLayout, MapRegion, MapRegionLink } from '@/types'
import WorldMapViewport from '@/components/worldmap/WorldMapViewport.vue'

const props = defineProps<{
  regions: MapRegion[]
  links: MapRegionLink[]
  currentRegionId: string | null
  layout?: MapLayout | null
}>()

const emit = defineEmits<{ (e: 'open', regionId: string): void }>()

const byId = computed(() => new Map(props.regions.map((region) => [region.id, region])))

const lines = computed(() =>
  props.links
    .map((link) => ({ link, a: byId.value.get(link.from), b: byId.value.get(link.to) }))
    .filter((entry): entry is { link: MapRegionLink; a: MapRegion; b: MapRegion } => Boolean(entry.a && entry.b)),
)

/** Markers keep their size on screen at every zoom. */
function counterScale(zoom: number): Record<string, string> {
  return { transform: `translate(-50%, -50%) scale(${1 / zoom})` }
}

const controls = [
  { icon: ZoomIn, label: 'Zoom in', key: 'zoomIn' },
  { icon: ZoomOut, label: 'Zoom out', key: 'zoomOut' },
  { icon: Maximize2, label: 'Show the whole map', key: 'fit' },
] as const
</script>

<template>
  <div class="relative w-full h-full min-h-[16rem] rounded-xl border border-white/10 bg-black/30 overflow-hidden">
    <WorldMapViewport :layout="layout">
      <template #default="{ zoom }">
        <svg class="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <template v-for="{ link, a, b } in lines" :key="`${link.from}-${link.to}`">
            <!-- Dark casing under a light line: visible on any map image. -->
            <line :x1="a.map_x" :y1="a.map_y" :x2="b.map_x" :y2="b.map_y" stroke="rgba(0,0,0,0.75)" stroke-width="7" stroke-linecap="round" vector-effect="non-scaling-stroke" />
            <line
              :x1="a.map_x"
              :y1="a.map_y"
              :x2="b.map_x"
              :y2="b.map_y"
              stroke="rgba(255,236,190,0.95)"
              stroke-width="3"
              stroke-linecap="round"
              :stroke-dasharray="link.is_locked ? '6 6' : undefined"
              vector-effect="non-scaling-stroke"
            />
          </template>
        </svg>
        <button
          v-for="region in regions"
          :key="region.id"
          type="button"
          class="absolute flex flex-col items-center gap-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300 rounded-md cursor-pointer"
          :class="{ 'opacity-60': region.discovery === 'revealed' }"
          :style="{ left: `${region.map_x}%`, top: `${region.map_y}%`, ...counterScale(zoom) }"
          :aria-label="`Open region ${region.label}`"
          @click="emit('open', region.id)"
        >
          <span
            class="w-4 h-4 rounded-full border-2 border-black/80"
            :class="region.id === currentRegionId ? 'bg-amber-300 ring-2 ring-amber-200/70' : 'bg-white/80'"
          />
          <!-- Solid dark chip: the name stays readable on any map image. -->
          <span
            class="rounded-md border px-2 py-0.5 whitespace-nowrap bg-black/75 shadow-lg"
            :class="region.id === currentRegionId ? 'border-amber-300/70 text-amber-100 font-semibold' : 'border-white/20 text-white/90'"
            :title="region.description"
          >
            {{ region.label }}
          </span>
        </button>
      </template>
      <template #controls="slot">
        <div class="absolute right-2 top-2 flex gap-1 rounded-md border border-white/15 bg-black/70 p-1">
          <button
            v-for="control in controls"
            :key="control.key"
            type="button"
            class="p-1.5 rounded text-white/85 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
            :aria-label="control.label"
            :title="control.label"
            @click="slot[control.key]()"
          >
            <component :is="control.icon" class="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      </template>
    </WorldMapViewport>
  </div>
</template>
