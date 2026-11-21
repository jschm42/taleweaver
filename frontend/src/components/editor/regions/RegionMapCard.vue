<script setup lang="ts">
/**
 * The world map card shared by the Map page (`navigate`: a click opens the region) and the
 * Regions page (`edit`: drag to place, click to select). Connections, travel times and the map
 * image are actions that save at once, so they wait while the Regions page has unsaved edits.
 */
import { computed, ref } from 'vue'
import { Image as ImageIcon, Link2 } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import type { MapLayout } from '@/types'
import { sectionService, type WorldSection } from '@/services/sectionService'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import RegionConnectDialog from '@/components/editor/regions/RegionConnectDialog.vue'
import RegionLinkDialog from '@/components/editor/regions/RegionLinkDialog.vue'
import RegionMapTilesModal from '@/components/editor/regions/RegionMapTilesModal.vue'
import RegionWorldMap from '@/components/editor/regions/RegionWorldMap.vue'
import type { RegionLink } from '@/components/editor/regions/regionGraph'

interface SceneOption {
  id: string
  label: string
  sectionId: string | null
}

const props = withDefaults(
  defineProps<{
    adventureId: string
    sections: WorldSection[]
    links: RegionLink[]
    scenes: SceneOption[]
    sceneCounts: Record<string, number>
    layout: MapLayout | null
    mode: 'edit' | 'navigate'
    selectedId?: string | null
    /** Unsaved region edits: immediate actions must wait. */
    blocked?: boolean
    description?: string
  }>(),
  { selectedId: null, blocked: false, description: '' },
)

const emit = defineEmits<{
  (e: 'open-region', id: string): void
  (e: 'move', id: string, x: number, y: number): void
  (e: 'refresh'): void
}>()

const toast = useToast()
const connecting = ref(false)
const connectFrom = ref<string | null>(null)
const connectTo = ref<string | null>(null)
const connectOpen = ref(false)
const activeLink = ref<RegionLink | null>(null)
const linkOpen = ref(false)
const imageOpen = ref(false)

const byId = computed(() => new Map(props.sections.map((s) => [s.id, s])))
const sceneLabels = computed(() => Object.fromEntries(props.scenes.map((s) => [s.id, s.label])))

function guard(): boolean {
  if (props.blocked) toast.warn('Save the regions first.')
  return !props.blocked
}

function toggleConnect(): void {
  if (!connecting.value && !guard()) return
  connecting.value = !connecting.value
  connectFrom.value = null
}

function regionClick(id: string): void {
  if (!connecting.value) {
    emit('open-region', id)
    return
  }
  if (!connectFrom.value) {
    connectFrom.value = id
    return
  }
  if (connectFrom.value === id) return
  connectTo.value = id
  connectOpen.value = true
  connecting.value = false
}

function openLink(link: RegionLink): void {
  if (!guard()) return
  activeLink.value = link
  linkOpen.value = true
}

/** Rewrites the planned links of the saved region list and stores it. */
async function savePlannedLinks(change: (sections: WorldSection[]) => void): Promise<void> {
  const sections: WorldSection[] = JSON.parse(JSON.stringify(props.sections))
  change(sections)
  try {
    await sectionService.saveSections(props.adventureId, sections)
    emit('refresh')
  } catch (error: unknown) {
    toast.error(error instanceof Error ? error.message : 'Failed to save the route.')
  }
}

function planRoute(minutes: number | null): void {
  const a = byId.value.get(connectFrom.value || '')
  const b = byId.value.get(connectTo.value || '')
  if (!a || !b) return
  // The planned region holds the route.
  const [owner, target] = a.status === 'built' ? [b, a] : [a, b]
  void savePlannedLinks((sections) => {
    const entry = sections.find((s) => s.id === owner.id)
    if (!entry) return
    entry.planned_links = [...entry.planned_links.filter((l) => l.to_section_id !== target.id), { to_section_id: target.id, travel_minutes: minutes, note: '' }]
  })
}

function updatePlanned(minutes: number | null, remove = false): void {
  const link = activeLink.value
  if (!link) return
  void savePlannedLinks((sections) => {
    for (const section of sections) {
      const ends = [section.id === link.from ? link.to : null, section.id === link.to ? link.from : null]
      section.planned_links = section.planned_links
        .filter((l) => !(remove && ends.includes(l.to_section_id)))
        .map((l) => (ends.includes(l.to_section_id) ? { ...l, travel_minutes: minutes } : l))
    }
  })
}
</script>

<template>
  <UiCard title="World map" :description="description">
    <template #actions>
      <UiButton size="sm" :variant="connecting ? 'primary' : 'secondary'" :icon="Link2" @click="toggleConnect">
        {{ connecting ? (connectFrom ? 'Now click the second region' : 'Click the first region') : 'Connect regions' }}
      </UiButton>
      <UiButton size="sm" :icon="ImageIcon" @click="guard() && (imageOpen = true)">Map images</UiButton>
    </template>
    <RegionWorldMap
      :sections="sections"
      :links="links"
      :selected-id="selectedId"
      :scene-counts="sceneCounts"
      :layout="layout"
      :mode="mode"
      :connect-from="connecting ? connectFrom || '' : null"
      @region-click="regionClick"
      @link-click="openLink"
      @move="(id, x, y) => emit('move', id, x, y)"
    />
    <RegionConnectDialog
      v-model:open="connectOpen"
      :adventure-id="adventureId"
      :from="byId.get(connectFrom || '') || null"
      :to="byId.get(connectTo || '') || null"
      :scenes="scenes"
      @saved="emit('refresh')"
      @plan="planRoute"
    />
    <RegionLinkDialog
      v-model:open="linkOpen"
      :adventure-id="adventureId"
      :link="activeLink"
      :sections="sections"
      :scene-labels="sceneLabels"
      @saved="emit('refresh')"
      @save-planned="(minutes) => updatePlanned(minutes)"
      @remove-planned="updatePlanned(null, true)"
    />
    <RegionMapTilesModal v-model:open="imageOpen" :adventure-id="adventureId" :layout="layout" @changed="emit('refresh')" />
  </UiCard>
</template>
