<script setup lang="ts">
/**
 * GameView — The active adventure screen
 *
 * Connects to the given game session and displays the chat,
 * intercepting commands and showing the character sheet + world map.
 */
import { ref, onMounted, watch, nextTick, computed, onUnmounted, onBeforeUnmount } from 'vue'
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
import { api } from '@/composables/useApi'
import { authState, refreshUser } from '@/store/auth'
import { getImageUrl, getItemIcon, hasRenderableImagePath } from '@/utils/game_icons'
import { audioService } from '@/services/audioService'

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
const showGameOver = ref(false)
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

const trackedQuest = computed(() => quests.value?.find(q => q.id === trackedQuestId.value))

// Tooltip & Hover State
const hoveredEntity = ref<any>(null)
const mousePos = ref({ x: 0, y: 0 })
const tooltipImageFailed = ref(false)

// Context Menu State
const contextMenu = ref<{
  x: number
  y: number
  items: any[]
  title: string
} | null>(null)

onBeforeUnmount(() => {
  audioService.stop()
})

const activeActionId = ref<string | null>(null)
const isPassRunning = computed(() => status.value === 'connecting' || status.value === 'loading')
const isActionInputBlocked = computed(() => inputLocked.value || isPassRunning.value || audioService.isPlaying.value || audioService.isGenerating.value)

function isReadOnlyUiCommand(normalized: string): boolean {
  return normalized === '/map' || normalized === '/sheet' || normalized === '/inventory' || normalized === '/quests'
}

const handleEntityClick = async (entity: any) => {
  if (isActionInputBlocked.value) return
  if (activeActionId.value) {
    const action = activeActionId.value
    const targetName = entity.name || entity.id
    let command = ""

    switch (action) {
      case 'talk': command = `/talk ${targetName}`; break
      case 'inspect': command = `/inspect ${targetName}`; break
      case 'take': command = `/take ${targetName}`; break
      case 'attack': 
        if (entity.is_attackable === false) {
          if (typeof notifications?.addNotification === 'function') {
            notifications.addNotification('You cannot attack this target.', 'warning')
          }
          activeActionId.value = null
          return
        }
        command = `/attack ${targetName}`; 
        break
      case 'push': command = `Push ${targetName}`; break
      case 'pull': command = `Pull ${targetName}`; break
      default: command = `${action} ${targetName}`; break
    }

    activeActionId.value = null
    await handlePlayerInput(command)
  } else {
    // Default behavior for click (e.g. pick up if portable item)
    if (entity.entity_type === 'OBJECT' && entity.is_portable !== false) {
      await handleTakeDirect(entity)
    }
  }
}

const openContextMenu = (entity: any, event: MouseEvent) => {
  if (isActionInputBlocked.value) return

  const items: any[] = []
  let title = entity.name || 'Action'
  
  if (entity.id === 'PLAYER') {
    title = 'You'
    items.push({ label: 'Inspect', action: '/sheet', icon: 'ra ra-player', color: 'text-cyan-400' })
    items.push({ label: 'Rest', action: 'Take a rest', icon: 'ra ra-sleeping-bag', color: 'text-emerald-400' })
    items.push({ label: 'Sing', action: 'Sing a song', icon: 'ra ra-music-spell', color: 'text-pink-400' })
    items.push({ label: 'Dance', action: 'Start dancing', icon: 'ra ra-double-team', color: 'text-orange-400' })
  } else if (entity.entity_type === 'NPC') {
    items.push({ label: 'Inspect', action: `/inspect ${entity.name}`, icon: 'ra ra-scroll-unfurled', color: 'text-cyan-400' })
    if (sheet.value?.rule_enforcement_mode === 'rpg') {
      const isAttackable = entity.is_attackable !== false
      if (isAttackable) {
        items.push({ label: 'Attack', action: `/attack ${entity.name}`, icon: 'ra ra-sword', color: 'text-red-400' })
      }
    }
    items.push({ label: 'Chat', action: `/talk ${entity.name}`, icon: 'ra ra-speech-bubbles', color: 'text-blue-400' })
  } else if (entity.entity_type === 'SCENE') {
    items.push({ label: 'Look around', action: 'Look around', icon: 'ra ra-eye', color: 'text-indigo-400' })
    items.push({ label: 'Search', action: 'Search the area', icon: 'ra ra-magnifying-glass', color: 'text-emerald-400' })
  } else if (entity.entity_type === 'OBJECT' || entity.entity_type === 'ITEM') {
    items.push({ label: 'Inspect', action: `/inspect ${entity.name}`, icon: 'ra ra-scroll-unfurled', color: 'text-cyan-400' })
    items.push({ label: 'Pick up', action: `/take ${entity.name}`, icon: 'ra ra-hand', color: 'text-amber-400' })
    items.push({ label: 'Push', action: `Push ${entity.name}`, icon: 'ra ra-cog', color: 'text-slate-400' })
    items.push({ label: 'Pull', action: `Pull ${entity.name}`, icon: 'ra ra-tread', color: 'text-slate-400' })
    items.push({ label: 'Hit', action: `Hit ${entity.name}`, icon: 'ra ra-hammer', color: 'text-red-400' })
    items.push({ label: 'Smell', action: `Smell ${entity.name}`, icon: 'ra ra-scent', color: 'text-pink-400' })
  }

  if (items.length > 0) {
    contextMenu.value = {
      x: event.clientX,
      y: event.clientY,
      items,
      title
    }
    // Also hide tooltip when menu opens
    hoveredEntity.value = null
  }
}

