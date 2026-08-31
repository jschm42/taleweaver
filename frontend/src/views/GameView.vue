<script setup lang="ts">
/**
 * GameView — The active adventure screen
 *
 * Connects to the given game session and displays the chat,
 * intercepting commands and showing the character sheet + world map.
 */
import { ref, watch, computed, onBeforeUnmount, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import CharacterSheetModal from '@/components/game/CharacterSheetModal.vue'
import MapModal from '@/components/game/MapModal.vue'
import QuestsModal from '@/components/game/QuestsModal.vue'
import WalkthroughModal from '@/components/game/WalkthroughModal.vue'
import GameOverScreen from '@/components/game/GameOverScreen.vue'
import SuccessScreen from '@/components/game/SuccessScreen.vue'
import DebugModal from '@/components/game/DebugModal.vue'
import GameLocationPanel from '@/components/game/GameLocationPanel.vue'
import GameNpcsPanel from '@/components/game/GameNpcsPanel.vue'
import GameItemsPanel from '@/components/game/GameItemsPanel.vue'
import GameWorldMemoryPanel from '@/components/game/GameWorldMemoryPanel.vue'
import GameViewHeader from '@/components/game/GameViewHeader.vue'
import GameDialogPanel from '@/components/game/GameDialogPanel.vue'
import ImmersiveGameView from '@/components/game/ImmersiveGameView.vue'
import FightDialogModal from '@/components/game/FightDialogModal.vue'
import CombatLootPopup from '@/components/game/CombatLootPopup.vue'
import ContainerModal from '@/components/game/ContainerModal.vue'
import ContainerUnlockModal from '@/components/game/ContainerUnlockModal.vue'
import SwitchStateModal from '@/components/game/SwitchStateModal.vue'
import SwitchUnlockModal from '@/components/game/SwitchUnlockModal.vue'
import TextLogModal from '@/components/game/TextLogModal.vue'
import GameHoverTooltip from '@/components/game/GameHoverTooltip.vue'
import GameNotificationsOverlay from '@/components/game/GameNotificationsOverlay.vue'
import ChroniclesModal from '@/components/game/ChroniclesModal.vue'
import CheckpointRestoreConfirmModal from '@/components/game/CheckpointRestoreConfirmModal.vue'
import ContextMenu from '@/components/game/ContextMenu.vue'
import SetupWarningBanner from '@/components/portal/SetupWarningBanner.vue'
import SessionNoteModal from '@/components/portal/SessionNoteModal.vue'
import { Sparkles } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import { configState, refreshConfig } from '@/store/config'
import { useGameSocket } from '@/composables/useGameSocket'
import { useNotifications } from '@/composables/useNotifications'
import { useGameAutoSpeak } from '@/composables/useGameAutoSpeak'
import { useGameUiFeedback } from '@/composables/useGameUiFeedback'
import { useGameInteractionState } from '@/composables/useGameInteractionState'
import { useGameSessionLifecycle } from '@/composables/useGameSessionLifecycle'
import { useGameCommandFlow } from '@/composables/useGameCommandFlow'
import { useGameProgressState } from '@/composables/useGameProgressState'
import { refreshUser } from '@/store/auth'
import { getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import { audioService } from '@/services/audioService'
import { type GameSettings } from '@/services/gameViewService'
import { gameCommandService } from '@/services/gameCommandService'
import { gameActionService } from '@/services/gameActionService'
import type { SessionCheckpoint } from '@/types'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const route = useRoute()
const showSheet = ref(false)
const sheetDirty = ref(false)
const showMap = ref(false)
const showQuests = ref(false)
const isMobileSidebarOpen = ref(false)
const isMobileViewport = ref(typeof window !== 'undefined' && window.matchMedia('(max-width: 1023px)').matches)
const isHeaderCollapsed = ref(
  localStorage.getItem('tw_header_collapsed') === 'true' ||
  (localStorage.getItem('tw_header_collapsed') === null && isMobileViewport.value)
)
const isQuestTrackerHidden = ref(localStorage.getItem('tw_quest_tracker_hidden') === 'true')
const gameViewMode = ref<'immersive' | 'classic'>(
  (localStorage.getItem('tw_game_view_mode') as any) || 'immersive'
)

watch(gameViewMode, (val) => {
  localStorage.setItem('tw_game_view_mode', val)
})

const toggleGameViewMode = () => {
  gameViewMode.value = gameViewMode.value === 'immersive' ? 'classic' : 'immersive'
}

let viewportMql: MediaQueryList | null = null
const handleViewportChange = (e: MediaQueryListEvent) => {
  isMobileViewport.value = e.matches
  if (e.matches && localStorage.getItem('tw_header_collapsed') === null) {
    isHeaderCollapsed.value = true
  }
}
if (typeof window !== 'undefined') {
  viewportMql = window.matchMedia('(max-width: 1023px)')
  viewportMql.addEventListener('change', handleViewportChange)
}

watch(isHeaderCollapsed, (val) => {
  localStorage.setItem('tw_header_collapsed', val ? 'true' : 'false')
})
watch(isQuestTrackerHidden, (val) => {
  localStorage.setItem('tw_quest_tracker_hidden', val ? 'true' : 'false')
})
const showDebugLog = ref(false)
const showNoteModal = ref(false)
const isSavingNote = ref(false)
const showChroniclesModal = ref(false)
const showRestoreConfirmModal = ref(false)
const isLoadingCheckpoints = ref(false)
const restoringCheckpointId = ref<string | null>(null)
const checkpoints = ref<SessionCheckpoint[]>([])
const pendingRestoreCheckpoint = ref<SessionCheckpoint | null>(null)
const showContainerModal = ref(false)
const showUnlockModal = ref(false)
const unlockModalContainer = ref<any>(null)
const unlockModalBusy = ref(false)
const unlockModalError = ref('')
const containerBusy = ref(false)
const containerCodeBusy = ref(false)
const showTextLogModal = ref(false)
const activeTextLog = ref<{
  id: string
  title: string
  format: string
  content: string
  imageUrl?: string | null
} | null>(null)
const activeContainer = ref<{
  id: string
  name: string
  items: any[]
} | null>(null)
const activeCodeContainer = ref<{ id: string; name: string; source: 'scene' | 'inventory' } | null>(null)
const awaitingContainerCodeInput = ref(false)
const dialogPanel = ref<any>(null)

// --- Switch unlock modal state ---
const showSwitchUnlockModal = ref(false)
const switchUnlockModalEntity = ref<any>(null)
const switchUnlockTargetState = ref('')
const switchUnlockBusy = ref(false)
const switchUnlockError = ref('')
const showSwitchStateModal = ref(false)   // primary state-picker modal

const showExitUnlockModal = ref(false)
const exitUnlockModalTarget = ref<any>(null)
const exitUnlockBusy = ref(false)
const exitUnlockError = ref('')
const exitTraversalBusy = ref<string>('')
const exitViewMode = ref<'cards' | 'radar'>('cards')

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
  promptSuggestions,
  worldMemories,
  worldRumors,
  statusText,
  debugLogs,
  inventoryGlow,
  mapGlow,
  questGlow,
  agentPaused,
  agentStepByStep,
  isCheckpointSaving,
  connect,
  disconnect,
  haltActiveOperations,
  refreshSession,
  sendMessage,
  emitSystemMessage,
  runAgentTurn,
  createTerminalEpilogue
} = useGameSocket()

const displayAdventureTitle = computed(() => {
  return sheet.value?.adventure_title || (route.query.title as string) || 'your adventure'
})

const isNewSession = computed(() => {
  return route.query.is_new === 'true'
})

const loadSessionCheckpoints = async () => {
  isLoadingCheckpoints.value = true
  try {
    checkpoints.value = await api.listSessionCheckpoints(props.id)
  } catch (error) {
    addNotification('Failed to load Chronicles timeline.', 'error')
  } finally {
    isLoadingCheckpoints.value = false
  }
}

const openChroniclesModal = async () => {
  showChroniclesModal.value = true
  await loadSessionCheckpoints()
}

const restoreCheckpoint = (checkpoint: SessionCheckpoint) => {
  pendingRestoreCheckpoint.value = checkpoint
  showRestoreConfirmModal.value = true
}

const closeRestoreConfirmModal = () => {
  if (restoringCheckpointId.value) return
  showRestoreConfirmModal.value = false
  pendingRestoreCheckpoint.value = null
}

const confirmRestoreCheckpoint = async () => {
  const checkpoint = pendingRestoreCheckpoint.value
  if (!checkpoint) return

  restoringCheckpointId.value = checkpoint.id
  try {
    haltActiveOperations()
    audioService.stop()
    const result = await api.restoreSessionCheckpoint(props.id, checkpoint.id)
    await connect(props.id)
    await loadSessionCheckpoints()
    showRestoreConfirmModal.value = false
    pendingRestoreCheckpoint.value = null
    addNotification(`Timeline restored. Removed ${result.deleted_messages} future messages.`, 'success')
  } catch (error) {
    addNotification('Failed to restore checkpoint timeline.', 'error')
  } finally {
    restoringCheckpointId.value = null
  }
}

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
const displayedTrackedQuest = computed(() => {
  if (isQuestTrackerHidden.value) return null
  return trackedQuest.value
})

watch(trackedQuestId, (newId) => {
  if (newId) {
    isQuestTrackerHidden.value = false
  }
})

onMounted(() => {
  // Re-fetch config so in-game controls (e.g. TTS) reflect the latest server-side settings,
  // even if the user changed them after the initial app mount.
  void refreshConfig()
})

onBeforeUnmount(() => {
  audioService.stop()
  if (viewportMql) {
    viewportMql.removeEventListener('change', handleViewportChange)
  }
})

const activeActionId = ref<string | null>(null)
const isPassRunning = computed(() => status.value === 'loading')
const isActionInputBlocked = computed(() => inputLocked.value || isPassRunning.value)
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
    if (isSwitchEntity(entity)) {
      openSwitchStateModal(entity)
      return
    }

    if (isReadableEntity(entity)) {
      await openTextLogFromEntity(entity)
      return
    }

    if (isContainerEntity(entity)) {
      openContainerFromEntity(entity)
      return
    }

    // Default behavior for click (e.g. pick up if portable item)
    if (gameCommandService.shouldAutoTakeOnEntityClick(entity)) {
      await handleTakeDirect(entity)
    }
  }
}

