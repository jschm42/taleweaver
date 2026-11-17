<script setup lang="ts">
import { computed, type Component } from 'vue'

const props = withDefaults(
  defineProps<{
    icon: Component
    /** Accessible name; also shown as tooltip. Required because the button has no text. */
    label: string
    variant?: 'ghost' | 'secondary' | 'danger'
    size?: 'sm' | 'md'
    disabled?: boolean
  }>(),
  { variant: 'ghost', size: 'md', disabled: false },
)

const VARIANT_CLASS = {
  ghost: 'text-wb-muted hover:text-wb-strong hover:bg-wb-raised',
  secondary: 'text-wb-body bg-wb-raised border border-wb-line-strong hover:bg-wb-overlay',
  danger: 'text-wb-muted hover:text-wb-danger-text hover:bg-wb-danger-soft',
}

const classes = computed(() => [
  'inline-flex items-center justify-center rounded-md transition-colors shrink-0',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
  'disabled:opacity-50 disabled:cursor-not-allowed',
  props.size === 'sm' ? 'w-7 h-7' : 'w-9 h-9',
  VARIANT_CLASS[props.variant],
])
</script>

<template>
  <button type="button" :class="classes" :aria-label="label" :title="label" :disabled="disabled">
    <component :is="icon" class="w-4 h-4" aria-hidden="true" />
  </button>
</template>
