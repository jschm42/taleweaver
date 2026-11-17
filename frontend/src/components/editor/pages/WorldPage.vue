<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import WorldTab from '@/components/editor/WorldTab.vue'
import { fixNewlines } from '@/utils/editor_utils'

const editor = useEditor()
</script>

<template>
  <WorldTab
    :form="editor.form"
    :adventure="editor.adventure"
    :debug-data="editor.debugData"
    :reference-options="editor.referenceOptions"
    :editing-field="editor.editingField"
    :temp-value="editor.tempValue"
    :is-saving="editor.isSaving"
    :is-batch-generating="editor.isBatchGenerating"
    :is-quick-generating="editor.isQuickGenerating"
    :is-generating-field="editor.isGeneratingField"
    :active-menu-id="editor.activeMenuId"
    :fix-newlines="fixNewlines"
    @quick-regen="editor.quickRegenerateVisual"
    @open-regen-dialog="editor.openRegenerateDialog"
    @open-upload-picker="editor.openUploadPicker"
    @download-asset="editor.downloadVisualAsset"
    @open-text-edit="editor.openTextEdit"
    @toggle-menu="editor.toggleMenu"
    @start-edit="editor.startEditing"
    @save-field="editor.saveField"
    @cancel-edit="editor.cancelEditing"
    @generate-field="editor.handleGenerateField"
    @update:temp-value="editor.tempValue = $event"
    @update:max-memory-turns="editor.form.max_memory_turns = $event"
    @update:mode="editor.handleUpdateRuleMode"
    @save-changes="editor.saveChanges"
    @notify="editor.addNotification"
  />
</template>