const handleMenuSelect = async (item: any) => {
  if (isActionInputBlocked.value) return
  const action = item.action
  contextMenu.value = null
  await handlePlayerInput(action)
}


function toNumberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

function firstNumeric(...values: unknown[]): number | null {
  for (const value of values) {
    const parsed = toNumberOrNull(value)
    if (parsed !== null) return parsed
  }
  return null
}

function hasNonZero(value: unknown): boolean {
  const parsed = toNumberOrNull(value)
  return parsed !== null && parsed !== 0
}

function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

function normalizeHoverEntity(entity: any): any {
  if (!entity || typeof entity !== 'object') return entity

  const normalized = { ...entity }
  const metadata = (normalized.metadata_json && typeof normalized.metadata_json === 'object') ? normalized.metadata_json : {}
  const embeddedStats = (metadata.stat_modifiers && typeof metadata.stat_modifiers === 'object') ? metadata.stat_modifiers : {}
  const directStats = (normalized.stat_modifiers && typeof normalized.stat_modifiers === 'object') ? normalized.stat_modifiers : {}

  const stat = (...keys: string[]) => firstNumeric(
    ...keys.map((k) => normalized[k]),
    ...keys.map((k) => metadata[k]),
    ...keys.map((k) => embeddedStats[k]),
    ...keys.map((k) => directStats[k]),
  )

  if (normalized.stat_modifier_strength == null) {
    const value = stat('stat_modifier_strength', 'strength', 'str', 'STR')
    if (value != null) normalized.stat_modifier_strength = value
  }
  if (normalized.stat_modifier_dexterity == null) {
    const value = stat('stat_modifier_dexterity', 'stat_modifier_agility', 'dexterity', 'agility', 'dex', 'DEX', 'AGI')
    if (value != null) normalized.stat_modifier_dexterity = value
  }
  if (normalized.stat_modifier_intelligence == null) {
    const value = stat('stat_modifier_intelligence', 'intelligence', 'int', 'INT')
    if (value != null) normalized.stat_modifier_intelligence = value
  }
  if (normalized.stat_modifier_wisdom == null) {
    const value = stat('stat_modifier_wisdom', 'wisdom', 'wis', 'WIS')
    if (value != null) normalized.stat_modifier_wisdom = value
  }
  if (normalized.stat_modifier_charisma == null) {
    const value = stat('stat_modifier_charisma', 'charisma', 'cha', 'CHA')
    if (value != null) normalized.stat_modifier_charisma = value
  }
  if (normalized.stat_modifier_armor_class == null) {
    const value = stat('stat_modifier_armor_class', 'armor_class', 'ac', 'AC')
    if (value != null) normalized.stat_modifier_armor_class = value
  }

  const effects = (metadata.effects && typeof metadata.effects === 'object') ? metadata.effects : {}
  if (normalized.hp_change == null) {
    const value = firstNumeric(normalized.hp_change, metadata.hp_change, metadata.health_change, effects.hp, effects.health)
    if (value != null) normalized.hp_change = value
  }
  if (normalized.mana_change == null) {
    const value = firstNumeric(normalized.mana_change, metadata.mana_change, effects.mana)
    if (value != null) normalized.mana_change = value
  }
  if (normalized.stamina_change == null) {
    const value = firstNumeric(normalized.stamina_change, metadata.stamina_change, effects.stamina, effects.energy)
    if (value != null) normalized.stamina_change = value
  }

  return normalized
}

const handleHover = (ent: any, event: MouseEvent) => {
  tooltipImageFailed.value = false
  hoveredEntity.value = normalizeHoverEntity(ent)
  mousePos.value = { x: event.clientX, y: event.clientY }
}

