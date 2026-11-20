<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import ScriptsTab from '@/components/editor/ScriptsTab.vue'

const editor = useEditor()
</script>

<template>
  <ScriptsTab
    :adventure="editor.adventure"
    :reference-options="editor.referenceOptions"
    :is-saving="editor.isSaving"
    @update-scripts="editor.handleUpdateScripts"
    @update-init-script="editor.handleUpdateInitScript"
    @notify="editor.addNotification"
  />
</template>
