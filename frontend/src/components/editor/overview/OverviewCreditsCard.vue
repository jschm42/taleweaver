<script setup lang="ts">
import { computed } from 'vue'
import { useEditor } from '@/composables/editor/editorContext'
import { formFieldError } from '@/composables/editor/useEditorFormDraft'
import UiCard from '@/components/ui/UiCard.vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'

/** Creator, copyright and license; exported with the adventure package. */
const editor = useEditor()
const form = computed(() => editor.form as Record<string, unknown>)

const FIELDS = [
  { field: 'creator', label: 'Creator', placeholder: 'e.g. Jane Doe', max: 100 },
  { field: 'copyright', label: 'Copyright', placeholder: 'e.g. Copyright (c) 2026', max: 100 },
  { field: 'license', label: 'License', placeholder: 'e.g. MIT, CC-BY-4.0', max: 100 },
]

function text(field: string): string {
  return String(form.value[field] ?? '')
}

function setText(field: string, value: string | number | null): void {
  form.value[field] = String(value ?? '')
}
</script>

<template>
  <UiCard title="Credits and license" description="Shown with the adventure and kept in exported packages.">
    <div class="grid gap-4 md:grid-cols-3">
      <UiField v-for="item in FIELDS" :key="item.field" :label="item.label" :error="formFieldError(form, item.field)">
        <UiInput
          :model-value="text(item.field)"
          :maxlength="item.max"
          :placeholder="item.placeholder"
          @update:model-value="(v) => setText(item.field, v)"
        />
      </UiField>
      <UiField label="License URL" class="md:col-span-3" :error="formFieldError(form, 'license_url')">
        <UiInput
          type="url"
          :model-value="text('license_url')"
          maxlength="500"
          placeholder="e.g. https://creativecommons.org/licenses/by-nc/4.0/"
          @update:model-value="(v) => setText('license_url', v)"
        />
      </UiField>
    </div>
  </UiCard>
</template>
