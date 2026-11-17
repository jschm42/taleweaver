<script setup lang="ts">
import { computed } from 'vue'
import type { KeyPolicy } from '@/composables/useApi'
import UiSelect from '@/components/ui/UiSelect.vue'
import { KEY_POLICY_OPTIONS } from './useKeyPolicy'

/** Who pays for one provider. ``inherit`` adds a "use server default" choice (user overrides). */
const props = defineProps<{
  modelValue: KeyPolicy | ''
  providerName: string
  disabled?: boolean
  inherit?: boolean
}>()
const emit = defineEmits<{ (e: 'update:modelValue', value: KeyPolicy | ''): void }>()

const hint = computed(() => KEY_POLICY_OPTIONS.find(o => o.value === props.modelValue)?.hint || 'Uses the server-wide policy.')

const options = computed(() => [
  ...(props.inherit ? [{ value: '', label: 'Server default' }] : []),
  ...KEY_POLICY_OPTIONS.map((option) => ({ value: option.value, label: option.label })),
])

function onChange(value: string | number | null): void {
  emit('update:modelValue', (value ?? '') as KeyPolicy | '')
}
</script>

<template>
  <UiSelect
    :model-value="modelValue"
    :options="options"
    :disabled="disabled"
    :title="hint"
    :aria-label="`Who pays for ${providerName}`"
    size="sm"
    class="w-44 shrink-0"
    @update:model-value="onChange"
  />
</template>
