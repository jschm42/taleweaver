<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import ProtagonistTab from '@/components/editor/ProtagonistTab.vue'

const editor = useEditor()
</script>

<template>
  <ProtagonistTab
    :protagonist="editor.debugData?.protagonist ?? null"
    :is-quick-generating="editor.isQuickGenerating"
    :visuals-cache-version="editor.visualsCacheVersion"
    :rule-enforcement-mode="editor.form.rule_enforcement_mode"
    :is-saving-text="editor.isSavingText"
    :reference-options="editor.referenceOptions"
    :adventure-id="editor.adventureId"
    :voice-list="editor.voiceList"
    @quick-regen="editor.quickRegenerateVisual"
    @open-regen-dialog="editor.openRegenerateDialog"
    @open-upload-picker="editor.openUploadPicker"
    @download-asset="editor.downloadVisualAsset"
    @save-field="editor.saveProtagonistField"
    @create-new-item="editor.createNewItemForProtagonist"
    @special-attacks-saved="editor.onSpecialAttacksSaved"
    @export-entity="editor.exportEntity"
    @import-entity="editor.importEntity"
  />
</template>
