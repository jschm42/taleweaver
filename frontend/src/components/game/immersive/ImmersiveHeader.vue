<script setup lang="ts">
/**
 * ImmersiveHeader — Atmospheric top bar for the immersive RPG view
 *
 * Displays scene and adventure metadata, active sequence with description tooltip,
 * tracked quest badge, in-game clock, speech controls, BabelFish language selector,
 * and experience counter.
 */
import { ref, computed } from 'vue'
import { configState } from '@/store/config'
import { audioService } from '@/services/audioService'
import GameClockWidget from '@/components/game/GameClockWidget.vue'
import BableFishSelector from '@/components/game/BableFishSelector.vue'
import {
  History,
  Scroll,
  Volume2,
  VolumeX,
  Map as MapIcon,
  Sliders,
  LogOut,
} from 'lucide-vue-next'

const props = defineProps<{
  sceneName?: string | null
  activeSequence?: any | null
  adventureTitle?: string | null
  creator?: string | null
  copyright?: string | null
  trackedQuest?: any
  gameTime?: { dateShort: string; time: string } | null
  clockTick?: boolean
  exp?: number
  mode?: 'rpg' | 'story' | 'chat'
  debugMode?: boolean
}>()

const emit = defineEmits<{
  openChronicles: []
  openQuests: []
  openSettings: []
  openDebug: []
  toggleMobileInteract: []
  exitSession: []
}>()

const showSequenceTooltip = ref(false)

const sequenceTitle = computed(() => {
  if (!props.activeSequence) return ''
  return (
    props.activeSequence.title ||
    props.activeSequence.name ||
    props.activeSequence.id ||
    ''
  ).trim()
})

const sequenceDescription = computed(() => {
  if (!props.activeSequence) return ''
  return (
    props.activeSequence.description ||
    props.activeSequence.summary ||
    props.activeSequence.teaser ||
    ''
  ).trim()
})

const sequenceOrder = computed(() => {
  return props.activeSequence?.order ?? null
})
</script>

