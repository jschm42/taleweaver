<script setup lang="ts">
/**
 * GameView — The active adventure screen
 *
 * Connects to the given game session and displays the chat,
 * intercepting commands and showing the character sheet + world map.
 */
import { onBeforeUnmount, onMounted, ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import ChatWindow from '@/components/ChatWindow.vue'
import CharacterSheetModal from '@/components/CharacterSheetModal.vue'
import MapModal from '@/components/MapModal.vue'
import { useGameSocket } from '@/composables/useGameSocket'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const showSheet = ref(false)
const showMap = ref(false)
const clockTick = ref(false)  // triggers brief highlight animation

const {
  messages,
  sheet,
  mermaidData,
  currentSceneImage,
  status,
  gameOverReason,
  connect,
  disconnect,
  sendMessage,
} = useGameSocket()

/**
 * Formats in_game_time (minutes) into a human-readable in-game clock.
 * Game day starts at 06:00. One game-minute = one real second (heartbeat pace).
 */
const gameTime = computed(() => {
  if (!sheet.value) return null
  const totalMinutes = sheet.value.in_game_time ?? 0
  const startHour = 6  // in-game day starts at 06:00
  const minutesInDay = 24 * 60
  const offsetMinutes = (totalMinutes + startHour * 60) % minutesInDay
  const day = Math.floor((totalMinutes + startHour * 60) / minutesInDay) + 1
  const hh = String(Math.floor(offsetMinutes / 60)).padStart(2, '0')
  const mm = String(offsetMinutes % 60).padStart(2, '0')
  return { day, time: `${hh}:${mm}` }
})

// Flash the clock on every update to give a living-time feel
watch(() => sheet.value?.in_game_time, () => {
  clockTick.value = true
  setTimeout(() => { clockTick.value = false }, 600)
})

const goBack = () => {
  disconnect()
  router.push({ name: 'portal' })
}

onMounted(() => {
  if (props.id) {
    connect(props.id)
  }
})

watch(() => props.id, (newId) => {
  disconnect()
  if (newId) {
    connect(newId)
  }
})

onBeforeUnmount(() => {
  disconnect()
})
</script>

<template>
  <main class="min-h-screen bg-slate-950 flex flex-col font-sans">
    <!-- Header Navigation -->
    <header class="bg-slate-900 border-b border-slate-800 px-6 py-4 flex justify-between items-center z-10 shrink-0">
      <!-- Left: back + title -->
      <div class="flex items-center gap-4">
        <button 
          @click="goBack" 
          class="p-2 rounded-full bg-slate-800 border border-slate-700 hover:bg-slate-700 transition-colors"
          title="Return to Portal"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-slate-300" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </button>
        <div>
          <h1 class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500">TaleWeaver Engine</h1>
          <p class="text-slate-500 text-xs mt-0.5">Session: {{ props.id.substring(0, 8) }}</p>
        </div>
      </div>

      <!-- Center: In-Game Clock -->
      <div class="hidden sm:flex flex-col items-center select-none" :class="{ 'clock-tick': clockTick }">
        <template v-if="gameTime">
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-2xl font-mono font-bold text-amber-300 tracking-widest leading-none">
              {{ gameTime.time }}
            </span>
          </div>
          <span class="text-xs font-semibold tracking-widest text-amber-600 mt-0.5 uppercase">Day {{ gameTime.day }}</span>
        </template>
        <template v-else>
          <span class="text-2xl font-mono font-bold text-slate-600 tracking-widest opacity-40">--:--</span>
          <span class="text-xs text-slate-700 mt-0.5 tracking-wider uppercase opacity-40">Day -</span>
        </template>
      </div>

      <!-- Right: action buttons -->
      <div class="flex items-center gap-2">
        <!-- Map Button -->
        <button
          class="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-300 text-sm font-medium transition-colors"
          :class="{ 'border-emerald-500/50 text-emerald-400': mermaidData }"
          @click="showMap = true"
          title="Open World Map (/map)"
        >
          <i class="ra ra-map text-base" :class="mermaidData ? 'text-emerald-500' : 'text-slate-400'"></i>
          <span class="hidden sm:inline">World Map</span>
        </button>

        <!-- Character Sheet Button -->
        <button
          class="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-300 text-sm font-medium transition-colors"
          @click="showSheet = true"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-emerald-500" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clip-rule="evenodd" />
          </svg>
          <span class="hidden sm:inline">Character</span>
        </button>
      </div>
    </header>

    <!-- Main Game Area -->
    <div class="flex-grow relative overflow-hidden flex flex-col items-center p-4 sm:p-6 w-full max-w-5xl mx-auto">
      <div v-if="gameOverReason" class="w-full bg-red-900/20 border border-red-500/30 p-4 rounded-xl mb-4 text-red-400 font-medium flex items-center gap-3 shadow-lg backdrop-blur-sm shrink-0">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span>{{ gameOverReason }}</span>
      </div>

      <!-- Scene Visual Container -->
      <Transition name="slide-up">
        <div 
          v-if="currentSceneImage" 
          class="w-full max-h-48 md:max-h-64 mb-4 rounded-2xl overflow-hidden border border-slate-800 shadow-2xl relative group shrink-0"
        >
          <img 
            :src="currentSceneImage" 
            class="w-full h-full object-cover grayscale-[0.2] group-hover:grayscale-0 transition-all duration-700"
            alt="Scene Visual"
          />
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 to-transparent"></div>
        </div>
      </Transition>

      <ChatWindow
        class="w-full flex-grow shadow-[0_8px_30px_rgb(0,0,0,0.5)] rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur-xl overflow-hidden"
        :messages="messages"
        :status="status"
        @send="sendMessage"
        @open-sheet="showSheet = true"
      />
    </div>

    <!-- Modals -->
    <CharacterSheetModal :open="showSheet" :sheet="sheet" @close="showSheet = false" />
    <MapModal :open="showMap" :mermaid-src="mermaidData" @close="showMap = false" />
  </main>
</template>

<style scoped>
/* Brief amber pulse whenever in_game_time advances */
.clock-tick span {
  animation: clockPulse 0.6s ease-out;
}

@keyframes clockPulse {
  0%   { color: #fbbf24; text-shadow: 0 0 12px rgba(251,191,36,0.8); }
  100% { color: inherit;  text-shadow: none; }
}
</style>
