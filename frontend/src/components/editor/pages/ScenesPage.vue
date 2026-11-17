<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import ScenesTab from '@/components/editor/ScenesTab.vue'
import CreateSceneForm from '@/components/editor/CreateSceneForm.vue'
import SceneRoutePanel from '@/components/editor/SceneRoutePanel.vue'

const editor = useEditor()
</script>

<template>
  <div class="space-y-6">
    <ScenesTab
      v-if="!editor.canShowSceneRoutePanel && !editor.isCreatingScene"
      :editor-scenes="editor.editorScenes"
      :debug-data="editor.debugData"
      :adventure-id="editor.adventureId"
      :is-batch-generating="editor.isBatchGenerating"
      :is-quick-generating="editor.isQuickGenerating"
      :active-menu-id="editor.activeMenuId"
      :visuals-cache-version="editor.visualsCacheVersion"
      :is-setting-start-scene="editor.isSettingStartScene"
      :adventure-scripts="editor.adventure?.scripts || editor.debugData?.adventure?.scripts || []"
      @quick-regen="editor.quickRegenerateVisual"
      @regen-all="editor.requestRegenerateAll"
      @open-regen-dialog="editor.openRegenerateDialog"
      @open-upload-picker="editor.openUploadPicker"
      @download-asset="editor.downloadVisualAsset"
      @open-text-edit="editor.openTextEdit"
      @set-start-scene="editor.setStartScene"
      @open-scene="editor.openSceneEditorRoute"
      @toggle-menu="editor.toggleMenu"
      @handle-hover="editor.handleHover"
      @clear-hover="editor.clearHover"
      @create-new-scene="editor.openCreateSceneForm"
    />

    <CreateSceneForm
      v-if="editor.isCreatingScene"
      :is-saving="editor.isSavingText"
      :editor-scenes="editor.editorScenes"
      @close="editor.cancelCreateScene"
      @create="editor.handleCreateScene"
    />

    <SceneRoutePanel
      v-if="editor.canShowSceneRoutePanel"
      :adventure-id="editor.adventureId"
      :scene-id="editor.activeMapSceneId || ''"
      :debug-data="editor.debugData"
      :reference-options="editor.referenceOptions"
      :is-saving-text="editor.isSavingText"
      :is-deleting-route-asset="editor.isDeletingRouteAsset"
      :is-batch-generating="editor.isBatchGenerating"
      :is-quick-generating="editor.isQuickGenerating"
      :active-menu-id="editor.activeMenuId"
      :visuals-cache-version="editor.visualsCacheVersion"
      :rule-enforcement-mode="editor.form.rule_enforcement_mode"
      :return-tab-label="editor.getTabLabel(editor.sceneEditorReturnTab)"
      :adventure-scripts="editor.adventure?.scripts || editor.debugData?.adventure?.scripts || []"
      @back="editor.closeSceneEditorDialog"
      @open-audio-library="editor.openAudioLibrary"
      @open-text-edit="editor.openTextEdit"
      @open-create-item="editor.openCreateItem"
      @open-create-npc="() => editor.openCreateNpc()"
      @open-add-existing="editor.openAddExistingItem"
      @open-regen-dialog="editor.openRegenerateDialog"
      @open-upload-picker="editor.openUploadPicker"
      @download-asset="editor.downloadVisualAsset"
      @toggle-menu="editor.toggleMenu"
      @handle-hover="editor.handleHover"
      @clear-hover="editor.clearHover"
      @open-exit="editor.openExitEditorRoute"
      @open-create-exit="editor.openCreateExitModal"
      @open-edit-exit="editor.openEditExitModal"
      @request-delete-scene="editor.requestDeleteRouteScene"
      @request-delete-exit="editor.requestDeleteRouteExit"
      @request-delete-entity="editor.requestDeleteRouteEntity"
      @clone-entity="editor.handleCloneRouteEntity"
      @export-entity="(kind, id, label) => { editor.activeMenuId = null; editor.exportEntity(kind, id, label) }"
      @import-entity="(kind, sceneId) => editor.importEntity(kind, sceneId)"
      @request-move-entity-to-scene="editor.requestMoveEntityToScene"
      @quick-regen="editor.quickRegenerateVisual"
      @regen-all="editor.requestRegenerateAll"
      @refresh="editor.refreshData"
      @scene-id-changed="editor.handleSceneIdChanged"
    />
  </div>
</template>
