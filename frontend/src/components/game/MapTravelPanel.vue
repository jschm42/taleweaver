<script setup lang="ts">
/**
 * MapTravelPanel — the bottom strip of the world map: the regions the player discovered and
 * the unlocked fast travel points. Choosing a point asks for confirmation and emits `travel`;
 * the game view then sends `/fast_travel <scene id>` (docs/specs/world_sections.md, 6.3).
 */
import { computed, ref, watch } from 'vue'
import { api } from '@/composables/useApi'
import { useConfirm } from '@/composables/useDialogs'
import type { MapRegion, MapRegionLink, TravelOptions, TravelPoint } from '@/types'
import PlayerRegionMap from '@/components/game/PlayerRegionMap.vue'

const props = defineProps<{
  open: boolean
  gameId: string
  regions: MapRegion[]
  regionLinks: MapRegionLink[]
  currentRegionId: string | null
}>()

const emit = defineEmits<{ (e: 'travel', sceneId: string): void }>()

const confirm = useConfirm()
const options = ref<TravelOptions | null>(null)
const loading = ref(false)
const failed = ref('')

const regionLabels = computed(() => Object.fromEntries(props.regions.map((r) => [r.id, r.label])))
const points = computed(() => options.value?.points || [])
const visible = computed(() => props.regions.length > 0 || points.value.length > 0)

async function load(): Promise<void> {
  if (!props.gameId) return
  loading.value = true
  failed.value = ''
  try {
    options.value = await api.getTravelOptions(props.gameId)
  } catch (error: unknown) {
    failed.value = error instanceof Error ? error.message : 'Could not load the travel points.'
  } finally {
    loading.value = false
  }
}

watch(() => props.open, (isOpen) => {
  if (isOpen) void load()
}, { immediate: true })

function duration(minutes: number): string {
  if (!minutes) return 'a short walk'
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const mins = minutes % 60
  return [days ? `${days} d` : '', hours ? `${hours} h` : '', mins ? `${mins} min` : ''].filter(Boolean).join(' ')
}

function where(point: TravelPoint): string {
  return point.section_id ? regionLabels.value[point.section_id] || '' : ''
}

async function travel(point: TravelPoint): Promise<void> {
  const companion = point.solo_passage ? ' Your companion cannot follow on this route.' : ''
  const ok = await confirm({
    title: `Travel to ${point.label}?`,
    message: `The journey takes about ${duration(point.minutes)}.${companion}`,
    confirmLabel: 'Travel',
  })
  if (ok) emit('travel', point.scene_id)
}
</script>

<template>
  <div v-if="visible" class="tw-dialog-header shrink-0 px-4 sm:px-8 py-3 space-y-2 border-t max-h-[45%] overflow-y-auto">
    <PlayerRegionMap
      v-if="regions.length > 1"
      :regions="regions"
      :links="regionLinks"
      :current-region-id="currentRegionId"
    />
    <div v-else-if="regions.length" class="flex flex-wrap items-center gap-2 text-xs">
      <span class="tw-muted">Regions:</span>
      <span
        v-for="region in regions"
        :key="region.id"
        class="tw-dialog-chip !opacity-100"
        :class="{ 'ring-1 ring-current': region.id === currentRegionId }"
        :title="region.description"
      >
        {{ region.label }}<span v-if="region.discovery === 'revealed'" class="tw-muted"> (seen)</span>
      </span>
    </div>

    <div v-if="loading" class="tw-muted text-xs">Loading travel points...</div>
    <div v-else-if="failed" class="text-xs text-red-300">{{ failed }}</div>
    <template v-else-if="points.length">
      <p v-if="options?.blocked" class="tw-muted text-xs">{{ options.blocked }}</p>
      <div class="flex flex-wrap gap-2">
        <button
          v-for="point in points"
          :key="point.scene_id"
          type="button"
          class="tw-dialog-chip !opacity-100 flex items-center gap-2 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="!point.available || !!options?.blocked"
          :title="point.available ? `About ${duration(point.minutes)}` : point.reason"
          @click="travel(point)"
        >
          <i class="ra ra-compass" aria-hidden="true"></i>
          <span>{{ point.label }}</span>
          <span v-if="where(point)" class="tw-muted">· {{ where(point) }}</span>
          <span v-if="point.available" class="tw-muted">· {{ duration(point.minutes) }}</span>
          <span v-else class="tw-muted">· {{ point.reason }}</span>
        </button>
      </div>
    </template>
  </div>
</template>
