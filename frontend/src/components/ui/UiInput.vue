<script setup lang="ts">
import { computed } from 'vue'
import { CONTROL_CLASS, controlBorder, useFieldControl } from '@/components/ui/fieldContext'

defineOptions({ inheritAttrs: false })

const model = defineModel<string | number | null>({ default: '' })

const props = withDefaults(
  defineProps<{
    type?: 'text' | 'email' | 'password' | 'url' | 'search' | 'number'
    id?: string
    invalid?: boolean
    required?: boolean
    disabled?: boolean
    placeholder?: string
    size?: 'sm' | 'md'
    /** Monospace text for IDs, dice and codes. */
    mono?: boolean
  }>(),
  { type: 'text', id: undefined, invalid: false, required: false, disabled: false, placeholder: '', size: 'md', mono: false },
)

const control = useFieldControl(props)

const classes = computed(() => [
  CONTROL_CLASS,
  controlBorder(control.invalid.value),
  props.size === 'sm' ? 'h-8 px-2.5' : 'h-9 px-3',
  props.mono ? '!font-mono' : '',
])

function handleInput(event: Event): void {
  const raw = (event.target as HTMLInputElement).value
  if (props.type !== 'number') {
    model.value = raw
    return
  }
  model.value = raw === '' ? null : Number(raw)
}
</script>

<template>
  <input
    v-bind="$attrs"
    :id="control.id.value"
    :type="type"
    :value="model ?? ''"
    :class="classes"
    :disabled="disabled"
    :placeholder="placeholder"
    :required="control.required.value"
    :aria-invalid="control.invalid.value || undefined"
    :aria-describedby="control.describedBy.value"
    @input="handleInput"
  />
</template>
