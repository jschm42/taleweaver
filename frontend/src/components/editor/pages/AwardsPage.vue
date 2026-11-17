<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import AwardsTab from '@/components/editor/AwardsTab.vue'

const editor = useEditor()
</script>

<template>
  <AwardsTab
    :adventure="editor.adventure"
    :reference-options="editor.referenceOptions"
    :editor-scenes="editor.editorScenes"
    :editor-objects="editor.editorAllItems"
    :editor-npcs="editor.editorNpcs"
    @update-awards="editor.handleUpdateAwards"
    @notify="editor.addNotification"
  />
</template>