const CONTAINER_OPEN_PREFIX = '[OPEN_CONTAINER] '
const TEXT_LOG_OPEN_PREFIX = '[OPEN_TEXT_LOG] '
const PREFILL_SAY_TO_PREFIX = '[PREFILL_SAY_TO] '
const FLIP_SWITCH_PREFIX = '[FLIP_SWITCH] '

const isSwitchEntity = (entity: any): boolean => {
  if (!entity) return false
  return String(entity.item_type || '').toUpperCase() === 'SWITCH'
}

const resolveSwitchTransitions = (entity: any): { transitions: any[]; initialState: string } => {
  let metadata: any = entity?.metadata_json
  if (typeof metadata === 'string') {
    try { metadata = JSON.parse(metadata) } catch { metadata = {} }
  }
  if (!metadata || typeof metadata !== 'object') metadata = {}

  // Prefer nested form (metadata.switch.transitions) but fall back to flat
  // (metadata.switch_transitions / entity.switch_transitions) for compatibility.
  const nested = (metadata.switch && typeof metadata.switch === 'object') ? metadata.switch : {}
  const transitions = (Array.isArray(nested.transitions) && nested.transitions.length > 0)
    ? nested.transitions
    : (Array.isArray(metadata.switch_transitions) ? metadata.switch_transitions
      : (Array.isArray(entity?.switch_transitions) ? entity.switch_transitions : []))
  const initialState = String(nested.initial_state || metadata.switch_initial_state || entity?.switch_initial_state || '').trim().toUpperCase()

  return { transitions, initialState }
}

const getSwitchTransitionGates = (entity: any, targetState: string): { code: string; item: string; rule: string } => {
  const { transitions, initialState } = resolveSwitchTransitions(entity)
  const configuredCurrent = String(entity?.switch_state || initialState || '').trim().toUpperCase()
  const targetUpper = String(targetState || '').trim().toUpperCase()

  let exactMatch: any = null
  let wildcardMatch: any = null
  for (const t of transitions) {
    if (!t || typeof t !== 'object') continue
    const fromVal = String(t.from || t.from_state || '').trim().toUpperCase()
    const toVal = String(t.to || t.to_state || '').trim().toUpperCase()
    if (!toVal || toVal !== targetUpper) continue
    if (fromVal) {
      if (fromVal === configuredCurrent) {
        exactMatch = t
        break
      }
    } else if (!wildcardMatch) {
      wildcardMatch = t
    }
  }
  const trans = exactMatch || wildcardMatch || null

  const gates = (trans?.gates && typeof trans.gates === 'object') ? trans.gates : {}
  return {
    code: String(gates.code || '').trim(),
    item: String(gates.item || gates.required_item || '').trim(),
    rule: String(gates.rule || gates.required_rule || '').trim(),
  }
}

/** Opens the primary state-picker modal for a switch entity. */
const openSwitchStateModal = (entity: any): void => {
  switchUnlockModalEntity.value = entity
  switchUnlockError.value = ''
  showSwitchStateModal.value = true
}

/**
 * Called when the player selects a target state in SwitchStateModal.
 * If a gate (code/item/rule) exists, opens SwitchUnlockModal.
 * Otherwise sends the /switch command directly.
 */
const handleSwitchStateSelect = (targetState: string): void => {
  const entity = switchUnlockModalEntity.value
  if (!entity) return

  showSwitchStateModal.value = false

  const gates = getSwitchTransitionGates(entity, targetState)
  if (gates.code || gates.item || gates.rule) {
    switchUnlockTargetState.value = targetState
    switchUnlockError.value = ''
    showSwitchUnlockModal.value = true
    return
  }

  // No gate — send the /switch command directly
  void sendMessage(`/switch "${entity.name}" ${targetState}`)
}

const handleSwitchFlipCodeSubmit = async (code: string) => {
  if (!switchUnlockModalEntity.value || switchUnlockBusy.value) return
  const entityId = String(switchUnlockModalEntity.value.id || '').trim()
  if (!entityId) return

  switchUnlockBusy.value = true
  switchUnlockError.value = ''
  try {
    const result = await api.flipSwitchWithCode(props.id, entityId, switchUnlockTargetState.value, code)
    // Update the local entity state immediately so the UI reflects the change
    const override = (entities.value || []).find((e: any) => String(e.id || '').toLowerCase() === entityId.toLowerCase())
    if (override) override.switch_state = result.switch_state
    addNotification(`${switchUnlockModalEntity.value.name || 'Switch'} flipped to ${result.switch_state}.`, 'success')
    showSwitchUnlockModal.value = false
    switchUnlockModalEntity.value = null
    switchUnlockTargetState.value = ''
  } catch (error: any) {
    switchUnlockError.value = error?.message || 'Incorrect code. The switch does not move.'
  } finally {
    switchUnlockBusy.value = false
  }
}

