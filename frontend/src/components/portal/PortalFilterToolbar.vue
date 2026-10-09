<script setup lang="ts">
import { ref } from 'vue'
import {
  Search,
  X,
  LayoutGrid,
  Table as TableIcon,
  Palette,
  Sparkles,
  SlidersHorizontal,
  RotateCcw,
  BookOpen,
  Sword,
  MessageSquare
} from 'lucide-vue-next'
import type { RuleTypeFilter, ViewMode } from '@/composables/usePortalFilters'

const props = defineProps<{
  section: 'templates' | 'sessions'
  searchQuery: string
  selectedType: RuleTypeFilter
  selectedTone: string
  selectedStyle: string
  viewMode: ViewMode
  availableTones: Array<{ id: string; name: string }>
  availableStyles: Array<{ id: string; name: string }>
  totalCount: number
  filteredCount: number
  isFiltered: boolean
}>()

const emit = defineEmits<{
  (e: 'update:search-query', val: string): void
  (e: 'update:selected-type', val: RuleTypeFilter): void
  (e: 'update:selected-tone', val: string): void
  (e: 'update:selected-style', val: string): void
  (e: 'update:view-mode', val: ViewMode): void
  (e: 'reset-filters'): void
}>()

const isExpandedMobile = ref(false)

const typeOptions: Array<{ id: RuleTypeFilter; label: string; icon: any }> = [
  { id: 'all', label: 'All Modes', icon: null },
  { id: 'rpg', label: 'RPG', icon: Sword },
  { id: 'story', label: 'Story', icon: BookOpen },
  { id: 'chat', label: 'Chat', icon: MessageSquare }
]
</script>

