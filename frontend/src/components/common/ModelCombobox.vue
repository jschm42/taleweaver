<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronDown, RefreshCw } from 'lucide-vue-next'
import type { ModelKind } from '@/composables/useApi'
import { getProviderModelsEntry, loadProviderModels, providerModelsKey } from '@/store/providerModels'

/**
 * Model picker backed by live provider discovery. Typing filters the list; any value
 * can still be entered manually (new or private models).
 */
const model = defineModel<string>({ required: true })

const props = withDefaults(defineProps<{
  provider: string
  kind: ModelKind
  baseUrl?: string
  inputId?: string
  placeholder?: string
  inputClass?: string
}>(), {
  baseUrl: '',
  inputId: undefined,
  placeholder: 'Choose or type a model ID',
  inputClass: 'w-full bg-slate-950 border border-slate-800 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white font-mono outline-none focus:ring-2 focus:ring-purple-500/50',
})

const MAX_OPTIONS = 200
const BASE_URL_DEBOUNCE_MS = 600

const containerEl = ref<HTMLElement | null>(null)
const isRightAligned = ref(false)
const isOpen = ref(false)
const filter = ref('')
const activeIndex = ref(-1)
const listId = `model-list-${Math.random().toString(36).slice(2, 9)}`
let debounceTimer: ReturnType<typeof setTimeout> | undefined
let blurTimer: ReturnType<typeof setTimeout> | undefined

const entry = computed(() => getProviderModelsEntry(providerModelsKey(props.provider, props.kind, props.baseUrl)))
const models = computed(() => entry.value?.list?.models ?? [])
const isLoading = computed((): boolean => entry.value?.status === 'loading')

const filtered = computed(() => {
  const needle = filter.value.trim().toLowerCase()
  const matches = needle
    ? models.value.filter((m) => m.id.toLowerCase().includes(needle) || m.label.toLowerCase().includes(needle))
    : models.value
  return matches.slice(0, MAX_OPTIONS)
})

const isUnlisted = computed((): boolean => {
  const list = entry.value?.list
  if (!model.value || list?.source !== 'live') {
    return false
  }
  return !list.models.some((m) => m.id === model.value)
})

const selectedModelLabel = computed((): string | undefined => {
  if (!model.value) return undefined
  const match = models.value.find((m) => m.id === model.value)
  if (!match || !match.label) return undefined
  const cleanId = match.id.trim().toLowerCase()
  const cleanLabel = match.label.trim().toLowerCase()
  if (cleanLabel === cleanId) return undefined
  const baseName = cleanId.replace(/^.*[/\\]/, '')
  return cleanLabel !== baseName ? match.label : undefined
})

const inputTooltip = computed((): string => {
  if (!model.value) return ''
  return selectedModelLabel.value
    ? `${model.value} (${selectedModelLabel.value})`
    : model.value
})

const status = computed((): { tone: 'muted' | 'warn'; text: string } => {
  const current = entry.value
  if (!current || current.status === 'loading') {
    return { tone: 'muted', text: 'Loading models…' }
  }
  if (current.status === 'error' || !current.list) {
    return { tone: 'warn', text: current.requestError }
  }
  const { source, error } = current.list
  const count = current.list.models.length
  if (source === 'live') {
    return { tone: 'muted', text: `${count} models available from the provider.` }
  }
  if (source === 'static') {
    return { tone: 'muted', text: 'Built-in list — this provider offers no model listing.' }
  }
  return { tone: 'warn', text: `Live list unavailable: ${error} Showing built-in defaults.` }
})

function updateAlignment(): void {
  if (!containerEl.value) return
  const rect = containerEl.value.getBoundingClientRect()
  isRightAligned.value = rect.left + rect.width / 2 > window.innerWidth / 2
}

function load(refresh = false): void {
  if (props.provider) {
    loadProviderModels(props.provider, props.kind, { baseUrl: props.baseUrl, refresh })
  }
}

