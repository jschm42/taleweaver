<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import AdvancedTab from '@/components/editor/AdvancedTab.vue'

const editor = useEditor()
</script>

<template>
  <AdvancedTab
    :form="editor.form"
    @update:generator="editor.form.is_adventure_generator = $event; editor.saveChanges()"
    @update:can-damage-npcs="editor.form.can_damage_npcs = $event; editor.saveChanges()"
    @update:npcs-can-damage-protagonist="editor.form.npcs_can_damage_protagonist = $event; editor.saveChanges()"
    @show-debug="editor.showDebug = true"
    @save-changes="editor.saveChanges"
  />
</template>
