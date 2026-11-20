<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import DynamicGenerationSection from '@/components/editor/DynamicGenerationSection.vue'

const editor = useEditor()
</script>

<template>
  <DynamicGenerationSection
    :model-value="editor.form.dynamic_generation"
    :is-saving="editor.isSaving"
    @update:model-value="editor.form.dynamic_generation = $event"
    @save="editor.handleUpdateDynamicGeneration"
  />
</template>