const handleSwitchFlipItemSubmit = async (itemId: string) => {
  if (!switchUnlockModalEntity.value || switchUnlockBusy.value) return
  const entityId = String(switchUnlockModalEntity.value.id || '').trim()
  if (!entityId) return

  switchUnlockBusy.value = true
  switchUnlockError.value = ''
  try {
    const result = await api.flipSwitchWithItem(props.id, entityId, switchUnlockTargetState.value, itemId)
    const override = (entities.value || []).find((e: any) => String(e.id || '').toLowerCase() === entityId.toLowerCase())
    if (override) override.switch_state = result.switch_state
    addNotification(`${switchUnlockModalEntity.value.name || 'Switch'} flipped to ${result.switch_state}.`, 'success')
    showSwitchUnlockModal.value = false
    switchUnlockModalEntity.value = null
    switchUnlockTargetState.value = ''
  } catch (error: any) {
    switchUnlockError.value = error?.message || 'Failed to activate the switch with this item.'
  } finally {
    switchUnlockBusy.value = false
  }
}

const isContainerEntity = (entity: any): boolean => {
  if (!entity) return false
  return String(entity.item_type || '').toUpperCase() === 'CONTAINER'
}

const isContainerLocked = (container: any): boolean => {
  if (!isContainerEntity(container)) return false

  let metadata = container?.metadata_json || {}
  if (typeof metadata === 'string') {
    try {
      metadata = JSON.parse(metadata)
    } catch {
      metadata = {}
    }
  }

  const code = String(container?.code_to_unlock || metadata?.code_to_unlock || '').trim()
  const item = String(container?.item_to_unlock || metadata?.item_to_unlock || '').trim()
  const rule = String(container?.rule_to_unlock || metadata?.rule_to_unlock || '').trim()

  const hasUnlockRequirements = Boolean(code || item || rule)

  if (hasUnlockRequirements) {
    if (container?.locked === false) {
      return false
    }
    return true
  }

  return container?.locked === true || metadata?.locked === true
}

const getContainerCodeRequirement = (container: any): string => {
  let metadata = container?.metadata_json || {}
  if (typeof metadata === 'string') {
    try {
      metadata = JSON.parse(metadata)
    } catch {
      metadata = {}
    }
  }
  return String(container?.code_to_unlock || metadata?.code_to_unlock || '').trim()
}

const markContainerUnlockedLocally = (containerId: string) => {
  const normalized = String(containerId || '').trim().toLowerCase()
  if (!normalized) return

  const updateLock = (entry: any) => {
    if (!entry || String(entry.id || '').toLowerCase() !== normalized) return
    entry.locked = false
    const metadata = (entry.metadata_json && typeof entry.metadata_json === 'object') ? { ...entry.metadata_json } : {}
    metadata.locked = false
    entry.metadata_json = metadata
  }

  for (const entry of (entities.value || [])) updateLock(entry)
  for (const entry of (inventoryItems.value || [])) updateLock(entry)
}

const isReadableEntity = (entity: any): boolean => {
  if (!entity) return false
  return String(entity.item_type || '').toUpperCase() === 'READABLE'
}

const extractTextLogPayload = (entity: any) => {
  const metadata = (entity?.metadata_json && typeof entity.metadata_json === 'object') ? entity.metadata_json : {}
  const content = String(
    entity?.text_log_content ||
    metadata.text_log_content ||
    entity?.description ||
    ''
  ).trim().slice(0, 500)
  const format = String(entity?.text_log_format || metadata.text_log_format || 'DOCUMENT').trim().toUpperCase()
  return {
    id: String(entity?.id || ''),
    title: String(entity?.name || entity?.id || 'Text Log'),
    format: ['DOCUMENT', 'SCROLL', 'BOOK', 'SIGN'].includes(format) ? format : 'DOCUMENT',
    content,
    imageUrl: entity?.image_url || null,
  }
}

const openTextLogFromEntity = async (entity: any) => {
  const payload = extractTextLogPayload(entity)
  activeTextLog.value = payload
  showTextLogModal.value = true

  if (!payload.id) {
    return
  }

  try {
    await api.markTextLogRead(props.id, payload.id)
    entity.is_read = true
  } catch {
    addNotification('Could not persist read status for this text log.', 'error')
  }
}

const closeTextLogModal = () => {
  showTextLogModal.value = false
  activeTextLog.value = null
}

const findItemById = (id: string): any | null => {
  if (!id) return null
  const foundInScene = (entities.value || []).find((entry: any) => String(entry.id || '').toLowerCase() === id.toLowerCase())
  if (foundInScene) return foundInScene
  const foundInInventory = (inventoryItems.value || []).find((entry: any) => String(entry?.id || '').toLowerCase() === id.toLowerCase())
  return foundInInventory || null
}

const normalizeContainerItems = (rawItems: any[]): any[] => {
  const result: any[] = []
  for (const entry of rawItems || []) {
    if (entry && typeof entry === 'object') {
      result.push(entry)
      continue
    }

    if (typeof entry === 'string') {
      const resolved = findItemById(entry)
      result.push(resolved || { id: entry, name: entry, item_type: 'PICKABLE' })
    }
  }
  return result
}

const openContainerFromEntity = (entity: any): boolean => {
  if (!isContainerEntity(entity)) return false
  if (isContainerLocked(entity)) {
    activeCodeContainer.value = {
      id: String(entity.id || entity.name || '').trim(),
      name: String(entity.name || entity.id || 'Container'),
      source: 'scene',
    }
    unlockModalContainer.value = entity
    unlockModalError.value = ''
    showUnlockModal.value = true
    return false
  }

  activeContainer.value = {
    id: String(entity.id || entity.name || '').trim(),
    name: String(entity.name || entity.id || 'Container'),
    items: normalizeContainerItems(entity.inventory || []),
  }
  showContainerModal.value = true
  return true
}

const openContainerFromInventoryItem = (item: any): boolean => {
  if (!isContainerEntity(item)) return false
  if (isContainerLocked(item)) {
    activeCodeContainer.value = {
      id: String(item.id || item.name || '').trim(),
      name: String(item.name || item.id || 'Container'),
      source: 'inventory',
    }
    unlockModalContainer.value = item
    unlockModalError.value = ''
    showUnlockModal.value = true
    return false
  }

  activeContainer.value = {
    id: String(item.id || item.name || '').trim(),
    name: String(item.name || item.id || 'Container'),
    items: normalizeContainerItems(item.inventory || []),
  }
  showContainerModal.value = true
  return true
}

