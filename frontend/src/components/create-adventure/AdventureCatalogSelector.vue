<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { CatalogTile } from '@/types'
import InfoPopoverButton from '@/components/create-adventure/InfoPopoverButton.vue'
import { Search, X, Check, ChevronRight, Sparkles } from 'lucide-vue-next'

const props = defineProps<{
  title: string
  subtitle: string
  icon: any
  items: CatalogTile[]
  selectedId: string
  accentColorClass: string
  helpText?: string
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
}>()

const isDialogOpen = ref(false)
const searchQuery = ref('')
const searchInputRef = ref<HTMLInputElement | null>(null)

const selectedItem = computed(() => {
  return props.items.find(item => item.id === props.selectedId) || null
})

const filteredItems = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return props.items
  return props.items.filter(item => {
    const nameMatch = item.name?.toLowerCase().includes(query)
    const descMatch = item.description?.toLowerCase().includes(query)
    const instMatch = item.instruction?.toLowerCase().includes(query)
    const idMatch = item.id?.toLowerCase().includes(query)
    return !!(nameMatch || descMatch || instMatch || idMatch)
  })
})

function openDialog() {
  searchQuery.value = ''
  isDialogOpen.value = true
  nextTick(() => {
    searchInputRef.value?.focus()
  })
}

function closeDialog() {
  isDialogOpen.value = false
}

function handleSelect(id: string) {
  emit('select', id)
  closeDialog()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isDialogOpen.value) {
    closeDialog()
  }
}

