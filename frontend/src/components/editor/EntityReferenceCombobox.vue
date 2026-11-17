<script setup lang="ts">
import { computed, nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import { CONTROL_INPUT_CLASS } from '@/components/ui/fieldContext'

export interface ReferenceOption {
  id: string
  name: string
  imageUrl?: string | null
  type?: string
  /** Optional extra line in the dropdown, e.g. the item's scene. */
  subtitle?: string
}

const props = defineProps<{
  modelValue: string
  options: ReferenceOption[]
  placeholder?: string
  searchPlaceholder?: string
  enableSearch?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const isOpen = ref(false)
const searchText = ref('')
const root = ref<HTMLElement | null>(null)
const dropdownStyle = ref<Record<string, string>>({})

const selectedOption = computed(() => {
  return props.options.find((option) => String(option.id) === String(props.modelValue || '')) || null
})

const filteredOptions = computed(() => {
  const query = searchText.value.trim().toLowerCase()
  if (!query) return props.options
  return props.options.filter((option) => {
    const id = String(option.id || '').toLowerCase()
    const name = String(option.name || '').toLowerCase()
    return id.includes(query) || name.includes(query)
  })
})

function updateDropdownPosition() {
  if (!root.value) return
  const rect = root.value.getBoundingClientRect()
  const dropdownMaxHeight = 280
  const spaceBelow = window.innerHeight - rect.bottom
  const openUpward = spaceBelow < dropdownMaxHeight && rect.top > spaceBelow
  const top = openUpward ? `${Math.max(8, rect.top - dropdownMaxHeight - 4)}px` : `${rect.bottom + 4}px`
  const left = `${rect.left}px`
  const width = `${rect.width}px`
  const maxHeight = `${Math.min(dropdownMaxHeight, openUpward ? rect.top - 12 : spaceBelow - 12)}px`
  dropdownStyle.value = {
    position: 'fixed',
    top,
    left,
    width,
    maxHeight,
    zIndex: '400',
  }
}

async function toggleOpen() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    searchText.value = ''
    await nextTick()
    updateDropdownPosition()
  }
}

function selectOption(optionId: string) {
  emit('update:modelValue', optionId)
  isOpen.value = false
  searchText.value = ''
}

function clearSelection() {
  emit('update:modelValue', '')
  searchText.value = ''
}

function handleDocumentClick(e: MouseEvent) {
  const target = e.target as Node | null
  if (!target) return
  if (root.value && root.value.contains(target)) return
  const dropdown = document.getElementById(`entity-ref-dropdown-${rootId}`)
  if (dropdown && dropdown.contains(target)) return
  isOpen.value = false
}

function handleDocumentKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    isOpen.value = false
  }
}

function handleWindowChange() {
  if (isOpen.value) updateDropdownPosition()
}

const rootId = `entity-ref-${Math.random().toString(36).slice(2, 10)}`

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
  document.addEventListener('keydown', handleDocumentKeydown)
  window.addEventListener('resize', handleWindowChange)
  window.addEventListener('scroll', handleWindowChange, true)
})

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick)
  document.removeEventListener('keydown', handleDocumentKeydown)
  window.removeEventListener('resize', handleWindowChange)
  window.removeEventListener('scroll', handleWindowChange, true)
})

watch(
  () => props.modelValue,
  () => {
    if (!isOpen.value) return
    searchText.value = ''
  },
)
</script>

<template>
  <div ref="root" class="relative w-full min-w-0" :data-ref-id="rootId">
    <button
      type="button"
      :class="[CONTROL_INPUT_CLASS, 'flex items-center justify-between gap-3 text-left']"
      :aria-expanded="isOpen"
      aria-haspopup="listbox"
      @click="toggleOpen"
    >
      <span :class="['truncate', selectedOption ? '' : 'text-wb-faint']">
        <template v-if="selectedOption">{{ selectedOption.name || selectedOption.id }} ({{ selectedOption.id }})</template>
        <template v-else>{{ placeholder || 'Select reference' }}</template>
      </span>
      <ChevronDown class="h-4 w-4 shrink-0 text-wb-muted" aria-hidden="true" />
    </button>

    <Teleport to="body">
      <div
        v-if="isOpen"
        :id="`entity-ref-dropdown-${rootId}`"
        :style="dropdownStyle"
        class="overflow-hidden rounded-md border border-wb-line-strong bg-wb-overlay font-wb shadow-wb-float"
      >
        <div v-if="enableSearch !== false" class="border-b border-wb-line p-2">
          <input
            v-model="searchText"
            type="text"
            :class="[CONTROL_INPUT_CLASS, '!h-8 !px-2.5']"
            :placeholder="searchPlaceholder || 'Search by ID or name'"
            aria-label="Search"
          />
        </div>

        <div class="max-h-60 overflow-auto" role="listbox">
          <button
            type="button"
            class="w-full border-b border-wb-line px-3 py-2 text-left wb-hint !text-wb-danger-text hover:bg-wb-danger-soft"
            @click="clearSelection"
          >
            Clear selection
          </button>

          <button
            v-for="option in filteredOptions"
            :key="option.id"
            type="button"
            role="option"
            :aria-selected="option.id === selectedOption?.id"
            class="w-full border-b border-wb-line px-3 py-2 text-left last:border-b-0 hover:bg-wb-raised focus-visible:bg-wb-raised focus-visible:outline-none"
            @click="selectOption(option.id)"
          >
            <div class="flex items-center gap-2">
              <img v-if="option.imageUrl" :src="option.imageUrl" class="h-8 w-8 rounded-md border border-wb-line object-cover" alt="" />
              <div class="min-w-0">
                <div class="wb-body truncate text-wb-strong">{{ option.name || option.id }}</div>
                <div class="wb-hint truncate">
                  {{ option.id }}<template v-if="option.subtitle"> · {{ option.subtitle }}</template>
                </div>
              </div>
            </div>
          </button>

          <p v-if="filteredOptions.length === 0" class="wb-hint px-3 py-3">No matching entries.</p>
        </div>
      </div>
    </Teleport>
  </div>
</template>
