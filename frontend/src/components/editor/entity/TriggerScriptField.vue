<script setup lang="ts">
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import UiField from '@/components/ui/UiField.vue'
import UiTextarea from '@/components/ui/UiTextarea.vue'

/** One trigger of an entity: a script and/or a text the Game Master narrates when it fires. */
const script = defineModel<string>('script', { default: '' })
const text = defineModel<string>('text', { default: '' })

withDefaults(
  defineProps<{
    /** e.g. "On unlock success" */
    label: string
    help: string
    context: string
    textPlaceholder?: string
    minHeight?: string
  }>(),
  { textPlaceholder: '', minHeight: '100px' },
)
</script>

<template>
  <div class="space-y-3">
    <ScriptEditor v-model="script" :label="`${label} script`" :help-text="help" :context="context" :min-height="minHeight" />
    <UiField :label="`${label} text`" hint="Narrated when the trigger fires; optional.">
      <UiTextarea v-model="text" :rows="2" :placeholder="textPlaceholder" />
    </UiField>
  </div>
</template>
