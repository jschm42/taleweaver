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
const clockTick = ref(false)
const isDebugVisuals = ref(false)

const {
  sheet,
  status,
  messages,
  gameOverReason,
  autoVisualize,
  entities,
  connect,
  disconnect,
  sendMessage,
  revealIllustration
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

        <!-- Auto-Visualize Toggle -->
        <div 
          class="flex items-center gap-2 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg cursor-pointer transition-all hover:bg-slate-700"
          :class="{ 'border-cyan-500/50': autoVisualize }"
          @click="autoVisualize = !autoVisualize"
          title="Toggle Auto-Visualize (Advanced Image Gen)"
        >
          <i class="ra ra-camera-shot text-base" :class="autoVisualize ? 'text-cyan-400' : 'text-slate-500'"></i>
          <span class="hidden lg:inline text-xs font-bold uppercase tracking-tighter" :class="autoVisualize ? 'text-cyan-400' : 'text-slate-500'">Visuals</span>
          <div :class="['w-6 h-3 rounded-full relative transition-colors duration-300', autoVisualize ? 'bg-cyan-600' : 'bg-slate-900']">
            <div :class="['absolute top-0.5 w-2 h-2 bg-white rounded-full transition-all duration-300', autoVisualize ? 'left-3.5' : 'left-0.5']"></div>
          </div>
        </div>
      </div>
    </header>

    <div class="flex-grow flex overflow-hidden">
      <!-- Left Sidebar: Inhabitants & Discovery -->
      <aside v-if="entities.length > 0" class="hidden xl:flex w-72 bg-slate-900 border-r border-slate-800 flex-col p-6 animate-fade-in shrink-0 overflow-y-auto custom-scrollbar">
        <div class="flex items-center justify-between gap-2 mb-6">
          <div class="flex items-center gap-2">
            <i class="ra ra-venoms-trap text-emerald-500"></i>
            <h3 class="text-xs font-bold uppercase tracking-widest text-slate-500">World Inhabitants</h3>
          </div>
          <button 
            @click="isDebugVisuals = !isDebugVisuals" 
            class="p-1.5 rounded bg-slate-800 border border-slate-700 hover:border-cyan-500/50 transition-all"
            :title="isDebugVisuals ? 'Disable Debug Visuals' : 'Enable Debug Visuals'"
          >
            <i class="ra ra-eye-shield text-xs" :class="isDebugVisuals ? 'text-cyan-400' : 'text-slate-500'"></i>
          </button>
        </div>

        <div class="space-y-4">
          <div v-for="ent in entities" :key="ent.id" class="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-2 group transition-all hover:border-slate-700">
            <div v-if="isDebugVisuals && ent.image_url" class="h-24 w-full rounded-lg overflow-hidden border border-white/5 bg-slate-900 mb-2">
              <img :src="'http://localhost:8000' + ent.image_url" class="w-full h-full object-cover opacity-80" />
            </div>

            <div class="flex items-center justify-between">
              <span class="text-xs font-bold" :class="ent.entity_type === 'NPC' ? 'text-cyan-400' : 'text-amber-400'">
                {{ ent.name }}
              </span>
              <span class="text-[9px] font-mono text-slate-600 uppercase">{{ ent.entity_type }}</span>
            </div>
            
            <p class="text-[10px] text-slate-500 leading-relaxed italic line-clamp-2">{{ ent.description }}</p>

            <button 
              v-if="ent.image_url"
              @click="revealIllustration(ent.name, ent.image_url)"
              class="w-full py-2 bg-slate-900 hover:bg-emerald-500/10 border border-slate-800 hover:border-emerald-500/30 rounded-lg text-[9px] font-bold uppercase tracking-widest text-slate-400 hover:text-emerald-400 transition-all flex items-center justify-center gap-2"
            >
              <i class="ra ra-camera"></i>
              Reveal Illustration
            </button>
          </div>
        </div>
      </aside>

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
