<script setup lang="ts">
/**
 * GameView — The active adventure screen
 *
 * Connects to the given game session and displays the chat,
 * intercepting commands and showing the character sheet + world map.
 */
import { onBeforeUnmount, onMounted, ref, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import CharacterSheetModal from '@/components/game/CharacterSheetModal.vue'
import MapModal from '@/components/game/MapModal.vue'
import QuestsModal from '@/components/game/QuestsModal.vue'
import WalkthroughModal from '@/components/game/WalkthroughModal.vue'
import SuccessScreen from '@/components/game/SuccessScreen.vue'
import DebugModal from '@/components/game/DebugModal.vue'
import GameScenePanel from '@/components/game/GameScenePanel.vue'
import GameNpcsPanel from '@/components/game/GameNpcsPanel.vue'
import GameItemsPanel from '@/components/game/GameItemsPanel.vue'
import GameQuestTracker from '@/components/game/GameQuestTracker.vue'
import GameClockWidget from '@/components/game/GameClockWidget.vue'
import GameDialogPanel from '@/components/game/GameDialogPanel.vue'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'
import { getImageUrl } from '@/utils/game_icons'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const dialogPanel = ref<any>(null)
const showSheet = ref(false)
const showMap = ref(false)
const showQuests = ref(false)
const showWalkthrough = ref(false)
const showSuccess = ref(false)
const showDebug = ref(false)
const showDebugLog = ref(false)
const fullWorldDebug = ref<any | null>(null)
const walkthroughData = ref<any | null>(null)
const trackedQuestId = ref<string | null>(null)
const clockTick = ref(false)
const { notifications, removeNotification } = useNotifications()
const gameSettings = ref<{ clock_24h: boolean; date_format?: 'DD.MM.YY' | 'MM/DD/YY' | 'YY-MM-DD' }>({
  clock_24h: false,
})

const {
  sheet,
  status,
  messages,
  gameOverReason,
  adventureImage,
  entities,
  mermaidData,
  nodes,
  npcMetadata,
  currentSceneImage,
  quests,
  awards,
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
const currentSceneDescription = computed(() => nodes.value[sheet.value?.scene_id || '']?.description || 'The current location of your adventure.')

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

  const dateShort = (() => {
    const d = current.getDate().toString().padStart(2, '0')
    const m = (current.getMonth() + 1).toString().padStart(2, '0')
    const y = current.getFullYear().toString().slice(-2)
    
    switch (gameSettings.value.date_format) {
      case 'MM/DD/YY': return `${m}/${d}/${y}`
      case 'YY-MM-DD': return `${y}-${m}-${d}`
      default: return `${d}.${m}.${y}`
    }
  })()

  const time = current.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: !gameSettings.value.clock_24h,
  }).replace(/^0/, '') // Strip leading zero for cleaner look in 12h

  // In 24h mode, ensure 2-digit hour
  const time24 = current.toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  return { 
    date, 
    dateShort,
    time: gameSettings.value.clock_24h ? time24 : time 
  }
})

// Flash the clock on every update to give a living-time feel
watch(() => sheet.value?.in_game_time, () => {
  clockTick.value = true
  setTimeout(() => { clockTick.value = false }, 600)
})

// Auto-untrack completed quests & Default tracking for new sessions
watch(quests, (newQuests) => {
  if (trackedQuestId.value) {
    const tracked = newQuests.find(q => q.id === trackedQuestId.value)
    if (tracked && tracked.status === 'completed') {
      trackedQuestId.value = null
    }
  }
  
  if (!trackedQuestId.value && newQuests && newQuests.length > 0) {
    const firstMain = newQuests.find(q => q.is_main && q.status === 'open')
    if (firstMain) {
      trackedQuestId.value = firstMain.id
    }
  }
}, { immediate: true })

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
const BASE = '/api'

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {}
  if (authState.token) {
    headers.Authorization = `Bearer ${authState.token}`
  }
  return headers
}

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

const openDebugInspector = async () => {
  showDebug.value = true

  if (!props.id) {
    fullWorldDebug.value = null
    return
  }

  try {
    const res = await fetch(`${BASE}/adventures/${props.id}/chat?include_full_world=true`, {
      headers: authHeaders()
    })
    if (!res.ok) {
      fullWorldDebug.value = null
      return
    }
    const data = await res.json()
    fullWorldDebug.value = data.full_world || null
  } catch {
    fullWorldDebug.value = null
  }
}