<template>
  <header class="relative z-20 flex items-center justify-between px-4 py-3 sm:px-6 sm:py-3.5 bg-slate-950/75 backdrop-blur-md border-b border-slate-800/80 shadow-2xl shrink-0">
    <!-- Left: Scene & Sequence Title & Back / Chronicles -->
    <div class="flex items-center gap-3 min-w-0">
      <button
        type="button"
        @click="emit('openChronicles')"
        class="flex items-center justify-center w-9 h-9 rounded-xl bg-slate-900/80 border border-slate-700/60 text-slate-300 hover:text-white hover:border-amber-400/50 hover:bg-amber-500/10 transition-all shadow-lg active:scale-95 shrink-0 cursor-pointer"
        title="Chronicles & Timeline"
      >
        <History class="w-4 h-4" />
      </button>

      <div class="flex flex-col min-w-0">
        <div class="flex items-center gap-1.5 sm:gap-2 min-w-0 flex-wrap sm:flex-nowrap">
          <!-- Active Sequence Badge with Hover Tooltip -->
          <div
            v-if="sequenceTitle"
            class="relative inline-flex items-center shrink-0"
            @mouseenter="showSequenceTooltip = true"
            @mouseleave="showSequenceTooltip = false"
          >
            <div
              class="flex items-center px-2.5 py-0.5 rounded-full bg-gradient-to-r from-amber-500/20 via-amber-500/15 to-amber-600/10 border border-amber-500/40 hover:border-amber-400 hover:bg-amber-500/25 transition-all duration-200 cursor-help shadow-sm group select-none"
              :class="{ 'border-amber-400/90 bg-amber-500/30 ring-1 ring-amber-400/30': showSequenceTooltip }"
            >
              <span class="text-xs sm:text-sm font-black text-amber-200 uppercase tracking-wide truncate max-w-[8rem] sm:max-w-[14rem] md:max-w-[20rem] comic-title">
                {{ sequenceTitle }}
              </span>
            </div>

            <!-- Sequence Short Description Tooltip on Mousehover -->
            <Transition name="tooltip-fade">
              <div
                v-if="showSequenceTooltip"
                class="absolute left-0 top-full mt-2.5 z-50 w-72 sm:w-84 max-w-[calc(100vw-2rem)] p-3.5 bg-slate-950/95 border border-amber-500/40 rounded-xl shadow-[0_16px_40px_rgba(0,0,0,0.85)] backdrop-blur-xl pointer-events-none select-none"
              >
                <!-- Glowing top border accent -->
                <div class="absolute -top-[1px] left-4 right-4 h-[1px] bg-gradient-to-r from-transparent via-amber-400/80 to-transparent"></div>

                <!-- Callout pointer arrow -->
                <div class="absolute -top-1.5 left-6 w-3 h-3 bg-slate-950 border-t border-l border-amber-500/40 rotate-45"></div>

                <div class="relative z-10">
                  <div class="flex items-center justify-between gap-2 mb-2 pb-1.5 border-b border-slate-800/80">
                    <div class="flex items-center gap-1.5 min-w-0">
                      <i class="ra ra-scroll-unfurled text-xs text-amber-400 shrink-0"></i>
                      <span class="text-[10px] font-black uppercase tracking-[0.2em] text-amber-400 truncate">
                        {{ sequenceOrder ? `Chapter ${sequenceOrder}` : 'Sequence' }}
                      </span>
                    </div>
                    <span class="text-[9px] font-mono font-bold text-amber-300/80 uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/25 shrink-0">
                      Active
                    </span>
                  </div>

                  <h4 class="text-xs sm:text-sm font-black text-white uppercase tracking-wider mb-1.5 comic-title leading-snug">
                    {{ sequenceTitle }}
                  </h4>

                  <p v-if="sequenceDescription" class="text-xs leading-relaxed text-slate-300 font-serif italic max-h-56 overflow-y-auto">
                    {{ sequenceDescription }}
                  </p>
                  <p v-else class="text-xs italic text-slate-500">
                    No short description available for this sequence.
                  </p>
                </div>
              </div>
            </Transition>
          </div>

          <!-- Divider between Sequence and Scene -->
          <span v-if="sequenceTitle" class="text-slate-600 font-bold text-xs select-none shrink-0">/</span>

          <!-- Scene Name -->
          <h2 class="text-sm sm:text-base font-black text-white uppercase tracking-wider truncate drop-shadow-md comic-title min-w-0">
            {{ props.sceneName || 'Unknown Location' }}
          </h2>
        </div>
        <div class="flex items-center gap-2 text-[11px] text-slate-400 truncate opacity-80 font-medium">
          <span v-if="props.adventureTitle" class="truncate">{{ props.adventureTitle }}</span>
          <span v-if="props.adventureTitle && (props.copyright || props.creator)" class="text-slate-600 select-none">•</span>
          <span v-if="props.copyright || props.creator" class="text-[10px] text-slate-500 tracking-wide truncate">
            {{ props.copyright || `© ${props.creator}` }}
          </span>
        </div>
      </div>
    </div>

    <!-- Center: Tracked Quest Banner -->
    <div
      v-if="props.trackedQuest"
      class="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900/80 border border-amber-500/30 text-amber-200 text-xs font-semibold backdrop-blur-sm shadow-md cursor-pointer hover:border-amber-400 transition-all"
      @click="emit('openQuests')"
    >
      <Scroll class="w-3.5 h-3.5 text-amber-400 shrink-0" />
      <span class="max-w-[20rem] truncate font-bold">{{ props.trackedQuest.title || props.trackedQuest.description }}</span>
    </div>

    <!-- Right: Status & Audio Controls -->
    <div class="flex items-center gap-2 sm:gap-3 shrink-0">
      <!-- Debug Mode Active Indicator -->
      <button
        v-if="props.debugMode"
        type="button"
        @click="emit('openDebug')"
        class="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-[0.2em] bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 hover:border-cyan-400 transition-all cursor-pointer shadow-sm animate-pulse"
        title="Debug Mode Active — Click to open Debug Inspector"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
        <span>DEBUG</span>
      </button>

      <!-- In-Game Clock -->
      <GameClockWidget :game-time="props.gameTime || null" :clock-tick="props.clockTick || false" />

      <!-- Experience XP -->
      <div
        class="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-black tracking-wider shadow-sm shrink-0"
        title="Experience Points (XP)"
      >
        <i class="ra ra-laurels text-sm text-amber-400"></i>
        <span class="tabular-nums">{{ props.exp ?? 0 }} XP</span>
      </div>

      <!-- TTS Toggle / Stop -->
      <div v-if="configState.isTtsEnabled" class="flex items-center gap-1.5">
        <button
          v-if="audioService.isPlaying.value"
          type="button"
          @click="audioService.stop()"
          class="flex items-center justify-center w-8 h-8 rounded-lg bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30 transition-all animate-pulse cursor-pointer"
          title="Stop Speech (SPACE)"
        >
          <VolumeX class="w-4 h-4" />
        </button>
        <button
          type="button"
          @click="audioService.toggleAutoSpeech()"
          class="flex items-center justify-center w-8 h-8 rounded-lg transition-all border cursor-pointer"
          :class="[
            audioService.autoSpeechEnabled.value
              ? 'bg-amber-500/20 border-amber-500/50 text-amber-300 hover:bg-amber-500/30'
              : 'bg-slate-900/80 border-slate-700/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          ]"
          :title="audioService.autoSpeechEnabled.value ? 'Auto-Narration ON (Click to disable)' : 'Auto-Narration OFF (Click to enable)'"
        >
          <Volume2 class="w-4 h-4" />
        </button>
      </div>

      <BableFishSelector />

      <!-- Session Settings (Memory & Configuration) -->
      <button
        type="button"
        @click="emit('openSettings')"
        class="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-900/80 border border-slate-700/60 text-slate-400 hover:text-white hover:border-amber-500/50 hover:bg-amber-500/10 transition-all cursor-pointer"
        title="Session Settings & Turn Memory"
      >
        <Sliders class="w-4 h-4" />
      </button>

      <!-- Leave / Exit Session Button -->
      <button
        type="button"
        @click="emit('exitSession')"
        class="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-900/80 border border-slate-700/60 text-slate-400 hover:text-rose-400 hover:border-rose-500/50 hover:bg-rose-500/10 transition-all cursor-pointer"
        title="Exit Session (Return to Portal)"
      >
        <LogOut class="w-4 h-4" />
      </button>

      <!-- Mobile Interact Toggle (Only on mobile) -->
      <button
        type="button"
        @click="emit('toggleMobileInteract')"
        class="md:hidden flex items-center justify-center px-3 py-1.5 rounded-xl bg-amber-500/20 border border-amber-500/50 text-amber-300 hover:bg-amber-500/30 transition-all text-xs font-black uppercase tracking-wider shadow-lg active:scale-95 cursor-pointer"
        title="Toggle Interact Menu"
      >
        <MapIcon class="w-4 h-4" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.comic-title {
  font-family: 'Acme', sans-serif;
  letter-spacing: 0.05em;
}

.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}

/* Tooltip animation */
.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.97);
}
</style>
