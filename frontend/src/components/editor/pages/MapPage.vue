<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import ExitRoutePanel from '@/components/editor/ExitRoutePanel.vue'
import MapTab from '@/components/editor/MapTab.vue'

const editor = useEditor()
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

    <MapTab
      v-if="!editor.canShowExitRoutePanel"
      :debug-data="editor.debugData"
      :editor-scenes="editor.editorScenes"
      :visuals-cache-version="editor.visualsCacheVersion"
      :active-scene-id="editor.activeMapSceneId"
      :active-exit-id="editor.activeMapExitId"
      @open-scene="editor.openSceneEditorRoute"
      @open-exit="editor.openExitEditorRoute"
    />
  </div>
</template>
