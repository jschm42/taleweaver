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
import GameScenePanel from '@/components/game/GameScenePanel.vue'
import GameNpcsPanel from '@/components/game/GameNpcsPanel.vue'
import GameItemsPanel from '@/components/game/GameItemsPanel.vue'
import GameViewHeader from '@/components/game/GameViewHeader.vue'
import GameDialogPanel from '@/components/game/GameDialogPanel.vue'
import FightDialogModal from '@/components/game/FightDialogModal.vue'
import GameHoverTooltip from '@/components/game/GameHoverTooltip.vue'
import GameNotificationsOverlay from '@/components/game/GameNotificationsOverlay.vue'
import ContextMenu from '@/components/game/ContextMenu.vue'
import SetupWarningBanner from '@/components/portal/SetupWarningBanner.vue'
import SessionNoteModal from '@/components/portal/SessionNoteModal.vue'
import { api } from '@/composables/useApi'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'
import { useGameAutoSpeak } from '@/composables/useGameAutoSpeak'
import { useGameProgressState } from '@/composables/useGameProgressState'
import { useGameUiFeedback } from '@/composables/useGameUiFeedback'
import { useGameInteractionState } from '@/composables/useGameInteractionState'
import { useGameSessionLifecycle } from '@/composables/useGameSessionLifecycle'
import { useGameCommandFlow } from '@/composables/useGameCommandFlow'
import { refreshUser } from '@/store/auth'
import { getImageUrl } from '@/utils/game_icons'
import { audioService } from '@/services/audioService'
import { type GameSettings } from '@/services/gameViewService'
import { gameCommandService } from '@/services/gameCommandService'
import { gameActionService } from '@/services/gameActionService'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const showSheet = ref(false)
const sheetDirty = ref(false)
const showMap = ref(false)
const showQuests = ref(false)
const showDebugLog = ref(false)
const showNoteModal = ref(false)
const isSavingNote = ref(false)

const saveSessionNote = async (note: string) => {
  isSavingNote.value = true
  try {
    await api.updateSession(props.id, { status_note: note })
    statusNote.value = note
    addNotification('Session note updated.', 'success')
    showNoteModal.value = false
  } catch (err) {
    addNotification('Failed to update session note.', 'error')
  } finally {
    isSavingNote.value = false
  }
}
const { notifications, removeNotification, addNotification } = useNotifications()
const gameSettings = ref<GameSettings>({
  clock_24h: false,
})

const {
  sheet,
  status,
  messages,
  gameOverReason,
  statusNote,
  adventureImage,
  entities,
  mapData,
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
  openInventoryContextMenu,
  handleMenuSelect,
} = useGameInteractionState({
  isActionInputBlocked,
  ruleMode: computed(() => sheet.value?.rule_enforcement_mode),
  npcMetadata,
  handlePlayerInput,
  onAction: () => {
    if (showSheet.value) sheetDirty.value = true
  }
})

const handleUnlockVoice = () => {
  audioService.unlock()
  speakLatestAssistantMessage({ force: true })
}

const handleEquipFromSheet = async (name: string) => {
  sheetDirty.value = true
  await gameActionService.sendIfUnlocked(isActionInputBlocked.value, sendMessage, `/equip ${name}`)
}

const handleUnequipFromSheet = async (slot: string) => {
  sheetDirty.value = true
  await gameActionService.sendIfUnlocked(isActionInputBlocked.value, sendMessage, `/unequip ${slot}`)
}

const handleConsumeFromSheet = async (name: string) => {
  sheetDirty.value = true
  await gameActionService.sendIfUnlocked(isActionInputBlocked.value, sendMessage, `/consume ${name}`)
}

const handleSheetChanged = async () => {
  sheetDirty.value = false
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

const handleCombatRest = async () => {
  await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, '/rest')
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
        :src="getImageUrl(adventureImage, { thumbnail: true })" 
        class="w-full h-full object-cover blur-sm brightness-[0.5]"
        @error="(e) => {
          const target = e.target as HTMLImageElement
          if (target.src.includes('_thumb')) {
            target.src = getImageUrl(adventureImage)
          } else {
            adventureImage = null
          }
        }"
      >
      <div class="absolute inset-0 bg-gradient-to-b from-transparent via-slate-950/40 to-slate-950"></div>
      <div class="absolute inset-0 bg-gradient-to-r from-transparent via-slate-950/20 to-slate-950"></div>
    </div>

    <GameViewHeader
      :title="sheet?.adventure_title"
      :version="sheet?.adventure_version"
      :tracked-quest="trackedQuest"
      :game-time="gameTime"
      :clock-tick="clockTick"
      :debug-mode="!!sheet?.debug_mode"
      @back="goBack"
      @edit-note="showNoteModal = true"
    />

    <div class="px-12 pt-6">
      <SetupWarningBanner />
    </div>


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
      @close="() => { showSheet = false; if (sheetDirty) handleSheetChanged(); }" 
      @equip="handleEquipFromSheet"
      @unequip="handleUnequipFromSheet"
      @consume="handleConsumeFromSheet"
      @changed="handleSheetChanged"
      @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'A mysterious item in your possession.' }, event)"
      @item-leave="hoveredEntity = null"
      @item-contextmenu="(item, event) => openInventoryContextMenu(item, event)"
    />
    <MapModal :open="showMap" :map-data="mapData" :nodes="nodes" :is-debug="!!sheet?.debug_mode" @close="showMap = false" />
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
    <SessionNoteModal
      v-if="showNoteModal"
      :initial-note="statusNote || ''"
      :is-saving="isSavingNote"
      @close="showNoteModal = false"
      @save="saveSessionNote"
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
      @rest="handleCombatRest"
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
    <GameHoverTooltip
      :hovered-entity="hoveredEntity"
      :tooltip-style="tooltipStyle"
      :tooltip-image-failed="tooltipImageFailed"
      :shows-mechanics="showsMechanics"
      :is-consumable-hover="isConsumableHover"
      :rule-mode="sheet?.rule_enforcement_mode"
      @image-error="onTooltipImageError"
    />

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
    <GameNotificationsOverlay
      :notifications="notifications"
      @dismiss="removeNotification"
    />
  </main>
</template>

<style scoped>
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

.selection-mode {
  cursor: crosshair !important;
}

.selection-mode .cursor-help {
  cursor: crosshair !important;
}

</style>


