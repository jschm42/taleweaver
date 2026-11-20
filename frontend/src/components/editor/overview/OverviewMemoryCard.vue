<script setup lang="ts">
import { computed } from 'vue'
import { useEditor } from '@/composables/editor/editorContext'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiRange from '@/components/ui/UiRange.vue'

/** How many past turns the narration model sees. */
const editor = useEditor()

const turns = computed({
  get: (): number => editor.form.max_memory_turns ?? 10,
  set: (value: number) => {
    editor.form.max_memory_turns = Math.min(100, Math.max(1, Math.round(value) || 10))
  },
})
</script>

<template>
  <UiCard title="Narrator memory">
    <UiField
      label="Past turns in the narration context"
      hint="10 is the default. More turns keep the story more consistent but cost more tokens; 30–100 is extended memory."
    >
      <UiRange v-model="turns" :min="1" :max="100" />
    </UiField>
  </UiCard>
</template>
