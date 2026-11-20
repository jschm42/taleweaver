<script setup lang="ts">
import { useId } from 'vue'

const model = defineModel<boolean>({ default: false })

withDefaults(
  defineProps<{
    label: string
    description?: string
    disabled?: boolean
    /** Hide the visible label (it stays the accessible name). */
    hideLabel?: boolean
  }>(),
  { description: '', disabled: false, hideLabel: false },
)

const labelId = `toggle-${useId()}`
const descriptionId = `${labelId}-description`
</script>

<template>
  <div class="flex items-start justify-between gap-4">
    <div v-if="!hideLabel" class="min-w-0">
      <div :id="labelId" class="wb-label !text-wb-strong">{{ label }}</div>
      <p v-if="description" :id="descriptionId" class="wb-hint mt-0.5">{{ description }}</p>
    </div>
    <button
      type="button"
      role="switch"
      :aria-checked="model"
      :aria-labelledby="hideLabel ? undefined : labelId"
      :aria-label="hideLabel ? label : undefined"
      :aria-describedby="description && !hideLabel ? descriptionId : undefined"
      :disabled="disabled"
      :class="[
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-wb-accent focus-visible:ring-offset-2 focus-visible:ring-offset-wb-canvas',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        model ? 'bg-wb-accent' : 'bg-wb-overlay border border-wb-line-strong',
      ]"
      @click="model = !model"
    >
      <span
        :class="[
          'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
          model ? 'translate-x-[18px]' : 'translate-x-0.5',
        ]"
      />
    </button>
  </div>
</template>
