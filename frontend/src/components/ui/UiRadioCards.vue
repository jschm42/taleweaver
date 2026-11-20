<script setup lang="ts" generic="T extends string | number">
import type { Component } from 'vue'

export interface RadioCardOption<V> {
  value: V
  label: string
  description?: string
  icon?: Component
  disabled?: boolean
}

/** A choice between a few options shown as cards (mode, role, type). Arrow keys move the choice. */
const model = defineModel<T>({ required: true })

const props = withDefaults(defineProps<{ options: RadioCardOption<T>[]; label: string; columns?: 1 | 2 | 3 }>(), {
  columns: 2,
})

const COLUMNS = { 1: 'grid-cols-1', 2: 'grid-cols-1 sm:grid-cols-2', 3: 'grid-cols-1 sm:grid-cols-3' }

function move(step: number): void {
  const enabled = props.options.filter((option) => !option.disabled)
  const index = enabled.findIndex((option) => option.value === model.value)
  const next = enabled[(index + step + enabled.length) % enabled.length]
  if (next) {
    model.value = next.value
  }
}
</script>

<template>
  <div
    role="radiogroup"
    :aria-label="label"
    :class="['grid gap-2', COLUMNS[columns]]"
    @keydown.right.prevent="move(1)"
    @keydown.down.prevent="move(1)"
    @keydown.left.prevent="move(-1)"
    @keydown.up.prevent="move(-1)"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="model === option.value"
      :tabindex="model === option.value ? 0 : -1"
      :disabled="option.disabled"
      :class="[
        'flex items-start gap-3 rounded-xl border p-3 text-left transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        model === option.value
          ? 'border-wb-accent bg-wb-accent-soft'
          : 'border-wb-line-strong bg-wb-raised hover:border-wb-faint',
      ]"
      @click="model = option.value"
    >
      <component
        :is="option.icon"
        v-if="option.icon"
        :class="['mt-0.5 h-4 w-4 shrink-0', model === option.value ? 'text-wb-accent-text' : 'text-wb-muted']"
        aria-hidden="true"
      />
      <span class="min-w-0">
        <span class="wb-label block !text-wb-strong">{{ option.label }}</span>
        <span v-if="option.description" class="wb-hint block mt-0.5">{{ option.description }}</span>
      </span>
    </button>
  </div>
</template>
