<script setup lang="ts">
import { useEditor } from '@/composables/editor/editorContext'
import AudioTab from '@/components/editor/AudioTab.vue'

const editor = useEditor()
</script>

<template>
  <AudioTab
    :adventure-id="editor.adventureId"
    :scenes="editor.debugData?.scenes || []"
    @refresh-world="editor.fetchDebugInfo"
  />
</template>
