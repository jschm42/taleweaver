<script setup lang="ts" generic="T extends string">
/** Small switch between a few views or filters ("All / Configured / Unset"). */
const model = defineModel<T>({ required: true })

const props = defineProps<{ options: { value: T; label: string; count?: number }[]; label: string; disabled?: boolean }>()

function move(step: number): void {
  if (props.disabled) return
  const index = props.options.findIndex((option) => option.value === model.value)
  const next = props.options[(index + step + props.options.length) % props.options.length]
  if (next) model.value = next.value
}
</script>

<template>
  <div
    role="radiogroup"
    :aria-label="label"
    :aria-disabled="disabled || undefined"
    :class="['inline-flex rounded-md border border-wb-line-strong bg-wb-raised p-0.5', disabled && 'opacity-50']"
    @keydown.right.prevent="move(1)"
    @keydown.left.prevent="move(-1)"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="model === option.value"
      :tabindex="model === option.value ? 0 : -1"
      :disabled="disabled"
      :class="[
        'wb-label rounded-md px-3 py-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent disabled:cursor-not-allowed',
        model === option.value ? 'bg-wb-overlay !text-wb-strong shadow-sm' : '!text-wb-muted hover:!text-wb-strong',
      ]"
      @click="model = option.value"
    >
      {{ option.label }}<span v-if="option.count !== undefined" class="ml-1 tabular-nums text-wb-faint">{{ option.count }}</span>
    </button>
  </div>
</template>
