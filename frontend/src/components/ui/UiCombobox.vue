<script setup lang="ts">
/**
 * Free text input with a suggestion list. Unlike a native datalist, the chevron button always
 * shows every option, even when the field already holds a typed value; typing filters the list.
 */
import { computed, onBeforeUnmount, ref, useId } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { CONTROL_CLASS, controlBorder, useFieldControl } from '@/components/ui/fieldContext'

defineOptions({ inheritAttrs: false })

const model = defineModel<string>({ default: '' })

const props = withDefaults(
  defineProps<{
    options: string[]
    id?: string
    invalid?: boolean
    required?: boolean
    disabled?: boolean
    placeholder?: string
    /** Monospace text for IDs. */
    mono?: boolean
    /** Accessible name of the toggle button. */
    toggleLabel?: string
  }>(),
  { id: undefined, invalid: false, required: false, disabled: false, placeholder: '', mono: false, toggleLabel: 'Show all options' },
)

const control = useFieldControl(props)
const listId = `combobox-${useId()}`
const rootEl = ref<HTMLElement | null>(null)
const open = ref(false)
const showAll = ref(true)
const activeIndex = ref(-1)

const visibleOptions = computed(() => {
  const query = model.value.trim().toLowerCase()
  if (showAll.value || !query) return props.options
  return props.options.filter((option) => option.toLowerCase().includes(query))
})

const inputClasses = computed(() => [
  CONTROL_CLASS,
  controlBorder(control.invalid.value),
  'h-9 pl-3 pr-9',
  props.mono ? '!font-mono' : '',
])

function handleDocumentClick(event: MouseEvent): void {
  if (rootEl.value && !rootEl.value.contains(event.target as Node)) close()
}

function openList(all: boolean): void {
  showAll.value = all
  activeIndex.value = visibleOptions.value.indexOf(model.value)
  if (open.value) return
  open.value = true
  document.addEventListener('click', handleDocumentClick, true)
}

function close(): void {
  open.value = false
  activeIndex.value = -1
  document.removeEventListener('click', handleDocumentClick, true)
}

function toggle(): void {
  if (open.value) {
    close()
    return
  }
  openList(true)
  rootEl.value?.querySelector('input')?.focus()
}

function handleInput(event: Event): void {
  model.value = (event.target as HTMLInputElement).value
  openList(false)
}

function select(option: string): void {
  model.value = option
  close()
}

function move(step: number): void {
  if (!open.value) {
    openList(true)
    return
  }
  const count = visibleOptions.value.length
  if (!count) return
  activeIndex.value = (activeIndex.value + step + count) % count
  rootEl.value?.querySelector(`#${listId}-${activeIndex.value}`)?.scrollIntoView({ block: 'nearest' })
}

function handleEnter(event: KeyboardEvent): void {
  const option = visibleOptions.value[activeIndex.value]
  if (!open.value || option === undefined) return
  event.preventDefault()
  select(option)
}

function handleEscape(event: KeyboardEvent): void {
  if (!open.value) return
  event.stopPropagation()
  close()
}

onBeforeUnmount(close)
</script>

<template>
  <div ref="rootEl" class="relative w-full">
    <input
      v-bind="$attrs"
      :id="control.id.value"
      type="text"
      role="combobox"
      autocomplete="off"
      :value="model"
      :class="inputClasses"
      :disabled="disabled"
      :placeholder="placeholder"
      :required="control.required.value"
      :aria-invalid="control.invalid.value || undefined"
      :aria-describedby="control.describedBy.value"
      :aria-expanded="open"
      :aria-controls="listId"
      :aria-activedescendant="open && activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined"
      aria-autocomplete="list"
      @input="handleInput"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter="handleEnter"
      @keydown.esc="handleEscape"
      @keydown.tab="close"
    />
    <button
      type="button"
      tabindex="-1"
      :aria-label="toggleLabel"
      :disabled="disabled || !options.length"
      class="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-md text-wb-muted transition-colors hover:text-wb-strong disabled:opacity-40 disabled:cursor-not-allowed"
      @click="toggle"
    >
      <ChevronDown :class="['h-4 w-4 transition-transform', open ? 'rotate-180' : '']" aria-hidden="true" />
    </button>
    <ul
      v-if="open && visibleOptions.length"
      :id="listId"
      role="listbox"
      class="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-y-auto rounded-xl border border-wb-line-strong bg-wb-overlay py-1 shadow-wb-float font-wb"
    >
      <li
        v-for="(option, index) in visibleOptions"
        :id="`${listId}-${index}`"
        :key="option"
        role="option"
        :aria-selected="option === model"
        :class="[
          'cursor-pointer truncate px-3 py-1.5 wb-body transition-colors',
          mono ? '!font-mono' : '',
          index === activeIndex ? 'bg-wb-raised text-wb-strong' : 'text-wb-body hover:bg-wb-raised hover:text-wb-strong',
          option === model ? 'text-wb-accent-text' : '',
        ]"
        @mousedown.prevent="select(option)"
      >
        {{ option }}
      </li>
    </ul>
  </div>
</template>
