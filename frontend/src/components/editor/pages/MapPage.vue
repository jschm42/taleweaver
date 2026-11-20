<script setup lang="ts">
import { computed, ref } from 'vue'
import { useEditor } from '@/composables/editor/editorContext'
import { sectionsOf } from '@/services/sectionService'
import ExitRoutePanel from '@/components/editor/ExitRoutePanel.vue'
import MapTab from '@/components/editor/MapTab.vue'
import UiField from '@/components/ui/UiField.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { UNASSIGNED, regionSceneIds } from '@/components/editor/regions/regionGraph'

const editor = useEditor()

// Region filter: large worlds show one region at a time plus the scenes one exit away.
const regionFilter = ref('')
const sections = computed(() => sectionsOf(editor.debugData?.adventure).filter((s) => s.status === 'built'))
const regionOptions = computed(() => [
  { value: '', label: 'All scenes' },
  ...sections.value.map((s) => ({ value: s.id, label: s.label })),
  { value: UNASSIGNED, label: 'No region' },
])
const filtered = computed(() => regionSceneIds(regionFilter.value, editor.editorScenes || [], editor.debugData?.exits || []))
const mapScenes = computed(() => {
  const ids = filtered.value
  if (!ids) return editor.editorScenes
  return (editor.editorScenes || []).filter((s: { id: string }) => ids.inside.has(s.id) || ids.border.has(s.id))
})
const dimmedSceneIds = computed(() => [...(filtered.value?.border || [])])
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

    <template v-if="!editor.canShowExitRoutePanel">
      <UiField v-if="sections.length" label="Region" hint="Shows one region; dimmed scenes lie in a neighbouring region." class="max-w-sm">
        <UiSelect v-model="regionFilter" :options="regionOptions" />
      </UiField>
      <MapTab
        :debug-data="editor.debugData"
        :editor-scenes="mapScenes"
        :visuals-cache-version="editor.visualsCacheVersion"
        :active-scene-id="editor.activeMapSceneId"
        :active-exit-id="editor.activeMapExitId"
        :dimmed-scene-ids="dimmedSceneIds"
        @open-scene="editor.openSceneEditorRoute"
        @open-exit="editor.openExitEditorRoute"
      />
    </template>
  </div>
</template>
