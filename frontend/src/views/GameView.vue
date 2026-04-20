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
import QuestsModal from '@/components/QuestsModal.vue'
import SuccessScreen from '@/components/SuccessScreen.vue'
import DebugModal from '@/components/DebugModal.vue'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'
import { getItemIcon, getTypeColor, getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const chatWindow = ref<any>(null)
const showSheet = ref(false)
const showMap = ref(false)
const showQuests = ref(false)
const showSuccess = ref(false)
const showDebug = ref(false)
const showDebugLog = ref(false)
const trackedQuestId = ref<string | null>(null)
const clockTick = ref(false)
const { notifications, removeNotification } = useNotifications()

const {
  sheet,
  status,
  messages,
  gameOverReason,
  autoVisualize,
  adventureImage,
  entities,
  mermaidData,
  nodes,
  npcMetadata,
  currentSceneImage,
  quests,
  isCompleted,
  statusText,
  debugLogs,
  connect,
  disconnect,
  sendMessage
} = useGameSocket()

const trackedQuest = computed(() => quests.value?.find(q => q.id === trackedQuestId.value))

// Tooltip & Hover State
const hoveredEntity = ref<any>(null)
const mousePos = ref({ x: 0, y: 0 })

const handleHover = (ent: any, event: MouseEvent) => {
  hoveredEntity.value = ent
  mousePos.value = { x: event.clientX, y: event.clientY }
}

const handleChatNpcHover = (name: string, event: MouseEvent) => {
  const metadata = npcMetadata.value[name]
  if (metadata) {
    hoveredEntity.value = metadata
    mousePos.value = { x: event.clientX, y: event.clientY }
  }
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
const inventoryItems = computed(() => sheet.value?.inventory ?? [])

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

// Flash the clock on every update to give a living-time feel
watch(() => sheet.value?.in_game_time, () => {
  clockTick.value = true
  setTimeout(() => { clockTick.value = false }, 600)
})

watch(isCompleted, (val) => {
  if (val) {
    showSuccess.value = true
  }
})

const handleTrackQuest = (questId: string | null) => {
  trackedQuestId.value = questId
  showQuests.value = false
}

const brokenImages = ref<Record<string, boolean>>({})

const handleImageError = (path?: string | null) => {
  if (!path) return
  brokenImages.value[path] = true
}

const showImage = (path?: string | null) => {
  return !!path && !brokenImages.value[path]
}

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
  <main class="h-screen bg-slate-950 flex flex-col font-sans overflow-hidden relative">
    <!-- Full-Width Adventure Background (Top Third) -->
    <div v-if="adventureImage" class="absolute inset-x-0 top-0 h-[35vh] pointer-events-none z-0 overflow-hidden">
      <img 
        :src="getImageUrl(adventureImage)" 
        class="w-full h-full object-cover blur-sm brightness-[0.5]"
        @error="adventureImage = null"
      >
      <div class="absolute inset-0 bg-gradient-to-b from-transparent via-slate-950/40 to-slate-950"></div>
      <div class="absolute inset-0 bg-gradient-to-r from-transparent via-slate-950/20 to-slate-950"></div>
    </div>

    <!-- Header Navigation -->    <header class="bg-transparent px-8 py-6 flex items-start justify-center z-10 shrink-0 relative">
      <!-- Left: back + Adventure Title (Absolute) -->
      <div class="absolute left-8 top-8 flex items-center gap-4 z-10">
        <button 
          @click="goBack" 
          class="p-2 rounded-full bg-slate-800/60 border border-slate-700/50 hover:bg-slate-700 transition-colors backdrop-blur-md shadow-xl"
          title="Return to Portal"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-slate-100" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
          </svg>
        </button>
        <h1 class="text-2xl md:text-3xl font-normal text-white drop-shadow-[0_2px_15px_rgba(0,0,0,0.8)] tracking-wide whitespace-nowrap" style="font-family: 'Acme', sans-serif;">
          {{ sheet?.adventure_title || 'Chronicle' }}
        </h1>
      </div>

      <!-- Center: Active Quest Tracker (Matches Chat Width) -->
      <div class="w-full max-w-5xl mx-auto px-4">
        <transition name="fade">
          <div v-if="trackedQuest" class="animate-fade-in pointer-events-none w-full">
            <div :class="['quest-panel-header glassmorphism flex items-start gap-4 px-5 py-4 rounded-2xl border border-white/5 pointer-events-auto shadow-2xl', trackedQuest.status === 'completed' ? 'opacity-60' : '']">
              <div class="w-10 h-10 flex items-center justify-center bg-indigo-500/10 rounded-xl border border-indigo-500/20 text-indigo-400 shrink-0 mt-0.5 shadow-inner">
                <i :class="['ra text-sm', trackedQuest.status === 'completed' ? 'ra-check' : 'ra-scroll']"></i>
              </div>
              <div class="flex-grow min-w-0">
                <div class="flex items-center justify-between mb-1">
                  <div :class="['text-sm font-black text-white uppercase tracking-tight truncate', trackedQuest.status === 'completed' ? 'line-through text-slate-400' : '']">
                    {{ trackedQuest.title }}
                  </div>
                  <div class="shrink-0 text-right ml-4">
                     <span v-if="trackedQuest.status === 'completed'" class="text-[9px] font-black uppercase tracking-[0.2em] text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded">Completed</span>
                     <span v-else class="text-[10px] font-black text-indigo-400 tabular-nums uppercase tracking-widest">{{ trackedQuest.exp_reward }} XP</span>
                  </div>
                </div>
                <div :class="['text-[11px] text-slate-400 leading-relaxed line-clamp-3', trackedQuest.status === 'completed' ? 'line-through text-slate-500' : '']">
                  {{ trackedQuest.description }}
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <!-- Right: Clock (Absolute) -->
      <div class="absolute right-8 top-8 z-10">
        <div class="flex flex-col items-end select-none game-clock" :class="{ 'clock-tick': clockTick }">
          <template v-if="gameTime">
            <div class="flex items-center gap-2 px-3 py-1.5 bg-slate-800/40 border border-slate-700/30 rounded-xl backdrop-blur-md">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-amber-500/80 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span class="clock-time text-lg font-black text-amber-300 tracking-widest leading-none">
                {{ gameTime.time }}
              </span>
            </div>
          </template>
        </div>
      </div>
    </header>


    <div class="flex-grow flex overflow-hidden relative">
      <!-- Left Sidebar: Scene, inhabitants & Discovery -->
      <aside v-if="entities.length > 0 || currentSceneImage" class="hidden xl:flex w-72 bg-slate-900/20 backdrop-blur-md border border-slate-800/50 rounded-3xl flex-col p-6 animate-fade-in shrink-0 overflow-y-auto custom-scrollbar relative z-10 m-6 shadow-2xl">
        <!-- CURRENT SCENE SECTION -->
        <div class="mb-8">
          <div class="flex items-center gap-2 mb-4">
            <i class="ra ra-mountain-cave text-indigo-500"></i>
            <h3 class="text-[10px] font-bold uppercase tracking-[0.2em] text-indigo-500/80">Location</h3>
          </div>
          <div 
            class="relative group cursor-help overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 transition-all hover:border-indigo-500/50"
            @mouseenter="handleHover({ 
              name: sheet?.current_scene || 'Current Scene', 
              description: nodes[sheet?.scene_id || '']?.description || 'The current location of your adventure.',
              image_url: currentSceneImage
            }, $event)"
            @mousemove="mousePos = { x: $event.clientX, y: $event.clientY }"
            @mouseleave="hoveredEntity = null"
          >
            <div class="aspect-video w-full relative overflow-hidden bg-slate-900 flex items-center justify-center">
              <img 
                v-if="currentSceneImage && showImage(currentSceneImage)" 
                :src="getImageUrl(currentSceneImage)" 
                class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                @error="handleImageError(currentSceneImage)"
              />
              <div v-else class="w-full h-full flex items-center justify-center bg-slate-800">
                <i :class="['ra text-7xl opacity-20', getItemIcon('SCENE'), 'text-indigo-400']"></i>
              </div>
              <div class="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-slate-950 to-transparent">
                <span class="text-xs font-bold text-white uppercase tracking-wider truncate block overflow-hidden shadow-sm">{{ sheet?.current_scene || 'Unknown' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- NPCs SECTION -->
        <div v-if="npcs.length > 0">
          <div class="flex items-center justify-between gap-2 mb-4">
            <div class="flex items-center gap-2">
              <i class="ra ra-venoms-trap text-cyan-500"></i>
              <h3 class="text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-500/80">Population</h3>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3 mb-8">
            <div 
              v-for="ent in npcs" 
              :key="ent.id" 
              class="relative bg-slate-950/40 border border-slate-800/40 rounded-2xl group cursor-help transition-all hover:border-cyan-500/40 hover:bg-slate-900/50 p-2 flex flex-col items-center shadow-lg"
              @mouseenter="handleHover(ent, $event)"
              @mousemove="mousePos = { x: $event.clientX, y: $event.clientY }"
              @mouseleave="hoveredEntity = null"
            >
              <div class="absolute top-1 right-1 z-10 flex gap-1">
                <i v-if="ent.id === 'PLAYER'" class="ra ra-pawn text-[8px] text-cyan-400 drop-shadow-md"></i>
                <i v-else class="ra ra-speech-bubble text-[8px] text-slate-600 group-hover:text-cyan-500 transition-colors drop-shadow-md"></i>
              </div>
              <div class="w-16 h-16 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center shrink-0 mb-2">
                <img 
                  v-if="ent.image_url && showImage(ent.image_url)" 
                  :src="getImageUrl(ent.image_url)" 
                  class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                  @error="handleImageError(ent.image_url)"
                />
                <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/50">
                  <i :class="['ra text-2xl', getItemIcon('NPC'), 'text-cyan-500/40']"></i>
                </div>
              </div>
              <span class="text-[10px] font-bold text-slate-400 group-hover:text-cyan-400 transition-colors uppercase tracking-tight truncate w-full text-center px-1 leading-tight">{{ ent.name }}</span>
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
              class="p-3 bg-slate-950/40 border border-slate-800/40 rounded-2xl group cursor-help transition-all hover:border-amber-500/40 hover:bg-slate-900/50 shadow-lg"
              @mouseenter="handleHover(ent, $event)"
              @mousemove="mousePos = { x: $event.clientX, y: $event.clientY }"
              @mouseleave="hoveredEntity = null"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 overflow-hidden">
                  <div v-if="ent.image_url && showImage(ent.image_url)" class="relative w-6 h-6 rounded-lg overflow-hidden border border-slate-800 shrink-0">
                    <img :src="getImageUrl(ent.image_url)" class="w-full h-full object-cover" @error="handleImageError(ent.image_url)" />
                  </div>
                  <div v-else class="w-6 h-6 rounded-lg border border-slate-800/50 bg-slate-900/50 flex items-center justify-center shrink-0">
                    <i :class="['ra text-[10px]', getItemIcon(ent.item_type), getTypeColor(ent.item_type)]"></i>
                  </div>
                  <span class="text-xs font-bold text-slate-400 group-hover:text-amber-400 transition-colors uppercase tracking-tight truncate">{{ ent.name }}</span>
                </div>
                <i class="ra ra-gem text-[10px] text-slate-800"></i>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- Main Game Area -->
      <div class="flex-grow relative overflow-hidden flex flex-col items-stretch p-4 sm:p-6 w-full max-w-5xl mx-auto min-h-0">
        <div v-if="gameOverReason" class="w-full bg-red-900/20 border border-red-500/30 p-4 rounded-xl mb-4 text-red-400 font-medium flex items-center gap-3 shadow-lg backdrop-blur-sm shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{{ gameOverReason }}</span>
        </div>

        <ChatWindow 
          ref="chatWindow"
          :messages="messages" 
          :status="status"
          :npc-metadata="npcMetadata"
          :entities="entities"
          :inventory="inventoryItems"
          @send="sendMessage"
          @open-sheet="showSheet = true"
          @open-map="showMap = true"
          @open-quests="showQuests = true"
          @npc-hover="handleChatNpcHover"
          @npc-leave="hoveredEntity = null"
          @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'A mysterious item in your possession.' }, event)"
          @item-leave="hoveredEntity = null"
          :tracked-quest="null"
          :status-text="statusText"
          @open-debug="showDebug = true"
          @toggle-debug-log="(val) => showDebugLog = val"
          :show-debug-log="showDebugLog"
          :debug-logs="debugLogs"
        />

        <!-- XP Badge (Bottom Right Overlaid on Chat) -->
        <div class="absolute bottom-6 right-10 z-20 pointer-events-none animate-fade-in">
          <span class="text-sm font-black text-slate-300/60 uppercase tracking-[0.2em] tabular-nums">
            {{ sheet?.exp || 0 }} XP
          </span>
        </div>
      </div>
    </div>

    <!-- Modals -->
    <CharacterSheetModal 
      :open="showSheet" 
      :sheet="sheet" 
      @close="showSheet = false" 
      @item-click="(name) => chatWindow?.appendText(name)"
      @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'A mysterious item in your possession.' }, event)"
      @item-leave="hoveredEntity = null"
    />
    <MapModal :open="showMap" :mermaid-src="mermaidData" :nodes="nodes" @close="showMap = false" />
    <QuestsModal 
      :is-open="showQuests" 
      :quests="quests" 
      :tracked-quest-id="trackedQuestId" 
      @close="showQuests = false" 
      @track-quest="handleTrackQuest"
    />
    <SuccessScreen 
      :show="showSuccess" 
      :total-exp="sheet?.exp || 0" 
      @close="goBack" 
    />
    <DebugModal 
      :open="showDebug" 
      :data="{ 
        sheet, 
        messages, 
        status, 
        entities, 
        quests, 
        nodes, 
        npcMetadata, 
        currentSceneImage,
        adventureImage
      }" 
      @close="showDebug = false" 
    />

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
              <img :src="getImageUrl(hoveredEntity.image_url)" class="absolute inset-0 w-full h-full object-cover" />
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
  
    <!-- TOAST NOTIFICATIONS -->
    <Teleport to="body">
      <div class="fixed bottom-8 right-8 z-[300] flex flex-col gap-3 pointer-events-none">
        <TransitionGroup name="notif">
          <div 
            v-for="n in notifications" 
            :key="n.id"
            :class="[
              'pointer-events-auto px-6 py-4 rounded-2xl border backdrop-blur-2xl shadow-2xl flex items-center gap-4 min-w-[320px] max-w-md animate-notif-in',
              n.type === 'error' ? 'bg-red-500/10 border-red-500/20 text-red-400' : 
              n.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
              'bg-blue-500/10 border-blue-500/20 text-blue-400'
            ]"
          >
            <i :class="[
              'text-lg',
              n.type === 'error' ? 'ra ra-cancel' : 
              n.type === 'success' ? 'ra ra-circle' : 'ra ra-light-bulb'
            ]"></i>
            <div class="flex-grow">
              <p class="text-[10px] font-black uppercase tracking-widest opacity-50">{{ n.type }}</p>
              <p class="text-xs font-bold leading-relaxed">{{ n.message }}</p>
            </div>
            <button @click="removeNotification(n.id)" class="opacity-50 hover:opacity-100 transition-opacity">
              <i class="ra ra-cancel text-xs"></i>
            </button>
          </div>
        </TransitionGroup>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Acme&display=swap');
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

/* Ensure RPG Awesome icons render correctly */
.ra {
  font-family: 'rpgawesome' !important;
  display: inline-block;
  line-height: 1;
  vertical-align: middle;
}

/* Notification Animations */
.notif-enter-active, .notif-leave-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.notif-enter-from { opacity: 0; transform: translateX(50px) scale(0.9); }
.notif-leave-to { opacity: 0; transform: translateX(50px) scale(0.9); }

@keyframes notifIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}

.animate-notif-in {
  animation: notifIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.quest-panel-header {
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
