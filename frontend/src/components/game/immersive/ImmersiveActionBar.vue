<script setup lang="ts">
/**
 * ImmersiveActionBar — Bottom quick action buttons and action ideas popup
 *
 * Provides quick access to Quests, World Map, Hero Sheet, Chronicles Timeline,
 * and Hints/Walkthrough, plus dynamic LLM prompt suggestion popup list.
 */
import { ref, onBeforeUnmount } from 'vue'
import {
  Scroll,
  Map as MapIcon,
  User,
  History,
  Lightbulb,
  BrainCircuit,
  Terminal,
  Sparkles,
  RefreshCw,
  X,
  HelpCircle,
} from 'lucide-vue-next'

const props = defineProps<{
  inventory?: any[]
  trackedQuest?: any
  worldMemories?: any[]
  inventoryGlow?: boolean
  mapGlow?: boolean
  questGlow?: boolean
  promptSuggestions?: string[]
  canSendInput?: boolean
  debugMode?: boolean
}>()

const emit = defineEmits<{
  openQuests: []
  openMap: []
  openSheet: []
  openChronicles: []
  openWalkthrough: []
  openMemories: []
  openDebug: []
  shuffleSuggestions: []
  selectSuggestion: [suggestion: string]
}>()

const showIdeasPopup = ref(false)
const ideasWrapperRef = ref<HTMLElement | null>(null)
const isShuffling = ref(false)

function toggleIdeasPopup() {
  if (showIdeasPopup.value) {
    closeIdeasPopup()
  } else {
    openIdeasPopup()
  }
}

function openIdeasPopup() {
  showIdeasPopup.value = true
  if (!props.promptSuggestions?.length) {
    handleShuffleClick()
  }
  setTimeout(() => {
    document.addEventListener('mousedown', handleOutsideClick)
  }, 0)
}

function closeIdeasPopup() {
  showIdeasPopup.value = false
  document.removeEventListener('mousedown', handleOutsideClick)
}

function handleShuffleClick() {
  isShuffling.value = true
  emit('shuffleSuggestions')
  setTimeout(() => {
    isShuffling.value = false
  }, 1200)
}

function handleOutsideClick(event: MouseEvent) {
  const target = event.target as Node | null
  if (!target) return
  if (ideasWrapperRef.value && !ideasWrapperRef.value.contains(target)) {
    closeIdeasPopup()
  }
}

function handleSelectSuggestion(suggestion: string) {
  emit('selectSuggestion', suggestion)
  closeIdeasPopup()
}

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleOutsideClick)
})
</script>