function onTooltipImageError(): void {
  tooltipImageFailed.value = true
}

const tooltipStyle = computed(() => {
  if (!hoveredEntity.value) return {}
  const x = mousePos.value.x + 20
  const y = mousePos.value.y
  const threshold = window.innerHeight * 0.6
  
  const style: Record<string, string> = {
    left: `${x}px`,
  }

  if (y > threshold) {
    style.bottom = `${window.innerHeight - y + 10}px`
    style.top = 'auto'
  } else {
    style.top = `${y + 10}px`
    style.bottom = 'auto'
  }
  return style
})

const isConsumableHover = computed(() => {
  const ent = hoveredEntity.value
  if (!ent) return false
  const itemType = String(ent.item_type || '').toUpperCase()
  return itemType === 'CONSUMABLE' || ent.hp_change != null || ent.mana_change != null || ent.stamina_change != null
})

const handleChatNpcHover = (name: string, event: MouseEvent) => {
  const metadata = npcMetadata.value[name]
  if (metadata) {
    tooltipImageFailed.value = false
    hoveredEntity.value = normalizeHoverEntity(metadata)
    mousePos.value = { x: event.clientX, y: event.clientY }
  }
}

watch(() => hoveredEntity.value?.image_url, () => {
  tooltipImageFailed.value = false
})

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

// --- WATCHERS FOR UI FEEDBACK (GLOW) ---

watch(() => sheet.value?.inventory, (newInv, oldInv) => {
  if (oldInv && newInv && newInv.length > oldInv.length) {
    inventoryGlow.value = true
    setTimeout(() => { inventoryGlow.value = false }, 3000)
  }
}, { deep: true })

watch(() => nodes.value, (newNodes, oldNodes) => {
  if (oldNodes && newNodes && newNodes.length > oldNodes.length) {
    mapGlow.value = true
    setTimeout(() => { mapGlow.value = false }, 3000)
  }
}, { deep: true })

watch(() => quests.value, (newQuests, oldQuests) => {
  if (oldQuests && newQuests) {
    const newActive = newQuests.filter(q => q.status === 'active').length
    const oldActive = oldQuests.filter(q => q.status === 'active').length
    if (newActive > oldActive) {
      questGlow.value = true
      setTimeout(() => { questGlow.value = false }, 3000)
    }
  }
}, { deep: true })

const handleTakeDirect = async (entity: any) => {
  if (isActionInputBlocked.value) return
  await sendMessage(`/take_direct ${entity.id || entity.name}`)
}
const currentSceneDescription = computed(() => nodes.value[sheet.value?.scene_id || '']?.description || 'The current location of your adventure.')

const lastAutoSpokenSignature = ref<string | null>(null)
const lastAutoSpeakAt = ref(0)
const AUTO_SPEAK_DEBOUNCE_MS = 350

function getMessageSignature(message: { timestamp?: Date; content: string }, index: number): string {
  const ts = message.timestamp instanceof Date ? message.timestamp.toISOString() : ''
  return `${index}|${ts}`
}

function speakLatestAssistantMessage(options: { force?: boolean } = {}): void {
  const { force = false } = options
  if (!audioService.autoSpeechEnabled.value) return
  if (inputLocked.value || isCombatActive.value) return

  const now = Date.now()
  if (!force && now - lastAutoSpeakAt.value < AUTO_SPEAK_DEBOUNCE_MS) return

  const index = messages.value.length - 1
  if (index < 0) return

  const lastMsg = messages.value[index]
  if (!lastMsg || lastMsg.role !== 'assistant') return
  if (!String(lastMsg.content || '').trim()) return

  const signature = getMessageSignature(lastMsg, index)
  if (!force && signature === lastAutoSpokenSignature.value) return

  lastAutoSpeakAt.value = now
  lastAutoSpokenSignature.value = signature
  audioService.speak(lastMsg.content, {
    sceneDescription: currentSceneDescription.value,
    adventureId: props.id,
    title: sheet.value?.adventure_title || undefined,
    sceneName: sheet.value?.current_scene || undefined,
    tone: sheet.value?.adventure_tone || undefined,
    npcMetadata: npcMetadata.value,
  })
}

watch(() => inputLocked.value, (isLocked) => {
  if (isLocked) return
  speakLatestAssistantMessage()
})

watch(() => messages.value.length, (newLength, oldLength) => {
  if (newLength <= oldLength) return
  speakLatestAssistantMessage()
})

watch(
  () => {
    const index = messages.value.length - 1
    if (index < 0) return ''
    const lastMsg = messages.value[index]
    if (!lastMsg || lastMsg.role !== 'assistant') return ''
    return `${index}|${String(lastMsg.content || '').trim()}`
  },
  (snapshot, previous) => {
    if (!snapshot || snapshot === previous) return
    speakLatestAssistantMessage()
  }
)

