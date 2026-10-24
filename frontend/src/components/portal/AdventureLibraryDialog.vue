<script setup lang="ts">
import { computed } from 'vue'
import type { UseAdventureLibraryResult } from '@/composables/useAdventureLibrary'
import { formatBytes } from '@/utils/editor_utils'
import AdventureLibraryCard from './AdventureLibraryCard.vue'

const props = defineProps<{
  library: UseAdventureLibraryResult
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const lib = props.library
const {
  items,
  loading,
  error,
  staleCatalog,
  selectedCount,
  selectedTotalBytes,
  catalogTotalBytes,
  allSelectableSelected,
  installErrors,
  installingId,
  installStatus,
  isSubmitting,
} = lib

const hasSelectable = computed(() => items.value.some(lib.isSelectable))
const showInitialLoading = computed(() => loading.value && items.value.length === 0)
const showEmpty = computed(() => !loading.value && items.value.length === 0)

const subtitle = computed(() => {
  const count = items.value.length
  const noun = count === 1 ? 'adventure' : 'adventures'
  return `${count} ${noun} · ${formatBytes(catalogTotalBytes.value)} total`
})

const statusTitle = computed(() => {
  const status = installStatus.value
  if (!status || status.phase === 'refreshing') {
    return 'Updating your library...'
  }
  return status.total > 1 ? `Installing ${status.current} of ${status.total}` : 'Installing adventure'
})

const statusDetail = computed(() => {
  const status = installStatus.value
  if (!status || status.phase === 'refreshing') {
    return 'Almost done - the new adventures will appear in your library.'
  }
  return `${status.title}: downloading and importing...`
})

/** The dialog is locked while installing; closing would hide progress and errors. */
function requestClose() {
  if (isSubmitting.value) {
    return
  }
  emit('close')
}

function toggleAll() {
  if (allSelectableSelected.value) {
    lib.clearSelection()
    return
  }
  lib.selectAll()
}
</script>

<template>
  <div class="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
    <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-md animate-fade-in" @click="requestClose"></div>

    <div
      class="relative w-full max-w-5xl max-h-[90vh] flex flex-col rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden animate-scale-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="adventure-library-title"
      :aria-busy="isSubmitting"
    >
      <div
        v-if="installStatus"
        class="absolute inset-0 z-20 flex flex-col items-center justify-center gap-4 bg-slate-950/75 backdrop-blur-sm px-6 text-center"
        role="status"
        aria-live="polite"
      >
        <div class="w-12 h-12 border-4 border-blue-500/15 border-t-blue-500 rounded-full animate-spin"></div>
        <p class="text-sm font-black text-white uppercase tracking-widest">{{ statusTitle }}</p>
        <p class="text-xs text-slate-300 max-w-sm">{{ statusDetail }}</p>
        <p class="text-[11px] text-slate-500">Please keep this window open.</p>
      </div>

      <div class="px-6 py-5 border-b border-white/10 flex items-start gap-4">
        <div class="flex-1 min-w-0">
          <h3 id="adventure-library-title" class="text-lg font-black text-white font-display">Adventure Library</h3>
          <p class="text-sm text-slate-300 mt-1">{{ subtitle }}</p>
          <p v-if="staleCatalog" class="text-xs text-amber-300/80 mt-1">
            <i class="ra ra-warning mr-1"></i>
            The catalog could not be refreshed; showing a cached copy.
          </p>
        </div>
        <button
          type="button"
          class="w-9 h-9 rounded-lg border border-white/15 text-slate-300 hover:bg-white/5 hover:text-white transition-colors flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="loading || isSubmitting"
          title="Refresh catalog"
          aria-label="Refresh catalog"
          @click="lib.refresh()"
        >
          <i class="ra ra-cycle" :class="{ 'animate-spin': loading }"></i>
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-6 py-5">
        <div v-if="error" class="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {{ error }}
        </div>

        <div v-if="showInitialLoading" class="flex flex-col items-center justify-center py-16 gap-4">
          <div class="w-10 h-10 border-4 border-blue-500/10 border-t-blue-500 rounded-full animate-spin"></div>
          <p class="text-xs text-slate-400 uppercase tracking-widest font-bold">Loading catalog...</p>
        </div>

        <div v-else-if="showEmpty" class="flex flex-col items-center justify-center py-16 gap-2 text-center">
          <i class="ra ra-book text-3xl text-slate-600"></i>
          <p class="text-sm text-slate-300 font-bold">No adventures are available right now.</p>
          <p class="text-xs text-slate-500">Try refreshing the catalog later.</p>
        </div>

        <template v-else>
          <label
            class="mb-4 inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest"
            :class="hasSelectable ? 'text-slate-300 cursor-pointer' : 'text-slate-600 cursor-not-allowed'"
          >
            <input
              type="checkbox"
              class="w-4 h-4 accent-blue-500"
              :checked="allSelectableSelected"
              :disabled="!hasSelectable"
              @change="toggleAll"
            />
            Select all
          </label>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <AdventureLibraryCard
              v-for="item in items"
              :key="item.entry.id"
              :item="item"
              :selected="lib.isSelected(item.entry.id)"
              :selectable="lib.isSelectable(item)"
              :installing="installingId === item.entry.id"
              @toggle="lib.toggle"
            />
          </div>
        </template>
      </div>

      <div class="sticky bottom-0 px-6 py-4 border-t border-white/10 bg-slate-900 space-y-3">
        <ul v-if="installErrors.length > 0" class="max-h-24 overflow-y-auto space-y-1 text-xs text-red-300">
          <li v-for="message in installErrors" :key="message">
            <i class="ra ra-warning mr-1"></i>
            {{ message }}
          </li>
        </ul>
        <div class="flex items-center justify-end gap-3">
          <span v-if="selectedCount > 0" class="mr-auto text-xs text-slate-400 font-mono">
            {{ formatBytes(selectedTotalBytes) }} selected
          </span>
          <button
            type="button"
            class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isSubmitting"
            @click="requestClose"
          >
            Close
          </button>
          <button
            type="button"
            class="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-black uppercase tracking-widest hover:bg-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            :disabled="selectedCount === 0 || isSubmitting"
            @click="lib.downloadSelected()"
          >
            <span
              v-if="isSubmitting"
              class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"
            ></span>
            {{ isSubmitting ? 'Installing...' : `Download selected (${selectedCount})` }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.3s ease-out;
}
.animate-scale-in {
  animation: scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>