<template>
  <div class="relative flex items-center justify-between px-4 py-2 border-b border-slate-800/60 gap-3">
    <!-- Quick Modals Buttons -->
    <div class="flex items-center gap-2 overflow-x-auto no-scrollbar flex-1 min-w-0">
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
        <HelpCircle class="w-4 h-4 text-amber-400" />
        <span class="hidden sm:inline uppercase tracking-wider">Hints</span>
      </button>

      <!-- World Memories & Chronicle -->
      <button
        type="button"
        @click="emit('openMemories')"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-purple-400 hover:bg-purple-500/10 text-slate-200 hover:text-purple-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
        title="World Memories & Chronicle"
      >
        <BrainCircuit class="w-4 h-4 text-purple-400" />
        <span class="hidden sm:inline uppercase tracking-wider">Memories</span>
        <span v-if="props.worldMemories?.length" class="px-1.5 py-0.2 bg-purple-500/20 text-purple-300 text-[9px] font-black rounded-full">
          {{ props.worldMemories.length }}
        </span>
      </button>

      <!-- Debug Panel Button (Debug Mode Only) -->
      <button
        v-if="props.debugMode"
        type="button"
        @click="emit('openDebug')"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-cyan-500/60 hover:border-cyan-400 hover:bg-cyan-500/10 text-cyan-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer shadow-cyan-950/30"
        title="Open Unified Debug Inspector"
      >
        <Terminal class="w-4 h-4 text-cyan-400" />
        <span class="hidden sm:inline uppercase tracking-wider">Debug</span>
      </button>
    </div>

    <!-- Ideas Section with Animated Popup List -->
    <div ref="ideasWrapperRef" class="relative shrink-0">
      <!-- Ideas Trigger Button (Always in English) -->
      <button
        type="button"
        @click="toggleIdeasPopup"
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer group/ideas"
        :class="[
          showIdeasPopup
            ? 'bg-amber-500/20 border-amber-400 text-amber-200 ring-2 ring-amber-400/30'
            : 'bg-amber-500/10 hover:bg-amber-500/20 border-amber-500/40 hover:border-amber-400 text-amber-300 hover:text-amber-200'
        ]"
        title="Prompt Suggestions & Ideas"
      >
        <Lightbulb class="w-3.5 h-3.5 text-amber-400 transition-transform duration-300 group-hover/ideas:rotate-12 group-hover/ideas:scale-110" />
        <span class="uppercase tracking-wider text-[11px]">Ideas</span>
        <span
          v-if="props.promptSuggestions?.length"
          class="px-1.5 py-0.2 bg-amber-400/20 text-amber-300 text-[9px] font-black rounded-full tabular-nums"
        >
          {{ Math.min(props.promptSuggestions.length, 5) }}
        </span>
      </button>

      <!-- Animated Ideas Popup -->
      <Transition name="popup-slide">
        <div
          v-if="showIdeasPopup"
          class="absolute bottom-full right-0 mb-3 w-80 sm:w-96 rounded-2xl bg-slate-900/95 backdrop-blur-xl border border-amber-500/30 shadow-[0_10px_35px_rgba(0,0,0,0.7)] p-3.5 z-50 flex flex-col gap-2.5"
        >
          <!-- Popup Header -->
          <div class="flex items-center justify-between pb-2 border-b border-slate-800">
            <div class="flex items-center gap-1.5">
              <Sparkles class="w-4 h-4 text-amber-400" />
              <span class="text-xs font-black uppercase tracking-wider text-amber-200">Action Ideas</span>
            </div>
            <div class="flex items-center gap-1">
              <button
                type="button"
                @click="handleShuffleClick"
                class="p-1 rounded-lg text-slate-400 hover:text-amber-300 hover:bg-amber-500/10 transition-colors cursor-pointer"
                title="Regenerate Ideas (/shuffle)"
              >
                <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isShuffling }" />
              </button>
              <button
                type="button"
                @click="closeIdeasPopup"
                class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
                title="Close"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <!-- Suggestions List -->
          <div v-if="props.promptSuggestions?.length" class="flex flex-col gap-1.5 max-h-64 overflow-y-auto custom-scrollbar">
            <button
              v-for="(suggestion, sIdx) in props.promptSuggestions.slice(0, 5)"
              :key="sIdx"
              type="button"
              @click="handleSelectSuggestion(suggestion)"
              class="w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-xl bg-slate-950/60 hover:bg-amber-500/15 border border-slate-800/80 hover:border-amber-400/50 text-slate-200 hover:text-amber-200 text-xs font-semibold transition-all group/item active:scale-[0.98] cursor-pointer"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-amber-400/60 group-hover/item:bg-amber-400 shrink-0 transition-colors"></span>
              <span class="flex-1 leading-snug">{{ suggestion }}</span>
            </button>
          </div>

          <!-- Empty / Loading State -->
          <div v-else class="py-5 text-center text-slate-400 text-xs flex flex-col items-center gap-2">
            <Sparkles class="w-5 h-5 text-amber-400/80 animate-spin" />
            <span class="font-medium">Generating situation-aware ideas...</span>
          </div>
        </div>
      </Transition>
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

.popup-slide-enter-active,
.popup-slide-leave-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.popup-slide-enter-from,
.popup-slide-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.96);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 4px;
}
</style>
