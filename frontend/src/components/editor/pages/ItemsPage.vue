<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import ItemsTab from '@/components/editor/ItemsTab.vue'
import { sectionsOf } from '@/services/sectionService'

const editor = useEditor()
</script>

<template>
  <ItemsTab
    :editor-objects="editor.editorObjects"
    :editor-switches="editor.editorSwitches"
    :editor-containers="editor.editorContainers"
    :editor-text-logs="editor.editorTextLogs"
    :editor-constructables="editor.editorConstructables"
    :is-batch-generating="editor.isBatchGenerating"
    :is-quick-generating="editor.isQuickGenerating"
    :active-menu-id="editor.activeMenuId"
    :rule-enforcement-mode="editor.form.rule_enforcement_mode"
    :visuals-cache-version="editor.visualsCacheVersion"
    :editor-scenes="editor.editorScenes"
    :adventure-id="editor.adventureId"
    :world-sections="sectionsOf(editor.debugData?.adventure)"
    :adventure-scripts="editor.adventure?.scripts || editor.debugData?.adventure?.scripts || []"
    @quick-regen="editor.quickRegenerateVisual"
    @regen-all="editor.requestRegenerateAll"
    @open-regen-dialog="editor.openRegenerateDialog"
    @open-upload-picker="editor.openUploadPicker"
    @download-asset="editor.downloadVisualAsset"
    @open-text-edit="editor.openTextEdit"
    @toggle-menu="editor.toggleMenu"
    @handle-hover="editor.handleHover"
    @clear-hover="editor.clearHover"
    @request-change-item-type="editor.requestChangeItemType"
    @request-move-item-to-scene="editor.requestMoveItemToScene"
    @request-delete-item="editor.requestDeleteItem"
    @export-entity="(kind, id, label) => { editor.activeMenuId = null; editor.exportEntity(kind, id, label) }"
    @duplicate-entity="(_kind, id) => editor.handleCloneRouteEntity('object', id)"
    @import-entity="editor.importEntity"
  />
</template>
