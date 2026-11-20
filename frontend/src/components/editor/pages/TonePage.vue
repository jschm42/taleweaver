<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import ToneTab from '@/components/editor/ToneTab.vue'

const editor = useEditor()
</script>

<template>
  <ToneTab
    :form="editor.form"
    :adventure="editor.adventure"
    :debug-data="editor.debugData"
    :tone-catalog="editor.toneCatalog"
    :is-saving="editor.isSaving"
    @update:tone="editor.form.selected_tone_id = $event"
    @update:narrator-voice="editor.form.narrator_voice = $event"
    @save-changes="editor.saveChanges"
  />
</template>
