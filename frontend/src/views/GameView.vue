<script setup lang="ts">
/**
 * GameView — The active adventure screen
 *
 * Connects to the given game session and displays the chat,
 * intercepting commands and showing the character sheet + world map.
 */
import { ref, watch, computed, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import CharacterSheetModal from '@/components/game/CharacterSheetModal.vue'
import MapModal from '@/components/game/MapModal.vue'
import QuestsModal from '@/components/game/QuestsModal.vue'
import WalkthroughModal from '@/components/game/WalkthroughModal.vue'
import GameOverScreen from '@/components/game/GameOverScreen.vue'
import SuccessScreen from '@/components/game/SuccessScreen.vue'
import DebugModal from '@/components/game/DebugModal.vue'
import StatBar from '@/components/game/StatBar.vue'
import GameScenePanel from '@/components/game/GameScenePanel.vue'
import GameNpcsPanel from '@/components/game/GameNpcsPanel.vue'
import GameItemsPanel from '@/components/game/GameItemsPanel.vue'
import GameQuestTracker from '@/components/game/GameQuestTracker.vue'
import GameClockWidget from '@/components/game/GameClockWidget.vue'
import GameDialogPanel from '@/components/game/GameDialogPanel.vue'
import FightDialogModal from '@/components/game/FightDialogModal.vue'
import ContextMenu from '@/components/game/ContextMenu.vue'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'
import { useGameAutoSpeak } from '@/composables/useGameAutoSpeak'
import { useGameProgressState } from '@/composables/useGameProgressState'
import { useGameUiFeedback } from '@/composables/useGameUiFeedback'
import { useGameInteractionState } from '@/composables/useGameInteractionState'
import { useGameSessionLifecycle } from '@/composables/useGameSessionLifecycle'
import { useGameCommandFlow } from '@/composables/useGameCommandFlow'
import { refreshUser } from '@/store/auth'
import { getImageUrl, getItemIcon, hasRenderableImagePath } from '@/utils/game_icons'
import { audioService } from '@/services/audioService'
import { type GameSettings } from '@/services/gameViewService'
import { gameCommandService } from '@/services/gameCommandService'
import { gameActionService } from '@/services/gameActionService'
import { fixNewlines, hasNonZero } from '@/services/hoverEntityService'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const showSheet = ref(false)
const showMap = ref(false)
const showQuests = ref(false)
const showDebugLog = ref(false)
const { notifications, removeNotification, addNotification } = useNotifications()
const gameSettings = ref<GameSettings>({
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
  combat,
  isCompleted,
  inputLocked,
  pendingTerminalEpilogue,
  statusText,
  debugLogs,
  inventoryGlow,
  mapGlow,
  questGlow,
  connect,
  disconnect,
  sendMessage,
  createTerminalEpilogue
} = useGameSocket()

const {
  showSuccess,
  showGameOver,
  trackedQuestId,
  clockTick,
  gameTime,
  continueCompletedGame,
  continueGameOverReadOnly,
  setTrackedQuest,
} = useGameProgressState({
  sheet,
  quests,
  status,
  isCompleted,
  pendingTerminalEpilogue,
  gameSettings,
  createTerminalEpilogue,
  refreshUser,
})

const trackedQuest = computed(() => quests.value?.find(q => q.id === trackedQuestId.value))

onBeforeUnmount(() => {
  audioService.stop()
})

const activeActionId = ref<string | null>(null)
const isPassRunning = computed(() => status.value === 'connecting' || status.value === 'loading')
const isActionInputBlocked = computed(() => inputLocked.value || isPassRunning.value || audioService.isPlaying.value || audioService.isGenerating.value)
const showVoiceUnlockHint = computed(() => audioService.autoSpeechEnabled.value && !audioService.isUnlocked.value)

const handleEntityClick = async (entity: any) => {
  if (isActionInputBlocked.value) return
  if (activeActionId.value) {
    const { command, errorMessage } = gameCommandService.resolveEntityActionCommand(activeActionId.value, entity)

    if (errorMessage) {
      addNotification(errorMessage, 'error')
      activeActionId.value = null
      return
    }

    activeActionId.value = null
    if (command) {
      await handlePlayerInput(command)
    }
  } else {
    // Default behavior for click (e.g. pick up if portable item)
    if (gameCommandService.shouldAutoTakeOnEntityClick(entity)) {
      await handleTakeDirect(entity)
    }
  }
}

// Split entities into NPCs and Objects, and inject the player as the top-listed NPC
const npcs = computed(() => {
  const worldNpcs = entities.value.filter(e => e.entity_type === 'NPC')
  if (sheet.value && sheet.value.name) {
    const playerEntity = {
      id: 'PLAYER',
      entity_type: 'NPC',
      name: sheet.value.name ? `You (${sheet.value.name})` : 'You',
      description: sheet.value.description || 'Your character in this adventure.',
      image_url: sheet.value.profile_image || null,
      role: sheet.value.role || null,
      hp: typeof sheet.value.hp === 'number' ? sheet.value.hp : 100,
      max_hp: typeof sheet.value.max_hp === 'number' ? sheet.value.max_hp : 100,
      mana: typeof sheet.value.mana === 'number' ? sheet.value.mana : 50,
      max_mana: typeof sheet.value.max_mana === 'number' ? sheet.value.max_mana : 50,
      stamina: typeof sheet.value.stamina === 'number' ? sheet.value.stamina : 50,
      max_stamina: typeof sheet.value.max_stamina === 'number' ? sheet.value.max_stamina : 50,
      inventory: Array.isArray(sheet.value.inventory) ? sheet.value.inventory : []
    }
    return [playerEntity, ...worldNpcs]
  }
  return worldNpcs
})
const items = computed(() => entities.value.filter(e => e.entity_type === 'OBJECT'))
const inventoryItems = computed(() => sheet.value?.inventory ?? [])
const combatConsumables = computed(() => (sheet.value?.inventory ?? []).filter((item: any) => item?.item_type === 'CONSUMABLE'))
const isCombatActive = computed(() => !!combat.value?.active)
const showCombatDialog = computed(() => {
  if (isClosingCombat.value) return false
  return !!combat.value && (!!combat.value.active || !!combat.value.loot_pending || !!combat.value.outcome)
})
const combatActionInFlight = ref(false)
const isClosingCombat = ref(false)
const isCombatEvaluating = computed(() => combatActionInFlight.value)
const showsMechanics = computed(() => {
  const mode = (sheet.value as any)?.rule_enforcement_mode as string | undefined
  return mode === 'rpg' || mode === 'story' || mode === 'strict'
})

watch(combat, (newCombat) => {
  if (!newCombat) {
    isClosingCombat.value = false
  }
})

useGameUiFeedback({
  sheet,
  nodes,
  quests,
  inventoryGlow,
  mapGlow,
  questGlow,
})

const handleTakeDirect = async (entity: any) => {
  if (isActionInputBlocked.value) return
  await sendMessage(`/take_direct ${entity.id || entity.name}`)
}
const currentSceneDescription = computed(() => nodes.value[sheet.value?.scene_id || '']?.description || 'The current location of your adventure.')

const {
  showWalkthrough,
  showDebug,
  walkthroughData,
  fullWorldDebug,
  goBack,
  openDebugInspector,
  revealWalkthrough,
  buyHint,
  handlePlayerInput,
} = useGameCommandFlow({
  routeId: computed(() => props.id),
  sheet,
  isActionInputBlocked,
  isCombatActive,
  disconnect,
  router,
  sendMessage,
  showMap,
  showSheet,
  showQuests,
  addNotification,
})

const { speakLatestAssistantMessage } = useGameAutoSpeak({
  messages,
  status,
  inputLocked,
  isCombatActive,
  currentSceneDescription,
  sheet,
  npcMetadata,
  sessionId: computed(() => props.id),
})

const handleTrackQuest = (questId: string | null) => {
  setTrackedQuest(questId)
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

useGameSessionLifecycle({
  routeId: computed(() => props.id),
  status,
  gameSettings,
  router,
  connect,
  disconnect,
  closePanels: () => {
    showSheet.value = false
    showMap.value = false
    showQuests.value = false
    showWalkthrough.value = false
    showDebug.value = false
  },
})

const {
  hoveredEntity,
  mousePos,
  tooltipImageFailed,
  contextMenu,
  tooltipStyle,
  isConsumableHover,
  handleHover,
  handleChatNpcHover,
  onTooltipImageError,
  openContextMenu,
  handleMenuSelect,
} = useGameInteractionState({
  isActionInputBlocked,
  ruleMode: computed(() => sheet.value?.rule_enforcement_mode),
  npcMetadata,
  handlePlayerInput,
})

const handleUnlockVoice = () => {
  audioService.unlock()
  speakLatestAssistantMessage({ force: true })
}

const handleEquipFromSheet = async (name: string) => {
  await gameActionService.sendIfUnlocked(isActionInputBlocked.value, sendMessage, `/equip ${name}`)
}

const handleUnequipFromSheet = async (slot: string) => {
  await gameActionService.sendIfUnlocked(isActionInputBlocked.value, sendMessage, `/unequip ${slot}`)
}

const handleConsumeFromSheet = async (name: string) => {
  await gameActionService.sendIfUnlocked(isActionInputBlocked.value, sendMessage, `/consume ${name}`)
}

const handleSheetChanged = async () => {
  if (!gameActionService.shouldRunRulePass(isActionInputBlocked.value, sheet.value?.rule_enforcement_mode)) return
  await sendMessage('/rule-pass')
}

const handleCombatAttack = async () => {
  await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, '/attack')
}

const handleCombatRun = async () => {
  await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, '/run')
}

const handleCombatConsume = async (name: string) => {
  await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, `/consume ${name}`)
}