const handleUnlockCodeSubmit = async (code: string) => {
  if (!unlockModalContainer.value || unlockModalBusy.value) return
  const containerId = String(unlockModalContainer.value.id || '').trim()
  if (!containerId) return

  unlockModalBusy.value = true
  unlockModalError.value = ''
  try {
    await api.unlockContainerWithCode(props.id, containerId, code)
    markContainerUnlockedLocally(containerId)
    addNotification(`${unlockModalContainer.value.name || 'Container'} unlocked.`, 'success')
    
    const source = activeCodeContainer.value?.source
    showUnlockModal.value = false
    unlockModalContainer.value = null
    clearContainerCodeState()
    
    if (source === 'scene') {
      const container = (items.value || []).find((entry: any) => String(entry.id || '').trim().toLowerCase() === containerId.toLowerCase())
      if (container) openContainerFromEntity(container)
    } else {
      const container = (inventoryItems.value || []).find((entry: any) => String(entry.id || '').trim().toLowerCase() === containerId.toLowerCase())
      if (container) openContainerFromInventoryItem(container)
    }
  } catch (error: any) {
    unlockModalError.value = error?.message || "The lock gives a mocking click. That code won't open this container."
  } finally {
    unlockModalBusy.value = false
  }
}

const handleUnlockItemSubmit = async (itemId: string) => {
  if (!unlockModalContainer.value || unlockModalBusy.value) return
  const containerId = String(unlockModalContainer.value.id || '').trim()
  if (!containerId) return

  unlockModalBusy.value = true
  unlockModalError.value = ''
  try {
    await api.unlockContainerWithItem(props.id, containerId, itemId)
    markContainerUnlockedLocally(containerId)
    addNotification(`${unlockModalContainer.value.name || 'Container'} unlocked.`, 'success')
    
    const source = activeCodeContainer.value?.source
    showUnlockModal.value = false
    unlockModalContainer.value = null
    clearContainerCodeState()
    
    if (source === 'scene') {
      const container = (items.value || []).find((entry: any) => String(entry.id || '').trim().toLowerCase() === containerId.toLowerCase())
      if (container) openContainerFromEntity(container)
    } else {
      const container = (inventoryItems.value || []).find((entry: any) => String(entry.id || '').trim().toLowerCase() === containerId.toLowerCase())
      if (container) openContainerFromInventoryItem(container)
    }
  } catch (error: any) {
    unlockModalError.value = error?.message || "Failed to unlock container with item."
  } finally {
    unlockModalBusy.value = false
  }
}

// ---------------------------------------------------------------------------
// Exit interactions
// ---------------------------------------------------------------------------

const handleExitClick = async (exit: any) => {
  if (!exit || isActionInputBlocked.value) return
  if (exitTraversalBusy.value || exitUnlockBusy.value) return

  // Map edges have no 'id' but always have 'from'/'to'. Build a composite key.
  // If a direct exit DB-ID is available (e.g., from unlock modal), use it.
  const exitId = String(exit.id || '').trim()
  const fromId = String(exit.from || '').trim().toUpperCase()
  const toId = String(exit.to || '').trim().toUpperCase()
  const exitRef = exitId || (fromId && toId ? `${fromId}::${toId}` : '')
  if (!exitRef) return

  if (isExitLocked(exit)) {
    exitUnlockModalTarget.value = { ...exit, id: exitRef, name: exit.label || 'Exit' }
    exitUnlockError.value = ''
    showExitUnlockModal.value = true
    return
  }

  await traverseSceneExit(exit, exitRef)
}

const traverseSceneExit = async (exit: any, exitRef: string) => {
  exitTraversalBusy.value = exitRef
  try {
    // Use the sendMessage pipeline so the scene transition triggers
    // a full LLM narration turn and clears old chat bubbles via the
    // scene_transition SSE event handled in useGameSocket.
    await sendMessage(`/traverse_exit ${exitRef}`)
  } catch (error: any) {
    addNotification(error?.message || 'Failed to traverse the exit.', 'error')
  } finally {
    exitTraversalBusy.value = ''
  }
}

const handleExitUnlockCodeSubmit = async (code: string) => {
  if (!exitUnlockModalTarget.value || exitUnlockBusy.value) return
  const exitId = String(exitUnlockModalTarget.value.id || '').trim()
  if (!exitId) return

  exitUnlockBusy.value = true
  exitUnlockError.value = ''
  try {
    await api.unlockExitWithCode(props.id, exitId, code)
    markExitUnlockedLocally(exitId)
    const target = exitUnlockModalTarget.value
    addNotification(`${target?.name || target?.label || 'Exit'} unlocked.`, 'success')
    showExitUnlockModal.value = false
    exitUnlockModalTarget.value = null
    await traverseSceneExit({ ...(target || {}), is_locked: false }, exitId)
  } catch (error: any) {
    exitUnlockError.value = error?.message || "That code didn't open the way."
  } finally {
    exitUnlockBusy.value = false
  }
}

const handleExitUnlockItemSubmit = async (itemId: string) => {
  if (!exitUnlockModalTarget.value || exitUnlockBusy.value) return
  const exitId = String(exitUnlockModalTarget.value.id || '').trim()
  if (!exitId) return

  exitUnlockBusy.value = true
  exitUnlockError.value = ''
  try {
    await api.unlockExitWithItem(props.id, exitId, itemId)
    markExitUnlockedLocally(exitId)
    const target = exitUnlockModalTarget.value
    addNotification(`${target?.name || target?.label || 'Exit'} unlocked.`, 'success')
    showExitUnlockModal.value = false
    exitUnlockModalTarget.value = null
    await traverseSceneExit({ ...(target || {}), is_locked: false }, exitId)
  } catch (error: any) {
    exitUnlockError.value = error?.message || 'Failed to unlock the exit with this item.'
  } finally {
    exitUnlockBusy.value = false
  }
}

const markExitUnlockedLocally = (exitId: string) => {
  const normalized = String(exitId || '').trim()
  if (!normalized || !mapData.value) return
  const edges = Array.isArray(mapData.value.edges) ? mapData.value.edges : []
  for (const edge of edges) {
    if (!edge || String(edge.id || '').trim() !== normalized) continue
    edge.is_locked = false
    edge.code_to_unlock = ''
    edge.item_to_unlock = ''
    edge.rule_to_unlock = ''
  }
}

const openContainerByHint = (hint: string): boolean => {
  const normalized = String(hint || '').trim().toLowerCase()
  if (!normalized) return false

  const sceneContainer = (items.value || []).find((entry: any) => {
    if (!isContainerEntity(entry)) return false
    const byId = String(entry.id || '').toLowerCase() === normalized
    const byName = String(entry.name || '').toLowerCase() === normalized
    return byId || byName
  })

  if (sceneContainer) {
    return openContainerFromEntity(sceneContainer)
  }

  const inventoryContainer = (inventoryItems.value || []).find((entry: any) => {
    if (!isContainerEntity(entry)) return false
    const byId = String(entry.id || '').toLowerCase() === normalized
    const byName = String(entry.name || '').toLowerCase() === normalized
    return byId || byName
  })

  if (inventoryContainer) {
    return openContainerFromInventoryItem(inventoryContainer)
  }

  return false
}

const openTextLogByHint = async (hint: string): Promise<boolean> => {
  const normalized = String(hint || '').trim().toLowerCase()
  if (!normalized) return false

  const sceneReadable = (items.value || []).find((entry: any) => {
    if (!isReadableEntity(entry)) return false
    const byId = String(entry.id || '').toLowerCase() === normalized
    const byName = String(entry.name || '').toLowerCase() === normalized
    return byId || byName
  })

  if (sceneReadable) {
    await openTextLogFromEntity(sceneReadable)
    return true
  }

  const inventoryReadable = (inventoryItems.value || []).find((entry: any) => {
    if (!isReadableEntity(entry)) return false
    const byId = String(entry.id || '').toLowerCase() === normalized
    const byName = String(entry.name || '').toLowerCase() === normalized
    return byId || byName
  })

  if (inventoryReadable) {
    await openTextLogFromEntity(inventoryReadable)
    return true
  }

  return false
}