watch(() => audioService.autoSpeechEnabled.value, (enabled) => {
  if (enabled) {
    // Delay forced auto-speak slightly to collapse rapid toggle bursts.
    setTimeout(() => {
      if (!audioService.autoSpeechEnabled.value) return
      speakLatestAssistantMessage({ force: true })
    }, AUTO_SPEAK_DEBOUNCE_MS)
  } else if (!enabled) {
    lastAutoSpokenSignature.value = null
    lastAutoSpeakAt.value = 0
    audioService.stop()
  }
})

onBeforeUnmount(() => {
  audioService.stop()
})

/**
 * Formats the session clock as a full datetime derived from the adventure start.
 */
const gameTime = computed(() => {
  if (!sheet.value?.start_datetime && sheet.value?.time_system !== 'relative') return null

  const timeSystem = sheet.value?.time_system || 'calendar'
  const timeConfig = sheet.value?.time_config || {}
  const dayLabel = timeConfig.day_label || 'Day'
  const elapsedMinutes = sheet.value?.in_game_time ?? 0

  if (timeSystem === 'relative') {
    const totalMinutes = elapsedMinutes
    // Support custom start time in relative mode too
    let baseHour = 8
    if (timeConfig.start_time) {
      const [h] = timeConfig.start_time.split(':').map(Number)
      if (!isNaN(h)) baseHour = h
    }

    const totalHours = Math.floor(totalMinutes / 60)
    const extraMinutes = totalMinutes % 60
    const currentHour = (baseHour + totalHours) % 24
    const daysPassed = Math.floor((baseHour + totalHours) / 24)
    
    const timeStr = `${currentHour.toString().padStart(2, '0')}:${extraMinutes.toString().padStart(2, '0')}`
    return {
      date: `${dayLabel} ${1 + daysPassed}`,
      dateShort: `${dayLabel} ${1 + daysPassed}`,
      time: timeStr
    }
  }

  // Calendar mode
  const start = new Date(sheet.value.start_datetime)
  if (Number.isNaN(start.getTime())) return null

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
    const y = current.getFullYear().toString()
    const yShort = y.slice(-2)
    
    switch (gameSettings.value.date_format) {
      case 'MM/DD/YY': return `${m}/${d}/${yShort}`
      case 'YY-MM-DD': return `${yShort}-${m}-${d}`
      default: return `${d}.${m}.${y}` // Keep full year for sci-fi/historical
    }
  })()

  const time = current.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: !gameSettings.value.clock_24h,
  }).replace(/^0/, '')

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
  if (val && pendingTerminalEpilogue.value) {
    showSuccess.value = true
  }
})

watch(status, async (val) => {
  if (val === 'game_over' && pendingTerminalEpilogue.value) {
    showGameOver.value = true
    await refreshUser()
  } else if (isCompleted.value && pendingTerminalEpilogue.value) {
    showSuccess.value = true
    await refreshUser()
  }
})

watch(pendingTerminalEpilogue, async (pending) => {
  if (!pending) {
    showSuccess.value = false
    showGameOver.value = false
    return
  }

  if (status.value === 'game_over') {
    showGameOver.value = true
  } else if (isCompleted.value) {
    showSuccess.value = true
  }

  await refreshUser()
})

const continueCompletedGame = async () => {
  showSuccess.value = false
  await createTerminalEpilogue()
  await refreshUser()
}

const continueGameOverReadOnly = async () => {
  showGameOver.value = false
  await createTerminalEpilogue()
  await refreshUser()
}

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

  if (isReadOnlyUiCommand(normalized)) {
    if (normalized === '/map') {
      showMap.value = true
      return
    }

    if (normalized === '/sheet' || normalized === '/inventory') {
      showSheet.value = true
      return
    }

    showQuests.value = true
    return
  }

  if (isActionInputBlocked.value) {
    return
  }

  if (isCombatActive.value) {
    const msg = content.trim().toLowerCase()
    const allowed = msg === 'attack' || msg === '/attack' || msg === 'run' || msg === '/run' || msg.startsWith('/consume ')
    if (!allowed) {
      return
    }
  }

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

  if (normalized === '/debug reveal_map') {
    await sendMessage('/debug reveal_map')
    showMap.value = true
    return
  }

  if (normalized === '/debug session') {
    await openDebugInspector()
    return
  }

  await sendMessage(content)
}

