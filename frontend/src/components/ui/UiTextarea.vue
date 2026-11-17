<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { CONTROL_CLASS, controlBorder, useFieldControl } from '@/components/ui/fieldContext'

defineOptions({ inheritAttrs: false })

const model = defineModel<string>({ default: '' })

const props = withDefaults(
  defineProps<{
    id?: string
    invalid?: boolean
    required?: boolean
    disabled?: boolean
    placeholder?: string
    rows?: number
    /** Grows with the content up to `maxRows`. */
    autoGrow?: boolean
    maxRows?: number
    mono?: boolean
  }>(),
  {
    id: undefined,
    invalid: false,
    required: false,
    disabled: false,
    placeholder: '',
    rows: 3,
    autoGrow: true,
    maxRows: 16,
    mono: false,
  },
)

const control = useFieldControl(props)
const el = ref<HTMLTextAreaElement | null>(null)

const classes = computed(() => [
  CONTROL_CLASS,
  controlBorder(control.invalid.value),
  'px-3 py-2 resize-y',
  props.mono ? 'wb-mono' : '',
])

function resize(): void {
  if (!props.autoGrow || !el.value) {
    return
  }
  const lineHeight = parseFloat(getComputedStyle(el.value).lineHeight) || 22
  el.value.style.height = 'auto'
  const max = lineHeight * props.maxRows + 16
  el.value.style.height = `${Math.min(el.value.scrollHeight, max)}px`
}

watch(model, () => nextTick(resize))
onMounted(resize)
</script>

<template>
  <textarea
    v-bind="$attrs"
    :id="control.id.value"
    ref="el"
    v-model="model"
    :rows="rows"
    :class="classes"
    :disabled="disabled"
    :placeholder="placeholder"
    :required="control.required.value"
    :aria-invalid="control.invalid.value || undefined"
    :aria-describedby="control.describedBy.value"
  />
</template>
