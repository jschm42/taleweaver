<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ChevronDown, ChevronRight, ChevronUp, Replace, ReplaceAll, X } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    currentMatchIndex: number
    totalMatches: number
    limitReached?: boolean
    error?: string | null
    canReplace?: boolean
  }>(),
  {
    limitReached: false,
    error: null,
    canReplace: true
  }
)

const emit = defineEmits<{
  (e: 'next'): void
  (e: 'prev'): void
  (e: 'replace'): void
  (e: 'replace-all'): void
  (e: 'close'): void
}>()

const query = defineModel<string>('query', { required: true })
const replaceText = defineModel<string>('replaceText', { required: true })
const matchCase = defineModel<boolean>('matchCase', { required: true })
const wholeWord = defineModel<boolean>('wholeWord', { required: true })
const useRegex = defineModel<boolean>('useRegex', { required: true })

const searchInput = ref<HTMLInputElement | null>(null)
const showReplace = ref(false)

const hasMatches = computed(() => props.totalMatches > 0)

const matchLabel = computed(() => {
  if (props.error) return 'Invalid regex'
  if (!hasMatches.value) return 'No results'
  const total = props.limitReached ? `${props.totalMatches}+` : String(props.totalMatches)
  return `${props.currentMatchIndex + 1} of ${total}`
})

const toggles = computed(() => [
  { key: 'case', label: 'Aa', title: 'Match case', model: matchCase },
  { key: 'word', label: '\\b', title: 'Match whole word', model: wholeWord },
  { key: 'regex', label: '.*', title: 'Use regular expression', model: useRegex }
])

function focusSearch() {
  searchInput.value?.focus()
  searchInput.value?.select()
}

function onSearchKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter') return
  e.preventDefault()
  emit(e.shiftKey ? 'prev' : 'next')
}

function onReplaceKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter') return
  e.preventDefault()
  emit(e.ctrlKey || e.metaKey ? 'replace-all' : 'replace')
}

function onBarKeydown(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  e.preventDefault()
  e.stopPropagation()
  emit('close')
}

onMounted(() => nextTick(focusSearch))

defineExpose({ focusSearch })
</script>

<template>
  <div
    class="absolute top-2 right-3 z-30 flex items-start gap-1 p-1.5 rounded-xl border border-white/10 bg-slate-900/95 shadow-2xl backdrop-blur-sm font-sans"
    role="search"
    @keydown="onBarKeydown"
  >
    <button
      v-if="canReplace"
      type="button"
      class="p-1 mt-0.5 rounded text-slate-400 hover:text-white hover:bg-white/5"
      :title="showReplace ? 'Hide replace' : 'Show replace'"
      @click="showReplace = !showReplace"
    >
      <ChevronDown v-if="showReplace" class="w-3.5 h-3.5" />
      <ChevronRight v-else class="w-3.5 h-3.5" />
    </button>

    <div class="flex flex-col gap-1">
      <!-- Search row -->
      <div class="flex items-center gap-1">
        <div
          :class="[
            'flex items-center w-56 rounded-lg border bg-slate-950/80 pr-1',
            error ? 'border-rose-500/60' : 'border-white/10 focus-within:border-amber-500/50'
          ]"
        >
          <input
            ref="searchInput"
            v-model="query"
            type="text"
            placeholder="Find"
            spellcheck="false"
            aria-label="Find in script"
            class="flex-1 min-w-0 bg-transparent px-2 py-1 text-[11px] font-mono text-slate-200 focus:outline-none"
            @keydown="onSearchKeydown"
          />
          <button
            v-for="toggle in toggles"
            :key="toggle.key"
            type="button"
            :title="toggle.title"
            :aria-pressed="toggle.model.value"
            :class="[
              'px-1 py-0.5 rounded text-[10px] font-mono font-bold border transition-colors',
              toggle.model.value
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'text-slate-500 border-transparent hover:text-slate-200 hover:bg-white/5'
            ]"
            @click="toggle.model.value = !toggle.model.value"
          >
            {{ toggle.label }}
          </button>
        </div>

        <span
          v-if="query"
          :class="[
            'min-w-[64px] text-center text-[10px] font-mono whitespace-nowrap',
            hasMatches ? 'text-slate-400' : 'text-rose-400'
          ]"
          :title="error || undefined"
        >
          {{ matchLabel }}
        </span>

        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30"
          title="Previous match (Shift+Enter)"
          :disabled="!hasMatches"
          @click="emit('prev')"
        >
          <ChevronUp class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30"
          title="Next match (Enter)"
          :disabled="!hasMatches"
          @click="emit('next')"
        >
          <ChevronDown class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-rose-300 hover:bg-rose-500/10"
          title="Close (Escape)"
          @click="emit('close')"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Replace row -->
      <div v-if="canReplace && showReplace" class="flex items-center gap-1">
        <input
          v-model="replaceText"
          type="text"
          placeholder="Replace"
          spellcheck="false"
          aria-label="Replace with"
          class="w-56 rounded-lg border border-white/10 bg-slate-950/80 px-2 py-1 text-[11px] font-mono text-slate-200 focus:outline-none focus:border-amber-500/50"
          @keydown="onReplaceKeydown"
        />
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30"
          title="Replace (Enter)"
          :disabled="!hasMatches"
          @click="emit('replace')"
        >
          <Replace class="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          class="p-1 rounded text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30"
          title="Replace all (Ctrl+Enter)"
          :disabled="!hasMatches"
          @click="emit('replace-all')"
        >
          <ReplaceAll class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  </div>
</template>
