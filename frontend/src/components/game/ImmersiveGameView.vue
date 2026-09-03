<script setup lang="ts">
/**
 * ImmersiveGameView — Aesthetic Comic-Style RPG View
 *
 * Immersive full-scene view orchestrating:
 * - Full-screen scene background with atmospheric overlays
 * - Top header with scene details, tracked quest, clock, and speech controls
 * - Left character stage with portrait cards and active speaker auras
 * - Center story area with interactive scene hotspots (exits, switches, items)
 *   and comic story feed (dialogue bubbles, narration boxes, turn history)
 * - Bottom action bar and user input with speech-to-text voice recording
 */
import { ref, computed, toRef } from 'vue'
import type { ChatMessage } from '@/types'
import type { ConnectionStatus } from '@/composables/useGameSocket'
import { getImageUrl } from '@/utils/game_icons'
import { useComicTurns } from '@/composables/useComicTurns'
import ImmersiveHeader from './immersive/ImmersiveHeader.vue'
import ImmersiveCharacterStage from './immersive/ImmersiveCharacterStage.vue'
import ImmersiveSceneHotspots from './immersive/ImmersiveSceneHotspots.vue'
import ImmersiveStoryFeed from './immersive/ImmersiveStoryFeed.vue'
import ImmersiveActionBar from './immersive/ImmersiveActionBar.vue'
import ImmersiveInputBar from './immersive/ImmersiveInputBar.vue'

const props = defineProps<{
  messages: ChatMessage[]
  status: ConnectionStatus
  npcMetadata: Record<string, any>
  entities: any[]
  inventory: any[]
  sceneExits: any[]
  sceneSwitches: any[]
  items: any[]
  trackedQuest?: any
  statusText?: string
  showDebugLog?: boolean
  debugLogs?: { timestamp: string; content: string }[]
  inventoryGlow?: boolean
  mapGlow?: boolean
  questGlow?: boolean
  activeActionId?: string | null
  mode?: 'rpg' | 'story' | 'chat'
  inputLocked?: boolean
  sheet?: any
  gameId?: string
  currentSceneImage?: string | null
  adventureImage?: string | null
  currentSceneName?: string | null
  currentSceneDescription?: string | null
  promptSuggestions?: string[]
  exp?: number
  gameTime?: { dateShort: string; time: string } | null
  clockTick?: boolean
  isCheckpointSaving?: boolean
  exitTraversalBusy?: string
  exitUnlockBusy?: boolean
}>()

const emit = defineEmits<{
  send: [content: string]
  openSheet: []
  openMap: []
  openQuests: []
  openChronicles: []
  openDebug: []
  openWalkthrough: []
  npcHover: [entityOrName: any, event: MouseEvent]
  npcLeave: []
  itemHover: [item: any, event: MouseEvent]
  itemLeave: []
  takeDirect: [entity: any]
  npcContextmenu: [entity: any, event: MouseEvent]
  itemContextmenu: [item: any, event: MouseEvent]
  selectAction: [actionId: string | null]
  npcClick: [name: string]
  itemClick: [item: any]
  traverseExit: [exit: any]
  switchFlip: [entity: any]
}>()

// --- State: Scene Image & Fallbacks ---
const brokenImages = ref<Record<string, boolean>>({})
const handleImageError = (path?: string | null) => {
  if (!path) return
  brokenImages.value[path] = true
}
const showImage = (path?: string | null) => {
  return !!path && !brokenImages.value[path]
}

const activeSceneImageUrl = computed(() => {
  if (props.currentSceneImage && showImage(props.currentSceneImage)) {
    return getImageUrl(props.currentSceneImage)
  }
  if (props.adventureImage && showImage(props.adventureImage)) {
    return getImageUrl(props.adventureImage)
  }
  return null
})

// --- State: Turn Evaluation & Input Blocking ---
const isEvaluating = computed(() => {
  return props.status === 'connecting' || props.status === 'loading' || !!props.inputLocked
})

const canSendInput = computed(() => {
  return (
    (props.status === 'connected' || props.status === 'completed') &&
    !props.inputLocked &&
    !isEvaluating.value &&
    !props.sheet?.agent_active
  )
})

// --- Comic Turns Composable ---
const {
  gameTurns,
  activeTurnIndex,
  activeTurn,
  viewingTurnIndex,
  activeSpeakers,
  npcs,
  goToTurn,
  goToLatestTurn,
  getEntityForHover,
} = useComicTurns({
  messages: toRef(props, 'messages'),
  entities: toRef(props, 'entities'),
  npcMetadata: toRef(props, 'npcMetadata'),
  sheet: toRef(props, 'sheet'),
})

// Mobile Hotspot Drawer
const showMobileInteract = ref(false)

// Input Bar Template Ref
const inputBarRef = ref<InstanceType<typeof ImmersiveInputBar> | null>(null)

function handleSend(content: string) {
  emit('send', content)
  goToLatestTurn()
}

function handleNpcClick(npc: any) {
  if (npc.id === 'PLAYER') {
    emit('openSheet')
  } else {
    if (!canSendInput.value) return
    emit('npcClick', npc.name)
    inputBarRef.value?.setInputText(`/say to ${npc.name}: `)
  }
}

function handleSuggestionSelect(suggestion: string) {
  if (!canSendInput.value) return
  inputBarRef.value?.setInputText(suggestion)
}

defineExpose({
  setInputText: (text: string) => {
    inputBarRef.value?.setInputText(text)
  },
  appendText: (text: string) => {
    inputBarRef.value?.appendText(text)
  },
  toggleSayPrefix: () => {
    inputBarRef.value?.toggleSayPrefix()
  },
})
</script>

