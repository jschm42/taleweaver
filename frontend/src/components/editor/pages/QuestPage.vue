<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import QuestTab from '@/components/editor/QuestTab.vue'

const editor = useEditor()
</script>

<template>
  <QuestTab
    :adventure="editor.adventure"
    :reference-options="editor.referenceOptions"
    :editor-scenes="editor.editorScenes"
    :editor-objects="editor.editorAllItems"
    :editor-npcs="editor.editorNpcs"
    @update-quests="editor.handleUpdateQuests"
    @notify="editor.addNotification"
  />
</template>