const loadWalkthrough = async () => {
  if (!props.id) return
  try {
    const res = await fetch(`${BASE}/adventures/${props.id}/walkthrough`, { headers: authHeaders() })
    if (!res.ok) {
      walkthroughData.value = {
        available: false,
        preview: 'No walkthrough available for this adventure yet.',
        message: 'No walkthrough available for this adventure yet.',
        current_xp: sheet.value?.exp || 0,
        reveal_cost: 200,
        hint_cost: 50,
      }
      return
    }
    walkthroughData.value = await res.json()
  } catch (error) {
    console.error('Failed to load walkthrough', error)
    walkthroughData.value = {
      available: false,
      preview: 'No walkthrough available for this adventure yet.',
      message: 'No walkthrough available for this adventure yet.',
      current_xp: sheet.value?.exp || 0,
      reveal_cost: 200,
      hint_cost: 50,
    }
  }
}

const openWalkthroughPanel = async () => {
  await loadWalkthrough()
  showWalkthrough.value = true
}

const revealWalkthrough = async () => {
  await sendMessage('/walkthrough reveal')
  await loadWalkthrough()
}

const buyHint = async () => {
  await sendMessage('/hint')
  await loadWalkthrough()
}

const handlePlayerInput = async (content: string) => {
  const normalized = content.trim().toLowerCase()
  if (normalized === '/walkthrough') {
    await openWalkthroughPanel()
    return
  }

  if (normalized === '/walkthrough reveal') {
    await revealWalkthrough()
    showWalkthrough.value = true
    return
  }

  if (normalized === '/hint') {
    await buyHint()
    return
  }

  if (normalized === '/debug walkthrough') {
    await sendMessage('/debug walkthrough')
    await loadWalkthrough()
    showWalkthrough.value = true
    return
  }

  await sendMessage(content)
}

const fetchGameSettings = async () => {
  try {
    const res = await fetch(`${BASE}/settings`, { headers: authHeaders() })
    if (res.ok) {
      const data = await res.json()
      if (data.game_settings) gameSettings.value = data.game_settings
    }
  } catch (e) {
    console.error('Failed to fetch game settings', e)
  }
}

const resolveGameIdFromRouteId = async (routeId: string): Promise<string | null> => {
  try {
    const sessions = await api.listSessions()
    const direct = sessions.find((s: any) => s.game_id === routeId)
    if (direct) return routeId

    const match = sessions.find((s: any) => s.template_id === routeId || s.adventure_id === routeId)
    return match?.game_id || null
  } catch (error) {
    console.error('Failed to resolve route id to game session id', error)
    return null
  }
}

const ensureGameIdForRouteId = async (routeId: string): Promise<string | null> => {
  const resolved = await resolveGameIdFromRouteId(routeId)
  if (resolved) return resolved

  // If no active session exists yet, routeId might be a template/adventure id.
  // Try to start one and continue with the returned game id.
  try {
    const created = await api.startSessionForTemplate(routeId)
    return created?.game_id || null
  } catch {
    return null
  }
}

const connectWithRouteFallback = async (routeId: string) => {
  await connect(routeId)
  if (status.value !== 'error') return

  const resolvedGameId = await ensureGameIdForRouteId(routeId)
  if (!resolvedGameId || resolvedGameId === routeId) return

  await router.replace({ name: 'game', params: { id: resolvedGameId } })
}

onMounted(() => {
  void (async () => {
    await fetchGameSettings()
    if (props.id) {
      await connectWithRouteFallback(props.id)
    }
  })()
})

watch(() => props.id, (newId) => {
  disconnect()
  if (newId) {
    void connectWithRouteFallback(newId)
  }
})

onBeforeUnmount(() => {
  disconnect()
})
</script>

