<script setup lang="ts">
import TriggerScriptField from '@/components/editor/entity/TriggerScriptField.vue'

/** Inline on_interact trigger (script + text) shared by objects and NPCs. */
defineProps<{
  entityLabel: string
}>()

const script = defineModel<string>('script', { default: '' })
const text = defineModel<string>('text', { default: '' })
</script>

<template>
  <TriggerScriptField
    v-model:script="script"
    v-model:text="text"
    label="On interact"
    :help="`Runs whenever the player interacts with this ${entityLabel} (inspect, use, push, talk, tamper), fixed objects included. For behaviour limited to one chapter, use a sequence script instead.`"
    context="on_interact"
    min-height="120px"
  />
</template>