const handleSwitchFlipByHint = (hint: string): boolean => {
  const normalized = String(hint || '').trim().toLowerCase()
  if (!normalized) return false

  const targetSwitch = (items.value || []).find((entry: any) => {
    if (!isSwitchEntity(entry)) return false
    const byId = String(entry.id || '').toLowerCase() === normalized
    const byName = String(entry.name || '').toLowerCase() === normalized
    return byId || byName
  }) || (entities.value || []).find((entry: any) => {
    if (!isSwitchEntity(entry)) return false
    const byId = String(entry.id || '').toLowerCase() === normalized
    const byName = String(entry.name || '').toLowerCase() === normalized
    return byId || byName
  })

  if (targetSwitch) {
    openSwitchStateModal(targetSwitch)
    return true
  }

  return false
}

const closeContainerModal = () => {
  showContainerModal.value = false
  activeContainer.value = null
}

const containerCodeErrorMessage = ref('')

const clearContainerCodeState = () => {
  awaitingContainerCodeInput.value = false
  containerCodeErrorMessage.value = ''
  activeCodeContainer.value = null
}

const submitContainerCode = async (code: string) => {
  if (!activeCodeContainer.value || containerCodeBusy.value) return
  const containerId = String(activeCodeContainer.value.id || '').trim()
  if (!containerId) return

  containerCodeBusy.value = true
  containerCodeErrorMessage.value = ''
  try {
    await api.unlockContainerWithCode(props.id, containerId, code)
    markContainerUnlockedLocally(containerId)
    addNotification(`${activeCodeContainer.value.name} unlocked.`, 'success')
    const source = activeCodeContainer.value.source
    clearContainerCodeState()

    if (source === 'scene') {
      const container = (items.value || []).find((entry: any) => String(entry.id || '').trim().toLowerCase() === containerId.toLowerCase())
      if (container) openContainerFromEntity(container)
    } else {
      const container = (inventoryItems.value || []).find((entry: any) => String(entry.id || '').trim().toLowerCase() === containerId.toLowerCase())
      if (container) openContainerFromInventoryItem(container)
    }
  } catch (error: any) {
    containerCodeErrorMessage.value = error?.message || "The lock gives a mocking click. That code won't open this container."
  } finally {
    containerCodeBusy.value = false
  }
}

const handlePlayerInput = async (content: string) => {
  const trimmed = String(content || '').trim()

  if (awaitingContainerCodeInput.value && activeCodeContainer.value) {
    if (!trimmed) return

    if (trimmed.toLowerCase() === '/cancel') {
      const containerName = activeCodeContainer.value.name
      clearContainerCodeState()
      const msg = `Code input cancelled for ${containerName}.`
      addNotification(msg, 'info')
      emitSystemMessage(msg)
      return
    }

    let codeCandidate = ''
    if (trimmed.toLowerCase().startsWith('/code ')) {
      codeCandidate = trimmed.slice(6).trim()
    } else if (!trimmed.startsWith('/')) {
      codeCandidate = trimmed
    }

    if (!codeCandidate) {
      // Keep gameplay controls responsive while the unlock prompt is pending.
      await handlePlayerInputBase(content)
      return
    }

    await submitContainerCode(codeCandidate)
    return
  }

  await handlePlayerInputBase(content)
}

const runContainerAction = async (commandBuilder: (containerIdOrName: string) => string) => {
  if (!activeContainer.value || containerBusy.value) return
  const identifier = activeContainer.value.id || activeContainer.value.name
  if (!identifier) return

  containerBusy.value = true
  try {
    await sendMessage(commandBuilder(identifier))
    closeContainerModal()
  } finally {
    containerBusy.value = false
  }
}

const handleContainerTakeAll = async () => {
  await runContainerAction((id) => `/container_take_all ${id}`)
}

