<script setup lang="ts">
/**
 * ImmersiveHeader — Atmospheric top bar for the immersive RPG view
 *
 * Displays scene and adventure metadata, tracked quest badge, in-game clock,
 * speech controls, BabelFish language selector, and experience counter.
 */
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
} from 'lucide-vue-next'

const props = defineProps<{
  sceneName?: string | null
  adventureTitle?: string | null
  creator?: string | null
  copyright?: string | null
  trackedQuest?: any
  gameTime?: { dateShort: string; time: string } | null
  clockTick?: boolean
  exp?: number
  mode?: 'rpg' | 'story' | 'chat'
}>()

const emit = defineEmits<{
  openChronicles: []
  openQuests: []
  openSettings: []
  toggleMobileInteract: []
}>()
</script>

<template>
  <header class="relative z-20 flex items-center justify-between px-4 py-3 sm:px-6 sm:py-3.5 bg-slate-950/75 backdrop-blur-md border-b border-slate-800/80 shadow-2xl shrink-0">
    <!-- Left: Scene Title & Back / Chronicles -->
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
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-[0.2em] bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
            Scene
          </span>
          <h2 class="text-sm sm:text-base font-black text-white uppercase tracking-wider truncate drop-shadow-md comic-title">
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
      <!-- In-Game Clock -->
      <GameClockWidget :game-time="props.gameTime || null" :clock-tick="props.clockTick || false" />

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

      <!-- Experience XP -->
      <div v-if="props.exp !== undefined && props.mode !== 'chat'" class="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-black tracking-wider">
        <i class="ra ra-laurels text-sm"></i>
        <span>{{ props.exp }} XP</span>
      </div>

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
</style>
