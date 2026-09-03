<script setup lang="ts">
/**
 * ImmersiveActionBar — Bottom quick action buttons and prompt suggestion chips
 *
 * Provides quick access to Quests, World Map, Hero Sheet, Chronicles Timeline,
 * and Hints/Walkthrough, plus dynamic LLM prompt suggestion chips.
 */
import {
  Scroll,
  Map as MapIcon,
  User,
  History,
  Lightbulb,
} from 'lucide-vue-next'

const props = defineProps<{
  inventory?: any[]
  trackedQuest?: any
  inventoryGlow?: boolean
  mapGlow?: boolean
  questGlow?: boolean
  promptSuggestions?: string[]
  canSendInput?: boolean
}>()

const emit = defineEmits<{
  openQuests: []
  openMap: []
  openSheet: []
  openChronicles: []
  openWalkthrough: []
  selectSuggestion: [suggestion: string]
}>()
</script>

<template>
  <div class="flex items-center justify-between px-4 py-2 border-b border-slate-800/60 overflow-x-auto no-scrollbar gap-3">
    <!-- Quick Modals Buttons -->
    <div class="flex items-center gap-2 shrink-0">
      <!-- Quests Button -->
      <button
        type="button"
        @click="emit('openQuests')"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-amber-400 hover:bg-amber-500/10 text-slate-200 hover:text-amber-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
        :class="{ 'ring-2 ring-amber-400/40': props.questGlow }"
        title="Open Quest Log"
      >
        <Scroll class="w-4 h-4 text-amber-400" />
        <span class="hidden sm:inline uppercase tracking-wider">Quests</span>
        <span v-if="props.trackedQuest" class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
      </button>

      <!-- World Map Button -->
      <button
        type="button"
        @click="emit('openMap')"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-sky-400 hover:bg-sky-500/10 text-slate-200 hover:text-sky-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
        :class="{ 'ring-2 ring-sky-400/40': props.mapGlow }"
        title="Open World Map"
      >
        <MapIcon class="w-4 h-4 text-sky-400" />
        <span class="hidden sm:inline uppercase tracking-wider">Map</span>
      </button>

      <!-- Hero & Inventory Button -->
      <button
        type="button"
        @click="emit('openSheet')"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-emerald-400 hover:bg-emerald-500/10 text-slate-200 hover:text-emerald-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
        :class="{ 'ring-2 ring-emerald-400/40': props.inventoryGlow }"
        title="Open Character Sheet & Inventory"
      >
        <User class="w-4 h-4 text-emerald-400" />
        <span class="hidden sm:inline uppercase tracking-wider">Hero</span>
        <span v-if="props.inventory?.length" class="px-1.5 py-0.2 bg-emerald-500/20 text-emerald-300 text-[9px] font-black rounded-full">
          {{ props.inventory.length }}
        </span>
      </button>

      <!-- Chronicles Timeline -->
      <button
        type="button"
        @click="emit('openChronicles')"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-indigo-400 hover:bg-indigo-500/10 text-slate-200 hover:text-indigo-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
        title="Open Chronicles Timeline"
      >
        <History class="w-4 h-4 text-indigo-400" />
        <span class="hidden sm:inline uppercase tracking-wider">Log</span>
      </button>

      <!-- Hints / Walkthrough -->
      <button
        type="button"
        @click="emit('openWalkthrough')"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-amber-400 hover:bg-amber-500/10 text-slate-200 hover:text-amber-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
        title="Adventure Hints & Walkthrough"
      >
        <Lightbulb class="w-4 h-4 text-amber-400" />
        <span class="hidden md:inline uppercase tracking-wider">Hints</span>
      </button>
    </div>

    <!-- Prompt Suggestions Chips -->
    <div v-if="props.promptSuggestions?.length" class="flex items-center gap-2 overflow-x-auto no-scrollbar">
      <button
        v-for="(suggestion, sIdx) in props.promptSuggestions.slice(0, 3)"
        :key="sIdx"
        type="button"
        :disabled="!props.canSendInput"
        @click="emit('selectSuggestion', suggestion)"
        class="px-3 py-1 rounded-full bg-slate-900/80 border border-slate-700/60 hover:border-amber-400/50 hover:bg-amber-500/10 text-slate-300 hover:text-amber-200 text-xs font-semibold whitespace-nowrap transition-all active:scale-95 truncate max-w-[16rem] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {{ suggestion }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
