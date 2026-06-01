<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

interface ReferenceOption {
  id: string
  name?: string
  imageUrl?: string | null
}

const props = defineProps<{
  modelValue: string
  rows?: number
  maxlength?: number
  placeholder?: string
  className?: string
  options: ReferenceOption[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const textAreaRef = ref<HTMLTextAreaElement | null>(null)
const suggestStartIndex = ref<number | null>(null)
const suggestQuery = ref('')
const activeSuggestionIndex = ref(0)
const dismissUntilInputChange = ref(false)
const popupPosition = ref({ top: 0, left: 0, width: 320, placeAbove: false })
const popupId = `reference-suggest-${Math.random().toString(36).slice(2, 10)}`
const repositionPopup = () => {
  if (!isSuggestionOpen.value) return
  updatePopupPosition()
}

const isSuggestionOpen = computed(() => suggestStartIndex.value !== null)

const filteredOptions = computed(() => {
  if (suggestStartIndex.value === null) return []
  const query = suggestQuery.value.trim().toLowerCase()
  if (!query) return props.options.slice(0, 20)
  return props.options
    .filter((option) => {
      const id = String(option.id || '').toLowerCase()
      const name = String(option.name || '').toLowerCase()
      return id.includes(query) || name.includes(query)
    })
    .slice(0, 20)
})

function updateSuggestState(value: string, cursorIndex: number) {
  const prefix = value.slice(0, cursorIndex)
  const markerIndex = prefix.lastIndexOf('##')
  if (markerIndex === -1) {
    suggestStartIndex.value = null
    suggestQuery.value = ''
    return
  }

  const between = prefix.slice(markerIndex + 2)
  if (between.includes(' ') || between.includes('\n') || between.includes('\t')) {
    suggestStartIndex.value = null
    suggestQuery.value = ''
    return
  }

  suggestStartIndex.value = markerIndex
  suggestQuery.value = between
}

function updatePopupPosition() {
  const area = textAreaRef.value
  if (!area) return

  const rect = area.getBoundingClientRect()
  const viewportPadding = 8
  const popupGap = 8
  const estimatedPopupHeight = 260

  let left = rect.left
  if (left < viewportPadding) left = viewportPadding

  let width = rect.width
  const maxWidth = window.innerWidth - viewportPadding * 2
  if (width > maxWidth) width = maxWidth
  if (left + width > window.innerWidth - viewportPadding) {
    left = Math.max(viewportPadding, window.innerWidth - viewportPadding - width)
  }

  const spaceBelow = window.innerHeight - rect.bottom
  const placeAbove = spaceBelow < estimatedPopupHeight && rect.top > spaceBelow
  const top = placeAbove ? rect.top - popupGap : rect.bottom + popupGap

  popupPosition.value = {
    top,
    left,
    width,
    placeAbove,
  }
}

function handleInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  const nextValue = target.value
  emit('update:modelValue', nextValue)
  dismissUntilInputChange.value = false
  updateSuggestState(nextValue, target.selectionStart || 0)
}

function handleCaretInteraction(event: Event) {
  if (dismissUntilInputChange.value) return
  const target = event.target as HTMLTextAreaElement
  updateSuggestState(target.value, target.selectionStart || 0)
}

function applyOption(optionId: string) {
  const area = textAreaRef.value
  if (!area || suggestStartIndex.value === null) return

  const value = props.modelValue || ''
  const cursor = area.selectionStart || 0
  const before = value.slice(0, suggestStartIndex.value)
  const after = value.slice(cursor)
  const inserted = `##${optionId}`
  const nextValue = `${before}${inserted}${after}`

  emit('update:modelValue', nextValue)
  suggestStartIndex.value = null
  suggestQuery.value = ''

  requestAnimationFrame(() => {
    const nextCursor = before.length + inserted.length
    area.focus()
    area.selectionStart = nextCursor
    area.selectionEnd = nextCursor
  })
}

function moveActiveSuggestion(direction: 1 | -1) {
  const options = filteredOptions.value
  if (options.length === 0) return

  const maxIndex = options.length - 1
  const nextIndex = activeSuggestionIndex.value + direction
  if (nextIndex < 0) {
    activeSuggestionIndex.value = maxIndex
  } else if (nextIndex > maxIndex) {
    activeSuggestionIndex.value = 0
  } else {
    activeSuggestionIndex.value = nextIndex
  }
}

function confirmActiveSuggestion() {
  const options = filteredOptions.value
  if (options.length === 0) return
  const safeIndex = Math.min(Math.max(activeSuggestionIndex.value, 0), options.length - 1)
  const selected = options[safeIndex]
  if (!selected) return
  applyOption(selected.id)
}

function closeSuggestions(dismissUntilChange = false) {
  suggestStartIndex.value = null
  suggestQuery.value = ''
  activeSuggestionIndex.value = 0
  if (dismissUntilChange) {
    dismissUntilInputChange.value = true
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (isSuggestionOpen.value && event.key === 'ArrowDown') {
    event.preventDefault()
    moveActiveSuggestion(1)
    return
  }

  if (isSuggestionOpen.value && event.key === 'ArrowUp') {
    event.preventDefault()
    moveActiveSuggestion(-1)
    return
  }

  if (isSuggestionOpen.value && event.key === 'Enter') {
    event.preventDefault()
    confirmActiveSuggestion()
    return
  }

  if (isSuggestionOpen.value && event.key === 'Tab' && !event.shiftKey) {
    event.preventDefault()
    confirmActiveSuggestion()
    return
  }

  if (event.key === 'Escape') {
    event.preventDefault()
    closeSuggestions(true)
  }
}

watch(isSuggestionOpen, async (open) => {
  if (!open) return
  activeSuggestionIndex.value = 0
  await nextTick()
  updatePopupPosition()
})

watch(filteredOptions, (options) => {
  if (options.length === 0) {
    activeSuggestionIndex.value = 0
    return
  }
  if (activeSuggestionIndex.value >= options.length) {
    activeSuggestionIndex.value = options.length - 1
  }
})

watch(activeSuggestionIndex, async (index) => {
  if (!isSuggestionOpen.value) return
  await nextTick()
  const optionEl = document.querySelector(`#${popupId} [data-suggestion-index="${index}"]`) as HTMLElement | null
  optionEl?.scrollIntoView({ block: 'nearest' })
})

onMounted(() => {
  window.addEventListener('resize', repositionPopup)
  window.addEventListener('scroll', repositionPopup, true)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', repositionPopup)
  window.removeEventListener('scroll', repositionPopup, true)
})
</script>

<template>
  <div class="relative">
    <textarea
      ref="textAreaRef"
      :value="modelValue"
      :rows="rows || 3"
      :maxlength="maxlength"
      :placeholder="placeholder"
      :class="className || 'w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner'"
      @input="handleInput"
      @click="handleCaretInteraction"
      @keyup="handleCaretInteraction"
      @keydown="handleKeydown"
      @blur="setTimeout(closeSuggestions, 120)"
    />

    <Teleport to="body">
      <div
        v-if="isSuggestionOpen"
        :id="popupId"
        class="fixed z-[4000] bg-slate-950 border border-white/10 rounded-lg shadow-2xl overflow-hidden"
        :style="{
          top: `${popupPosition.top}px`,
          left: `${popupPosition.left}px`,
          width: `${popupPosition.width}px`,
          transform: popupPosition.placeAbove ? 'translateY(-100%)' : 'none',
        }"
      >
        <div class="px-3 py-2 text-[11px] text-slate-400 border-b border-white/10">
          Insert reference with ##OBJECT_ID
        </div>
        <div class="max-h-56 overflow-auto">
          <button
            v-for="(option, index) in filteredOptions"
            :key="option.id"
            type="button"
            class="w-full text-left px-3 py-2 border-b border-white/5 last:border-b-0"
            :class="index === activeSuggestionIndex ? 'bg-emerald-500/20' : 'hover:bg-emerald-500/10'"
            :data-suggestion-index="index"
            @mousedown.prevent="applyOption(option.id)"
            @mouseenter="activeSuggestionIndex = index"
          >
            <div class="flex items-center gap-2">
              <img
                v-if="option.imageUrl"
                :src="option.imageUrl"
                class="w-6 h-6 rounded object-cover border border-white/10"
                alt=""
              />
              <div class="min-w-0">
                <div class="text-xs text-white truncate">{{ option.name || option.id }}</div>
                <div class="text-[11px] text-slate-400 truncate">{{ option.id }}</div>
              </div>
            </div>
          </button>
          <div v-if="filteredOptions.length === 0" class="px-3 py-3 text-xs text-slate-500">
            No matching IDs.
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
