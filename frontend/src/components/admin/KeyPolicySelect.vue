<script setup lang="ts">
import { computed } from 'vue'
import type { KeyPolicy } from '@/composables/useApi'
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

function onChange(event: Event): void {
  emit('update:modelValue', (event.target as HTMLSelectElement).value as KeyPolicy | '')
}
</script>

<template>
  <select
    :value="modelValue"
    :disabled="disabled"
    :title="hint"
    :aria-label="`Who pays for ${providerName}`"
    class="cursor-pointer rounded-lg border border-slate-700/60 bg-slate-950 px-2 py-1 text-[11px] font-bold text-slate-200 outline-none focus:border-emerald-500/50 disabled:opacity-50"
    @change="onChange"
  >
    <option v-if="inherit" value="">Server default</option>
    <option v-for="option in KEY_POLICY_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
  </select>
</template>