const handleContainerDropToScene = async () => {
  await runContainerAction((id) => `/container_drop_scene ${id}`)
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

const isListedInDiscoveries = (entity: any): boolean => {
  if (!entity || entity.entity_type !== 'OBJECT') return false

  const metadata = (entity.metadata_json && typeof entity.metadata_json === 'object') ? entity.metadata_json : {}
  const discoveryVisibility = (metadata.discovery_visibility && typeof metadata.discovery_visibility === 'object')
    ? metadata.discovery_visibility
    : {}

  if (typeof discoveryVisibility.listed_in_discoveries === 'boolean') {
    return discoveryVisibility.listed_in_discoveries
  }

  return String(entity.item_type || '').toUpperCase() !== 'SWITCH' && entity.listed_in_discoveries !== false
}

const items = computed(() => entities.value.filter((e: any) => isListedInDiscoveries(e)))
const sceneSwitches = computed(() => entities.value.filter((e: any) => isSwitchEntity(e)))
const inventoryItems = computed(() => sheet.value?.inventory ?? [])
const combatConsumables = computed(() => (sheet.value?.inventory ?? []).filter((item: any) => item?.item_type === 'CONSUMABLE'))

// Exits currently accessible from the player's scene (one-way + bidirectional edges)
const sceneExits = computed<any[]>(() => {
  const edges = Array.isArray(mapData.value?.edges) ? mapData.value.edges : []
  const current = String(sheet.value?.scene_id || '').trim().toUpperCase()
  if (!current) return []
  const result: any[] = []
  for (const edge of edges) {
    if (!edge || typeof edge !== 'object') continue
    const fromId = String(edge.from || '').trim().toUpperCase()
    const toId = String(edge.to || '').trim().toUpperCase()
    const exitType = String(edge.exit_type || '').toLowerCase()
    if (fromId === current) {
      result.push({ ...edge, direction: 'forward' })
    } else if (exitType === 'bidirectional' && toId === current) {
      result.push({ ...edge, direction: 'backward' })
    }
  }
  return result
})

const isExitLocked = (exit: any): boolean => {
  if (!exit) return false
  const code = String(exit.code_to_unlock || '').trim()
  const item = String(exit.item_to_unlock || '').trim()
  const rule = String(exit.rule_to_unlock || '').trim()
  if (!code && !item && !rule) return Boolean(exit.is_locked)
  return Boolean(exit.is_locked)
}

const exitDisplayName = (exit: any): string => {
  if (!exit) return 'Exit'
  const raw = String(exit.label || '').trim()
  if (!raw) return 'Exit'
  const arrowMatch = raw.match(/^(.+?)\s*(?:->|→)\s*.+$/)
  if (arrowMatch) return arrowMatch[1].trim()
  return raw
}

interface ExitLockBadge {
  label: string
  icon: string
  detail: string
}

const exitLockBadge = (exit: any): ExitLockBadge | null => {
  if (!exit || !isExitLocked(exit)) return null
  const code = String(exit.code_to_unlock || '').trim()
  const item = String(exit.item_to_unlock || '').trim()
  const rule = String(exit.rule_to_unlock || '').trim()
  const description = String(exit.lock_description || '').trim()

  if (code) {
    return { label: 'Locked by Code', icon: 'ra ra-key', detail: description || 'Requires a passcode' }
  }
  if (item) {
    return { label: `Requires ${item}`, icon: 'ra ra-key', detail: description || `Requires the ${item}` }
  }
  if (rule) {
    return { label: `Rule: ${rule}`, icon: 'ra ra-scroll-unfurled', detail: description || `Requires: ${rule}` }
  }
  return { label: 'Locked', icon: 'ra ra-lock', detail: description || 'The way is barred' }
}


// Recover from stale snapshots where edges lack the WorldExit UUID by refreshing once.
watch(sceneExits, (exits) => {
  if (!exits || exits.length === 0) return
  const needsRefresh = exits.some((e: any) => {
    const id = String(e?.id || '').trim()
    return !id
  })
  if (needsRefresh && typeof refreshSession === 'function') {
    void refreshSession()
  }
})
const lootPopupItems = computed(() => (combat.value?.loot_items || []) as any[])
const isCombatActive = computed(() => !!combat.value?.active)
const showCombatDialog = computed(() => {
  if (isClosingCombat.value) return false
  return !!combat.value && (!!combat.value.active || !!combat.value.loot_pending || !!combat.value.outcome)
})
const combatActionInFlight = ref(false)
const isClosingCombat = ref(false)
const showLootPopup = ref(false)
const lootPopupShownForCombat = ref(false)
const isCombatEvaluating = computed(() => combatActionInFlight.value)
const showsMechanics = computed(() => {
  const mode = (sheet.value as any)?.rule_enforcement_mode as string | undefined
  return mode === 'rpg' || mode === 'story' || mode === 'strict'
})

watch(combat, (newCombat, oldCombat) => {
  if (!newCombat) {
    isClosingCombat.value = false
    showLootPopup.value = false
    lootPopupShownForCombat.value = false
    return
  }

  const hadLootPhase = !!oldCombat?.loot_pending
  const enteredLootPhase = !!newCombat.loot_pending && !hadLootPhase
  const hasLootItems = (newCombat.loot_items || []).length > 0
  if (enteredLootPhase && hasLootItems && !lootPopupShownForCombat.value) {
    showLootPopup.value = true
    lootPopupShownForCombat.value = true
  }

  if (!newCombat.loot_pending) {
    showLootPopup.value = false
    lootPopupShownForCombat.value = false
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

const hasSceneContext = computed(() => Boolean(entities.length || currentSceneImage || sheet.value?.current_scene || sheet.value?.scene_id))

const {
  showWalkthrough,
  showDebug,
  walkthroughData,
  fullWorldDebug,
  goBack,
  openDebugInspector,
  openWalkthroughPanel,
  revealWalkthrough,
  buyHint,
  handlePlayerInput: handlePlayerInputBase,
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
  emitSystemMessage,
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
    isMobileSidebarOpen.value = false
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
  npcEntities: npcs,
  playerSheet: sheet,
  handlePlayerInput,
  onAction: () => {
    if (showSheet.value) sheetDirty.value = true
  },
  onDirectAction: (action: string) => {
    if (action.startsWith(PREFILL_SAY_TO_PREFIX)) {
      const npcName = action.replace(PREFILL_SAY_TO_PREFIX, '').trim()
      const prefill = npcName ? `/say to ${npcName}: ` : '/say to '
      dialogPanel.value?.setInputText(prefill)
      return true
    }

    if (action.startsWith(FLIP_SWITCH_PREFIX)) {
      const hint = action.replace(FLIP_SWITCH_PREFIX, '').trim()
      return handleSwitchFlipByHint(hint)
    }

    if (!action.startsWith(CONTAINER_OPEN_PREFIX)) {
      if (!action.startsWith(TEXT_LOG_OPEN_PREFIX)) {
        return false
      }
      const hint = action.replace(TEXT_LOG_OPEN_PREFIX, '').trim()
      void openTextLogByHint(hint)
      return true
    }

    const hint = action.replace(CONTAINER_OPEN_PREFIX, '').trim()
    return openContainerByHint(hint)
  },
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
  // Closing/viewing the sheet must never trigger an autonomous GM turn.
  // Player-initiated actions already send explicit commands.
  sheetDirty.value = false
}

const handleCombatAttack = async () => {
  const dispatched = await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, '/attack')
  if (!dispatched) {
    const blockedMsg = 'Your move is still being resolved. Hold your stance for a moment.'
    addNotification(blockedMsg, 'info')
    emitSystemMessage(blockedMsg)
  }
}

const handleCombatRun = async () => {
  const dispatched = await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, '/run')
  if (!dispatched) {
    const blockedMsg = 'Your move is still being resolved. Hold your stance for a moment.'
    addNotification(blockedMsg, 'info')
    emitSystemMessage(blockedMsg)
  }
}

const handleCombatConsume = async (name: string) => {
  const dispatched = await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, `/consume ${name}`)
  if (!dispatched) {
    const blockedMsg = 'Your move is still being resolved. Hold your stance for a moment.'
    addNotification(blockedMsg, 'info')
    emitSystemMessage(blockedMsg)
  }
}

const handleCombatRest = async () => {
  const dispatched = await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, '/rest')
  if (!dispatched) {
    const blockedMsg = 'Your move is still being resolved. Hold your stance for a moment.'
    addNotification(blockedMsg, 'info')
    emitSystemMessage(blockedMsg)
  }
}

const handleCombatSpecial = async (actionId: string) => {
  const dispatched = await gameActionService.runCombatCommand(combatActionInFlight, sendMessage, `/special ${actionId}`)
  if (!dispatched) {
    const blockedMsg = 'Your move is still being resolved. Hold your stance for a moment.'
    addNotification(blockedMsg, 'info')
    emitSystemMessage(blockedMsg)
  }
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
    () => {
      showLootPopup.value = false
      isClosingCombat.value = true
    },
    () => {
      // Ensure the guard resets eventually once the combat state is truly gone
      if (!combat.value) {
        isClosingCombat.value = false
      }
    }
  )
}

const closeLootPopup = () => {
  showLootPopup.value = false
}

watch(showCombatDialog, (visible) => {
  if (!visible) {
    combatActionInFlight.value = false
  }
})

// Autonomous Agent Gameplay Loop
watch(
  [() => sheet.value?.agent_active, status, agentPaused, agentStepByStep],
  async ([agentActive, currentStatus, paused, stepByStep]) => {
    if (agentActive && currentStatus === 'connected' && !paused && !stepByStep) {
      // Wait 1.5 seconds so the player can follow the gameplay progression
      await new Promise(resolve => setTimeout(resolve, 1500))
      // Re-verify that the agent is still active, status is connected, and we are not paused or step-by-step
      if (sheet.value?.agent_active && status.value === 'connected' && !agentPaused.value && !agentStepByStep.value) {
        try {
          await runAgentTurn()
        } catch (err) {
          console.error('Agent turn failed', err)
        }
      }
    }
  },
  { immediate: true }
)
</script>

