<script setup lang="ts">
import { computed, watch } from 'vue'
import { Sparkles } from 'lucide-vue-next'
import { CONTROL_CLASS, controlBorder, useFieldControl } from '@/components/ui/fieldContext'
import UiButton from '@/components/ui/UiButton.vue'
import UiIconButton from '@/components/ui/UiIconButton.vue'
import {
  MAX_EDITOR_ID_LENGTH,
  generateEditorId,
  sanitizeEditorId,
} from '@/utils/editor_utils'

const props = withDefaults(
  defineProps<{
    modelValue?: string | null
    prefix?: string
    sourceName?: string
    takenIds?: Iterable<string> | null
    originalId?: string | null
    maxLength?: number
    disabled?: boolean
    readonly?: boolean
    placeholder?: string
    compact?: boolean
    showGenerate?: boolean
    showCounter?: boolean
    required?: boolean
    inputClass?: string
    ariaLabel?: string
  }>(),
  {
    modelValue: '',
    prefix: '',
    sourceName: '',
    takenIds: null,
    originalId: null,
    maxLength: MAX_EDITOR_ID_LENGTH,
    disabled: false,
    readonly: false,
    placeholder: '',
    compact: false,
    showGenerate: true,
    showCounter: true,
    required: false,
    inputClass: '',
    ariaLabel: 'Identifier',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'commit', value: string): void
  (e: 'validChange', isValid: boolean): void
}>()

const field = useFieldControl({})

const effectiveMaxLength = computed(() =>
  Math.max(4, Math.floor(Number(props.maxLength) || MAX_EDITOR_ID_LENGTH)),
)

const currentValue = computed(() => String(props.modelValue ?? ''))

const normalizedOriginalId = computed(() =>
  String(props.originalId ?? '').trim().toUpperCase(),
)

/** An existing ID that is left unchanged stays valid, even if it predates the length limit. */
const isUnchangedOriginal = (value: string): boolean =>
  !!normalizedOriginalId.value && value.trim().toUpperCase() === normalizedOriginalId.value

/** Sanitizes input, but never shortens an unchanged legacy ID. */
function sanitize(value: string): string {
  return isUnchangedOriginal(value) ? value.trim().toUpperCase() : sanitizeEditorId(value, effectiveMaxLength.value)
}

const takenSet = computed(() => {
  const set = new Set<string>()
  if (!props.takenIds) return set
  for (const id of props.takenIds) {
    const normalized = String(id || '').trim().toUpperCase()
    if (normalized && normalized !== normalizedOriginalId.value) {
      set.add(normalized)
    }
  }
  return set
})

const effectivePlaceholder = computed(() => {
  if (props.placeholder) return props.placeholder
  return props.prefix ? `${props.prefix}NAME` : 'UNIQUE_ID'
})

const validationError = computed(() => {
  const val = currentValue.value.trim()
  if (!val) {
    return props.required ? 'ID is required.' : ''
  }
  if (!/^[A-Z0-9_]+$/.test(val)) {
    return 'Use uppercase letters (A-Z), digits (0-9), and underscores (_) only.'
  }
  if (val.length > effectiveMaxLength.value && !isUnchangedOriginal(val)) {
    return `ID must be ${effectiveMaxLength.value} characters or fewer.`
  }
  if (takenSet.value.has(val)) {
    return 'This ID is already in use.'
  }
  return ''
})

const isValid = computed(() => {
  if (props.required && !currentValue.value.trim()) return false
  return !validationError.value
})

watch(
  isValid,
  (valid) => {
    emit('validChange', valid)
  },
  { immediate: true },
)

function handleInput(event: Event) {
  const target = event.target as HTMLInputElement
  const sanitized = sanitize(target.value)
  if (target.value !== sanitized) {
    target.value = sanitized
  }
  emit('update:modelValue', sanitized)
}

function handleBlur(event: Event) {
  const target = event.target as HTMLInputElement
  const sanitized = sanitize(target.value)
  if (sanitized !== currentValue.value) {
    emit('update:modelValue', sanitized)
  }
  emit('commit', sanitized)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter') return
  const sanitized = sanitize(currentValue.value)
  emit('commit', sanitized)
}

const generateLabel = computed(
  () => `Generate ID${props.prefix ? ` (${props.prefix}...)` : ''}, up to ${effectiveMaxLength.value} characters`,
)

function handleGenerate() {
  if (props.disabled || props.readonly) return
  const nextId = generateEditorId({
    prefix: props.prefix,
    sourceName: props.sourceName,
    takenIds: takenSet.value,
    maxLen: effectiveMaxLength.value,
    randomFallback: true,
  })
  emit('update:modelValue', nextId)
  emit('commit', nextId)
}
</script>

<template>
  <div class="space-y-1">
    <div class="flex items-center gap-1.5">
      <div class="relative min-w-0 flex-1">
        <input
          :id="field.id.value"
          :value="currentValue"
          :maxlength="effectiveMaxLength"
          :disabled="disabled"
          :readonly="readonly"
          :placeholder="effectivePlaceholder"
          :aria-label="ariaLabel"
          :aria-invalid="!!validationError || undefined"
          :aria-describedby="field.describedBy.value"
          spellcheck="false"
          autocomplete="off"
          :class="[
            CONTROL_CLASS,
            controlBorder(!!validationError),
            '!font-mono uppercase',
            compact ? 'h-8 px-2.5' : 'h-9 px-3',
            showCounter ? 'pr-14' : '',
            readonly ? 'cursor-not-allowed opacity-60' : '',
            inputClass,
          ]"
          @input="handleInput"
          @blur="handleBlur"
          @keydown="handleKeydown"
        />
        <span
          v-if="showCounter"
          :class="[
            'wb-mono pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2',
            currentValue.length >= effectiveMaxLength ? '!text-wb-warn-text' : 'text-wb-faint',
          ]"
        >
          {{ currentValue.length }}/{{ effectiveMaxLength }}
        </span>
      </div>

      <template v-if="showGenerate && !disabled && !readonly">
        <UiIconButton v-if="compact" :icon="Sparkles" :label="generateLabel" variant="secondary" size="sm" @click="handleGenerate" />
        <UiButton v-else :icon="Sparkles" :title="generateLabel" @click="handleGenerate">Auto</UiButton>
      </template>
    </div>

    <p v-if="validationError" class="wb-hint !text-wb-danger-text" role="alert">{{ validationError }}</p>
  </div>
</template>
