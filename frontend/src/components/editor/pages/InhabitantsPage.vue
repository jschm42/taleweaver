<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import InhabitantsTab from '@/components/editor/InhabitantsTab.vue'

const editor = useEditor()
</script>

<template>
  <InhabitantsTab
    :form="editor.form"
    :adventure="editor.adventure"
    :debug-data="editor.debugData"
    :is-batch-generating="editor.isBatchGenerating"
    :is-quick-generating="editor.isQuickGenerating"
    :active-menu-id="editor.activeMenuId"
    :editor-npcs="editor.editorNpcs"
    :rule-enforcement-mode="editor.form.rule_enforcement_mode"
    :visuals-cache-version="editor.visualsCacheVersion"
    :editor-scenes="editor.editorScenes"
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
    @request-move-npc-to-scene="editor.requestMoveNpcToScene"
    @open-create-npc="() => editor.openCreateNpc()"
    @open-special-attacks="(npc: any) => (editor.specialAttacksNpc = npc)"
    @export-entity="(kind, id, label) => { editor.activeMenuId = null; editor.exportEntity(kind, id, label) }"
    @duplicate-entity="(_kind, id) => editor.handleCloneRouteEntity('npc', id)"
    @import-entity="editor.importEntity"
  />
</template>