<template>
  <main 
    class="h-full min-h-0 bg-slate-950 flex flex-col font-sans overflow-hidden relative"
    :class="{ 'selection-mode': activeActionId }"
  >
    <!-- IMMERSIVE COMIC VIEW MODE -->
    <template v-if="gameViewMode === 'immersive'">
      <ImmersiveGameView
        ref="dialogPanel"
        :messages="messages"
        :status="status"
        :npc-metadata="npcMetadata"
        :entities="entities"
        :inventory="inventoryItems"
        :scene-exits="sceneExits"
        :scene-switches="sceneSwitches"
        :items="items"
        :tracked-quest="trackedQuest"
        :status-text="statusText"
        :show-debug-log="showDebugLog"
        :debug-logs="debugLogs"
        :inventory-glow="inventoryGlow"
        :map-glow="mapGlow"
        :quest-glow="questGlow"
        :active-action-id="activeActionId"
        :mode="sheet?.rule_enforcement_mode"
        :input-locked="isActionInputBlocked"
        :sheet="sheet"
        :game-id="props.id"
        :current-scene-image="currentSceneImage"
        :adventure-image="adventureImage"
        :current-scene-name="sheet?.current_scene"
        :current-scene-description="currentSceneDescription"
        :prompt-suggestions="promptSuggestions"
        :exp="sheet?.exp || 0"
        :game-time="gameTime"
        :clock-tick="clockTick"
        :is-checkpoint-saving="isCheckpointSaving"
        :exit-traversal-busy="exitTraversalBusy"
        :exit-unlock-busy="exitUnlockBusy"
        @send="handlePlayerInput"
        @open-sheet="showSheet = true"
        @open-map="showMap = true"
        @open-quests="showQuests = true"
        @open-chronicles="openChroniclesModal"
        @open-debug="openDebugInspector"
        @open-walkthrough="openWalkthroughPanel"
        @toggle-view-mode="toggleGameViewMode"
        @npc-hover="(ent, event) => typeof ent === 'object' && ent !== null ? handleHover(ent, event) : handleChatNpcHover(ent, event)"
        @npc-leave="hoveredEntity = null"
        @npc-click="(name) => handleEntityClick({ name, entity_type: 'NPC' })"
        @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'A mysterious item in your possession.' }, event)"
        @item-leave="hoveredEntity = null"
        @item-click="handleEntityClick"
        @take-direct="handleTakeDirect"
        @npc-contextmenu="(entity, event) => openContextMenu(entity, event)"
        @item-contextmenu="(entity, event) => openContextMenu(entity, event)"
        @traverse-exit="handleExitClick"
        @switch-flip="openSwitchStateModal"
      />
    </template>

    <!-- CLASSIC RPG PANEL VIEW MODE -->
    <template v-else>
      <!-- Full-Width Adventure Background (Top Third) -->
      <div v-if="adventureImage" class="absolute inset-x-0 top-0 h-[35vh] pointer-events-none z-0 overflow-hidden">
        <img 
          :src="getImageUrl(adventureImage, { thumbnail: true })" 
          class="w-full h-full object-cover blur-sm brightness-[0.5]"
          @error="(e) => {
            const target = e.target as HTMLImageElement
            if (target.src.includes('_thumb')) {
              target.src = getOriginalImageUrl(adventureImage)
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
        :creator="sheet?.creator"
        :copyright="sheet?.copyright"
        :license="sheet?.license"
        :license-url="sheet?.license_url"
        :tracked-quest="displayedTrackedQuest"
        :game-time="gameTime"
        :clock-tick="clockTick"
        :debug-mode="!!sheet?.debug_mode"
        :is-checkpoint-saving="isCheckpointSaving"
        :collapsed="isHeaderCollapsed"
        :view-mode="gameViewMode"
        @back="goBack"
        @open-chronicles="openChroniclesModal"
        @edit-note="showNoteModal = true"
        @collapse="isHeaderCollapsed = true"
        @hide-quest="isQuestTrackerHidden = true"
        @toggle-view-mode="toggleGameViewMode"
      />

      <!-- Floating Controls (when header is collapsed) -->
      <div v-if="isHeaderCollapsed" class="absolute top-0 right-4 z-40 flex items-center gap-2">
        <button
          @click="toggleGameViewMode"
          class="px-3 py-1.5 rounded-b-xl border border-t-0 border-slate-800 bg-slate-900/90 text-amber-400 hover:text-amber-300 transition-all hover:bg-slate-800 shadow-lg flex items-center gap-1.5 cursor-pointer text-xs font-black uppercase tracking-wider backdrop-blur-md"
          title="Switch to Immersive View"
        >
          <Sparkles class="w-3.5 h-3.5 text-amber-400" />
          <span class="hidden sm:inline">Immersive View</span>
        </button>
        <button 
          @click="isHeaderCollapsed = false"
          class="px-4 py-1.5 rounded-b-xl border border-t-0 border-slate-800 bg-slate-900/90 text-slate-400 hover:text-slate-200 transition-all hover:bg-slate-800 shadow-lg flex items-center justify-center gap-1 cursor-pointer backdrop-blur-md"
          title="Show Header"
        >
          <span class="text-[9px] uppercase tracking-widest font-black">Show Header</span>
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      <div v-if="configState.isLoaded && !configState.hasLlmConfig" class="px-12 pt-6">
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

        <!-- Backdrop for mobile sidebar drawer -->
        <div
          v-if="isMobileSidebarOpen && hasSceneContext"
          class="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-30 xl:hidden animate-fade-in"
          @click="isMobileSidebarOpen = false"
        ></div>

        <!-- Left Sidebar: Scene, inhabitants & Discovery -->
        <aside
          v-if="hasSceneContext" 
          :class="[
            'bg-slate-900/95 xl:bg-slate-900/20 backdrop-blur-md border border-slate-800/50 rounded-3xl flex flex-col p-6 shrink-0 overflow-y-auto custom-scrollbar shadow-2xl transition-all duration-300 ease-in-out',
            isMobileSidebarOpen 
              ? 'fixed inset-y-6 left-6 z-40 w-72 max-w-[calc(100vw-3rem)] translate-x-0' 
              : 'fixed inset-y-6 left-6 z-40 w-72 -translate-x-[calc(100%+3rem)] xl:translate-x-0 xl:relative xl:inset-y-0 xl:left-0 xl:m-6'
          ]"
        >
          <GameLocationPanel
            :scene-id="sheet?.scene_id"
            :scene-name="sheet?.current_scene"
            :scene-description="currentSceneDescription"
            :scene-image="currentSceneImage"
            :show-image="showImage"
            :is-debug="!!sheet?.debug_mode"
            :scene-exits="sceneExits"
            :map-data="mapData"
            :nodes="nodes"
            :is-action-input-blocked="isActionInputBlocked"
            :exit-traversal-busy="exitTraversalBusy"
            :exit-unlock-busy="exitUnlockBusy"
            @hover="(payload, event) => handleHover(payload, event)"
            @move="mousePos = { x: $event.clientX, y: $event.clientY }"
            @leave="hoveredEntity = null"
            @traverse="handleExitClick"
            @image-error="handleImageError"
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

          <!-- Switches Panel -->
          <div v-if="sceneSwitches.length > 0" class="mb-8">
            <button
              class="flex items-center gap-1.5 w-full text-left focus:outline-none cursor-pointer mb-4 select-none"
            >
              <i class="ra ra-lever text-lime-500 text-sm"></i>
              <h3 class="text-xs font-bold uppercase tracking-[0.2em] text-lime-500/80">Switches</h3>
            </button>
            <div class="flex flex-col gap-2">
              <div
                v-for="sw in sceneSwitches"
                :key="sw.id"
                class="relative bg-slate-950/40 border border-slate-800/40 rounded-2xl group transition-all hover:border-lime-500/40 hover:bg-slate-900/50 p-3 flex items-center gap-3 cursor-pointer shadow-lg"
                @click="!isActionInputBlocked && openSwitchStateModal(sw)"
                @contextmenu.prevent="!isActionInputBlocked && openSwitchStateModal(sw)"
                @mouseenter="handleHover(sw, $event)"
                @mousemove="mousePos = { x: $event.clientX, y: $event.clientY }"
                @mouseleave="hoveredEntity = null"
              >
                <div class="w-10 h-10 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 flex items-center justify-center shrink-0">
                  <img
                    v-if="sw.image_url && showImage(sw.image_url)"
                    :src="sw.image_url"
                    class="w-full h-full object-cover object-top transition-transform duration-500 group-hover:scale-110"
                    @error="handleImageError(sw.image_url)"
                  />
                  <div v-else class="w-full h-full flex items-center justify-center bg-slate-800/50">
                    <i class="ra ra-lever text-xl text-lime-400"></i>
                  </div>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-xs font-black text-slate-300 group-hover:text-lime-400 transition-colors uppercase tracking-tight truncate">{{ sw.name }}</p>
                  <p class="text-[10px] text-slate-500 mt-0.5 font-mono truncate" v-if="!!sheet?.debug_mode">ID: {{ sw.id }}</p>
                </div>
                <span class="px-2 py-0.5 bg-lime-500/10 border border-lime-500/20 rounded-full text-[9px] font-black text-lime-400 uppercase tracking-wider shrink-0">
                  {{ String(sw.switch_state || (sw.metadata_json?.switch?.initial_state) || '—').toUpperCase() }}
                </span>
              </div>
            </div>
          </div>

          <GameWorldMemoryPanel
            :memories="worldMemories"
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
          :prompt-suggestions="promptSuggestions"
          @send="handlePlayerInput"
          @open-sheet="showSheet = true"
          @open-map="showMap = true"
          @open-quests="showQuests = true"
          @toggle-sidebar="isMobileSidebarOpen = !isMobileSidebarOpen"
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
    </template>

    <!-- Modals -->
    <CharacterSheetModal 
      :open="showSheet" 
      :sheet="sheet" 
      :is-debug="!!sheet?.debug_mode"
      @close="() => { showSheet = false; if (sheetDirty) handleSheetChanged(); }" 
      @equip="handleEquipFromSheet"
      @unequip="handleUnequipFromSheet"
      @consume="handleConsumeFromSheet"
      @open-container="openContainerFromInventoryItem"
      @read-item="openTextLogFromEntity"
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
      :tracker-hidden="isQuestTrackerHidden"
      @close="showQuests = false" 
      @track-quest="handleTrackQuest"
      @toggle-tracker="(val) => isQuestTrackerHidden = val"
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
    <ChroniclesModal
      :open="showChroniclesModal"
      :checkpoints="checkpoints"
      :loading="isLoadingCheckpoints"
      :restoring-id="restoringCheckpointId"
      @close="showChroniclesModal = false"
      @restore="restoreCheckpoint"
    />
    <CheckpointRestoreConfirmModal
      :open="showRestoreConfirmModal"
      :checkpoint="pendingRestoreCheckpoint"
      :busy="!!restoringCheckpointId"
      @close="closeRestoreConfirmModal"
      @confirm="confirmRestoreCheckpoint"
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
      @special="handleCombatSpecial"
      @consume="handleCombatConsume"
      @loot-take="handleLootTake"
      @loot-leave="handleLootLeave"
      @loot-done="handleLootDone"
      @debug-win="handleCombatDebugWin"
      @debug-loose="handleCombatDebugLoose"
      @entity-hover="(entity, event) => handleHover(entity, event)"
      @entity-leave="hoveredEntity = null"
    />

    <CombatLootPopup
      :open="showLootPopup && !!combat?.loot_pending"
      :items="lootPopupItems"
      :busy="combatActionInFlight"
      @close="closeLootPopup"
      @confirm="handleLootDone"
      @item-hover="(item, event) => handleHover({ ...item, entity_type: 'ITEM', description: item.description || 'Loot recovered from battle.' }, event)"
      @item-leave="hoveredEntity = null"
    />

    <ContainerModal
      :open="showContainerModal"
      :title="activeContainer?.name || 'Container'"
      :items="activeContainer?.items || []"
      :busy="containerBusy"
      @close="closeContainerModal"
      @take-all="handleContainerTakeAll"
      @drop-to-scene="handleContainerDropToScene"
      @item-hover="(item, event) => handleHover(item, event)"
      @item-leave="hoveredEntity = null"
    />

    <ContainerUnlockModal
      :open="showUnlockModal"
      :container="unlockModalContainer"
      :inventory-items="inventoryItems"
      :busy="unlockModalBusy"
      :error-message="unlockModalError"
      @close="showUnlockModal = false"
      @submit-code="handleUnlockCodeSubmit"
      @use-key-item="handleUnlockItemSubmit"
    />

    <ContainerUnlockModal
      :open="showExitUnlockModal"
      :container="exitUnlockModalTarget"
      :inventory-items="inventoryItems"
      :busy="exitUnlockBusy"
      :error-message="exitUnlockError"
      kind="exit"
      header-label="Locked Exit"
      :accent-color="'cyan'"
      @close="showExitUnlockModal = false"
      @submit-code="handleExitUnlockCodeSubmit"
      @use-key-item="handleExitUnlockItemSubmit"
    />

    <SwitchStateModal
      :open="showSwitchStateModal"
      :switch-entity="switchUnlockModalEntity"
      :inventory-items="inventoryItems"
      @close="showSwitchStateModal = false"
      @select-state="handleSwitchStateSelect"
    />

    <SwitchUnlockModal
      :open="showSwitchUnlockModal"
      :switch-entity="switchUnlockModalEntity"
      :target-state="switchUnlockTargetState"
      :inventory-items="inventoryItems"
      :busy="switchUnlockBusy"
      :error-message="switchUnlockError"
      @close="showSwitchUnlockModal = false"
      @submit-code="handleSwitchFlipCodeSubmit"
      @use-key-item="handleSwitchFlipItemSubmit"
    />


    <TextLogModal
      :open="showTextLogModal"
      :game-id="props.id"
      :title="activeTextLog?.title || 'Text Log'"
      :format="activeTextLog?.format || 'DOCUMENT'"
      :content="activeTextLog?.content || ''"
      :image-url="activeTextLog?.imageUrl || null"
      @close="closeTextLogModal"
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

    <!-- RESUMING/LOADING OVERLAY -->
    <Teleport to="body">
      <div
        v-if="status === 'loading'"
        class="fixed inset-0 z-[220] bg-slate-950/75 backdrop-blur-sm flex items-center justify-center px-6"
      >
        <div class="w-full max-w-md rounded-2xl border border-white/15 bg-slate-900/95 p-7 shadow-2xl animate-fade-in">
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 rounded-xl bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center shrink-0">
              <i class="ra ra-cycle animate-spin text-emerald-400 text-xl"></i>
            </div>
            <div class="space-y-2">
              <h3 class="text-lg font-black text-white tracking-tight">
                {{ isNewSession ? 'Session Is Starting' : 'Resuming Session' }}
              </h3>
              <p class="text-sm text-slate-300 leading-relaxed">
                {{ isNewSession ? 'Assets are copied for' : 'Loading assets for' }} <span class="font-bold text-emerald-300">{{ displayAdventureTitle }}</span>.
                Please wait a moment.
              </p>
              <p class="text-[11px] uppercase tracking-[0.18em] text-slate-500 font-bold">
                {{ isNewSession ? 'Preventing duplicate starts...' : 'Establishing connection...' }}
              </p>
            </div>
          </div>
        </div>
      </div>
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

