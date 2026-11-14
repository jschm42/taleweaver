<script setup lang="ts">
import { computed, watch } from 'vue'
import { Sparkles } from 'lucide-vue-next'
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

const effectiveMaxLength = computed(() =>
  Math.max(4, Math.floor(Number(props.maxLength) || MAX_EDITOR_ID_LENGTH)),
)

const currentValue = computed(() => String(props.modelValue ?? ''))

const normalizedOriginalId = computed(() =>
  String(props.originalId ?? '').trim().toUpperCase(),
)

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
  if (val.length > effectiveMaxLength.value) {
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
  const sanitized = sanitizeEditorId(target.value, effectiveMaxLength.value)
  if (target.value !== sanitized) {
    target.value = sanitized
  }
  emit('update:modelValue', sanitized)
}

function handleBlur(event: Event) {
  const target = event.target as HTMLInputElement
  const sanitized = sanitizeEditorId(target.value, effectiveMaxLength.value)
  if (sanitized !== currentValue.value) {
    emit('update:modelValue', sanitized)
  }
  emit('commit', sanitized)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter') return
  const sanitized = sanitizeEditorId(currentValue.value, effectiveMaxLength.value)
  emit('commit', sanitized)
}

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
      <div class="relative flex-1 min-w-0">
        <input
          :value="currentValue"
          :maxlength="effectiveMaxLength"
          :disabled="disabled"
          :readonly="readonly"
          :placeholder="effectivePlaceholder"
          :aria-label="ariaLabel"
          spellcheck="false"
          autocomplete="off"
          :class="[
            'w-full bg-black/40 border rounded-xl font-mono uppercase text-white placeholder:text-slate-600 focus:outline-none transition-colors',
            compact ? 'px-2.5 py-1.5 text-xs' : 'px-3 py-2 text-sm',
            showCounter ? (compact ? 'pr-12' : 'pr-14') : '',
            validationError
              ? 'border-rose-500/80 focus:border-rose-400'
              : 'border-white/10 focus:border-emerald-500',
            disabled || readonly ? 'opacity-60 cursor-not-allowed' : '',
            inputClass,
          ]"
          @input="handleInput"
          @blur="handleBlur"
          @keydown="handleKeydown"
        />
        <span
          v-if="showCounter"
          :class="[
            'pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 font-mono',
            compact ? 'text-[10px]' : 'text-[11px]',
            currentValue.length >= effectiveMaxLength ? 'text-amber-400' : 'text-slate-500',
          ]"
        >
          {{ currentValue.length }}/{{ effectiveMaxLength }}
        </span>
      </div>

      <button
        v-if="showGenerate && !disabled && !readonly"
        type="button"
        :title="`Generate ID${prefix ? ` (${prefix}...)` : ''} (max ${effectiveMaxLength} chars)`"
        :class="[
          'shrink-0 inline-flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 hover:bg-emerald-500/15 hover:border-emerald-500/40 text-slate-300 hover:text-emerald-200 transition-colors',
          compact ? 'px-2 py-1.5 text-[11px]' : 'px-2.5 py-2 text-xs',
        ]"
        @click="handleGenerate"
      >
        <Sparkles :class="compact ? 'w-3.5 h-3.5' : 'w-3.5 h-3.5'" />
        <span v-if="!compact" class="hidden sm:inline font-medium">Auto</span>
      </button>
    </div>

    <div
      v-if="validationError"
      class="text-[11px] text-rose-400 leading-tight"
    >
      {{ validationError }}
    </div>
  </div>
</template>
