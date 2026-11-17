<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import SequencesSection from '@/components/editor/SequencesSection.vue'

const editor = useEditor()
</script>

<template>
  <div class="space-y-6">
    <div class="space-y-6">
      <SequencesSection
        :adventure="editor.adventure"
        :editor-scenes="editor.editorScenes"
        :editor-objects="editor.editorAllItems"
        :editor-npcs="editor.editorNpcs"
        :is-saving="editor.isSaving"
        @update-sequences="editor.handleUpdateSequences"
        @update-progression-mode="editor.handleUpdateProgressionMode"
        @notify="editor.addNotification"
      />
    </div>
  </div>
</template>