const handleEquipFromSheet = async (name: string) => {
  if (isActionInputBlocked.value) return
  await sendMessage(`/equip ${name}`)
}

const handleUnequipFromSheet = async (slot: string) => {
  if (isActionInputBlocked.value) return
  await sendMessage(`/unequip ${slot}`)
}

const handleConsumeFromSheet = async (name: string) => {
  if (isActionInputBlocked.value) return
  await sendMessage(`/consume ${name}`)
}

const handleSheetChanged = async () => {
  if (isActionInputBlocked.value) return
  if (sheet.value?.rule_enforcement_mode === 'chat') return
  await sendMessage('/rule-pass')
}

const handleCombatAttack = async () => {
  if (combatActionInFlight.value) return
  combatActionInFlight.value = true
  try {
    await sendMessage('/attack')
  } finally {
    combatActionInFlight.value = false
  }
}

const handleCombatRun = async () => {
  if (combatActionInFlight.value) return
  combatActionInFlight.value = true
  try {
    await sendMessage('/run')
  } finally {
    combatActionInFlight.value = false
  }
}

const handleCombatConsume = async (name: string) => {
  if (combatActionInFlight.value) return
  combatActionInFlight.value = true
  try {
    await sendMessage(`/consume ${name}`)
  } finally {
    combatActionInFlight.value = false
  }
}

const handleCombatDebugWin = async () => {
  await sendMessage('/debug win_fight')
}

const handleCombatDebugLoose = async () => {
  await sendMessage('/debug loose_fight')
}

const handleLootTake = async (item: any) => {
  if (combatActionInFlight.value) return
  const key = (item?.id || item?.name || '').toString().trim()
  if (!key) return
  combatActionInFlight.value = true
  try {
    await sendMessage(`/loot take ${key}`)
  } finally {
    combatActionInFlight.value = false
  }
}

const handleLootLeave = async (item: any) => {
  if (combatActionInFlight.value) return
  const key = (item?.id || item?.name || '').toString().trim()
  if (!key) return
  combatActionInFlight.value = true
  try {
    await sendMessage(`/loot leave ${key}`)
  } finally {
    combatActionInFlight.value = false
  }
}

const handleLootDone = async () => {
  if (combatActionInFlight.value) return
  combatActionInFlight.value = true
  isClosingCombat.value = true
  try {
    await sendMessage('/loot done')
  } finally {
    combatActionInFlight.value = false
    // Ensure the guard resets eventually once the combat state is truly gone
    if (!combat.value) {
      isClosingCombat.value = false
    }
  }
}

watch(showCombatDialog, (visible) => {
  if (!visible) {
    combatActionInFlight.value = false
  }
})

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

const handleGlobalKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') {
    showSheet.value = false
    showMap.value = false
    showQuests.value = false
    showWalkthrough.value = false
    showDebug.value = false
  }
}

onMounted(() => {
  void (async () => {
    await fetchGameSettings()
    if (props.id) {
      await connectWithRouteFallback(props.id)
    }
  })()
  window.addEventListener('keydown', handleGlobalKeydown)
})

watch(() => props.id, (newId) => {
  disconnect()
  if (newId) {
    void connectWithRouteFallback(newId)
  }
})

onBeforeUnmount(() => {
  disconnect()
  window.removeEventListener('keydown', handleGlobalKeydown)
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

    <!-- Header Navigation -->    <header class="bg-transparent px-4 md:px-8 pt-8 pb-4 grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] items-start gap-6 z-10 shrink-0 relative min-h-[110px]">
      <!-- Left: back + Adventure Title -->
      <div class="flex items-center gap-4 z-10 min-w-0 lg:order-1">
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
      <div class="w-full flex justify-center lg:order-2 min-w-0">
        <GameQuestTracker :tracked-quest="trackedQuest" />
      </div>

      <!-- Right: Clock -->
      <div class="flex justify-end lg:order-3 lg:mt-0 mt-[-10px]">
        <GameClockWidget :game-time="gameTime" :clock-tick="clockTick" />
      </div>
      <div v-if="sheet?.debug_mode" class="absolute top-24 left-1/2 -translate-x-1/2 z-[100] px-4 py-1 bg-rose-600/80 backdrop-blur-md border border-rose-400/50 rounded-full text-[10px] font-black text-white uppercase tracking-[0.2em] animate-pulse shadow-lg">
        Debug Protocol Active
      </div>
    </header>


    <div class="flex-grow min-h-0 flex overflow-hidden relative">
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

.selection-mode aside, 
.selection-mode .chat-log-container {
  /* Subtle highlight for interactive areas in selection mode */
  /* background: rgba(16, 185, 129, 0.02); */
}
</style>


