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

const {
  sheet,
  status,
  messages,
  gameOverReason,
  autoVisualize,
  entities,
  mermaidData,
  nodes,
  currentSceneImage,
  connect,
  disconnect,
  sendMessage
} = useGameSocket()

// Tooltip & Hover State
const hoveredEntity = ref<any>(null)
const mousePos = ref({ x: 0, y: 0 })

const handleHover = (ent: any, event: MouseEvent) => {
  hoveredEntity.value = ent
  mousePos.value = { x: event.clientX, y: event.clientY }
}

// Split entities into NPCs and Objects, and inject the player as the top-listed NPC
const npcs = computed(() => {
  const worldNpcs = entities.value.filter(e => e.entity_type === 'NPC')
  if (sheet.value && sheet.value.name) {
    const playerEntity = {
      id: 'PLAYER',
      entity_type: 'NPC',
      name: `You (${sheet.value.name})`,
      description: sheet.value.description || '',
      image_url: sheet.value.profile_image || sheet.value.profile_image || null,
      role: sheet.value.role || null
    }
    return [playerEntity, ...worldNpcs]
  }
  return worldNpcs
})
const items = computed(() => entities.value.filter(e => e.entity_type === 'OBJECT'))

/**
 * Formats the session clock as a full datetime derived from the adventure start.
 */
