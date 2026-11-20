<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import ValidationTab from '@/components/editor/ValidationTab.vue'

const editor = useEditor()
</script>

<template>
  <ValidationTab
    :template-id="editor.adventureId"
    :adventure-title="editor.adventure?.title"
    @notify="editor.addNotification"
    @findings-count="editor.onValidationFindingsCount"
    @fix-applied="editor.refreshData"
  />
</template>
