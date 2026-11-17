<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import ProtagonistTab from '@/components/editor/ProtagonistTab.vue'

const editor = useEditor()
</script>

<template>
  <ProtagonistTab
    :debug-data="editor.debugData"
    :is-quick-generating="editor.isQuickGenerating"
    :active-menu-id="editor.activeMenuId"
    :visuals-cache-version="editor.visualsCacheVersion"
    :rule-enforcement-mode="editor.form.rule_enforcement_mode"
    :is-saving-text="editor.isSavingText"
    :reference-options="editor.referenceOptions"
    @quick-regen="editor.quickRegenerateVisual"
    @open-regen-dialog="editor.openRegenerateDialog"
    @open-upload-picker="editor.openUploadPicker"
    @download-asset="editor.downloadVisualAsset"
    @toggle-menu="editor.toggleMenu"
    :adventure-id="editor.adventureId"
    :voice-list="editor.voiceList"
    @save-field="editor.saveProtagonistField"
    @create-new-item="editor.createNewItemForProtagonist"
    @special-attacks-saved="editor.onSpecialAttacksSaved"
    @export-entity="editor.exportEntity"
    @import-entity="editor.importEntity"
  />
</template>