function open(): void {
  clearTimeout(blurTimer)
  filter.value = ''
  isOpen.value = true
  updateAlignment()

  const currentIndex = filtered.value.findIndex((m) => m.id === model.value)
  activeIndex.value = currentIndex >= 0 ? currentIndex : -1
  if (currentIndex >= 0) {
    setTimeout(() => {
      const activeEl = document.getElementById(`${listId}-${currentIndex}`)
      activeEl?.scrollIntoView({ block: 'nearest' })
    }, 0)
  }
}

function onBlur(): void {
  blurTimer = setTimeout(() => {
    isOpen.value = false
  }, 150)
}

function onInput(event: Event): void {
  model.value = (event.target as HTMLInputElement).value
  filter.value = model.value
  activeIndex.value = -1
  isOpen.value = true
  updateAlignment()
}

function choose(id: string): void {
  clearTimeout(blurTimer)
  model.value = id
  isOpen.value = false
}

function move(step: number): void {
  if (!isOpen.value) {
    open()
    return
  }
  const count = filtered.value.length
  if (count === 0) {
    return
  }
  activeIndex.value = (activeIndex.value + step + count) % count
  const activeEl = document.getElementById(`${listId}-${activeIndex.value}`)
  activeEl?.scrollIntoView({ block: 'nearest' })
}

function onEnter(event: KeyboardEvent): void {
  if (!isOpen.value) {
    return
  }
  const option = filtered.value[activeIndex.value]
  if (option) {
    event.preventDefault()
    choose(option.id)
  } else {
    isOpen.value = false
  }
}

interface PathParts {
  prefix: string
  name: string
}

function splitPath(id: string): PathParts {
  const lastSlash = Math.max(id.lastIndexOf('/'), id.lastIndexOf('\\'))
  if (lastSlash === -1 || lastSlash === id.length - 1) {
    return { prefix: '', name: id }
  }
  return {
    prefix: id.slice(0, lastSlash + 1),
    name: id.slice(lastSlash + 1),
  }
}

function hasDistinctLabel(option: { id: string; label?: string }): boolean {
  if (!option.label) return false
  const cleanId = option.id.trim().toLowerCase()
  const cleanLabel = option.label.trim().toLowerCase()
  if (cleanLabel === cleanId) return false
  const baseName = cleanId.replace(/^.*[/\\]/, '')
  return cleanLabel !== baseName
}

function formatTooltip(option: { id: string; label?: string }): string {
  if (hasDistinctLabel(option)) {
    return `${option.id}\n(${option.label})`
  }
  return option.id
}

watch(() => [props.provider, props.kind] as const, () => load(), { immediate: true })
watch(() => props.baseUrl, () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => load(), BASE_URL_DEBOUNCE_MS)
})

onMounted(() => {
  updateAlignment()
  window.addEventListener('resize', updateAlignment)
})

onBeforeUnmount(() => {
  clearTimeout(debounceTimer)
  clearTimeout(blurTimer)
  window.removeEventListener('resize', updateAlignment)
})
</script>

