<script setup lang="ts">
import { computed, ref, watch } from 'vue'

export interface ReferenceOption {
  id: string
  name: string
  imageUrl?: string | null
  type?: string
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

function toggleOpen() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    searchText.value = ''
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

watch(
  () => props.modelValue,
  () => {
    if (!isOpen.value) return
    searchText.value = ''
  },
)
</script>

<template>
  <div class="relative">
    <button
      type="button"
      class="w-full bg-slate-900 border border-white/10 rounded px-3 py-2 text-left text-sm text-white flex items-center justify-between gap-3"
      @click="toggleOpen"
    >
      <span class="truncate">
        <template v-if="selectedOption">
          {{ selectedOption.name || selectedOption.id }} ({{ selectedOption.id }})
        </template>
        <template v-else>
          {{ placeholder || 'Select reference' }}
        </template>
      </span>
      <span class="text-slate-400 text-xs">▼</span>
    </button>

    <div v-if="isOpen" class="absolute z-[130] mt-1 w-full bg-slate-950 border border-white/10 rounded-lg shadow-2xl overflow-hidden">
      <div class="p-2 border-b border-white/10" v-if="enableSearch !== false">
        <input
          v-model="searchText"
          type="text"
          class="w-full bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm text-white"
          :placeholder="searchPlaceholder || 'Search by ID or name'"
        />
      </div>

      <div class="max-h-64 overflow-auto">
        <button
          type="button"
          class="w-full text-left px-3 py-2 text-xs text-rose-300 hover:bg-rose-500/10 border-b border-white/5"
          @click="clearSelection"
        >
          Clear selection
        </button>

        <button
          v-for="option in filteredOptions"
          :key="option.id"
          type="button"
          class="w-full px-3 py-2 text-left hover:bg-emerald-500/10 border-b border-white/5 last:border-b-0"
          @click="selectOption(option.id)"
        >
          <div class="flex items-center gap-2">
            <img
              v-if="option.imageUrl"
              :src="option.imageUrl"
              class="w-8 h-8 rounded object-cover border border-white/10"
              alt=""
            />
            <div class="min-w-0">
              <div class="text-sm text-white truncate">{{ option.name || option.id }}</div>
              <div class="text-[11px] text-slate-400 truncate">{{ option.id }}</div>
            </div>
          </div>
        </button>

        <div v-if="filteredOptions.length === 0" class="px-3 py-3 text-xs text-slate-500">
          No matching entries.
        </div>
      </div>
    </div>
  </div>
</template>