const gameTime = computed(() => {
  if (!sheet.value?.start_datetime) return null

  const start = new Date(sheet.value.start_datetime)
  if (Number.isNaN(start.getTime())) return null

  const elapsedMinutes = sheet.value.in_game_time ?? 0
  const current = new Date(start.getTime() + elapsedMinutes * 60_000)

  const date = current.toLocaleDateString('de-DE', {
    weekday: 'long',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  const time = current.toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  return { date, time }
})

const getItemIcon = (type?: string) => {
  switch (type?.toUpperCase()) {
    case 'CONSUMABLE': return 'ra-bottle-vapors'
    case 'WEAPON': return 'ra-sword'
    case 'TOOL': return 'ra-hammer'
    case 'KEY': return 'ra-old-key'
    case 'READABLE': return 'ra-book'
    case 'WEARABLE': return 'ra-helmet'
    case 'COMBINABLE': return 'ra-gears'
    case 'PICKABLE': return 'ra-hand'
    case 'STATIC': return 'ra-anchor'
    default: return 'ra-quill-ink'
  }
}

const getTypeColor = (type?: string) => {
  switch (type?.toUpperCase()) {
    case 'WEAPON': return 'text-red-400'
    case 'CONSUMABLE': return 'text-emerald-400'
    case 'KEY': return 'text-amber-400'
    case 'READABLE': return 'text-cyan-400'
    case 'WEARABLE': return 'text-blue-400'
    default: return 'text-slate-600'
  }
}

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
  <main class="h-screen bg-slate-950 flex flex-col font-sans overflow-hidden">
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
      <div class="hidden sm:flex flex-col items-center select-none game-clock" :class="{ 'clock-tick': clockTick }">
        <template v-if="gameTime">
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="clock-time text-2xl font-bold text-amber-300 tracking-widest leading-none">
              {{ gameTime.time }}
            </span>
          </div>
          <span class="clock-date text-xs font-semibold tracking-widest text-amber-600 mt-0.5 uppercase">
            {{ gameTime.date }}
          </span>
        </template>
        <template v-else>
          <span class="clock-time text-2xl font-bold text-slate-600 tracking-widest opacity-40">--:--</span>
          <span class="clock-date text-xs text-slate-700 mt-0.5 tracking-wider uppercase opacity-40">--.--.----</span>
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
        <!-- NPCs SECTION -->
        <div v-if="npcs.length > 0">
          <div class="flex items-center justify-between gap-2 mb-4">
            <div class="flex items-center gap-2">
              <i class="ra ra-venoms-trap text-cyan-500"></i>
              <h3 class="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-500/80">Population</h3>
            </div>
          </div>
          <div class="space-y-3 mb-8">
            <div 
              v-for="ent in npcs" 
              :key="ent.id" 
              class="p-3 bg-slate-950 border border-slate-800 rounded-xl group cursor-help transition-all hover:border-cyan-500/40 hover:bg-slate-900/50"
              @mouseenter="handleHover(ent, $event)"
              @mousemove="mousePos = { x: $event.clientX, y: $event.clientY }"
              @mouseleave="hoveredEntity = null"
            >
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold text-slate-400 group-hover:text-cyan-400 transition-colors uppercase tracking-tight">{{ ent.name }}</span>
                <i class="ra ra-pawn text-[10px] text-slate-800"></i>
              </div>
            </div>
          </div>
        </div>

        <!-- ITEMS SECTION -->
        <div v-if="items.length > 0">
          <div class="flex items-center justify-between gap-2 mb-4">
            <div class="flex items-center gap-2">
              <i class="ra ra-locked-fortress text-amber-500"></i>
              <h3 class="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-500/80">Discovery</h3>
            </div>
          </div>
          <div class="space-y-3">
            <div 
              v-for="ent in items" 
              :key="ent.id" 
              class="p-3 bg-slate-950 border border-slate-800 rounded-xl group cursor-help transition-all hover:border-amber-500/40 hover:bg-slate-900/50"
              @mouseenter="handleHover(ent, $event)"
              @mousemove="mousePos = { x: $event.clientX, y: $event.clientY }"
              @mouseleave="hoveredEntity = null"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 overflow-hidden">
                  <i :class="['ra text-xs shrink-0', getItemIcon(ent.item_type), getTypeColor(ent.item_type)]"></i>
                  <span class="text-xs font-bold text-slate-400 group-hover:text-amber-400 transition-colors uppercase tracking-tight truncate">{{ ent.name }}</span>
                </div>
                <i class="ra ra-gem text-[10px] text-slate-800"></i>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- Main Game Area -->
      <div class="flex-grow relative overflow-hidden flex flex-col items-center p-4 sm:p-6 w-full max-w-5xl mx-auto min-h-0">
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
    <MapModal :open="showMap" :mermaid-src="mermaidData" :nodes="nodes" @close="showMap = false" />

    <!-- HOVER TOOLTIP -->
    <Teleport to="body">
      <Transition name="tooltip">
        <div 
          v-if="hoveredEntity" 
          class="fixed z-[100] pointer-events-none transition-all duration-75"
          :style="{ left: (mousePos.x + 20) + 'px', top: (mousePos.y - 40) + 'px' }"
        >
          <div class="w-64 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl backdrop-blur-xl overflow-hidden flex flex-col animate-tooltip-in">
            <!-- Image Area -->
            <div v-if="hoveredEntity.image_url" class="h-32 w-full relative">
              <img :src="'http://localhost:8000' + hoveredEntity.image_url" class="absolute inset-0 w-full h-full object-cover" />
              <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
            </div>

            <!-- Content -->
            <div class="p-4 bg-slate-900">
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-bold text-white uppercase tracking-wider">{{ hoveredEntity.name }}</span>
                <span 
                  class="text-[8px] px-1.5 py-0.5 rounded border font-mono uppercase"
                  :class="hoveredEntity.entity_type === 'NPC' ? 'border-cyan-500/50 text-cyan-400' : 'border-amber-500/50 text-amber-400'"
                >
                  {{ hoveredEntity.entity_type }}
                </span>
              </div>
              <p class="text-xs text-slate-400 leading-relaxed italic">{{ hoveredEntity.description }}</p>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </main>
</template>

<style scoped>
@font-face {
  font-family: 'OrbitronClock';
  src: url('@/assets/fonts/Orbitron-VariableFont_wght.ttf') format('truetype');
  font-weight: 100 900;
  font-style: normal;
}

.game-clock .clock-time,
.game-clock .clock-date {
  font-family: 'OrbitronClock', monospace;
}

/* Brief amber pulse whenever in_game_time advances */
.clock-tick span {
  animation: clockPulse 0.6s ease-out;
}

@keyframes clockPulse {
  0%   { color: #fbbf24; text-shadow: 0 0 12px rgba(251,191,36,0.8); }
  100% { color: inherit;  text-shadow: none; }
}

/* Tooltip Animations */
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.2s, transform 0.2s; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.95) translateY(5px); }

.animate-tooltip-in {
  animation: toolTipIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(10px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* Sidebar Scrollbar */
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.1); }
</style>
