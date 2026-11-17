<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import TriggerTreeTab from '@/components/editor/TriggerTreeTab.vue'

const editor = useEditor()
</script>

<template>
  <TriggerTreeTab
    :adventure="{ ...(editor.debugData?.adventure || {}), ...(editor.adventure || {}) }"
    :protagonist="editor.debugData?.protagonist"
    :scenes="editor.editorScenes"
    :exits="editor.debugData?.exits || []"
    :npcs="editor.editorNpcs"
    :objects="editor.editorAllItems"
    @edit="editor.handleTriggerTreeEdit"
  />
</template>
