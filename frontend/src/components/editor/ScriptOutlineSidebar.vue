<script setup lang="ts">
// Right-hand outline of the functions defined in a script. Collapses to a narrow rail;
// clicking an entry emits `select` so the parent editor can jump to its line.
import { computed, ref } from 'vue'
import { ChevronsLeft, ChevronsRight, ListTree, Search, X } from 'lucide-vue-next'
import type { OutlineFunction } from '@/types/scriptOutline'

const props = withDefaults(
  defineProps<{
    functions?: OutlineFunction[]
    activeLine?: number
    collapsed?: boolean
  }>(),
  {
    functions: () => [],
    activeLine: 1,
    collapsed: false
  }
)

const emit = defineEmits<{
  (e: 'select', fn: OutlineFunction): void
  (e: 'update:collapsed', collapsed: boolean): void
  (e: 'close'): void
}>()

const query = ref('')

const normalizedQuery = computed(() => query.value.trim().toLowerCase())

function matchesQuery(fn: OutlineFunction, needle: string): boolean {
  if (!needle) {
    return true
  }
  const haystack = [fn.name, fn.scope ?? '', fn.params].join(' ').toLowerCase()
  return haystack.includes(needle)
}

const filteredFunctions = computed(() =>
  props.functions.filter((fn) => matchesQuery(fn, normalizedQuery.value))
)

const emptyMessage = computed(() =>
  props.functions.length === 0 ? 'No functions defined in this script.' : 'No functions match the filter.'
)

function docSummary(fn: OutlineFunction): string {
  if (!fn.docstring) {
    return ''
  }
  return fn.docstring.trim().split('\n')[0] ?? ''
}

function entryTooltip(fn: OutlineFunction): string {
  const signature = `${fn.scope ? `${fn.scope}.` : ''}${fn.name}(${fn.params})`
  const doc = fn.docstring?.trim()
  return doc ? `${signature}\n\n${doc}` : signature
}

function isActive(fn: OutlineFunction): boolean {
  return fn.line === props.activeLine
}

function entryKey(fn: OutlineFunction): string {
  return `${fn.scope ?? ''}.${fn.name}:${fn.line}:${fn.column}`
}

function setCollapsed(value: boolean) {
  emit('update:collapsed', value)
}

function clearQuery() {
  query.value = ''
}
</script>

<template>
  <aside
    class="flex flex-col shrink-0 h-full bg-slate-900/95 border-l border-white/10 transition-[width] duration-200"
    :class="props.collapsed ? 'w-9' : 'w-64 md:w-72'"
    aria-label="Script outline"
  >
    <!-- Collapsed mini rail -->
    <div v-if="props.collapsed" class="flex flex-col items-center gap-3 py-2">
      <button
        type="button"
        class="p-1 rounded-md text-slate-400 hover:text-amber-400 hover:bg-white/5 transition-colors"
        title="Expand outline"
        aria-label="Expand outline"
        @click="setCollapsed(false)"
      >
        <ChevronsLeft class="w-4 h-4" />
      </button>
      <ListTree class="w-4 h-4 text-slate-500" aria-hidden="true" />
      <span
        class="px-1 py-0.5 rounded bg-amber-500/15 text-[10px] font-bold text-amber-400"
        :title="`${props.functions.length} functions`"
      >
        {{ props.functions.length }}
      </span>
    </div>

    <template v-else>
      <!-- Header -->
      <div class="flex items-center gap-2 px-3 py-2 border-b border-white/10">
        <ListTree class="w-4 h-4 text-amber-400 shrink-0" aria-hidden="true" />
        <span class="text-xs font-black uppercase tracking-[0.2em] text-amber-400">Functions</span>
        <span class="px-1.5 py-0.5 rounded-full bg-amber-500/15 text-[10px] font-bold text-amber-300">
          {{ filteredFunctions.length }}<template v-if="normalizedQuery">/{{ props.functions.length }}</template>
        </span>
        <div class="ml-auto flex items-center gap-1">
          <button
            type="button"
            class="p-1 rounded-md text-slate-400 hover:text-amber-400 hover:bg-white/5 transition-colors"
            title="Collapse outline"
            aria-label="Collapse outline"
            @click="setCollapsed(true)"
          >
            <ChevronsRight class="w-4 h-4" />
          </button>
          <button
            type="button"
            class="p-1 rounded-md text-slate-400 hover:text-red-400 hover:bg-white/5 transition-colors"
            title="Close outline"
            aria-label="Close outline"
            @click="emit('close')"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- Filter -->
      <div class="px-3 py-2 border-b border-white/10">
        <div class="relative">
          <Search class="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" aria-hidden="true" />
          <input
            v-model="query"
            type="text"
            placeholder="Filter by name, scope or params..."
            aria-label="Filter functions"
            class="w-full pl-7 pr-7 py-1.5 rounded-lg bg-black/40 border border-white/10 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-amber-500/50"
            @keydown.esc="clearQuery"
          />
          <button
            v-if="query"
            type="button"
            class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-500 hover:text-slate-200"
            title="Clear filter"
            aria-label="Clear filter"
            @click="clearQuery"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <!-- Function list -->
      <ul v-if="filteredFunctions.length" class="flex-1 overflow-y-auto py-1">
        <li v-for="fn in filteredFunctions" :key="entryKey(fn)">
          <button
            type="button"
            class="w-full text-left px-3 py-1.5 border-l-2 transition-colors"
            :class="
              isActive(fn)
                ? 'border-emerald-400 bg-emerald-500/10'
                : 'border-transparent hover:bg-white/5 hover:border-amber-500/40'
            "
            :title="entryTooltip(fn)"
            :aria-current="isActive(fn) ? 'true' : undefined"
            @click="emit('select', fn)"
          >
            <div class="flex items-center gap-1.5 min-w-0">
              <span v-if="fn.isAsync" class="shrink-0 px-1 rounded bg-sky-500/15 text-[9px] font-bold uppercase text-sky-300">
                async
              </span>
              <span class="truncate font-mono text-xs">
                <span v-if="fn.scope" class="text-slate-500">{{ fn.scope }}.</span>
                <span :class="isActive(fn) ? 'text-emerald-300' : 'text-amber-300'">{{ fn.name }}</span>
              </span>
              <span class="ml-auto shrink-0 px-1 rounded bg-white/5 text-[10px] font-mono text-slate-400">
                Ln {{ fn.line }}
              </span>
            </div>
            <div class="truncate font-mono text-[10px] text-slate-500">({{ fn.params }})</div>
            <div v-if="fn.docstring" class="truncate text-[10px] italic text-slate-400">
              {{ docSummary(fn) }}
            </div>
          </button>
        </li>
      </ul>

      <!-- Empty state -->
      <div v-else class="flex-1 flex flex-col items-center justify-center gap-2 px-4 text-center">
        <ListTree class="w-6 h-6 text-slate-600" aria-hidden="true" />
        <p class="text-xs text-slate-500">{{ emptyMessage }}</p>
        <button
          v-if="normalizedQuery"
          type="button"
          class="text-[10px] font-bold uppercase tracking-wider text-amber-400 hover:text-amber-300"
          @click="clearQuery"
        >
          Clear filter
        </button>
      </div>
    </template>
  </aside>
</template>