const handleCombatDebugWin = async () => {
  await sendMessage('/debug win_fight')
}

const handleCombatDebugLoose = async () => {
  await sendMessage('/debug loose_fight')
}

const handleLootTake = async (item: any) => {
  await gameActionService.runLootCommand(combatActionInFlight, sendMessage, 'take', item)
}

const handleLootLeave = async (item: any) => {
  await gameActionService.runLootCommand(combatActionInFlight, sendMessage, 'leave', item)
}

const handleLootDone = async () => {
  await gameActionService.runLootDone(
    combatActionInFlight,
    sendMessage,
    () => { isClosingCombat.value = true },
    () => {
      // Ensure the guard resets eventually once the combat state is truly gone
      if (!combat.value) {
        isClosingCombat.value = false
      }
    }
  )
}

watch(showCombatDialog, (visible) => {
  if (!visible) {
    combatActionInFlight.value = false
  }
})
</script>

<template>
  <main 
    class="h-full min-h-0 bg-slate-950 flex flex-col font-sans overflow-hidden relative"
    :class="{ 'selection-mode': activeActionId }"
  >
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

    <!-- Header Navigation -->    <header class="bg-transparent px-4 md:px-8 pt-8 pb-4 flex flex-col lg:flex-row items-start gap-6 z-10 shrink-0 relative min-h-[110px]">
      <!-- Left: back + Adventure Title -->
      <div class="flex items-center gap-4 z-10 min-w-0 xl:w-72 shrink-0">
        <button 
          @click="goBack" 
          class="flex items-center gap-3 px-5 py-2.5 rounded-xl bg-slate-800/60 border border-slate-700/50 hover:bg-emerald-500/10 hover:border-emerald-500/40 transition-all duration-300 backdrop-blur-md shadow-xl group shrink-0"
          title="Return to Portal"
        >
          <i class="ra ra-back-arrow text-sm text-slate-100 group-hover:text-emerald-400 transition-colors"></i>
          <span class="text-xxs font-black uppercase tracking-[0.2em] text-slate-100 group-hover:text-white transition-colors">Back</span>
        </button>

        <div class="flex flex-col min-w-0">
          <h1 class="text-xl md:text-3xl font-normal text-white drop-shadow-[0_2px_15px_rgba(0,0,0,0.8)] tracking-wide whitespace-nowrap truncate" style="font-family: 'Acme', sans-serif;">
            {{ sheet?.adventure_title || 'Chronicle' }}
          </h1>
          <div v-if="sheet?.adventure_version" class="text-[10px] font-mono font-bold text-slate-500 opacity-60 uppercase tracking-widest mt-1">
            v{{ sheet.adventure_version }}
          </div>
        </div>
      </div>

      <!-- Center: Active Quest Tracker (Matches Chat Width) -->
      <div class="flex-grow w-full lg:w-auto min-w-0 flex justify-center">
        <GameQuestTracker :tracked-quest="trackedQuest" />
      </div>

      <!-- Right Area (Clock is now absolute to save space and align quest better) -->
      <div class="absolute top-8 right-4 md:right-8 lg:mt-0 z-20">
        <GameClockWidget :game-time="gameTime" :clock-tick="clockTick" />
      </div>
      <div v-if="sheet?.debug_mode" class="absolute top-24 left-1/2 -translate-x-1/2 z-[100] px-4 py-1 bg-rose-600/80 backdrop-blur-md border border-rose-400/50 rounded-full text-[10px] font-black text-white uppercase tracking-[0.2em] animate-pulse shadow-lg">
        Debug Protocol Active
      </div>
    </header>


    <div class="flex-grow min-h-0 flex overflow-hidden relative">
      <div
        v-if="showVoiceUnlockHint"
        class="absolute top-2 left-1/2 -translate-x-1/2 z-30 px-4 py-2 rounded-xl border border-amber-400/40 bg-amber-300/10 backdrop-blur-md shadow-lg max-w-[92%]"
      >
        <div class="flex items-center gap-3 text-xs text-amber-100">
          <i class="ra ra-sound-on text-amber-300"></i>
          <span>Auto-Speak is enabled, but browser policy blocks audio until your first interaction.</span>
          <button
            type="button"
            class="px-2.5 py-1 rounded-md bg-amber-400/20 hover:bg-amber-400/35 border border-amber-300/40 text-amber-50 font-semibold transition-colors"
            @click="handleUnlockVoice"
          >
            Enable voice
          </button>
        </div>
      </div>

      <!-- Left Sidebar: Scene, inhabitants & Discovery -->
      <aside v-if="entities.length > 0 || currentSceneImage" class="hidden xl:flex w-72 bg-slate-900/20 backdrop-blur-md border border-slate-800/50 rounded-3xl flex-col p-6 animate-fade-in shrink-0 overflow-y-auto custom-scrollbar relative z-10 m-6 shadow-2xl">
        <GameScenePanel
          :scene-id="sheet?.scene_id"
          :scene-name="sheet?.current_scene"
          :scene-description="currentSceneDescription"
          :scene-image="currentSceneImage"
          :show-image="showImage"
          :is-debug="!!sheet?.debug_mode"
          @hover="(payload, event) => handleHover(payload, event)"
          @move="(event) => mousePos = { x: event.clientX, y: event.clientY }"
          @leave="hoveredEntity = null"
          @contextmenu="(payload, event) => openContextMenu(payload, event)"
          @click="handleEntityClick"
          @image-error="(path) => handleImageError(path)"
        />

        <GameNpcsPanel
          :npcs="npcs"
          :show-image="showImage"
          :mode="sheet?.rule_enforcement_mode"
          :is-debug="!!sheet?.debug_mode"
          @hover="(entity, event) => handleHover({ ...entity, entity_type: 'NPC' }, event)"
          @move="(event) => mousePos = { x: event.clientX, y: event.clientY }"
          @leave="hoveredEntity = null"
          @contextmenu="(entity, event) => openContextMenu({ ...entity, entity_type: 'NPC' }, event)"
          @click="handleEntityClick"
          @image-error="(path) => handleImageError(path)"
        />

        <GameItemsPanel
          :items="items"
          :show-image="showImage"
          :is-debug="!!sheet?.debug_mode"
          @hover="(entity, event) => handleHover(entity, event)"
          @move="(event) => mousePos = { x: event.clientX, y: event.clientY }"
          @leave="hoveredEntity = null"
          @contextmenu="(entity, event) => openContextMenu(entity, event)"
          @click="handleEntityClick"
          @image-error="(path) => handleImageError(path)"
          @take-direct="handleTakeDirect"
        />
      </aside>

      <!-- Main Game Area -->
      <GameDialogPanel
        ref="dialogPanel"
        :messages="messages"
        :status="status"
        :input-locked="isActionInputBlocked"
        :npc-metadata="npcMetadata"
        :entities="entities"
        :inventory-items="inventoryItems"
        :tracked-quest="trackedQuest"
        :status-text="statusText"
        :show-debug-log="showDebugLog"
        :debug-logs="debugLogs"
        :game-over-reason="gameOverReason"
        :exp="sheet?.exp || 0"
        :mode="sheet?.rule_enforcement_mode"
        :inventory-glow="inventoryGlow"
        :map-glow="mapGlow"
        :quest-glow="questGlow"
        :active-action-id="activeActionId"
        :sheet="sheet"
        :game-id="props.id"
        :current-scene-description="currentSceneDescription"
        @send="handlePlayerInput"
        @open-sheet="showSheet = true"
        @open-map="showMap = true"
        @open-quests="showQuests = true"
        @select-action="(id) => activeActionId = id"
        @npc-hover="handleChatNpcHover"
        @npc-leave="hoveredEntity = null"
        @npc-click="(name) => handleEntityClick({ name, entity_type: 'NPC' })"
        @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'A mysterious item in your possession.' }, event)"
        @item-leave="hoveredEntity = null"
        @item-click="handleEntityClick"
        @take-direct="handleTakeDirect"
        @open-debug="openDebugInspector"
        @toggle-debug-log="(val) => showDebugLog = val"
        @npc-contextmenu="(entity, event) => openContextMenu(entity, event)"
        @item-contextmenu="(entity, event) => openContextMenu(entity, event)"
      />
    </div>

    <!-- Modals -->
    <CharacterSheetModal 
      :open="showSheet" 
      :sheet="sheet" 
      :is-debug="!!sheet?.debug_mode"
      @close="showSheet = false" 
      @equip="handleEquipFromSheet"
      @unequip="handleUnequipFromSheet"
      @consume="handleConsumeFromSheet"
      @changed="handleSheetChanged"
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
      :note="gameOverReason"
      @continue="continueCompletedGame"
      @close="goBack" 
    />
    <GameOverScreen 
      :show="showGameOver" 
      :reason="gameOverReason" 
      @continue="continueGameOverReadOnly"
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

    <FightDialogModal
      :open="showCombatDialog"
      :combat="combat"
      :consumables="combatConsumables"
      :npc-metadata="npcMetadata"
      :player-sheet="sheet"
      :evaluating="isCombatEvaluating"
      :is-debug="!!sheet?.debug_mode"
      @attack="handleCombatAttack"
      @run="handleCombatRun"
      @consume="handleCombatConsume"
      @loot-take="handleLootTake"
      @loot-leave="handleLootLeave"
      @loot-done="handleLootDone"
      @debug-win="handleCombatDebugWin"
      @debug-loose="handleCombatDebugLoose"
      @entity-hover="(entity, event) => handleHover(entity, event)"
      @entity-leave="hoveredEntity = null"
    />

    <!-- HOVER TOOLTIP -->
    <Teleport to="body">
      <Transition name="tooltip">
        <div 
          v-if="hoveredEntity" 
          class="fixed z-[999] pointer-events-none"
          :style="tooltipStyle"
        >
          <div class="w-64 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl backdrop-blur-xl overflow-hidden flex flex-col animate-tooltip-in">
            <!-- Image Area -->
            <div v-if="hasRenderableImagePath(hoveredEntity.image_url) && !tooltipImageFailed" class="h-48 w-full relative">
              <img :src="getImageUrl(hoveredEntity.image_url)" class="absolute inset-0 w-full h-full object-cover object-top" @error="onTooltipImageError" />
              <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
            </div>
            <div v-else class="h-32 w-full relative bg-slate-950 border-b border-slate-800 flex items-center justify-center">
              <i
                :class="[
                  'ra text-4xl',
                  hoveredEntity.entity_type?.toUpperCase() === 'NPC' ? 'ra-player text-cyan-400/80' : 'ra-vest text-amber-400/80'
                ]"
              ></i>
              <div class="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(148,163,184,0.12),transparent_65%)]"></div>
            </div>

            <!-- Content -->
            <div class="p-4 bg-slate-900">
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-bold text-white uppercase tracking-wider">{{ hoveredEntity.name }}</span>
                <span 
                  class="text-xxs px-1.5 py-0.5 rounded border font-mono uppercase"
                  :class="hoveredEntity.entity_type?.toUpperCase() === 'NPC' ? 'border-cyan-500/50 text-cyan-400' : (hoveredEntity.entity_type?.toUpperCase() === 'SCENE' ? 'border-indigo-500/50 text-indigo-400' : 'border-amber-500/50 text-amber-400')"
                >
                  {{ hoveredEntity.entity_type || 'OBJECT' }}
                </span>
              </div>
              <p class="text-xs text-slate-400 leading-relaxed italic mb-3 whitespace-pre-wrap">{{ fixNewlines(hoveredEntity.description) }}</p>

              <!-- NPC Stats -->
              <div v-if="hoveredEntity.entity_type?.toUpperCase() === 'NPC' && sheet?.rule_enforcement_mode !== 'chat'" class="flex flex-col gap-1 mt-3 pt-3 border-t border-slate-800">
                <StatBar v-if="hoveredEntity.hp != null" label="Health" :value="Number(hoveredEntity.hp)" :max="Number(hoveredEntity.max_hp || 100)" color="crimson" size="sm" />
                <StatBar v-if="hoveredEntity.stamina != null" label="Stamina" :value="Number(hoveredEntity.stamina)" :max="Number(hoveredEntity.max_stamina || 100)" color="emerald" size="sm" />
                <StatBar v-if="hoveredEntity.mana != null && sheet?.rule_enforcement_mode === 'rpg'" label="Mana" :value="Number(hoveredEntity.mana)" :max="Number(hoveredEntity.max_mana || 100)" color="sapphire" size="sm" />
              </div>

              <!-- NPC Inventory -->
              <div v-if="hoveredEntity.entity_type?.toUpperCase() === 'NPC' && Array.isArray(hoveredEntity.inventory) && hoveredEntity.inventory.length > 0" class="mt-3 pt-3 border-t border-slate-800">
                <div class="flex items-center gap-1.5 mb-2">
                  <i class="ra ra-treasure-chest text-xxs text-slate-500"></i>
                  <span class="text-xxs font-black uppercase tracking-widest text-slate-500">Possessions</span>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <div 
                    v-for="(item, iidx) in hoveredEntity.inventory" 
                    :key="item?.id || iidx"
                    class="px-2 py-1 rounded-lg bg-slate-950/60 border border-slate-800 text-xxs text-slate-300 flex items-center gap-1.5"
                  >
                    <div v-if="typeof item === 'object' && item?.image_url" class="w-4 h-4 rounded overflow-hidden shrink-0 border border-slate-700">
                      <img :src="getImageUrl(item.image_url)" class="w-full h-full object-cover" />
                    </div>
                    <i v-else-if="typeof item === 'object'" :class="['ra text-[12px]', getItemIcon(item?.item_type || 'PICKABLE'), 'text-amber-500/60']"></i>
                    <i v-else class="ra ra-emerald text-[12px] text-amber-500/60"></i>
                    {{ typeof item === 'object' ? item?.name : item }}
                  </div>
                </div>
              </div>

              <!-- Item Stats -->
              <div v-if="(hoveredEntity.entity_type === 'OBJECT' || hoveredEntity.entity_type === 'ITEM') && sheet?.rule_enforcement_mode !== 'chat'" class="mt-3 pt-3 border-t border-slate-800">
                <div class="grid grid-cols-2 gap-2 text-xxs uppercase font-bold tracking-wider">
                  <!-- Preferred Slot -->
                  <div v-if="hoveredEntity.slot" class="col-span-2 text-slate-500 lowercase italic font-medium">
                    {{ hoveredEntity.slot.replace('_', ' ') }}
                  </div>

                  <template v-if="isConsumableHover">
                    <div v-if="hasNonZero(hoveredEntity.hp_change)" class="text-red-400 flex justify-between">
                      <span>HP</span>
                      <span>{{ Number(hoveredEntity.hp_change) >= 0 ? '+' : '' }}{{ hoveredEntity.hp_change }}</span>
                    </div>
                    <div v-if="hasNonZero(hoveredEntity.mana_change)" class="text-blue-400 flex justify-between">
                      <span>Mana</span>
                      <span>{{ Number(hoveredEntity.mana_change) >= 0 ? '+' : '' }}{{ hoveredEntity.mana_change }}</span>
                    </div>
                    <div v-if="hasNonZero(hoveredEntity.stamina_change)" class="text-emerald-400 flex justify-between">
                      <span>Stamina</span>
                      <span>{{ Number(hoveredEntity.stamina_change) >= 0 ? '+' : '' }}{{ hoveredEntity.stamina_change }}</span>
                    </div>
                  </template>

                  <template v-if="showsMechanics">
                    <div v-if="hasNonZero(hoveredEntity.stat_modifier_strength)" class="text-red-400 flex justify-between">
                      <span>STR</span> <span>+{{ hoveredEntity.stat_modifier_strength }}</span>
                    </div>
                    <div v-if="hasNonZero(hoveredEntity.stat_modifier_dexterity)" class="text-emerald-400 flex justify-between">
                      <span>DEX</span> <span>+{{ hoveredEntity.stat_modifier_dexterity }}</span>
                    </div>
                    <div v-if="hasNonZero(hoveredEntity.stat_modifier_intelligence)" class="text-blue-400 flex justify-between">
                      <span>INT</span> <span>+{{ hoveredEntity.stat_modifier_intelligence }}</span>
                    </div>
                    <div v-if="hasNonZero(hoveredEntity.stat_modifier_wisdom)" class="text-purple-400 flex justify-between">
                      <span>WIS</span> <span>+{{ hoveredEntity.stat_modifier_wisdom }}</span>
                    </div>
                    <div v-if="hasNonZero(hoveredEntity.stat_modifier_charisma)" class="text-pink-400 flex justify-between">
                      <span>CHA</span> <span>+{{ hoveredEntity.stat_modifier_charisma }}</span>
                    </div>
                    <div v-if="hasNonZero(hoveredEntity.stat_modifier_armor_class)" class="text-amber-400 flex justify-between">
                      <span>AC</span> <span>+{{ hoveredEntity.stat_modifier_armor_class }}</span>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- CONTEXT MENU -->
    <Teleport to="body">
      <ContextMenu
        v-if="contextMenu"
        :x="contextMenu.x"
        :y="contextMenu.y"
        :items="contextMenu.items"
        :title="contextMenu.title"
        @close="contextMenu = null"
        @select="handleMenuSelect"
      />
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
              <p class="text-xxs font-black uppercase tracking-widest opacity-50">{{ n.type }}</p>
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

.selection-mode {
  cursor: crosshair !important;
}

.selection-mode .cursor-help {
  cursor: crosshair !important;
}

</style>