<template>
  <div class="relative w-full h-full flex flex-col justify-between overflow-hidden select-none bg-slate-950 font-sans">
    <!-- 1. FULL VIEW SCENE BACKGROUND -->
    <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none">
      <img
        v-if="activeSceneImageUrl"
        :src="activeSceneImageUrl"
        class="w-full h-full object-cover object-center filter brightness-[0.9] saturate-[1.1] contrast-[1.05] scale-[1.01] transition-all duration-1000"
        alt="Scene background"
        @error="handleImageError(props.currentSceneImage || props.adventureImage)"
      />
      <div v-else class="w-full h-full bg-gradient-to-b from-slate-900 via-slate-950 to-black"></div>

      <!-- Atmospheric overlays -->
      <div class="absolute inset-0 bg-black/20"></div>
      <div class="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-transparent to-slate-950/40"></div>
      <div class="absolute inset-0 bg-gradient-to-r from-slate-950/60 via-transparent to-slate-950/40"></div>
    </div>

    <!-- 2. TOP ATMOSPHERIC HEADER BAR -->
    <ImmersiveHeader
      :scene-name="props.currentSceneName || props.sheet?.current_scene"
      :adventure-title="props.sheet?.adventure_title"
      :creator="props.sheet?.creator"
      :copyright="props.sheet?.copyright"
      :tracked-quest="props.trackedQuest"
      :game-time="props.gameTime"
      :clock-tick="props.clockTick"
      :exp="props.exp"
      :mode="props.mode"
      @open-chronicles="emit('openChronicles')"
      @open-quests="emit('openQuests')"
      @toggle-mobile-interact="showMobileInteract = !showMobileInteract"
    />

    <!-- 3. MAIN INTERACTIVE STAGE AREA -->
    <div class="relative z-10 flex-grow min-h-0 flex flex-row gap-2 sm:gap-4 p-2 sm:p-4 lg:p-6 overflow-hidden">
      <!-- 3A. LEFT / CHARACTER STAGE -->
      <ImmersiveCharacterStage
        :npcs="npcs"
        :active-speakers="activeSpeakers"
        @npc-click="handleNpcClick"
        @npc-hover="(npc, event) => emit('npcHover', getEntityForHover(npc), event)"
        @npc-leave="emit('npcLeave')"
        @npc-contextmenu="(npc, event) => emit('npcContextmenu', npc, event)"
      />

      <!-- 3B. CENTER / STORY AREA WITH SCENE HOTSPOTS & COMIC FEED -->
      <main class="flex-1 flex flex-col justify-between min-h-0 relative overflow-hidden">
        <ImmersiveSceneHotspots
          :scene-exits="props.sceneExits"
          :scene-switches="props.sceneSwitches"
          :items="props.items"
          :is-evaluating="isEvaluating"
          :show-mobile-interact="showMobileInteract"
          :current-scene-name="props.currentSceneName || props.sheet?.current_scene"
          @traverse-exit="(exit) => emit('traverseExit', exit)"
          @switch-flip="(sw) => emit('switchFlip', sw)"
          @item-click="(item) => emit('itemClick', item)"
          @item-hover="(item, event) => emit('itemHover', item, event)"
          @item-leave="emit('itemLeave')"
          @item-contextmenu="(item, event) => emit('itemContextmenu', item, event)"
          @take-direct="(item) => emit('takeDirect', item)"
        />

        <ImmersiveStoryFeed
          :game-turns="gameTurns"
          :active-turn="activeTurn"
          :active-turn-index="activeTurnIndex"
          :viewing-turn-index="viewingTurnIndex"
          :is-evaluating="isEvaluating"
          :status-text="props.statusText"
          :sheet="props.sheet"
          :entities="props.entities"
          :current-scene-description="props.currentSceneDescription"
          :npc-metadata="props.npcMetadata"
          :game-id="props.gameId"
          @go-to-turn="goToTurn"
          @go-to-latest-turn="goToLatestTurn"
          @open-sheet="emit('openSheet')"
          @npc-click="(name) => emit('npcClick', name)"
          @item-click="(item) => emit('itemClick', item)"
          @take-direct="(item) => emit('takeDirect', item)"
          @npc-hover="(entity, event) => emit('npcHover', entity, event)"
          @npc-leave="emit('npcLeave')"
          @npc-contextmenu="(entity, event) => emit('npcContextmenu', entity, event)"
        />
      </main>
    </div>

    <!-- 4. BOTTOM ACTION BAR & USER INPUT -->
    <footer class="relative z-20 flex flex-col bg-slate-950/95 backdrop-blur-xl border-t border-slate-800/90 shadow-[0_-10px_30px_rgba(0,0,0,0.8)] shrink-0">
      <ImmersiveActionBar
        :inventory="props.inventory"
        :tracked-quest="props.trackedQuest"
        :inventory-glow="props.inventoryGlow"
        :map-glow="props.mapGlow"
        :quest-glow="props.questGlow"
        :prompt-suggestions="props.promptSuggestions"
        :can-send-input="canSendInput"
        @open-quests="emit('openQuests')"
        @open-map="emit('openMap')"
        @open-sheet="emit('openSheet')"
        @open-chronicles="emit('openChronicles')"
        @open-walkthrough="emit('openWalkthrough')"
        @select-suggestion="handleSuggestionSelect"
      />

      <ImmersiveInputBar
        ref="inputBarRef"
        :can-send-input="canSendInput"
        :is-evaluating="isEvaluating"
        :status-text="props.statusText"
        :agent-active="props.sheet?.agent_active"
        :debug-mode="!!props.sheet?.debug_mode"
        @send="handleSend"
      />
    </footer>
  </div>
</template>