<template>
  <main class="h-full min-h-0 bg-slate-950 flex flex-col font-sans overflow-hidden relative">
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

    <!-- Header Navigation -->    <header class="bg-transparent px-4 md:px-8 pt-8 pb-4 grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] items-start gap-6 z-10 shrink-0 relative min-h-[110px]">
      <!-- Left: back + Adventure Title -->
      <div class="flex items-center gap-4 z-10 min-w-0 lg:order-1">
        <button 
          @click="goBack" 
          class="flex items-center gap-3 px-5 py-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-emerald-500/10 hover:border-emerald-500/40 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
          title="Return to Portal"
        >
          <i class="ra ra-back-arrow text-sm text-slate-100 group-hover:text-emerald-400 transition-colors"></i>
          <span class="text-[10px] font-black uppercase tracking-[0.2em] text-slate-100 group-hover:text-white transition-colors">Back</span>
        </button>
        <h1 class="text-xl md:text-3xl font-normal text-white drop-shadow-[0_2px_15px_rgba(0,0,0,0.8)] tracking-wide whitespace-nowrap truncate" style="font-family: 'Acme', sans-serif;">
          {{ sheet?.adventure_title || 'Chronicle' }}
        </h1>
      </div>

      <!-- Center: Active Quest Tracker (Matches Chat Width) -->
      <div class="w-full flex justify-center lg:order-2 min-w-0">
        <GameQuestTracker :tracked-quest="trackedQuest" />
      </div>

      <!-- Right: Clock -->
      <div class="flex justify-end lg:order-3 lg:mt-0 mt-[-10px]">
        <GameClockWidget :game-time="gameTime" :clock-tick="clockTick" />
      </div>
    </header>


    <div class="flex-grow min-h-0 flex overflow-hidden relative">
      <!-- Left Sidebar: Scene, inhabitants & Discovery -->
      <aside v-if="entities.length > 0 || currentSceneImage" class="hidden xl:flex w-72 bg-slate-900/20 backdrop-blur-md border border-slate-800/50 rounded-3xl flex-col p-6 animate-fade-in shrink-0 overflow-y-auto custom-scrollbar relative z-10 m-6 shadow-2xl">
        <GameScenePanel
          :scene-name="sheet?.current_scene"
          :scene-description="currentSceneDescription"
          :scene-image="currentSceneImage"
          :show-image="showImage"
          @hover="(payload, event) => handleHover(payload, event)"
          @move="(event) => mousePos = { x: event.clientX, y: event.clientY }"
          @leave="hoveredEntity = null"
          @image-error="(path) => handleImageError(path)"
        />

        <GameNpcsPanel
          :npcs="npcs"
          :show-image="showImage"
          @hover="(entity, event) => handleHover(entity, event)"
          @move="(event) => mousePos = { x: event.clientX, y: event.clientY }"
          @leave="hoveredEntity = null"
          @image-error="(path) => handleImageError(path)"
        />

        <GameItemsPanel
          :items="items"
          :show-image="showImage"
          @hover="(entity, event) => handleHover(entity, event)"
          @move="(event) => mousePos = { x: event.clientX, y: event.clientY }"
          @leave="hoveredEntity = null"
          @image-error="(path) => handleImageError(path)"
        />
      </aside>

      <!-- Main Game Area -->
      <GameDialogPanel
        ref="dialogPanel"
        :messages="messages"
        :status="status"
        :npc-metadata="npcMetadata"
        :entities="entities"
        :inventory-items="inventoryItems"
        :tracked-quest="trackedQuest"
        :status-text="statusText"
        :show-debug-log="showDebugLog"
        :debug-logs="debugLogs"
        :game-over-reason="gameOverReason"
        :exp="sheet?.exp || 0"
        @send="handlePlayerInput"
        @open-sheet="showSheet = true"
        @open-map="showMap = true"
        @open-quests="showQuests = true"
        @open-walkthrough="openWalkthroughPanel"
        @npc-hover="handleChatNpcHover"
        @npc-leave="hoveredEntity = null"
        @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'A mysterious item in your possession.' }, event)"
        @item-leave="hoveredEntity = null"
        @open-debug="openDebugInspector"
        @toggle-debug-log="(val) => showDebugLog = val"
      />
    </div>

    <!-- Modals -->
    <CharacterSheetModal 
      :open="showSheet" 
      :sheet="sheet" 
      @close="showSheet = false" 
      @item-click="(name) => dialogPanel?.appendText(name)"
      @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'A mysterious item in your possession.' }, event)"
      @item-leave="hoveredEntity = null"
    />
    <MapModal :open="showMap" :mermaid-src="mermaidData" :nodes="nodes" @close="showMap = false" />
    <QuestsModal 
      :is-open="showQuests" 
      :quests="quests" 
      :awards="awards"
      :tracked-quest-id="trackedQuestId" 
      @close="showQuests = false" 
      @track-quest="handleTrackQuest"
    />
    <WalkthroughModal
      :open="showWalkthrough"
      :data="walkthroughData"
      :entities="entities"
      @close="showWalkthrough = false"
      @reveal="revealWalkthrough"
      @hint="buyHint"
      @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'A mysterious item in your possession.' }, event)"
      @item-leave="hoveredEntity = null"
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
        adventureImage,
        fullWorld: fullWorldDebug
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
