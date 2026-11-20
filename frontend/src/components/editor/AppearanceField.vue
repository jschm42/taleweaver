<script setup lang="ts">
import { computed } from 'vue'
import UiField from '@/components/ui/UiField.vue'
import UiInput from '@/components/ui/UiInput.vue'

const APPEARANCE_MAX_LENGTH = 100

const props = defineProps<{
  modelValue: string | null | undefined
  targetType: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const PLACEHOLDERS: Record<string, string> = {
  cover: 'ruined lighthouse, stormy sea, teal and amber, ominous',
  protagonist: 'lean young woman, short red hair, leather coat, brass goggles',
  npc: 'gaunt elderly man, white beard, ink-stained robe, round spectacles',
  object: 'small brass key, ornate bow, tarnished green patina',
}

const value = computed({
  get: () => props.modelValue || '',
  set: (next: string) => emit('update:modelValue', next),
})
const label = computed(() => (props.targetType === 'cover' ? 'Cover visual keywords' : 'Appearance keywords'))
const placeholder = computed(() => PLACEHOLDERS[props.targetType] || '')
</script>

<template>
  <UiField
    :label="label"
    hint="Optional comma-separated visual keywords (English works best) for the image prompt."
    :count="value.length"
    :max-length="APPEARANCE_MAX_LENGTH"
  >
    <UiInput :model-value="value" @update:model-value="(next) => (value = String(next ?? ''))" :maxlength="APPEARANCE_MAX_LENGTH" :placeholder="placeholder" />
  </UiField>
</template>