<template>
  <div class="space-y-1.5">
    <div ref="containerEl" class="relative">
      <input
        :id="props.inputId"
        :value="model"
        type="text"
        role="combobox"
        autocomplete="off"
        spellcheck="false"
        :aria-expanded="isOpen"
        :aria-controls="listId"
        :aria-activedescendant="activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined"
        :placeholder="props.placeholder"
        :title="inputTooltip"
        :class="props.inputClass"
        @focus="open"
        @blur="onBlur"
        @input="onInput"
        @keydown.down.prevent="move(1)"
        @keydown.up.prevent="move(-1)"
        @keydown.enter="onEnter"
        @keydown.esc="isOpen = false"
      />
      <ChevronDown class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />

      <!-- Dropdown list with smart positioning and generous width for long model paths -->
      <ul
        v-if="isOpen && filtered.length > 0"
        :id="listId"
        role="listbox"
        class="absolute z-40 mt-1 max-h-80 overflow-y-auto rounded-xl border border-white/10 bg-[#0a111c] shadow-2xl py-1 divide-y divide-white/[0.04] left-0 w-full min-w-full sm:w-max sm:min-w-[460px] md:min-w-[520px] max-w-[calc(100vw-2rem)] sm:max-w-xl md:max-w-2xl"
        :class="isRightAligned ? 'sm:right-0 sm:left-auto' : 'sm:left-0 sm:right-auto'"
        @mousedown.prevent
      >
        <li
          v-for="(option, index) in filtered"
          :id="`${listId}-${index}`"
          :key="option.id"
          role="option"
          :aria-selected="option.id === model"
          class="px-3.5 py-2 cursor-pointer flex flex-col gap-0.5 transition-colors"
          :class="[
            index === activeIndex
              ? 'bg-purple-600/25 text-white'
              : option.id === model
              ? 'bg-purple-500/10 text-white'
              : 'hover:bg-white/5 text-slate-200'
          ]"
          :title="formatTooltip(option)"
          @mousedown.prevent="choose(option.id)"
        >
          <div class="flex items-start justify-between gap-2 min-w-0">
            <div class="min-w-0 flex-1">
              <div class="text-xs sm:text-sm font-mono break-all leading-snug">
                <span v-if="splitPath(option.id).prefix" class="text-slate-400 font-normal">
                  {{ splitPath(option.id).prefix }}
                </span>
                <span class="font-medium text-slate-100">
                  {{ splitPath(option.id).name }}
                </span>
              </div>
              <div
                v-if="hasDistinctLabel(option)"
                class="text-[11px] text-slate-400 mt-0.5 break-words line-clamp-1 leading-tight"
              >
                {{ option.label }}
              </div>
            </div>
            <span
              v-if="option.id === model"
              class="shrink-0 text-[10px] font-mono font-bold text-purple-300 bg-purple-500/20 px-1.5 py-0.5 rounded border border-purple-500/30"
            >
              active
            </span>
          </div>
        </li>
      </ul>

      <!-- Informative hint when filter has no matches -->
      <div
        v-else-if="isOpen && filter.trim().length > 0"
        class="absolute z-40 mt-1 rounded-xl border border-white/10 bg-[#0a111c] shadow-2xl p-3 text-xs text-slate-400 left-0 w-full min-w-full sm:min-w-[360px]"
        :class="isRightAligned ? 'sm:right-0 sm:left-auto' : 'sm:left-0 sm:right-auto'"
        @mousedown.prevent
      >
        No matching models for "<span class="text-white font-mono break-all">{{ filter }}</span>". Custom model ID will be used.
      </div>
    </div>

    <!-- Status row with count, reload button, and active model display name -->
    <div class="space-y-1">
      <div class="flex items-start justify-between gap-3">
        <p class="text-[11px] leading-snug" :class="status.tone === 'warn' ? 'text-amber-400' : 'text-slate-500'">
          {{ status.text }}
          <span v-if="isUnlisted" class="block text-amber-400 break-all">
            "{{ model }}" is not in the provider's list — it will be used as entered.
          </span>
        </p>
        <button
          type="button"
          class="shrink-0 flex items-center gap-1 text-[11px] text-slate-400 hover:text-white disabled:opacity-40"
          title="Reload the model list from the provider"
          :disabled="isLoading || !props.provider"
          @click="load(true)"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
          Reload
        </button>
      </div>
      <p
        v-if="selectedModelLabel && !isUnlisted"
        class="text-[11px] text-slate-400 truncate"
        :title="selectedModelLabel"
      >
        <span class="text-slate-500 font-semibold uppercase text-[10px] tracking-wider">Model:</span>
        <span class="text-slate-300 ml-1.5 font-medium">{{ selectedModelLabel }}</span>
      </p>
    </div>
  </div>
</template>
