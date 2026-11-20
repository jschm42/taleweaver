<script setup lang="ts">
import { useFieldControl } from '@/components/ui/fieldContext'

/** Slider with its current value shown on the right. Use inside UiField for the label. */
const model = defineModel<number>({ required: true })

const props = withDefaults(
  defineProps<{
    min?: number
    max?: number
    step?: number
    /** Appended to the shown value, e.g. "%". */
    unit?: string
    id?: string
    disabled?: boolean
  }>(),
  { min: 0, max: 100, step: 1, unit: '', id: undefined, disabled: false },
)

const control = useFieldControl(props)
</script>

<template>
  <div class="flex items-center gap-3">
    <input
      :id="control.id.value"
      type="range"
      :min="min"
      :max="max"
      :step="step"
      :value="model"
      :disabled="disabled"
      :aria-describedby="control.describedBy.value"
      class="h-2 min-w-0 flex-1 cursor-pointer accent-wb-accent disabled:cursor-not-allowed disabled:opacity-50"
      @input="model = Number(($event.target as HTMLInputElement).value)"
    />
    <span class="wb-mono w-12 shrink-0 text-right text-wb-strong tabular-nums">{{ model }}{{ unit }}</span>
  </div>
</template>
