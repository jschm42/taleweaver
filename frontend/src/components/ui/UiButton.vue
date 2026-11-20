<script setup lang="ts">
import { computed, type Component } from 'vue'
import UiSpinner from '@/components/ui/UiSpinner.vue'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'ai'

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant
    size?: 'sm' | 'md'
    type?: 'button' | 'submit' | 'reset'
    loading?: boolean
    disabled?: boolean
    icon?: Component
    iconRight?: Component
    block?: boolean
  }>(),
  { variant: 'secondary', size: 'md', type: 'button', loading: false, disabled: false, block: false },
)

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: 'bg-wb-accent text-white hover:bg-wb-accent/90',
  secondary: 'bg-wb-raised text-wb-strong border border-wb-line-strong hover:bg-wb-overlay',
  ghost: 'text-wb-body hover:bg-wb-raised hover:text-wb-strong',
  danger: 'bg-wb-danger text-white hover:bg-wb-danger/90',
  ai: 'bg-wb-ai text-white hover:bg-wb-ai/90',
}

const SIZE_CLASS = { sm: 'h-8 px-3 gap-1.5 wb-label', md: 'h-9 px-4 gap-2 wb-body' }

const classes = computed(() => [
  'inline-flex items-center justify-center rounded-md font-wb font-medium whitespace-nowrap transition-colors',
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent focus-visible:ring-offset-2 focus-visible:ring-offset-wb-canvas',
  'disabled:opacity-50 disabled:cursor-not-allowed',
  VARIANT_CLASS[props.variant],
  SIZE_CLASS[props.size],
  props.block ? 'w-full' : '',
])
</script>

<template>
  <button :type="type" :class="classes" :disabled="disabled || loading" :aria-busy="loading || undefined">
    <UiSpinner v-if="loading" size="sm" class="!text-current" />
    <component :is="icon" v-else-if="icon" class="w-4 h-4 shrink-0" aria-hidden="true" />
    <slot />
    <component :is="iconRight" v-if="iconRight" class="w-4 h-4 shrink-0" aria-hidden="true" />
  </button>
</template>
