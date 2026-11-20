<script setup lang="ts">
import { computed } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { useEditor } from '@/composables/editor/editorContext'
import { FORM_LIMITS, formFieldError } from '@/composables/editor/useEditorFormDraft'
import { useFormFieldGenerator } from '@/composables/editor/useFormFieldGenerator'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiField from '@/components/ui/UiField.vue'

/**
 * Long text setting of the adventure (`editor.form[field]`): counter, limit, `##ID` references
 * and an optional "Generate" button that writes into the draft.
 */
const props = withDefaults(
  defineProps<{
    field: string
    label: string
    hint?: string
    info?: string
    placeholder?: string
    rows?: number
    generatable?: boolean
  }>(),
  { hint: '', info: '', placeholder: '', rows: 4, generatable: false },
)

const editor = useEditor()
const generator = useFormFieldGenerator(editor)
const form = computed(() => editor.form as Record<string, unknown>)

const value = computed({
  get: (): string => String(form.value[props.field] ?? ''),
  set: (next: string) => {
    form.value[props.field] = next
  },
})
const error = computed(() => formFieldError(form.value, props.field))
const busy = computed(() => generator.isGenerating(props.field))
</script>

<template>
  <div class="space-y-2">
    <UiField :label="label" :hint="hint" :info="info" :error="error" :count="value.length" :max-length="FORM_LIMITS[field]">
      <ReferenceTextarea
        v-model="value"
        :rows="rows"
        :options="editor.referenceOptions || []"
        :placeholder="placeholder"
      />
    </UiField>
    <div v-if="generatable" class="flex justify-end">
      <UiButton variant="ai" size="sm" :icon="Sparkles" :loading="busy" :disabled="editor.isSaving" @click="generator.generate(field)">
        {{ value.trim() ? 'Regenerate' : 'Generate' }}
      </UiButton>
    </div>
  </div>
</template>
