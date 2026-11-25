<script setup lang="ts">
/**
 * Multi-select combobox: shows selected items in the input summary, filters suggestions on type,
 * toggles options via checkboxes, and lets the user add new custom values.
 */
import { computed, onBeforeUnmount, ref, useId } from 'vue'
import { Check, ChevronDown, Plus } from 'lucide-vue-next'
import { CONTROL_CLASS, controlBorder, useFieldControl } from '@/components/ui/fieldContext'

defineOptions({ inheritAttrs: false })

const model = defineModel<string[]>({ default: () => [] })

const props = withDefaults(
  defineProps<{
    options: string[]
    id?: string
    invalid?: boolean
    disabled?: boolean
    placeholder?: string
    allowCustom?: boolean
    toggleLabel?: string
  }>(),
  {
    id: undefined,
    invalid: false,
    disabled: false,
    placeholder: 'Select...',
    allowCustom: true,
    toggleLabel: 'Show all options',
  },
)

const control = useFieldControl(props)
const listId = `multicombobox-${useId()}`
const rootEl = ref<HTMLElement | null>(null)
const open = ref(false)
const query = ref('')

const allOptions = computed(() => {
  const seen = new Set<string>()
  const merged: string[] = []
  for (const item of [...props.options, ...(model.value || [])]) {
    const clean = item.trim()
    if (clean && !seen.has(clean)) {
      seen.add(clean)
      merged.push(clean)
    }
  }
  return merged
})

const visibleOptions = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return allOptions.value
  return allOptions.value.filter((opt) => opt.toLowerCase().includes(q))
})

const canAddCustom = computed(() => {
  if (!props.allowCustom) return false
  const q = query.value.trim()
  if (!q) return false
  return !allOptions.value.some((opt) => opt.toLowerCase() === q.toLowerCase())
})

const displayValue = computed(() => {
  if (open.value) return query.value
  return (model.value || []).join(', ')
})

const inputClasses = computed(() => [
  CONTROL_CLASS,
  controlBorder(control.invalid.value),
  'h-9 pl-3 pr-9',
])

function isSelected(option: string): boolean {
  return (model.value || []).includes(option)
}

function toggleOption(option: string): void {
  const current = [...(model.value || [])]
  const idx = current.indexOf(option)
  if (idx >= 0) current.splice(idx, 1)
  else current.push(option)
  model.value = current
}

function addCustom(): void {
  const q = query.value.trim()
  if (!q) return
  if (!isSelected(q)) model.value = [...(model.value || []), q]
  query.value = ''
}

function handleDocumentClick(event: MouseEvent): void {
  if (rootEl.value && !rootEl.value.contains(event.target as Node)) close()
}

function openList(): void {
  if (open.value) return
  query.value = ''
  open.value = true
  document.addEventListener('click', handleDocumentClick, true)
}

function close(): void {
  open.value = false
  query.value = ''
  document.removeEventListener('click', handleDocumentClick, true)
}

function toggle(): void {
  if (open.value) {
    close()
    return
  }
  openList()
  rootEl.value?.querySelector('input')?.focus()
}

function handleInput(event: Event): void {
  query.value = (event.target as HTMLInputElement).value
  if (!open.value) openList()
}

onBeforeUnmount(() => document.removeEventListener('click', handleDocumentClick, true))
</script>

<template>
  <div ref="rootEl" class="relative">
    <input
      :id="control.id.value"
      v-bind="$attrs"
      type="text"
      role="combobox"
      autocomplete="off"
      :value="displayValue"
      :disabled="disabled"
      :placeholder="placeholder"
      :aria-expanded="open"
      :aria-controls="listId"
      aria-autocomplete="list"
      :class="inputClasses"
      @focus="openList"
      @input="handleInput"
      @keydown.enter.prevent="canAddCustom ? addCustom() : undefined"
      @keydown.escape="close"
    />
    <button
      type="button"
      tabindex="-1"
      :disabled="disabled"
      :aria-label="toggleLabel"
      class="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-lg text-wb-muted transition-colors hover:text-wb-ink focus-visible:outline-none disabled:pointer-events-none"
      @mousedown.prevent
      @click="toggle"
    >
      <ChevronDown class="h-4 w-4 transition-transform" :class="{ 'rotate-180': open }" aria-hidden="true" />
    </button>
    <ul
      v-if="open"
      :id="listId"
      role="listbox"
      aria-multiselectable="true"
      class="absolute left-0 right-0 z-30 mt-1 max-h-56 overflow-y-auto rounded-lg border border-wb-line-strong bg-wb-elevated p-1 shadow-xl"
    >
      <li
        v-for="option in visibleOptions"
        :key="option"
        role="option"
        :aria-selected="isSelected(option)"
        class="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-sm transition-colors hover:bg-wb-surface"
        :class="isSelected(option) ? 'text-wb-strong font-medium' : 'text-wb-ink'"
        @mousedown.prevent
        @click="toggleOption(option)"
      >
        <span
          class="flex h-4 w-4 shrink-0 items-center justify-center rounded border"
          :class="isSelected(option) ? 'border-wb-accent bg-wb-accent text-wb-on-accent' : 'border-wb-line-strong'"
        >
          <Check v-if="isSelected(option)" class="h-3 w-3" aria-hidden="true" />
        </span>
        <span class="truncate">{{ option }}</span>
      </li>
      <li
        v-if="canAddCustom"
        role="option"
        aria-selected="false"
        class="flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-wb-accent transition-colors hover:bg-wb-surface"
        @mousedown.prevent
        @click="addCustom"
      >
        <Plus class="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span class="truncate">Add "{{ query.trim() }}"</span>
      </li>
      <li v-if="!visibleOptions.length && !canAddCustom" class="px-2.5 py-1.5 text-xs text-wb-muted">
        No categories available. Type to add one.
      </li>
    </ul>
  </div>
</template>