<template>
  <div class="mb-6 rounded-2xl border border-white/10 bg-slate-900/60 backdrop-blur-md p-3 sm:p-4 shadow-xl transition-all">
    <!-- Main Toolbar Row -->
    <div class="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
      
      <!-- Left: Search Input -->
      <div class="relative flex-1 min-w-[200px]">
        <Search class="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        <input
          type="text"
          :value="props.searchQuery"
          @input="$emit('update:search-query', ($event.target as HTMLInputElement).value)"
          :placeholder="props.section === 'templates' ? 'Search adventures by name, concept, creator...' : 'Search sessions by title, scene, notes...'"
          class="w-full pl-10 pr-9 py-2 rounded-xl bg-black/40 border border-white/10 text-xs sm:text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-aether-primary/50 focus:ring-1 focus:ring-aether-primary/40 transition-all"
        />
        <button
          v-if="props.searchQuery"
          @click="$emit('update:search-query', '')"
          class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white p-0.5 rounded transition-colors"
          title="Clear search"
          aria-label="Clear search"
        >
          <X class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Controls Row on mobile / Desktop Right Controls -->
      <div class="flex flex-wrap sm:flex-nowrap items-center gap-2 lg:gap-3">
        
        <!-- Type Filter (Dropdown or Buttons) -->
        <div class="relative flex-1 sm:flex-none">
          <select
            :value="props.selectedType"
            @change="$emit('update:selected-type', ($event.target as HTMLSelectElement).value as RuleTypeFilter)"
            class="w-full sm:w-auto appearance-none pl-3 pr-8 py-2 rounded-xl bg-black/40 border text-xs font-semibold focus:outline-none focus:border-aether-primary/50 transition-all cursor-pointer"
            :class="props.selectedType !== 'all' ? 'border-cyan-500/50 text-cyan-300 bg-cyan-950/20' : 'border-white/10 text-slate-300 hover:border-white/20'"
            title="Filter by game mode"
            aria-label="Filter by game mode"
          >
            <option value="all">All Modes</option>
            <option value="rpg">RPG Mode</option>
            <option value="story">Story Mode</option>
            <option value="chat">Chat Mode</option>
          </select>
          <div class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs">
            ▾
          </div>
        </div>

        <!-- Tone Filter Dropdown -->
        <div class="relative flex-1 sm:flex-none">
          <select
            :value="props.selectedTone"
            @change="$emit('update:selected-tone', ($event.target as HTMLSelectElement).value)"
            class="w-full sm:w-auto appearance-none pl-3 pr-8 py-2 rounded-xl bg-black/40 border text-xs font-semibold focus:outline-none focus:border-aether-primary/50 transition-all cursor-pointer"
            :class="props.selectedTone !== 'all' ? 'border-amber-500/50 text-amber-300 bg-amber-950/20' : 'border-white/10 text-slate-300 hover:border-white/20'"
            title="Filter by narrative tone"
            aria-label="Filter by narrative tone"
          >
            <option value="all">All Tones</option>
            <option
              v-for="tone in props.availableTones"
              :key="tone.id"
              :value="tone.id"
            >
              {{ tone.name }}
            </option>
          </select>
          <div class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs">
            ▾
          </div>
        </div>

        <!-- Style Filter Dropdown -->
        <div class="relative flex-1 sm:flex-none">
          <select
            :value="props.selectedStyle"
            @change="$emit('update:selected-style', ($event.target as HTMLSelectElement).value)"
            class="w-full sm:w-auto appearance-none pl-3 pr-8 py-2 rounded-xl bg-black/40 border text-xs font-semibold focus:outline-none focus:border-aether-primary/50 transition-all cursor-pointer"
            :class="props.selectedStyle !== 'all' ? 'border-purple-500/50 text-purple-300 bg-purple-950/20' : 'border-white/10 text-slate-300 hover:border-white/20'"
            title="Filter by visual style"
            aria-label="Filter by visual style"
          >
            <option value="all">All Styles</option>
            <option
              v-for="style in props.availableStyles"
              :key="style.id"
              :value="style.id"
            >
              {{ style.name }}
            </option>
          </select>
          <div class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 text-xs">
            ▾
          </div>
        </div>

        <!-- View Mode Switcher (Grid vs Table) -->
        <div class="flex items-center rounded-xl bg-black/50 border border-white/10 p-0.5 shrink-0">
          <button
            @click="$emit('update:view-mode', 'grid')"
            class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5"
            :class="props.viewMode === 'grid'
              ? 'bg-aether-primary/20 text-aether-primary border border-aether-primary/30 shadow-sm'
              : 'text-slate-400 hover:text-white'"
            title="Grid view"
            aria-label="Grid view"
          >
            <LayoutGrid class="w-4 h-4" />
            <span class="hidden sm:inline text-[11px] uppercase tracking-wider">Grid</span>
          </button>
          <button
            @click="$emit('update:view-mode', 'table')"
            class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5"
            :class="props.viewMode === 'table'
              ? 'bg-aether-primary/20 text-aether-primary border border-aether-primary/30 shadow-sm'
              : 'text-slate-400 hover:text-white'"
            title="Table view"
            aria-label="Table view"
          >
            <TableIcon class="w-4 h-4" />
            <span class="hidden sm:inline text-[11px] uppercase tracking-wider">Table</span>
          </button>
        </div>

      </div>
    </div>

    <!-- Active Filters Summary & Reset Bar -->
    <div
      v-if="props.isFiltered || props.totalCount > 0"
      class="mt-3 pt-3 border-t border-white/5 flex flex-wrap items-center justify-between gap-2 text-xs"
    >
      <div class="flex flex-wrap items-center gap-2 text-slate-400">
        <span>
          Showing <span class="font-bold text-white">{{ props.filteredCount }}</span> of
          <span class="font-bold text-slate-300">{{ props.totalCount }}</span>
          {{ props.section === 'templates' ? 'adventures' : 'sessions' }}
        </span>

        <!-- Active Filter Badges -->
        <span
          v-if="props.selectedType !== 'all'"
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-[11px]"
        >
          Type: {{ props.selectedType.toUpperCase() }}
          <button @click="$emit('update:selected-type', 'all')" class="hover:text-white ml-0.5">
            <X class="w-3 h-3" />
          </button>
        </span>

        <span
          v-if="props.selectedTone !== 'all'"
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px]"
        >
          Tone: {{ props.availableTones.find(t => t.id === props.selectedTone)?.name || props.selectedTone }}
          <button @click="$emit('update:selected-tone', 'all')" class="hover:text-white ml-0.5">
            <X class="w-3 h-3" />
          </button>
        </span>

        <span
          v-if="props.selectedStyle !== 'all'"
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-500/10 border border-purple-500/30 text-purple-300 text-[11px]"
        >
          Style: {{ props.availableStyles.find(s => s.id === props.selectedStyle)?.name || props.selectedStyle }}
          <button @click="$emit('update:selected-style', 'all')" class="hover:text-white ml-0.5">
            <X class="w-3 h-3" />
          </button>
        </span>
      </div>

      <!-- Reset Button -->
      <button
        v-if="props.isFiltered"
        @click="$emit('reset-filters')"
        class="inline-flex items-center gap-1.5 text-[11px] font-bold text-slate-400 hover:text-white uppercase tracking-wider transition-colors px-2 py-1 rounded-lg hover:bg-white/5"
      >
        <RotateCcw class="w-3.5 h-3.5" />
        Reset filters
      </button>
    </div>
  </div>
</template>
