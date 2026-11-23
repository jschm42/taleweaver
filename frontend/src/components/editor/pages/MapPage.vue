<script setup lang="ts">
/**
 * The adventure's map. From two regions on it opens on the world map; clicking a region shows
 * that region's scene graph (scenes one exit away are shown dimmed as the way out). With only the
 * one region every adventure has, the scene graph shows every scene.
 */
import { computed, ref, watch } from 'vue'
import { ArrowLeft } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { useToast } from '@/composables/useToast'
import { layoutOf, sectionsOf } from '@/services/sectionService'
import ExitRoutePanel from '@/components/editor/ExitRoutePanel.vue'
import MapTab from '@/components/editor/MapTab.vue'
import UiButton from '@/components/ui/UiButton.vue'
import RegionMapCard from '@/components/editor/regions/RegionMapCard.vue'
import { regionLinks, regionSceneIds, sceneCount } from '@/components/editor/regions/regionGraph'
import { sceneRegionMap } from '@/components/editor/regions/regionExits'

// The open region per adventure survives a trip to a scene's editor and back.
const lastRegion = new Map<string, string | null>()

const editor = useEditor()
const toast = useToast()

const sections = computed(() => sectionsOf(editor.debugData?.adventure))
const scenes = computed(() => (editor.editorScenes || []) as { id: string; label?: string; name?: string; section_id?: string | null }[])
const exits = computed(() => editor.debugData?.exits || [])
const regionId = ref<string | null>(lastRegion.get(editor.adventureId) ?? null)
watch(regionId, (value) => lastRegion.set(editor.adventureId, value))

// One region alone needs no world map: the scene graph shows every scene.
const hasRegions = computed(() => sections.value.length > 1)
const counts = computed(() => Object.fromEntries(sections.value.map((s) => [s.id, sceneCount(scenes.value, s.id)])))
const links = computed(() => regionLinks(sections.value, scenes.value, exits.value))
const sceneOptions = computed(() =>
  scenes.value.map((s) => ({ id: s.id, label: s.label || s.name || s.id, sectionId: s.section_id || null })),
)
const regionLabel = computed(() => sections.value.find((s) => s.id === regionId.value)?.label || regionId.value)

const filtered = computed(() => (hasRegions.value && regionId.value ? regionSceneIds(regionId.value, scenes.value, exits.value) : null))
const mapScenes = computed(() => {
  const ids = filtered.value
  if (!ids) return editor.editorScenes
  return scenes.value.filter((s) => ids.inside.has(s.id) || ids.border.has(s.id))
})
const sceneRegions = computed(() => (hasRegions.value ? sceneRegionMap(scenes.value, sections.value) : undefined))
// The open region as MapTab expects it (undefined = none open).
const currentRegionId = computed(() => (hasRegions.value && regionId.value ? regionId.value : undefined))
const dimmedSceneIds = computed(() => [...(filtered.value?.border || [])])
const showWorld = computed(() => hasRegions.value && !regionId.value)

function openRegion(id: string): void {
  const section = sections.value.find((s) => s.id === id)
  if (section && section.status !== 'built' && !counts.value[id]) {
    toast.info(`${section.label} is planned and has no scenes yet. Build it on the Regions page.`)
    return
  }
  regionId.value = id
}
</script>

<template>
  <div class="space-y-6">
    <ExitRoutePanel
      v-if="editor.canShowExitRoutePanel"
      :adventure-id="editor.adventureId"
      :exit-id="editor.activeMapExitId || ''"
      :debug-data="editor.debugData"
      :reference-options="editor.referenceOptions"
      :is-saving="editor.isSaving"
      :is-deleting-route-asset="editor.isDeletingRouteAsset"
      :return-tab-label="editor.getTabLabel(editor.exitEditorReturnTab)"
      @refresh="editor.fetchDebugInfo"
      @request-delete-exit="editor.requestDeleteRouteExit"
      @back="editor.closeExitEditorRoute"
    />

    <template v-else-if="showWorld">
      <RegionMapCard
        mode="navigate"
        :adventure-id="editor.adventureId"
        :sections="sections"
        :links="links"
        :scenes="sceneOptions"
        :scene-counts="counts"
        :layout="layoutOf(editor.debugData?.adventure)"
        description="Click a region to open its scenes. Click a route to set its travel time."
        @open-region="openRegion"
        @refresh="editor.fetchDebugInfo"
      />
    </template>

    <template v-else>
      <div v-if="hasRegions" class="flex flex-wrap items-center gap-3">
        <UiButton variant="secondary" size="sm" :icon="ArrowLeft" @click="regionId = null">World map</UiButton>
        <span class="wb-heading">{{ regionLabel }}</span>
        <span class="wb-hint">Dimmed scenes lie in a neighbouring region; blue dashed exits lead there (hover for details).</span>
      </div>
      <MapTab
        :debug-data="editor.debugData"
        :editor-scenes="mapScenes"
        :visuals-cache-version="editor.visualsCacheVersion"
        :active-scene-id="editor.activeMapSceneId"
        :active-exit-id="editor.activeMapExitId"
        :dimmed-scene-ids="dimmedSceneIds"
        :scene-regions="sceneRegions"
        :current-region-id="currentRegionId"
        @open-scene="editor.openSceneEditorRoute"
        @open-exit="editor.openExitEditorRoute"
      />
    </template>
  </div>
</template>
