<script setup lang="ts">
import { computed } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { CONTROL_CLASS, controlBorder, useFieldControl } from '@/components/ui/fieldContext'

export interface SelectOption {
  value: string | number
  label: string
  disabled?: boolean
}

defineOptions({ inheritAttrs: false })

const model = defineModel<string | number | null>({ default: null })

const props = withDefaults(
  defineProps<{
    options?: SelectOption[]
    id?: string
    invalid?: boolean
    required?: boolean
    disabled?: boolean
    /** Text of an empty first option; omitted when not set. */
    placeholder?: string
    size?: 'sm' | 'md'
  }>(),
  { options: () => [], id: undefined, invalid: false, required: false, disabled: false, placeholder: '', size: 'md' },
)

const control = useFieldControl(props)

const classes = computed(() => [
  CONTROL_CLASS,
  controlBorder(control.invalid.value),
  'appearance-none cursor-pointer pr-9',
  props.size === 'sm' ? 'h-8 pl-2.5' : 'h-9 pl-3',
])

function handleChange(event: Event): void {
  const raw = (event.target as HTMLSelectElement).value
  const match = props.options.find((option) => String(option.value) === raw)
  model.value = match ? match.value : raw === '' ? null : raw
}
</script>

<template>
  <div class="relative">
    <select
      v-bind="$attrs"
      :id="control.id.value"
      :value="model ?? ''"
      :class="classes"
      :disabled="disabled"
      :required="control.required.value"
      :aria-invalid="control.invalid.value || undefined"
      :aria-describedby="control.describedBy.value"
      @change="handleChange"
    >
      <option v-if="placeholder" value="">{{ placeholder }}</option>
      <slot>
        <option v-for="option in options" :key="option.value" :value="option.value" :disabled="option.disabled">
          {{ option.label }}
        </option>
      </slot>
    </select>
    <ChevronDown
      class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-wb-muted"
      aria-hidden="true"
    />
  </div>
</template>