watch(isDialogOpen, (isOpen) => {
  if (isOpen) {
    window.addEventListener('keydown', handleKeydown)
  } else {
    window.removeEventListener('keydown', handleKeydown)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl md:rounded-3xl p-3.5 sm:p-5 md:p-6 flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between gap-3 mb-3 sm:mb-4">
      <div class="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <div :class="['w-8 h-8 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm', accentColorClass]">
          <component :is="icon" class="w-4 h-4 sm:w-5 sm:h-5" />
        </div>
        <div class="min-w-0">
          <h3 class="text-xs sm:text-sm font-black text-white uppercase tracking-[0.18em] truncate">{{ title }}</h3>
          <p class="text-[10px] sm:text-xxs text-white/40 uppercase tracking-widest truncate">{{ subtitle }}</p>
        </div>
      </div>
      <InfoPopoverButton v-if="helpText" :title="title" :text="helpText" />
    </div>

    <!-- Selected Element Card (Clickable to open dialog) -->
    <div
      role="button"
      tabindex="0"
      @click="openDialog"
      @keydown.enter="openDialog"
      @keydown.space.prevent="openDialog"
      class="group relative h-20 sm:h-22 rounded-xl sm:rounded-2xl overflow-hidden border border-white/10 hover:border-white/30 bg-slate-950/60 p-2.5 sm:p-3 flex items-center justify-between gap-3 cursor-pointer transition-all duration-300 hover:shadow-xl hover:shadow-black/40 select-none active:scale-[0.99]"
      :title="`Click to change ${title}`"
    >
      <!-- Background subtle image glow/preview -->
      <template v-if="selectedItem?.image_url">
        <img
          :src="selectedItem.image_url"
          class="absolute inset-0 w-full h-full object-cover object-center opacity-20 group-hover:opacity-35 transition-opacity duration-500 pointer-events-none"
        />
        <div class="absolute inset-0 bg-gradient-to-r from-slate-950 via-slate-950/80 to-transparent pointer-events-none"></div>
      </template>

      <!-- Left: Thumbnail and info -->
      <div class="relative z-10 flex items-center gap-2.5 sm:gap-3.5 min-w-0">
        <!-- Thumbnail -->
        <div class="w-14 h-14 sm:w-16 sm:h-16 rounded-lg sm:rounded-xl overflow-hidden shrink-0 border border-white/15 bg-black/40 shadow-md relative group-hover:scale-105 transition-transform duration-300">
          <img
            v-if="selectedItem?.image_url"
            :src="selectedItem.image_url"
            :alt="selectedItem?.name || title"
            class="w-full h-full object-cover object-top"
          />
          <div v-else class="w-full h-full flex items-center justify-center text-white/20">
            <component :is="icon" class="w-6 h-6" />
          </div>
        </div>

        <!-- Name & Description -->
        <div class="min-w-0">
          <div class="flex items-center gap-1.5">
            <span class="text-[9px] sm:text-[10px] font-black uppercase tracking-widest text-cyan-400">Current</span>
          </div>
          <h4 class="text-xs sm:text-sm font-black text-white uppercase tracking-wider truncate group-hover:text-cyan-300 transition-colors">
            {{ selectedItem?.name || `Select ${title}...` }}
          </h4>
          <p v-if="selectedItem?.description" class="text-[10px] sm:text-xxs text-white/50 truncate max-w-[200px] sm:max-w-xs md:max-w-sm mt-0.5">
            {{ selectedItem.description }}
          </p>
          <p v-else class="text-[10px] sm:text-xxs text-white/30 truncate mt-0.5">
            Click to choose from {{ items.length }} options
          </p>
        </div>
      </div>

      <!-- Right: Action pill button -->
      <div class="relative z-10 shrink-0">
        <div class="inline-flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-xl border border-white/15 bg-white/10 group-hover:bg-white/20 group-hover:border-white/30 text-white font-bold text-xxs sm:text-xs uppercase tracking-wider transition-all duration-200 shadow-sm">
          <span>Change</span>
          <ChevronRight class="w-3.5 h-3.5 text-white/60 group-hover:text-white group-hover:translate-x-0.5 transition-all" />
        </div>
      </div>
    </div>

    <!-- Modal Dialog (Kachelauswahl mit Suchfeld) -->
    <Teleport to="body">
      <div
        v-if="isDialogOpen"
        class="fixed inset-0 z-[100] bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-5 md:p-6 animate-fade-in"
        @click.self="closeDialog"
      >
        <div
          class="w-full max-w-3xl max-h-[85vh] bg-slate-900 border border-white/10 rounded-2xl md:rounded-3xl shadow-2xl flex flex-col overflow-hidden animate-scale-up"
        >
          <!-- Modal Header -->
          <div class="p-3.5 sm:p-5 border-b border-white/10 flex items-center justify-between gap-3 bg-slate-950/50">
            <div class="flex items-center gap-3 min-w-0">
              <div :class="['w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center shrink-0', accentColorClass]">
                <component :is="icon" class="w-5 h-5" />
              </div>
              <div class="min-w-0">
                <h3 class="text-sm sm:text-base font-black text-white uppercase tracking-wider truncate">
                  Select {{ title }}
                </h3>
                <p class="text-[10px] sm:text-xs text-white/40 uppercase tracking-widest truncate">
                  {{ searchQuery ? `${filteredItems.length} of ${items.length} options` : `${items.length} options available` }}
                </p>
              </div>
            </div>

            <button
              type="button"
              @click="closeDialog"
              class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl border border-white/10 hover:border-white/25 bg-white/5 hover:bg-white/10 text-white/60 hover:text-white flex items-center justify-center transition-all cursor-pointer"
              title="Close dialog"
            >
              <X class="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
          </div>

          <!-- Search Bar -->
          <div class="p-3 sm:p-4 bg-slate-950/30 border-b border-white/5">
            <div class="relative flex items-center">
              <Search class="w-4 h-4 text-white/40 absolute left-3.5 pointer-events-none" />
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                :placeholder="`Search ${title.toLowerCase()}...`"
                class="w-full bg-black/40 border border-white/10 focus:border-cyan-400 rounded-xl pl-10 pr-9 py-2 sm:py-2.5 text-xs sm:text-sm text-white placeholder:text-white/30 outline-none transition-all"
              />
              <button
                v-if="searchQuery"
                type="button"
                @click="searchQuery = ''; searchInputRef?.focus()"
                class="absolute right-3 text-white/40 hover:text-white p-1 transition-colors"
                title="Clear search"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Tile Selection Grid (Kachelauswahl) -->
          <div class="p-3 sm:p-5 overflow-y-auto custom-scrollbar flex-1 min-h-0">
            <div
              v-if="filteredItems.length > 0"
              class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 sm:gap-3.5"
            >
              <button
                v-for="item in filteredItems"
                :key="item.id"
                type="button"
                @click="handleSelect(item.id)"
                class="relative h-28 sm:h-32 rounded-xl sm:rounded-2xl overflow-hidden border-2 transition-all duration-300 group text-left p-3 flex flex-col justify-end cursor-pointer active:scale-95"
                :class="selectedId === item.id ? 'border-cyan-400 ring-4 ring-cyan-400/20 shadow-lg shadow-cyan-950/50' : 'border-white/10 hover:border-white/30 hover:scale-[1.02]'"
              >
                <!-- Tile Image -->
                <img
                  v-if="item.image_url"
                  :src="item.image_url"
                  :alt="item.name"
                  class="absolute inset-0 w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-110"
                />
                <div v-else class="absolute inset-0 bg-slate-800 flex items-center justify-center">
                  <component :is="icon" class="w-8 h-8 text-white/20" />
                </div>

                <!-- Gradient Overlay -->
                <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent opacity-85 group-hover:opacity-75 transition-opacity"></div>

                <!-- Selected Indicator Badge -->
                <div
                  v-if="selectedId === item.id"
                  class="absolute top-2.5 right-2.5 px-2 py-0.5 rounded-md bg-cyan-400 text-slate-950 font-black text-[9px] uppercase tracking-wider flex items-center gap-1 shadow-md z-10"
                >
                  <Check class="w-3 h-3 stroke-[3]" />
                  <span>Selected</span>
                </div>

                <!-- Tile Name & Description -->
                <div class="relative z-10">
                  <p class="text-xs font-black text-white uppercase tracking-wider truncate drop-shadow-sm">
                    {{ item.name }}
                  </p>
                  <p v-if="item.description" class="text-[10px] text-white/60 line-clamp-1 mt-0.5 font-medium">
                    {{ item.description }}
                  </p>
                </div>
              </button>
            </div>

            <!-- Empty Search Results -->
            <div v-else class="py-12 flex flex-col items-center justify-center text-center gap-3 text-white/40">
              <Search class="w-8 h-8 text-white/20" />
              <p class="text-xs uppercase tracking-widest font-bold">No {{ title.toLowerCase() }} found</p>
              <button
                type="button"
                @click="searchQuery = ''; searchInputRef?.focus()"
                class="px-3 py-1.5 rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 text-white text-xs font-bold transition-all"
              >
                Clear Search Filter
              </button>
            </div>
          </div>

          <!-- Modal Footer -->
          <div class="p-3 sm:p-4 border-t border-white/10 bg-slate-950/50 flex items-center justify-between gap-3">
            <div class="min-w-0 text-xs text-white/50 truncate">
              <span class="text-white/30 uppercase tracking-widest font-black mr-1 text-[10px]">Active:</span>
              <span class="text-white font-bold">{{ selectedItem?.name || 'None' }}</span>
            </div>
            <button
              type="button"
              @click="closeDialog"
              class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-white/10 text-white text-xs font-bold uppercase tracking-wider transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.25);
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.45);
}
</style>
