<script setup lang="ts">
/**
 * PlayerRegionMap — the world map of the play view: the regions the player discovered at their
 * map position and the known routes between them; the current region is highlighted.
 * Regions only seen behind a revealed exit are drawn faint. Data: GET /map (sections,
 * section_links, current_section_id).
 */
import { computed } from 'vue'
import type { MapRegion, MapRegionLink } from '@/types'

const props = defineProps<{
  regions: MapRegion[]
  links: MapRegionLink[]
  currentRegionId: string | null
}>()

const byId = computed(() => new Map(props.regions.map((region) => [region.id, region])))

const lines = computed(() =>
  props.links
    .map((link) => ({ link, a: byId.value.get(link.from), b: byId.value.get(link.to) }))
    .filter((entry): entry is { link: MapRegionLink; a: MapRegion; b: MapRegion } => Boolean(entry.a && entry.b)),
)
</script>

<template>
  <div class="relative w-full aspect-[16/6] min-h-[8rem] rounded-xl border border-white/10 bg-black/30 overflow-hidden" role="img" :aria-label="`World map with ${regions.length} known regions`">
    <svg class="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <line
        v-for="{ link, a, b } in lines"
        :key="`${link.from}-${link.to}`"
        :x1="a.map_x"
        :y1="a.map_y"
        :x2="b.map_x"
        :y2="b.map_y"
        stroke="currentColor"
        class="tw-muted"
        stroke-width="0.5"
        :stroke-dasharray="link.is_locked ? '1.5 1' : undefined"
        vector-effect="non-scaling-stroke"
      />
    </svg>
    <div
      v-for="region in regions"
      :key="region.id"
      class="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center gap-1 text-xs"
      :class="{ 'opacity-50': region.discovery === 'revealed' }"
      :style="{ left: `${region.map_x}%`, top: `${region.map_y}%` }"
      :title="region.description"
    >
      <span
        class="w-3 h-3 rounded-full border-2"
        :class="region.id === currentRegionId ? 'bg-amber-300 border-amber-200 shadow shadow-amber-300/50' : 'bg-white/20 border-white/50'"
      />
      <span class="whitespace-nowrap" :class="region.id === currentRegionId ? 'font-semibold' : 'tw-muted'">{{ region.label }}</span>
    </div>
  </div>
</template>
