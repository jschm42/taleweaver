<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import VisualsTab from '@/components/editor/VisualsTab.vue'

const editor = useEditor()
</script>

<template>
  <VisualsTab
    :form="editor.form"
    :adventure="editor.adventure"
    :adventure-id="editor.adventureId"
    :image-styles-catalog="editor.imageStylesCatalog"
    :tone-catalog="editor.toneCatalog"
    @update:style="editor.form.selected_style_id = $event"
    @update:ui-theme="editor.adventure && (editor.adventure.ui_theme = $event)"
    @save-changes="editor.saveChanges"
  />
</template>
