<script setup lang="ts">
import GameQuestTracker from '@/components/game/GameQuestTracker.vue'
import GameClockWidget from '@/components/game/GameClockWidget.vue'
import LicenseInfoPopup from '@/components/common/LicenseInfoPopup.vue'
import { FileText, History, PenLine, ScrollText, Sparkles } from 'lucide-vue-next'
import { ref, computed } from 'vue'

const props = defineProps<{
  title?: string | null
  version?: string | null
  creator?: string | null
  copyright?: string | null
  license?: string | null
  licenseUrl?: string | null
  trackedQuest?: any
  gameTime: { dateShort: string; time: string } | null
  clockTick: boolean
  debugMode?: boolean
  isCheckpointSaving?: boolean
  collapsed?: boolean
  viewMode?: 'immersive' | 'classic'
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'edit-note'): void
  (e: 'open-chronicles'): void
  (e: 'collapse'): void
  (e: 'hide-quest'): void
  (e: 'toggle-view-mode'): void
}>()

const handleBack = () => {
  emit('back')
}

const showLicensePopup = ref(false)
const licenseButtonRef = ref<HTMLElement | null>(null)

const hasLicenseInfo = computed(() => {
  return !!(props.creator || props.copyright || props.license || props.licenseUrl)
})
</script>

<template>
  <header 
    :class="[
      'bg-transparent px-4 md:px-8 grid grid-cols-2 sm:flex sm:flex-row items-start justify-between gap-4 md:gap-6 z-10 shrink-0 relative transition-all duration-300 ease-in-out group/header',
      collapsed ? 'h-0 min-h-0 pt-0 pb-0 overflow-hidden opacity-0 pointer-events-none' : 'pt-8 pb-4 min-h-[110px]'
    ]"
  >
    <div class="flex flex-col items-start gap-2 z-10 min-w-0 shrink-0 order-1 col-span-1 sm:w-1/4">
      <div class="flex items-center gap-2">
        <button
          @click="handleBack"
          class="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-emerald-500/10 hover:border-emerald-500/40 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
          title="Return to Portal"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-5 h-5 text-slate-100 group-hover:text-emerald-400 transition-colors">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
        </button>

        <button
          v-if="props.title"
          @click="emit('open-chronicles')"
          class="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-sky-500/10 hover:border-sky-500/40 text-sky-300/80 hover:text-sky-200 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
          title="Open Chronicles Timeline"
        >
          <History class="w-5 h-5" />
        </button>

        <button
          v-if="props.title"
          @click="emit('edit-note')"
          class="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-amber-500/10 hover:border-amber-500/40 text-amber-400/80 hover:text-amber-400 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
          title="Edit Session Note"
        >
          <FileText class="w-5 h-5" />
        </button>

        <button
          @click="emit('toggle-view-mode')"
          class="flex items-center justify-center w-10 h-10 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-amber-500/10 hover:border-amber-500/40 text-amber-300 hover:text-amber-200 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
          :title="props.viewMode === 'classic' ? 'Switch to Immersive View' : 'Switch to Classic Mode'"
        >
          <Sparkles class="w-5 h-5 text-amber-400 group-hover:scale-110 transition-transform" />
        </button>
      </div>

      <div class="flex flex-col min-w-0">
        <h1 class="text-xl md:text-3xl font-normal text-white drop-shadow-[0_2px_15px_rgba(0,0,0,0.8)] tracking-wide adventure-title">
          {{ props.title || 'Chronicle' }}
        </h1>
        <div class="flex items-center gap-2 mt-1">
          <div v-if="props.version" class="text-[10px] font-mono font-bold text-slate-500 opacity-60 uppercase tracking-widest">
            v{{ props.version }}
          </div>
          <div v-if="hasLicenseInfo" class="relative" ref="licenseButtonRef">
            <button
              @click.stop="showLicensePopup = !showLicensePopup"
              :class="[
                'group inline-flex items-center rounded-md bg-gradient-to-br from-amber-500/15 to-amber-300/10 border border-amber-400/30 text-amber-300 hover:from-amber-500/25 hover:to-amber-300/20 hover:border-amber-400/60 hover:text-amber-200 transition-all shadow-sm',
                props.license ? 'h-6 px-2 gap-1.5 text-[9px] font-black uppercase tracking-[0.15em]' : 'justify-center w-6 h-6'
              ]"
              :title="`License: ${props.license || 'View details'}`"
              aria-label="License & credits"
            >
              <ScrollText class="w-3 h-3 shrink-0" />
              <span v-if="props.license" class="leading-none">{{ props.license }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="flex-grow w-full sm:w-2/4 min-w-0 flex justify-center order-3 sm:order-2 col-span-2">
      <GameQuestTracker :tracked-quest="props.trackedQuest" @hide="emit('hide-quest')" />
    </div>

    <div class="z-20 shrink-0 sm:w-1/4 flex justify-end order-2 sm:order-3 col-span-1 justify-self-end w-full sm:w-auto">
      <div class="flex items-center gap-2 sm:gap-3">
        <div
          v-if="props.isCheckpointSaving"
          class="inline-flex items-center gap-2 rounded-full border border-emerald-400/35 bg-emerald-500/10 px-3 py-1.5 text-[11px] font-black uppercase tracking-widest text-emerald-300 animate-pulse"
        >
          <PenLine class="w-3.5 h-3.5" />
          Saving...
        </div>
        <GameClockWidget :game-time="props.gameTime" :clock-tick="props.clockTick" />

        <!-- View Switcher Button (Switch to Immersive View) -->
        <button
          type="button"
          @click="emit('toggle-view-mode')"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/80 border border-slate-700/60 hover:border-amber-400 hover:bg-amber-500/10 text-slate-300 hover:text-white transition-all text-xs font-black uppercase tracking-wider shadow-lg active:scale-95 cursor-pointer backdrop-blur-md"
          title="Switch to Immersive Stage View"
        >
          <Sparkles class="w-3.5 h-3.5 text-amber-400" />
          <span class="hidden sm:inline">Immersive View</span>
        </button>
      </div>
    </div>

    <div v-if="props.debugMode" class="absolute top-24 left-1/2 -translate-x-1/2 z-[100] px-4 py-1 bg-rose-600/80 backdrop-blur-md border border-rose-400/50 rounded-full text-[10px] font-black text-white uppercase tracking-[0.2em] animate-pulse shadow-lg">
      Debug Protocol Active
    </div>

    <!-- Collapse Button -->
    <button
      v-if="!props.collapsed"
      @click="emit('collapse')"
      class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 z-20 px-3 py-1 rounded-full border border-slate-800/80 bg-slate-900/95 text-slate-500 hover:text-slate-300 hover:scale-105 transition-all shadow-lg flex items-center justify-center cursor-pointer pointer-events-auto opacity-0 group-hover/header:opacity-100 focus:opacity-100"
      title="Collapse Header"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
        <path stroke-linecap="round" stroke-linejoin="round" d="M5 15l7-7 7 7" />
      </svg>
    </button>

    <!-- License popup (teleported to body to escape overflow-hidden parents) -->
    <LicenseInfoPopup
      v-model:open="showLicensePopup"
      :license="props.license"
      :license-url="props.licenseUrl"
      :creator="props.creator"
      :copyright="props.copyright"
      :anchor-el="licenseButtonRef"
      accent="amber"
    />
  </header>
</template>

<style scoped>
.adventure-title {
  font-family: 'Acme', sans-serif;
}
</style>
