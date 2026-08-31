<script setup lang="ts">
/**
 * ImmersiveGameView — Aesthetic Comic-Style RPG View
 *
 * Immersive full-scene view featuring:
 * - Bright, vibrant full-screen scene background with subtle atmospheric vignettes
 * - Prominent NPC portraits with metadata lookup, status bars & active speaker aura
 * - Comic speech bubbles with authentic angled callout tails pointing towards the speaker on the left
 * - Inline speaker avatar & name in the text flow (Verlauf im Textfluss)
 * - Animated GM Thinking Spinner when requests are being processed
 * - Strict input locking during turn resolution
 * - TAB shortcut to prefill /say and display protagonist speech bubbles
 * - Interactive scene item/switch/exit badges with full icon/image support
 * - Compact bottom action bar with quick modals (Quests, Map, Hero, Timeline, Hints)
 * - User input bar with STT voice recording and command auto-complete
 */
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import DOMPurify from 'dompurify'
import { configState } from '@/store/config'
import type { ChatMessage } from '@/types'
import type { ConnectionStatus } from '@/composables/useGameSocket'
import { getItemIcon, getTypeColor, getImageUrl, getOriginalImageUrl } from '@/utils/game_icons'
import { audioService } from '@/services/audioService'
import StatBar from './StatBar.vue'
import GameClockWidget from '@/components/game/GameClockWidget.vue'
import BableFishSelector from '@/components/game/BableFishSelector.vue'
import CommandPopup from '@/components/game/CommandPopup.vue'
import { getFilteredCommands } from '@/utils/commands'
import {
  Mic,
  Scroll,
  Map as MapIcon,
  User,
  History,
  Lightbulb,
  Sparkles,
  LayoutGrid,
  ChevronLeft,
  ChevronRight,
  Volume2,
  VolumeX,
  DoorOpen,
  Lock,
  SendHorizontal,
  Hand
} from 'lucide-vue-next'

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
  toggleViewMode: []
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
const onImageLoadError = (e: Event, path?: string | null) => {
  if (!path) return
  const target = e.target as HTMLImageElement
  if (target && target.src && target.src.includes('_thumb')) {
    target.src = getOriginalImageUrl(path)
  } else {
    handleImageError(path)
  }
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
  return (props.status === 'connected' || props.status === 'completed') && !props.inputLocked && !isEvaluating.value && !props.sheet?.agent_active
})

// --- State: Input & History ---
const inputText = ref('')
const inputEl = ref<HTMLInputElement | null>(null)
const history = ref<string[]>(JSON.parse(sessionStorage.getItem('tw_chat_history') || '[]'))
const historyIndex = ref(-1)

function addToHistory(text: string) {
  if (!text) return
  if (history.value[0] === text) return
  history.value.unshift(text)
  if (history.value.length > 20) history.value.pop()
  sessionStorage.setItem('tw_chat_history', JSON.stringify(history.value))
}

function navigateHistory(direction: 'up' | 'down') {
  if (history.value.length === 0) return
  if (direction === 'up') {
    if (historyIndex.value < history.value.length - 1) {
      historyIndex.value++
      inputText.value = history.value[historyIndex.value]
    }
  } else {
    if (historyIndex.value > 0) {
      historyIndex.value--
      inputText.value = history.value[historyIndex.value]
    } else if (historyIndex.value === 0) {
      historyIndex.value = -1
      inputText.value = ''
    }
  }
}

// Exit Tooltip State
const hoveredExit = ref<any | null>(null)
const hoveredExitPos = ref({ x: 0, y: 0 })

function handleExitMouseEnter(exit: any, event: MouseEvent) {
  hoveredExit.value = exit
  hoveredExitPos.value = { x: event.clientX, y: event.clientY }
}

function handleExitMouseLeave() {
  hoveredExit.value = null
}

function handleExitMouseMove(event: MouseEvent) {
  if (hoveredExit.value) {
    hoveredExitPos.value = { x: event.clientX, y: event.clientY }
  }
}

// Mobile Layout State
const showMobileInteract = ref(false)

// Command Autocompletion
const showCommandPopup = ref(false)
const commandPopupIndex = ref(0)

const filteredCommands = computed(() => {
  return getFilteredCommands(inputText.value, !!props.sheet?.debug_mode)
})

watch(inputText, (newVal) => {
  if (newVal.startsWith('/')) {
    showCommandPopup.value = true
    if (commandPopupIndex.value >= filteredCommands.value.length) {
      commandPopupIndex.value = 0
    }
  } else {
    showCommandPopup.value = false
  }
})

function selectCommand(cmdId: string) {
  inputText.value = cmdId + ' '
  showCommandPopup.value = false
  inputEl.value?.focus()
}

// --- Voice Recording & Whisper STT ---
const isRecording = ref(false)
const isTranscribing = ref(false)
const mediaStream = ref<MediaStream | null>(null)
const audioContext = ref<AudioContext | null>(null)
const scriptProcessor = ref<ScriptProcessorNode | null>(null)
const leftChannel = ref<Float32Array[]>([])
const pttKeyPressed = ref(false)
const recordStartTime = ref<number>(0)
let globalMouseUpListener: (() => void) | null = null

const whisperStatus = ref<'not_loaded' | 'loading' | 'loaded' | 'error'>('not_loaded')
const whisperModelName = ref('tiny')
const pttPrefixSay = ref(false)
const pttKeyActiveCode = ref('')
let whisperStatusTimer: any = null

function writeString(view: DataView, offset: number, string: string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i))
  }
}

function bufferToWav(buffer: Float32Array, sampleRate: number): ArrayBuffer {
  const bufferLength = buffer.length
  const wavBuffer = new ArrayBuffer(44 + bufferLength * 2)
  const view = new DataView(wavBuffer)

  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + bufferLength * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, bufferLength * 2, true)

  let offset = 44
  for (let i = 0; i < buffer.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, buffer[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return wavBuffer
}

async function startVoiceRecording() {
  if (isRecording.value || !canSendInput.value) return
  try {
    leftChannel.value = []
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaStream.value = stream
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
    const audioCtx = new AudioCtx({ sampleRate: 16000 })
    audioContext.value = audioCtx
    const source = audioCtx.createMediaStreamSource(stream)
    const processor = audioCtx.createScriptProcessor(4096, 1, 1)
    scriptProcessor.value = processor
    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0)
      leftChannel.value.push(new Float32Array(inputData))
    }
    source.connect(processor)
    processor.connect(audioCtx.destination)
    isRecording.value = true
    recordStartTime.value = Date.now()
  } catch (err) {
    console.error('Failed to start recording:', err)
  }
}

async function stopVoiceRecording() {
  if (!isRecording.value) return
  isRecording.value = false
  if (scriptProcessor.value) {
    scriptProcessor.value.disconnect()
    scriptProcessor.value = null
  }
  if (audioContext.value) {
    void audioContext.value.close()
    audioContext.value = null
  }
  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach((track) => track.stop())
    mediaStream.value = null
  }
  if (Date.now() - recordStartTime.value < 500) return

  const totalLength = leftChannel.value.reduce((acc, chunk) => acc + chunk.length, 0)
  const flattened = new Float32Array(totalLength)
  let offset = 0
  for (const chunk of leftChannel.value) {
    flattened.set(chunk, offset)
    offset += chunk.length
  }

  const wavBuffer = bufferToWav(flattened, 16000)
  const audioBlob = new Blob([wavBuffer], { type: 'audio/wav' })
  isTranscribing.value = true
  try {
    const { api } = await import('@/composables/useApi')
    const result = await api.transcribeAudio(audioBlob)
    const text = result.text.trim()
    if (text) {
      const prefix = pttPrefixSay.value ? '/say ' : ''
      if (inputText.value.trim()) {
        inputText.value = `${inputText.value.trim()} ${prefix}${text}`
      } else {
        inputText.value = `${prefix}${text}`
      }
      handleSend()
    }
  } catch (err) {
    console.error('Failed to transcribe audio:', err)
  } finally {
    isTranscribing.value = false
  }
}

function handleMicButtonMousedown(e: MouseEvent | TouchEvent) {
  e.preventDefault()
  if (!canSendInput.value) return
  pttPrefixSay.value = (e as MouseEvent).shiftKey || false
  pttKeyActiveCode.value = ''
  void startVoiceRecording()

  globalMouseUpListener = () => {
    void stopVoiceRecording()
    if (globalMouseUpListener) {
      window.removeEventListener('mouseup', globalMouseUpListener)
      window.removeEventListener('touchend', globalMouseUpListener)
      globalMouseUpListener = null
    }
  }
  window.addEventListener('mouseup', globalMouseUpListener)
  window.addEventListener('touchend', globalMouseUpListener)
}

// --- Turns & Comic Dialogue Parsing ---
interface DialogueSegment {
  speaker: string
  speakerEntity?: any
  target?: string
  targetEntity?: any
  avatarUrl?: string | null
  isPlayer?: boolean
  text: string
  isAction?: boolean
}

interface ComicTurn {
  index: number
  userMessage?: ChatMessage | null
  userIsDialogue?: boolean
  userTargetName?: string | null
  userTargetEntity?: any
  userSpeechText?: string
  assistantMessage?: ChatMessage | null
  systemMessages: ChatMessage[]
  narration: string
  dialogues: DialogueSegment[]
  revealedItemIds: string[]
  timestamp?: string
}

function resolveNpcMetadata(nameOrId: string) {
  if (!nameOrId || !props.npcMetadata) return null
  const norm = String(nameOrId).trim().toLowerCase()
  if (props.npcMetadata[nameOrId]) return props.npcMetadata[nameOrId]
  if (props.npcMetadata[norm]) return props.npcMetadata[norm]
  for (const [k, v] of Object.entries(props.npcMetadata)) {
    if (k.toLowerCase() === norm || (v as any)?.name?.toLowerCase() === norm || (v as any)?.id?.toLowerCase() === norm) {
      return v
    }
  }
  return null
}

function resolveNpc(name: string) {
  if (!name) return null
  const norm = name.trim().toLowerCase()
  const foundEntity = (props.entities || []).find((e) => e.entity_type === 'NPC' && (e.name?.toLowerCase() === norm || e.id?.toLowerCase() === norm))
  const meta = resolveNpcMetadata(name) || (foundEntity ? resolveNpcMetadata(foundEntity.id) || resolveNpcMetadata(foundEntity.name) : null)

  if (foundEntity || meta) {
    return {
      id: foundEntity?.id || meta?.id || norm,
      entity_type: 'NPC',
      name: foundEntity?.name || meta?.name || name,
      description: foundEntity?.description || meta?.description || meta?.backstory || 'A character in this adventure.',
      image_url: foundEntity?.image_url || meta?.image_url || null,
      role: foundEntity?.role || meta?.role || null,
      hp: foundEntity?.hp != null ? foundEntity.hp : meta?.hp != null ? meta.hp : 100,
      max_hp: foundEntity?.max_hp != null ? foundEntity.max_hp : meta?.max_hp != null ? meta.max_hp : 100,
      stamina: foundEntity?.stamina != null ? foundEntity.stamina : meta?.stamina != null ? meta.stamina : 50,
      max_stamina: foundEntity?.max_stamina != null ? foundEntity.max_stamina : meta?.max_stamina != null ? meta.max_stamina : 50,
      mana: foundEntity?.mana != null ? foundEntity.mana : meta?.mana != null ? meta.mana : 50,
      max_mana: foundEntity?.max_mana != null ? foundEntity.max_mana : meta?.max_mana != null ? meta.max_mana : 50,
      inventory: Array.isArray(foundEntity?.inventory) ? foundEntity.inventory : Array.isArray(meta?.inventory) ? meta.inventory : [],
      stat_modifiers: foundEntity?.stat_modifiers || meta?.stat_modifiers || {},
      metadata_json: foundEntity?.metadata_json || meta?.metadata_json || {},
    }
  }
  return null
}

function parseUserMessage(msg: ChatMessage | null | undefined): {
  isDialogue: boolean
  targetName?: string | null
  targetEntity?: any
  speechText: string
} {
  if (!msg || !msg.content) return { isDialogue: false, speechText: '' }
  const raw = msg.content.trim()

  if (raw.toLowerCase().startsWith('/say to ')) {
    const after = raw.slice(8).trim()
    const colonIdx = after.indexOf(':')
    if (colonIdx > 0) {
      const targetCandidate = after.slice(0, colonIdx).trim()
      const speech = after.slice(colonIdx + 1).trim().replace(/^["“]|["”]$/g, '')
      const targetEntity = resolveNpc(targetCandidate)
      return {
        isDialogue: true,
        targetName: targetEntity?.name || targetCandidate,
        targetEntity,
        speechText: speech,
      }
    } else {
      for (const ent of (props.entities || [])) {
        if (ent.entity_type === 'NPC' && ent.name) {
          const entName = ent.name.toLowerCase()
          if (after.toLowerCase().startsWith(entName)) {
            const speech = after.slice(ent.name.length).trim().replace(/^[:,"“\s]+|["”]$/g, '')
            return {
              isDialogue: true,
              targetName: ent.name,
              targetEntity: resolveNpc(ent.name),
              speechText: speech,
            }
          }
        }
      }
      return { isDialogue: true, speechText: after }
    }
  }

  if (raw.toLowerCase().startsWith('/say ')) {
    const speech = raw.slice(5).trim().replace(/^["“]|["”]$/g, '')
    const colonIdx = speech.indexOf(':')
    if (colonIdx > 0) {
      const targetCandidate = speech.slice(0, colonIdx).trim()
      const targetEntity = resolveNpc(targetCandidate)
      if (targetEntity) {
        return {
          isDialogue: true,
          targetName: targetEntity.name,
          targetEntity,
          speechText: speech.slice(colonIdx + 1).trim().replace(/^["“]|["”]$/g, ''),
        }
      }
    }
    return { isDialogue: true, speechText: speech }
  }

  if (raw.startsWith('"') && raw.endsWith('"') && raw.length > 2) {
    const unquoted = raw.slice(1, -1).trim()
    const colonIdx = unquoted.indexOf(':')
    if (colonIdx > 0) {
      const targetCandidate = unquoted.slice(0, colonIdx).trim()
      const targetEntity = resolveNpc(targetCandidate)
      if (targetEntity) {
        return {
          isDialogue: true,
          targetName: targetEntity.name,
          targetEntity,
          speechText: unquoted.slice(colonIdx + 1).trim().replace(/^["“]|["”]$/g, ''),
        }
      }
    }
    return { isDialogue: true, speechText: unquoted }
  }

  return { isDialogue: false, speechText: raw }
}

const gameTurns = computed<ComicTurn[]>(() => {
  const msgs = props.messages || []
  if (!msgs.length) return []

  const turns: ComicTurn[] = []
  let currentTurn: ComicTurn = {
    index: 0,
    systemMessages: [],
    narration: '',
    dialogues: [],
    revealedItemIds: [],
  }

  for (let i = 0; i < msgs.length; i++) {
    const msg = msgs[i]
    if (msg.role === 'license_info') continue

    if (msg.role === 'user') {
      if (currentTurn.userMessage || currentTurn.assistantMessage || currentTurn.narration) {
        turns.push(currentTurn)
        currentTurn = {
          index: turns.length,
          systemMessages: [],
          narration: '',
          dialogues: [],
          revealedItemIds: [],
        }
      }
      currentTurn.userMessage = msg
      const userParsed = parseUserMessage(msg)
      currentTurn.userIsDialogue = userParsed.isDialogue
      currentTurn.userTargetName = userParsed.targetName
      currentTurn.userTargetEntity = userParsed.targetEntity
      currentTurn.userSpeechText = userParsed.speechText
      currentTurn.timestamp = msg.timestamp
    } else if (msg.role === 'assistant') {
      currentTurn.assistantMessage = msg
      currentTurn.timestamp = msg.timestamp || currentTurn.timestamp
      if (msg.itemIds && Array.isArray(msg.itemIds)) {
        currentTurn.revealedItemIds.push(...msg.itemIds)
      }
      const parsed = parseAssistantContent(msg.content)
      currentTurn.narration = parsed.narration
      currentTurn.dialogues.push(...parsed.dialogues)
    } else if (msg.role === 'system') {
      currentTurn.systemMessages.push(msg)
    }
  }

  if (currentTurn.userMessage || currentTurn.assistantMessage || currentTurn.narration || currentTurn.systemMessages.length) {
    turns.push(currentTurn)
  }

  return turns
})

const viewingTurnIndex = ref<number | null>(null)

const activeTurnIndex = computed(() => {
  if (viewingTurnIndex.value !== null && viewingTurnIndex.value >= 0 && viewingTurnIndex.value < gameTurns.value.length) {
    return viewingTurnIndex.value
  }
  return Math.max(0, gameTurns.value.length - 1)
})

const activeTurn = computed<ComicTurn | null>(() => {
  if (!gameTurns.value.length) return null
  return gameTurns.value[activeTurnIndex.value] || null
})

watch(
  () => props.messages.length,
  () => {
    if (viewingTurnIndex.value === null || viewingTurnIndex.value >= gameTurns.value.length - 2) {
      viewingTurnIndex.value = null
    }
  }
)

function goToTurn(idx: number) {
  viewingTurnIndex.value = Math.max(0, Math.min(gameTurns.value.length - 1, idx))
}

function goToLatestTurn() {
  viewingTurnIndex.value = null
}

function parseAssistantContent(content: string): { narration: string; dialogues: DialogueSegment[] } {
  if (!content) return { narration: '', dialogues: [] }

  const dialogues: DialogueSegment[] = []
  const cleanContent = content.replace(/\\n/g, '\n').trim()
  const lines = cleanContent.split('\n')
  const narrationLines: string[] = []

  const speechRegex = /^(?:\*\*([^*:\n]+?):\*\*|\*\*([^*:\n]+?)\*\*:|([A-Za-z0-9_\s'-]{2,30}):)\s*(?:["“](.+?)["”]|(.+))$/

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) continue

    const match = line.match(speechRegex)
    if (match) {
      let speakerName = (match[1] || match[2] || match[3] || '').trim()
      let targetName: string | undefined = undefined
      let targetEntity: any = undefined

      const toMatch = speakerName.match(/^(.+?)\s+(?:to|\(to)\s+(.+?)\)?$/i)
      if (toMatch) {
        speakerName = toMatch[1].trim()
        targetName = toMatch[2].trim()
        targetEntity = resolveNpc(targetName)
      }

      const speechText = (match[4] || match[5] || '').trim().replace(/^["“]|["”]$/g, '')

      const resolvedNpc = resolveNpc(speakerName)
      if (speakerName.toLowerCase() === 'you' || speakerName.toLowerCase() === (props.sheet?.name || '').toLowerCase()) {
        dialogues.push({
          speaker: props.sheet?.name || 'You',
          isPlayer: true,
          target: targetName,
          targetEntity,
          avatarUrl: props.sheet?.profile_image,
          text: speechText,
        })
      } else {
        dialogues.push({
          speaker: resolvedNpc?.name || speakerName,
          speakerEntity: resolvedNpc,
          target: targetName,
          targetEntity,
          avatarUrl: resolvedNpc?.image_url,
          isPlayer: false,
          text: speechText,
        })
      }
    } else {
      narrationLines.push(line)
    }
  }

  return {
    narration: narrationLines.join('\n\n'),
    dialogues,
  }
}

// Active speaking NPCs set in current active turn
const activeSpeakers = computed<Set<string>>(() => {
  const speakers = new Set<string>()
  if (!activeTurn.value) return speakers
  for (const d of activeTurn.value.dialogues) {
    if (d.isPlayer) continue
    if (d.speaker) speakers.add(d.speaker.toLowerCase())
    if (d.speakerEntity?.id) speakers.add(String(d.speakerEntity.id).toLowerCase())
    if (d.speakerEntity?.name) speakers.add(String(d.speakerEntity.name).toLowerCase())
  }
  return speakers
})

function isNpcSpeaking(npc: any): boolean {
  if (!npc) return false
  const nameMatch = npc.name && activeSpeakers.value.has(npc.name.toLowerCase())
  const idMatch = npc.id && activeSpeakers.value.has(String(npc.id).toLowerCase())
  return Boolean(nameMatch || idMatch)
}

const npcs = computed(() => {
  const worldNpcs = (props.entities || [])
    .filter((e) => String(e.entity_type || e.type || '').toUpperCase() === 'NPC')
    .map((e) => {
      const meta = resolveNpcMetadata(e.name) || resolveNpcMetadata(e.id)
      return {
        ...e,
        entity_type: 'NPC',
        image_url: e.image_url || meta?.image_url || null,
        role: e.role || meta?.role || null,
      }
    })

  // Actively speaking NPCs in the current scene are prioritized directly under the protagonist
  const sortedWorldNpcs = [...worldNpcs].sort((a, b) => {
    const aSpeaking = isNpcSpeaking(a) ? 1 : 0
    const bSpeaking = isNpcSpeaking(b) ? 1 : 0
    return bSpeaking - aSpeaking
  })

  if (props.sheet && props.sheet.name) {
    const playerEntity = {
      id: 'PLAYER',
      entity_type: 'NPC',
      name: props.sheet.name ? `You (${props.sheet.name})` : 'You',
      description: props.sheet.description || 'Your hero character.',
      image_url: props.sheet.profile_image || null,
      role: props.sheet.role || 'Hero',
      hp: typeof props.sheet.hp === 'number' ? props.sheet.hp : 100,
      max_hp: typeof props.sheet.max_hp === 'number' ? props.sheet.max_hp : 100,
      mana: typeof props.sheet.mana === 'number' ? props.sheet.mana : 50,
      max_mana: typeof props.sheet.max_mana === 'number' ? props.sheet.max_mana : 50,
      stamina: typeof props.sheet.stamina === 'number' ? props.sheet.stamina : 50,
      max_stamina: typeof props.sheet.max_stamina === 'number' ? props.sheet.max_stamina : 50,
      inventory: Array.isArray(props.sheet.inventory) ? props.sheet.inventory : [],
      stats: props.sheet.stats,
    }
    return [playerEntity, ...sortedWorldNpcs]
  }
  return sortedWorldNpcs
})

function getEntityForHover(nameOrEntity: any) {
  if (typeof nameOrEntity === 'object' && nameOrEntity && nameOrEntity.id) {
    const cloned = { ...nameOrEntity }
    if (!cloned.entity_type) cloned.entity_type = 'NPC'
    if (!cloned.description) {
      const meta = resolveNpcMetadata(cloned.name || cloned.id)
      if (meta?.description || meta?.backstory) cloned.description = meta.description || meta.backstory
    }
    return cloned
  }
  const name = typeof nameOrEntity === 'string' ? nameOrEntity.trim() : String(nameOrEntity?.name || '').trim()
  const norm = name.toLowerCase()
  if (norm === 'you' || norm === (props.sheet?.name || '').toLowerCase() || norm === `you (${props.sheet?.name || ''})`.toLowerCase()) {
    return {
      id: 'PLAYER',
      name: props.sheet?.name || 'You',
      entity_type: 'NPC',
      description: props.sheet?.description || 'Your hero character.',
      image_url: props.sheet?.profile_image || null,
      role: props.sheet?.role || 'Hero',
      hp: typeof props.sheet?.hp === 'number' ? props.sheet?.hp : 100,
      max_hp: typeof props.sheet?.max_hp === 'number' ? props.sheet?.max_hp : 100,
      mana: typeof props.sheet?.mana === 'number' ? props.sheet?.mana : 50,
      max_mana: typeof props.sheet?.max_mana === 'number' ? props.sheet?.max_mana : 50,
      stamina: typeof props.sheet?.stamina === 'number' ? props.sheet?.stamina : 50,
      max_stamina: typeof props.sheet?.max_stamina === 'number' ? props.sheet?.max_stamina : 50,
      inventory: Array.isArray(props.sheet?.inventory) ? props.sheet.inventory : [],
      stats: props.sheet?.stats,
    }
  }
  const found = npcs.value.find((n) => n.name?.toLowerCase() === norm || n.id?.toLowerCase() === norm)
  if (found) {
    return {
      ...found,
      entity_type: 'NPC',
      description: found.description || resolveNpcMetadata(found.name || found.id)?.description || resolveNpcMetadata(found.name || found.id)?.backstory || 'A character in this adventure.',
    }
  }
  const resolved = resolveNpc(name)
  if (resolved) return resolved
  return { name, entity_type: 'NPC', description: 'A character in this adventure.' }
}

function renderFormattedHtml(text: string): string {
  if (!text) return ''
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
  const withVoiceTags = escaped.replace(/(\[[^\]\n]+\])/g, '<span class="comic-voice-tag">$1</span>')
  const withBolds = withVoiceTags.replace(/\*\*(.*?)\*\*/g, '<strong class="text-amber-200 font-bold">$1</strong>')
  const withObjectIds = withBolds.replace(/##([A-Za-z0-9_-]+)/g, '<span class="comic-object-tag">$1</span>')

  return DOMPurify.sanitize(withObjectIds, {
    ALLOWED_TAGS: ['span', 'strong', 'em', 'br', 'div'],
    ALLOWED_ATTR: ['class'],
  })
}

function handleSend() {
  const trimmed = inputText.value.trim()
  if (!trimmed || !canSendInput.value) return
  addToHistory(trimmed)
  historyIndex.value = -1
  emit('send', trimmed)
  inputText.value = ''
  goToLatestTurn()
}

// Prefill /say command when TAB key is pressed
function insertSayCommand() {
  if (!canSendInput.value) return
  if (!inputText.value.startsWith('/say ')) {
    inputText.value = '/say ' + inputText.value
  }
  void nextTick(() => {
    inputEl.value?.focus()
    const len = inputText.value.length
    inputEl.value?.setSelectionRange(len, len)
  })
}

function handleKeydown(e: KeyboardEvent) {
  // TAB key: Insert /say command
  if (e.key === 'Tab' || e.code === 'Tab' || e.keyCode === 9) {
    e.preventDefault()
    e.stopPropagation()
    if (canSendInput.value) {
      insertSayCommand()
    }
    return
  }

  if (showCommandPopup.value && filteredCommands.value.length > 0) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      commandPopupIndex.value = (commandPopupIndex.value + 1) % filteredCommands.value.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      commandPopupIndex.value = (commandPopupIndex.value - 1 + filteredCommands.value.length) % filteredCommands.value.length
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      const sel = filteredCommands.value[commandPopupIndex.value]
      if (sel) selectCommand(sel.id)
      return
    }
    if (e.key === 'Escape') {
      showCommandPopup.value = false
      return
    }
  }

  if (e.key === 'ArrowUp') {
    e.preventDefault()
    navigateHistory('up')
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    navigateHistory('down')
    return
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (canSendInput.value) {
      handleSend()
    }
  }
}

function handleSuggestionSelect(suggestion: string) {
  if (!canSendInput.value) return
  inputText.value = suggestion
  void nextTick(() => {
    inputEl.value?.focus()
  })
}

function handleNpcClick(npc: any) {
  if (npc.id === 'PLAYER') {
    emit('openSheet')
  } else {
    if (!canSendInput.value) return
    emit('npcClick', npc.name)
    inputText.value = `/say to ${npc.name}: `
    void nextTick(() => {
      inputEl.value?.focus()
      const len = inputText.value.length
      inputEl.value?.setSelectionRange(len, len)
    })
  }
}

function getBubbleTtsText(text: string, speakerName?: string) {
  return speakerName ? `${speakerName}: ${text}` : text
}

function isSpeakingBubble(text: string, speakerName?: string) {
  if (!audioService.isPlaying.value) return false
  const target = getBubbleTtsText(text, speakerName)
  return audioService.currentText.value === target || audioService.currentText.value === text
}

function speakBubble(text: string, speakerName?: string) {
  if (!text || !configState.isTtsEnabled) return
  if (isSpeakingBubble(text, speakerName)) {
    audioService.stop()
    return
  }
  audioService.unlock()
  const contentToSpeak = getBubbleTtsText(text, speakerName)
  audioService.speak(contentToSpeak, {
    sceneDescription: props.currentSceneDescription || undefined,
    adventureId: props.sheet?.template_id,
    sessionId: props.gameId,
    title: props.sheet?.adventure_title,
    sceneName: props.sheet?.current_scene,
    tone: props.sheet?.adventure_tone,
    npcMetadata: props.npcMetadata,
  })
}

function handleGlobalKeydown(e: KeyboardEvent) {
  // Global TAB shortcut to jump to chat & prefill /say
  if (e.key === 'Tab' || e.code === 'Tab' || e.keyCode === 9) {
    if (canSendInput.value) {
      e.preventDefault()
      e.stopPropagation()
      insertSayCommand()
    }
    return
  }

  const target = e.target as HTMLElement
  const isTyping = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable

  const isV = e.code === 'KeyV'
  const isB = e.code === 'KeyB'
  const isT = e.code === 'KeyT'
  if ((isV || isB || isT) && !isTyping && canSendInput.value) {
    e.preventDefault()
    if (!pttKeyPressed.value) {
      pttKeyPressed.value = true
      pttKeyActiveCode.value = e.code
      pttPrefixSay.value = isB || isT || e.shiftKey
      void startVoiceRecording()
    }
  }
}

function handleGlobalKeyup(e: KeyboardEvent) {
  const activeCode = pttKeyActiveCode.value || 'KeyV'
  if (e.code === activeCode && pttKeyPressed.value) {
    e.preventDefault()
    pttKeyPressed.value = false
    pttKeyActiveCode.value = ''
    void stopVoiceRecording()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown, { capture: true })
  window.addEventListener('keyup', handleGlobalKeyup)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown, { capture: true })
  window.removeEventListener('keyup', handleGlobalKeyup)
  if (whisperStatusTimer) clearInterval(whisperStatusTimer)
})

defineExpose({
  setInputText: (text: string) => {
    inputText.value = text
    void nextTick(() => {
      inputEl.value?.focus()
      const pos = inputText.value.length
      inputEl.value?.setSelectionRange(pos, pos)
    })
  },
  appendText: (text: string) => {
    inputText.value = inputText.value ? `${inputText.value} ${text}` : text
    void nextTick(() => {
      inputEl.value?.focus()
      const pos = inputText.value.length
      inputEl.value?.setSelectionRange(pos, pos)
    })
  },
  toggleSayPrefix: () => {
    const current = inputText.value.trim()
    if (current.startsWith('/say ')) {
      inputText.value = current.slice(5)
    } else {
      inputText.value = '/say ' + inputText.value
    }
    void nextTick(() => {
      inputEl.value?.focus()
    })
  }
})
</script>

<template>
  <div class="relative w-full h-full flex flex-col justify-between overflow-hidden select-none bg-slate-950 font-sans">
    <!-- 1. FULL VIEW SCENE BACKGROUND (Brighter & Crisp) -->
    <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none">
      <img
        v-if="activeSceneImageUrl"
        :src="activeSceneImageUrl"
        class="w-full h-full object-cover object-center filter brightness-[0.9] saturate-[1.1] contrast-[1.05] scale-[1.01] transition-all duration-1000"
        alt="Scene background"
        @error="handleImageError(props.currentSceneImage || props.adventureImage)"
      />
      <div v-else class="w-full h-full bg-gradient-to-b from-slate-900 via-slate-950 to-black"></div>

      <!-- Light, balanced atmospheric overlays -->
      <div class="absolute inset-0 bg-black/20"></div>
      <div class="absolute inset-0 bg-gradient-to-t from-slate-950/85 via-transparent to-slate-950/40"></div>
      <div class="absolute inset-0 bg-gradient-to-r from-slate-950/60 via-transparent to-slate-950/40"></div>
    </div>

    <!-- 2. TOP ATMOSPHERIC HEADER BAR -->
    <header class="relative z-20 flex items-center justify-between px-4 py-3 sm:px-6 sm:py-3.5 bg-slate-950/75 backdrop-blur-md border-b border-slate-800/80 shadow-2xl shrink-0">
      <!-- Left: Scene Title & Back -->
      <div class="flex items-center gap-3 min-w-0">
        <button
          type="button"
          @click="emit('openChronicles')"
          class="flex items-center justify-center w-9 h-9 rounded-xl bg-slate-900/80 border border-slate-700/60 text-slate-300 hover:text-white hover:border-amber-400/50 hover:bg-amber-500/10 transition-all shadow-lg active:scale-95 shrink-0 cursor-pointer"
          title="Chronicles & Timeline"
        >
          <History class="w-4 h-4" />
        </button>

        <div class="flex flex-col min-w-0">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-[0.2em] bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
              Scene
            </span>
            <h2 class="text-sm sm:text-base font-black text-white uppercase tracking-wider truncate drop-shadow-md comic-title">
              {{ props.currentSceneName || props.sheet?.current_scene || 'Unknown Location' }}
            </h2>
          </div>
          <div class="flex items-center gap-2 text-[11px] text-slate-400 truncate opacity-80 font-medium">
            <span v-if="props.sheet?.adventure_title" class="truncate">{{ props.sheet.adventure_title }}</span>
            <span v-if="props.sheet?.adventure_title && (props.sheet?.copyright || props.sheet?.creator)" class="text-slate-600 select-none">•</span>
            <span v-if="props.sheet?.copyright || props.sheet?.creator" class="text-[10px] text-slate-500 tracking-wide truncate">
              {{ props.sheet.copyright || `© ${props.sheet.creator}` }}
            </span>
          </div>
        </div>
      </div>

      <!-- Center: Tracked Quest Banner -->
      <div
        v-if="props.trackedQuest"
        class="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900/80 border border-amber-500/30 text-amber-200 text-xs font-semibold backdrop-blur-sm shadow-md cursor-pointer hover:border-amber-400 transition-all"
        @click="emit('openQuests')"
      >
        <Scroll class="w-3.5 h-3.5 text-amber-400 shrink-0" />
        <span class="max-w-[20rem] truncate font-bold">{{ props.trackedQuest.title || props.trackedQuest.description }}</span>
      </div>

      <!-- Right: Status, Audio & View Switcher -->
      <div class="flex items-center gap-2 sm:gap-3 shrink-0">
        <!-- In-Game Clock -->
        <GameClockWidget :game-time="props.gameTime || null" :clock-tick="props.clockTick || false" />

        <!-- TTS Toggle / Stop -->
        <div v-if="configState.isTtsEnabled" class="flex items-center gap-1.5">
          <button
            v-if="audioService.isPlaying.value"
            type="button"
            @click="audioService.stop()"
            class="flex items-center justify-center w-8 h-8 rounded-lg bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30 transition-all animate-pulse cursor-pointer"
            title="Stop Speech (SPACE)"
          >
            <VolumeX class="w-4 h-4" />
          </button>
          <button
            type="button"
            @click="audioService.toggleAutoSpeech()"
            class="flex items-center justify-center w-8 h-8 rounded-lg transition-all border cursor-pointer"
            :class="[
              audioService.autoSpeechEnabled.value
                ? 'bg-amber-500/20 border-amber-500/50 text-amber-300 hover:bg-amber-500/30'
                : 'bg-slate-900/80 border-slate-700/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            ]"
            :title="audioService.autoSpeechEnabled.value ? 'Auto-Narration ON (Click to disable)' : 'Auto-Narration OFF (Click to enable)'"
          >
            <Volume2 class="w-4 h-4" />
          </button>
        </div>

        <BableFishSelector />

        <!-- Experience XP -->
        <div v-if="props.exp !== undefined && props.mode !== 'chat'" class="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-black tracking-wider">
          <i class="ra ra-laurels text-sm"></i>
          <span>{{ props.exp }} XP</span>
        </div>

        <!-- View Switcher Button (Switch to Classic View) -->
        <button
          type="button"
          @click="emit('toggleViewMode')"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/80 border border-slate-700/60 hover:border-emerald-400/50 hover:bg-emerald-500/10 text-slate-300 hover:text-white transition-all text-xs font-black uppercase tracking-wider shadow-lg active:scale-95 cursor-pointer"
          title="Switch to Classic RPG Panel View"
        >
          <LayoutGrid class="w-3.5 h-3.5 text-emerald-400" />
          <span class="hidden sm:inline">Classic View</span>
        </button>

        <!-- Mobile Interact Toggle (Only on mobile) -->
        <button
          type="button"
          @click="showMobileInteract = !showMobileInteract"
          class="md:hidden flex items-center justify-center px-3 py-1.5 rounded-xl bg-amber-500/20 border border-amber-500/50 text-amber-300 hover:bg-amber-500/30 transition-all text-xs font-black uppercase tracking-wider shadow-lg active:scale-95 cursor-pointer"
          title="Toggle Interact Menu"
        >
          <MapIcon class="w-4 h-4" />
        </button>
      </div>
    </header>

    <!-- 3. MAIN INTERACTIVE STAGE AREA -->
    <div class="relative z-10 flex-grow min-h-0 flex flex-row gap-2 sm:gap-4 p-2 sm:p-4 lg:p-6 overflow-hidden">
      <!-- 3A. LEFT / SCENE NPC STAGE (Compact 2:3 Vertical Portraits with Overlaid Name) -->
      <aside class="flex flex-col gap-2 shrink-0 overflow-y-auto w-20 sm:w-28 md:w-36 lg:w-44 custom-scrollbar pr-1 py-1 max-h-full">
        <TransitionGroup name="npc-stage" tag="div" class="flex flex-col gap-2 w-full">
          <div
            v-for="npc in npcs"
            :key="npc.id"
            class="relative group flex flex-col items-center bg-slate-950 rounded-xl border-2 transition-all duration-300 shrink-0 w-full aspect-[2/3] overflow-hidden cursor-pointer shadow-[0_6px_20px_rgba(0,0,0,0.7)] active:scale-98"
            :class="[
              isNpcSpeaking(npc)
                ? 'border-amber-400 shadow-[0_0_25px_rgba(251,191,36,0.6)] ring-2 ring-amber-400/60'
                : npc.id === 'PLAYER'
                  ? 'border-emerald-500/70 hover:border-emerald-400'
                  : 'border-slate-700/70 hover:border-cyan-400/80'
            ]"
            @click="handleNpcClick(npc)"
            @mouseenter="emit('npcHover', getEntityForHover(npc), $event)"
            @mousemove="emit('npcHover', getEntityForHover(npc), $event)"
            @mouseleave="emit('npcLeave')"
            @contextmenu.prevent="emit('npcContextmenu', npc, $event)"
          >
            <!-- Full 2:3 Character Portrait -->
            <img
              v-if="npc.image_url && showImage(npc.image_url)"
              :src="getImageUrl(npc.image_url, { thumbnail: true })"
              :alt="npc.name"
              class="w-full h-full object-cover object-top transition-transform duration-700 group-hover:scale-105"
              :class="{ 'grayscale opacity-50': npc.is_defeated || npc.hp === 0 }"
              @error="onImageLoadError($event, npc.image_url)"
            />
            <div v-else class="w-full h-full flex flex-col items-center justify-center bg-gradient-to-b from-slate-900 to-slate-950 text-slate-600">
              <i :class="['ra text-4xl mb-1', npc.id === 'PLAYER' ? 'ra-player text-emerald-400' : 'ra-helmet text-cyan-400']"></i>
            </div>

            <!-- Active Speaker Badge -->
            <div v-if="isNpcSpeaking(npc)" class="absolute top-2 right-2 z-20 px-1.5 py-0.5 rounded-full bg-amber-500 text-black text-[8px] font-black uppercase tracking-wider shadow-md animate-bounce">
              Speaking
            </div>

            <!-- Hero Tag for Player -->
            <div v-else-if="npc.id === 'PLAYER'" class="absolute top-2 left-2 z-20 px-1.5 py-0.5 rounded-full bg-emerald-500/80 text-white backdrop-blur-md border border-emerald-300/40 text-[8px] font-black uppercase tracking-wider shadow-md">
              You
            </div>

            <!-- Defeated Ribbon -->
            <div v-if="npc.is_defeated || npc.hp === 0" class="absolute -right-6 top-3 bg-red-600 text-white text-[8px] font-black uppercase tracking-[0.12em] py-0.5 w-24 text-center rotate-45 shadow-lg z-20">
              Defeated
            </div>

            <!-- Name & Role Overlay with Gradient & Strong Shadow -->
            <div class="absolute inset-x-0 bottom-0 pt-8 pb-2 px-2 bg-gradient-to-t from-black/95 via-black/60 to-transparent flex flex-col items-center text-center pointer-events-none z-10">
              <h4 class="text-[11px] sm:text-xs font-black text-white group-hover:text-amber-300 transition-colors uppercase tracking-wider drop-shadow-[0_2px_3px_rgba(0,0,0,1)] truncate w-full">
                {{ npc.name }}
              </h4>
              <span v-if="npc.role" class="text-[9px] font-bold text-slate-300/90 uppercase tracking-widest drop-shadow-[0_1px_2px_rgba(0,0,0,1)] truncate w-full mt-0.5">
                {{ npc.role }}
              </span>
            </div>
          </div>
        </TransitionGroup>
      </aside>

      <!-- 3B. CENTER / COMIC STORY & SPEECH BUBBLES AREA -->
      <main class="flex-1 flex flex-col justify-between min-h-0 relative overflow-hidden">
        <!-- Floating Interactive Scene Hotspots (Items, Switches, Exits) -->
        <div
          class="shrink-0 z-50 md:z-10"
          :class="[
            isEvaluating ? 'opacity-50 pointer-events-none' : '',
            showMobileInteract ? 'absolute right-2 top-2 bg-slate-900/95 p-3 rounded-2xl border border-slate-700 shadow-2xl max-w-[70vw] max-h-[60vh] overflow-y-auto flex flex-col gap-2' : 'hidden md:flex flex-wrap items-center gap-2 mb-3'
          ]"
        >
          <!-- Exits / Portals -->
          <div
            v-for="exit in props.sceneExits"
            :key="exit.id || exit.label"
            class="group flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/85 hover:bg-slate-800 border border-slate-700/80 hover:border-amber-400/60 text-slate-200 hover:text-white backdrop-blur-md transition-all shadow-lg cursor-pointer active:scale-95"
            @click="emit('traverseExit', exit)"
            @mouseenter="e => handleExitMouseEnter(exit, e)"
            @mouseleave="handleExitMouseLeave"
            @mousemove="handleExitMouseMove"
          >
            <Lock
              v-if="exit.is_locked"
              class="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform"
            />
            <DoorOpen
              v-else
              class="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform"
            />
            <span class="text-xs font-bold uppercase tracking-wider truncate max-w-[8rem]">{{ exit.label || 'Exit' }}</span>
            <span v-if="exit.is_locked" class="px-1.5 py-0.2 bg-red-500/20 text-red-300 border border-red-500/30 text-[9px] font-black rounded-full uppercase">
              Locked
            </span>
          </div>

          <!-- Switches -->
          <div
            v-for="sw in props.sceneSwitches"
            :key="sw.id"
            class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/85 hover:bg-slate-800 border border-lime-500/40 text-slate-200 hover:text-lime-300 backdrop-blur-md transition-all shadow-lg cursor-pointer active:scale-95"
            @click="emit('switchFlip', sw)"
          >
            <i class="ra ra-lever text-lime-400 text-sm"></i>
            <span class="text-xs font-bold uppercase tracking-wider truncate max-w-[8rem]">{{ sw.name }}</span>
            <span class="px-1.5 py-0.2 bg-lime-500/20 text-lime-300 text-[9px] font-black rounded-full uppercase">
              {{ String(sw.switch_state || sw.metadata_json?.switch?.initial_state || '—').toUpperCase() }}
            </span>
          </div>

          <!-- Scene Items / Discoveries with Rich Image / RPG Icon -->
          <div
            v-for="item in props.items"
            :key="item.id"
            class="group flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900/85 hover:bg-slate-800 border border-cyan-500/40 hover:border-cyan-400 text-slate-200 hover:text-cyan-300 backdrop-blur-md transition-all shadow-lg cursor-pointer active:scale-95"
            @click="emit('itemClick', item)"
            @mouseenter="emit('itemHover', item, $event)"
            @mouseleave="emit('itemLeave')"
            @contextmenu.prevent="emit('itemContextmenu', item, $event)"
          >
            <div class="w-6 h-6 rounded-md overflow-hidden bg-slate-950 border border-slate-700/80 flex items-center justify-center shrink-0">
              <img
                v-if="item.image_url && showImage(item.image_url)"
                :src="getImageUrl(item.image_url, { thumbnail: true })"
                :alt="item.name"
                class="w-full h-full object-cover"
                @error="onImageLoadError($event, item.image_url)"
              />
              <i v-else :class="['ra text-sm', getItemIcon(item.item_type), getTypeColor(item.item_type)]"></i>
            </div>

            <span class="text-xs font-bold uppercase tracking-wider truncate max-w-[9rem]">{{ item.name }}</span>

            <span
              v-if="String(item.item_type || '').toUpperCase() === 'READABLE'"
              class="px-1 py-0.2 rounded text-[8px] font-black uppercase bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
            >
              Note
            </span>

            <button
              v-if="item.is_portable !== false"
              type="button"
              class="ml-1 text-slate-400 hover:text-emerald-400 p-1 rounded-md bg-slate-800/80 hover:bg-slate-700 transition-colors cursor-pointer"
              title="Take Item"
              @click.stop="emit('takeDirect', item)"
            >
              <Hand class="w-3 h-3 text-emerald-400" />
            </button>
          </div>
        </div>

        <!-- COMIC STORY CONTAINER (Turn Display & GM Thinking Spinner) -->
        <div class="flex-1 overflow-y-auto custom-scrollbar p-2 sm:p-4 flex flex-col gap-4 min-h-0 relative">
          <!-- GM Thinking Spinner Overlay / Banner -->
          <div
            v-if="isEvaluating"
            class="flex items-center gap-3.5 p-4 rounded-2xl bg-amber-950/80 border-2 border-amber-400/80 text-amber-100 shadow-[0_8px_30px_rgba(251,191,36,0.3)] backdrop-blur-xl animate-fade-in my-1 shrink-0"
          >
            <div class="relative flex items-center justify-center w-7 h-7 shrink-0">
              <div class="w-7 h-7 border-3 border-amber-400/30 border-t-amber-400 rounded-full animate-spin"></div>
              <Sparkles class="w-3.5 h-3.5 text-amber-300 absolute animate-pulse" />
            </div>
            <div class="flex flex-col min-w-0">
              <div class="flex items-center gap-2">
                <span class="px-2 py-0.5 rounded-full bg-amber-500 text-slate-950 text-[9px] font-black uppercase tracking-[0.2em]">
                  Thinking
                </span>
                <span class="text-xs font-black uppercase tracking-wider text-amber-200">
                  {{ props.statusText || 'Game Master is resolving your action...' }}
                </span>
              </div>
              <p class="text-[11px] text-amber-300/80 italic mt-0.5 truncate">
                Weaving the world's narrative response...
              </p>
            </div>
          </div>

          <!-- Empty State -->
          <div v-if="!activeTurn && !isEvaluating" class="flex-1 flex flex-col items-center justify-center text-slate-500">
            <Sparkles class="w-8 h-8 text-amber-400/60 mb-2 animate-pulse" />
            <p class="text-sm font-semibold tracking-wider uppercase">Awaiting Adventure Turn...</p>
          </div>

          <template v-else-if="activeTurn">
            <!-- 1) PROTAGONIST / USER SPEECH OR ACTION BUBBLE -->
            <div
              v-if="activeTurn.userMessage"
              class="flex flex-col gap-1 animate-fade-in items-start group"
            >
              <div class="relative max-w-2xl">
                <!-- Overlay TTS Button (visible on hover) -->
                <button
                  v-if="configState.isTtsEnabled"
                  type="button"
                  @click.stop="speakBubble(activeTurn.userSpeechText || activeTurn.userMessage.content, props.sheet?.name || 'You')"
                  class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/90 hover:bg-emerald-900 border border-emerald-400/60 text-emerald-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
                  :title="isSpeakingBubble(activeTurn.userSpeechText || activeTurn.userMessage.content, props.sheet?.name || 'You') ? 'Stop Audio' : 'Play Audio'"
                >
                  <VolumeX v-if="isSpeakingBubble(activeTurn.userSpeechText || activeTurn.userMessage.content, props.sheet?.name || 'You')" class="w-3 h-3 text-red-400" />
                  <Volume2 v-else class="w-3 h-3" />
                  <span>{{ isSpeakingBubble(activeTurn.userSpeechText || activeTurn.userMessage.content, props.sheet?.name || 'You') ? 'Stop' : 'Audio' }}</span>
                </button>

                <!-- SVG Speech Tail pointing to Speaker on Left -->
                <svg
                  class="absolute -left-3.5 top-4 w-4 h-6 text-slate-900 pointer-events-none z-20 overflow-visible"
                  viewBox="0 0 16 24"
                >
                  <polygon
                    points="16,0 0,12 16,24"
                    class="fill-slate-900 stroke-emerald-400"
                    stroke-width="2"
                    stroke-linejoin="round"
                  />
                  <rect x="14" y="1" width="4" height="22" class="fill-slate-900" />
                </svg>

                <div
                  class="relative p-3.5 sm:p-4.5 rounded-2xl border-2 shadow-[0_8px_25px_rgba(0,0,0,0.6)] backdrop-blur-xl bg-slate-900/95 border-emerald-400 text-slate-100"
                >
                  <!-- Content: Name Tag, Target Addressee & Speech in same text size -->
                  <p
                    class="comic-bubble-text text-sm sm:text-base leading-relaxed font-semibold"
                    :class="activeTurn.userIsDialogue ? 'italic text-white' : 'text-emerald-100'"
                  >
                    <!-- Speaker Tag -->
                    <span
                      class="inline-flex items-center align-baseline mr-1.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider bg-emerald-500/20 border-emerald-400/50 text-emerald-300 hover:bg-emerald-500/30 hover:border-emerald-400 cursor-pointer transition-all shadow-sm"
                      @mouseenter="emit('npcHover', getEntityForHover(props.sheet?.name || 'You'), $event)"
                      @mousemove="emit('npcHover', getEntityForHover(props.sheet?.name || 'You'), $event)"
                      @mouseleave="emit('npcLeave')"
                      @click="emit('openSheet')"
                    >
                      {{ props.sheet?.name || 'You' }}
                    </span>

                    <!-- Target Addressee Tag with Arrow (e.g. ➔ [DAD ARTHUR]) -->
                    <template v-if="activeTurn.userTargetName">
                      <span class="inline-flex items-center align-baseline text-slate-400 mx-1 not-italic font-black text-xs select-none">
                        ➔
                      </span>
                      <span
                        class="inline-flex items-center align-baseline mr-2.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider bg-cyan-500/20 border-cyan-400/50 text-cyan-300 hover:bg-cyan-500/30 hover:border-cyan-400 cursor-pointer transition-all shadow-sm"
                        @mouseenter="emit('npcHover', getEntityForHover(activeTurn.userTargetEntity || activeTurn.userTargetName), $event)"
                        @mousemove="emit('npcHover', getEntityForHover(activeTurn.userTargetEntity || activeTurn.userTargetName), $event)"
                        @mouseleave="emit('npcLeave')"
                        @click="emit('npcClick', activeTurn.userTargetName)"
                      >
                        {{ activeTurn.userTargetName }}
                      </span>
                    </template>

                    {{ activeTurn.userIsDialogue ? `"${activeTurn.userSpeechText}"` : activeTurn.userSpeechText }}
                  </p>
                </div>
              </div>
            </div>

            <!-- 2) GM COMIC NARRATIVE CAPTION BOX -->
            <div v-if="activeTurn.narration" class="animate-fade-in relative group">
              <div class="relative bg-slate-900/95 border-2 border-amber-500/70 rounded-2xl p-4 sm:p-5 shadow-[0_12px_35px_rgba(0,0,0,0.7)] backdrop-blur-xl">
                <!-- Overlay TTS Button (sitting on upper border frame) -->
                <button
                  v-if="configState.isTtsEnabled"
                  type="button"
                  @click.stop="speakBubble(activeTurn.narration)"
                  class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-950/90 hover:bg-amber-900 border border-amber-400/60 text-amber-300 text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md"
                  :title="isSpeakingBubble(activeTurn.narration) ? 'Stop Audio' : 'Play Audio'"
                >
                  <VolumeX v-if="isSpeakingBubble(activeTurn.narration)" class="w-3 h-3 text-red-400" />
                  <Volume2 v-else class="w-3 h-3" />
                  <span>{{ isSpeakingBubble(activeTurn.narration) ? 'Stop' : 'Audio' }}</span>
                </button>

                <!-- Narrative Text with Inline "GAME MASTER" Badge in Text Flow -->
                <div class="comic-narration-text text-sm sm:text-base leading-relaxed text-slate-100">
                  <span
                    class="inline-flex items-center align-middle mr-2.5 not-italic select-none px-2 py-0.5 rounded-md bg-amber-500 text-slate-950 font-sans font-black text-[10px] uppercase tracking-[0.2em] shadow-sm"
                  >
                    Game Master
                  </span>
                  <span v-html="renderFormattedHtml(activeTurn.narration)"></span>
                </div>
              </div>
            </div>

            <!-- 3) NPC DIALOGUE COMIC SPEECH BUBBLES -->
            <div
              v-for="(dlg, dIdx) in activeTurn.dialogues"
              :key="dIdx"
              class="flex flex-col gap-1 animate-fade-in items-start group"
            >
              <div class="relative max-w-2xl">
                <!-- Overlay TTS Button (visible on hover) -->
                <button
                  v-if="configState.isTtsEnabled"
                  type="button"
                  @click.stop="speakBubble(dlg.text, dlg.speaker)"
                  class="absolute -top-2.5 right-3 z-30 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-200 flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider shadow-lg cursor-pointer backdrop-blur-md border"
                  :class="dlg.isPlayer ? 'bg-emerald-950/90 hover:bg-emerald-900 border-emerald-400/60 text-emerald-300' : 'bg-amber-950/90 hover:bg-amber-900 border-amber-400/60 text-amber-300'"
                  :title="isSpeakingBubble(dlg.text, dlg.speaker) ? 'Stop Audio' : 'Play Audio'"
                >
                  <VolumeX v-if="isSpeakingBubble(dlg.text, dlg.speaker)" class="w-3 h-3 text-red-400" />
                  <Volume2 v-else class="w-3 h-3" />
                  <span>{{ isSpeakingBubble(dlg.text, dlg.speaker) ? 'Stop' : 'Audio' }}</span>
                </button>

                <!-- Comic Angled Speech Tail pointing Left directly towards the NPC portrait card -->
                <svg
                  class="absolute -left-3.5 top-4 w-4 h-6 text-slate-900 pointer-events-none z-20 overflow-visible"
                  viewBox="0 0 16 24"
                >
                  <polygon
                    points="16,0 0,12 16,24"
                    class="fill-slate-900"
                    :class="dlg.isPlayer ? 'stroke-emerald-400' : 'stroke-amber-400'"
                    stroke-width="2"
                    stroke-linejoin="round"
                  />
                  <rect x="14" y="1" width="4" height="22" class="fill-slate-900" />
                </svg>

                <div
                  class="relative p-3.5 sm:p-4.5 rounded-2xl border-2 shadow-[0_10px_30px_rgba(0,0,0,0.65)] backdrop-blur-xl bg-slate-900/95"
                  :class="dlg.isPlayer ? 'border-emerald-400 text-slate-100' : 'border-amber-400 text-slate-100 shadow-[0_0_20px_rgba(251,191,36,0.25)]'"
                >
                  <p class="comic-bubble-text text-sm sm:text-base leading-relaxed font-medium italic text-white">
                    <!-- Speaker Tag -->
                    <span
                      class="inline-flex items-center align-baseline mr-1.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider cursor-pointer transition-all shadow-sm"
                      :class="[
                        dlg.isPlayer
                          ? 'bg-emerald-500/20 border-emerald-400/50 text-emerald-300 hover:bg-emerald-500/30 hover:border-emerald-400'
                          : 'bg-amber-500/20 border-amber-400/50 text-amber-300 hover:bg-amber-500/30 hover:border-amber-400'
                      ]"
                      @mouseenter="emit('npcHover', getEntityForHover(dlg.speakerEntity || dlg.speaker), $event)"
                      @mousemove="emit('npcHover', getEntityForHover(dlg.speakerEntity || dlg.speaker), $event)"
                      @mouseleave="emit('npcLeave')"
                      @contextmenu.prevent="emit('npcContextmenu', resolveNpc(dlg.speaker) || { name: dlg.speaker, entity_type: 'NPC' }, $event)"
                      @click="dlg.isPlayer ? emit('openSheet') : emit('npcClick', dlg.speaker)"
                    >
                      {{ dlg.speaker }}
                    </span>

                    <!-- Target Addressee Badge (if targeted) -->
                    <template v-if="dlg.target">
                      <span class="inline-flex items-center align-baseline text-slate-400 mx-1 not-italic font-black text-xs select-none">
                        ➔
                      </span>
                      <span
                        class="inline-flex items-center align-baseline mr-2.5 not-italic select-none px-2 py-0.5 rounded-lg border font-black text-xs sm:text-sm uppercase tracking-wider bg-cyan-500/20 border-cyan-400/50 text-cyan-300 hover:bg-cyan-500/30 hover:border-cyan-400 cursor-pointer transition-all shadow-sm"
                        @mouseenter="emit('npcHover', getEntityForHover(dlg.targetEntity || dlg.target), $event)"
                        @mousemove="emit('npcHover', getEntityForHover(dlg.targetEntity || dlg.target), $event)"
                        @mouseleave="emit('npcLeave')"
                        @click="emit('npcClick', dlg.target)"
                      >
                        {{ dlg.target }}
                      </span>
                    </template>

                    "{{ dlg.text }}"
                  </p>
                </div>
              </div>
            </div>

            <!-- 4) REVEALED ITEMS DISCOVERY CARDS -->
            <div v-if="activeTurn.revealedItemIds.length" class="flex flex-wrap gap-3 my-2">
              <div
                v-for="itemId in activeTurn.revealedItemIds"
                :key="itemId"
                v-show="props.entities.find((e) => e.id === itemId)"
                class="flex items-center gap-3 p-2.5 rounded-xl bg-slate-900/90 border border-emerald-500/50 shadow-lg cursor-pointer hover:border-emerald-400"
                @click="emit('itemClick', props.entities.find((e) => e.id === itemId))"
              >
                <div class="w-8 h-8 rounded-lg overflow-hidden bg-slate-950 border border-slate-700 flex items-center justify-center shrink-0">
                  <img
                    v-if="props.entities.find((e) => e.id === itemId)?.image_url && showImage(props.entities.find((e) => e.id === itemId).image_url)"
                    :src="getImageUrl(props.entities.find((e) => e.id === itemId).image_url, { thumbnail: true })"
                    class="w-full h-full object-cover"
                    @error="onImageLoadError($event, props.entities.find((e) => e.id === itemId).image_url)"
                  />
                  <i v-else :class="['ra text-base', getItemIcon(props.entities.find((e) => e.id === itemId)?.item_type), getTypeColor(props.entities.find((e) => e.id === itemId)?.item_type)]"></i>
                </div>
                <div>
                  <span class="text-xs font-bold text-white block">{{ props.entities.find((e) => e.id === itemId)?.name }}</span>
                  <span class="text-[10px] text-emerald-400 uppercase font-black tracking-wider">New Discovery!</span>
                </div>
                <button
                  type="button"
                  class="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-black uppercase tracking-wider ml-2 cursor-pointer"
                  @click.stop="emit('takeDirect', props.entities.find((e) => e.id === itemId))"
                >
                  Take
                </button>
              </div>
            </div>
          </template>
        </div>

        <!-- COMIC TURN NAVIGATION & PAGING CONTROLS -->
        <div v-if="gameTurns.length > 1" class="flex items-center justify-between px-3 py-1.5 bg-slate-950/80 border-t border-slate-800/80 shrink-0 text-xs font-bold text-slate-400">
          <div class="flex items-center gap-1">
            <button
              type="button"
              :disabled="activeTurnIndex <= 0"
              @click="goToTurn(activeTurnIndex - 1)"
              class="p-1 rounded bg-slate-900 border border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed hover:text-white cursor-pointer"
              title="Previous Turn"
            >
              <ChevronLeft class="w-3.5 h-3.5" />
            </button>
            <span class="px-2 font-mono">Turn {{ activeTurnIndex + 1 }} / {{ gameTurns.length }}</span>
            <button
              type="button"
              :disabled="activeTurnIndex >= gameTurns.length - 1"
              @click="goToTurn(activeTurnIndex + 1)"
              class="p-1 rounded bg-slate-900 border border-slate-700 disabled:opacity-30 disabled:cursor-not-allowed hover:text-white cursor-pointer"
              title="Next Turn"
            >
              <ChevronRight class="w-3.5 h-3.5" />
            </button>
          </div>

          <button
            v-if="viewingTurnIndex !== null"
            type="button"
            @click="goToLatestTurn"
            class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-black uppercase tracking-wider hover:bg-amber-500/30 cursor-pointer"
          >
            Jump to Latest
          </button>
        </div>
      </main>
    </div>

    <!-- 4. BOTTOM COMPACT ACTION BAR & USER INPUT -->
    <footer class="relative z-20 flex flex-col bg-slate-950/95 backdrop-blur-xl border-t border-slate-800/90 shadow-[0_-10px_30px_rgba(0,0,0,0.8)] shrink-0">
      <!-- 4A. COMPACT ACTION BUTTONS & PROMPT SUGGESTIONS ROW -->
      <div class="flex items-center justify-between px-4 py-2 border-b border-slate-800/60 overflow-x-auto no-scrollbar gap-3">
        <!-- Quick Modals Buttons -->
        <div class="flex items-center gap-2 shrink-0">
          <!-- Quests Button -->
          <button
            type="button"
            @click="emit('openQuests')"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-amber-400 hover:bg-amber-500/10 text-slate-200 hover:text-amber-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
            :class="{ 'ring-2 ring-amber-400/40': props.questGlow }"
            title="Open Quest Log"
          >
            <Scroll class="w-4 h-4 text-amber-400" />
            <span class="hidden sm:inline uppercase tracking-wider">Quests</span>
            <span v-if="props.trackedQuest" class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
          </button>

          <!-- World Map Button -->
          <button
            type="button"
            @click="emit('openMap')"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-sky-400 hover:bg-sky-500/10 text-slate-200 hover:text-sky-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
            :class="{ 'ring-2 ring-sky-400/40': props.mapGlow }"
            title="Open World Map"
          >
            <MapIcon class="w-4 h-4 text-sky-400" />
            <span class="hidden sm:inline uppercase tracking-wider">Map</span>
          </button>

          <!-- Hero & Inventory Button -->
          <button
            type="button"
            @click="emit('openSheet')"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-emerald-400 hover:bg-emerald-500/10 text-slate-200 hover:text-emerald-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
            :class="{ 'ring-2 ring-emerald-400/40': props.inventoryGlow }"
            title="Open Character Sheet & Inventory"
          >
            <User class="w-4 h-4 text-emerald-400" />
            <span class="hidden sm:inline uppercase tracking-wider">Hero</span>
            <span v-if="props.inventory?.length" class="px-1.5 py-0.2 bg-emerald-500/20 text-emerald-300 text-[9px] font-black rounded-full">
              {{ props.inventory.length }}
            </span>
          </button>

          <!-- Chronicles Timeline -->
          <button
            type="button"
            @click="emit('openChronicles')"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-indigo-400 hover:bg-indigo-500/10 text-slate-200 hover:text-indigo-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
            title="Open Chronicles Timeline"
          >
            <History class="w-4 h-4 text-indigo-400" />
            <span class="hidden sm:inline uppercase tracking-wider">Log</span>
          </button>

          <!-- Hints / Walkthrough -->
          <button
            type="button"
            @click="emit('openWalkthrough')"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-amber-400 hover:bg-amber-500/10 text-slate-200 hover:text-amber-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
            title="Adventure Hints & Walkthrough"
          >
            <Lightbulb class="w-4 h-4 text-amber-400" />
            <span class="hidden md:inline uppercase tracking-wider">Hints</span>
          </button>

          <!-- Toggle View Mode Button in Action Bar -->
          <button
            type="button"
            @click="emit('toggleViewMode')"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 border border-slate-700/80 hover:border-emerald-400/60 hover:bg-emerald-500/10 text-slate-300 hover:text-emerald-300 text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
            title="Switch to Classic View"
          >
            <LayoutGrid class="w-4 h-4 text-emerald-400" />
            <span class="hidden lg:inline uppercase tracking-wider">Classic</span>
          </button>
        </div>

        <!-- Prompt Suggestions Chips -->
        <div v-if="props.promptSuggestions?.length" class="flex items-center gap-2 overflow-x-auto no-scrollbar">
          <button
            v-for="(suggestion, sIdx) in props.promptSuggestions.slice(0, 3)"
            :key="sIdx"
            type="button"
            :disabled="!canSendInput"
            @click="handleSuggestionSelect(suggestion)"
            class="px-3 py-1 rounded-full bg-slate-900/80 border border-slate-700/60 hover:border-amber-400/50 hover:bg-amber-500/10 text-slate-300 hover:text-amber-200 text-xs font-semibold whitespace-nowrap transition-all active:scale-95 truncate max-w-[16rem] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {{ suggestion }}
          </button>
        </div>
      </div>

      <!-- 4B. USER TEXT INPUT ROW -->
      <div class="p-3 sm:p-4">
        <!-- Voice Recording Overlay -->
        <div
          v-if="isRecording || isTranscribing"
          class="mb-2 p-3 rounded-xl border flex items-center justify-between gap-3 text-xs font-bold shadow-lg animate-fade-in"
          :class="isRecording ? 'border-red-500/40 bg-red-950/60 text-red-200' : 'border-amber-500/40 bg-amber-950/60 text-amber-200'"
        >
          <div class="flex items-center gap-2">
            <span v-if="isRecording" class="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping"></span>
            <span v-else class="w-2.5 h-2.5 rounded-full border-2 border-amber-400 border-t-transparent animate-spin"></span>
            <span>{{ isRecording ? 'PTT Active: Recording Voice...' : 'Transcribing Speech...' }}</span>
          </div>
          <span class="text-[10px] uppercase font-mono text-slate-400">
            {{ isRecording ? "Release key or mouse to finish" : "Please wait..." }}
          </span>
        </div>

        <!-- Input Box & Actions -->
        <div class="relative flex items-center gap-2">
          <!-- Command auto-completion popup -->
          <CommandPopup
            v-if="showCommandPopup && filteredCommands.length"
            :commands="filteredCommands"
            :active-index="commandPopupIndex"
            @select="selectCommand"
            @close="showCommandPopup = false"
            @update:active-index="val => commandPopupIndex = val"
          />

          <!-- Push-To-Talk Mic Button -->
          <button
            type="button"
            :disabled="!canSendInput"
            @mousedown="handleMicButtonMousedown"
            class="flex items-center justify-center w-11 h-11 rounded-xl bg-slate-900 border border-slate-700/80 hover:border-amber-400/60 hover:bg-amber-500/10 text-slate-300 hover:text-amber-300 transition-all shadow-md active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed shrink-0 cursor-pointer"
            title="Push-To-Talk (Hold to speak)"
          >
            <Mic class="w-5 h-5" :class="{ 'text-red-400 animate-pulse': isRecording }" />
          </button>

          <!-- Main Input Field -->
          <div class="relative flex-1">
            <input
              ref="inputEl"
              v-model="inputText"
              type="text"
              :disabled="!canSendInput"
              :placeholder="isEvaluating ? (props.statusText || 'GM is deciding...') : (props.sheet?.agent_active ? 'AI Agent Mode is active.' : 'What do you do next? (TAB for /say, / for commands)')"
              class="w-full bg-slate-900/90 border-2 border-slate-700/70 focus:border-amber-400/80 focus:ring-2 focus:ring-amber-400/20 rounded-xl py-2.5 pl-4 pr-10 text-sm sm:text-base text-slate-100 placeholder-slate-500 outline-none transition-all disabled:opacity-50 font-medium"
              @keydown.tab.prevent.stop="insertSayCommand"
              @keydown="handleKeydown"
            />

            <!-- Send Button inside input -->
            <button
              type="button"
              :disabled="!canSendInput || !inputText.trim()"
              @click="handleSend"
              class="absolute right-1.5 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-md active:scale-90 cursor-pointer"
              title="Send Action (Enter)"
            >
              <SendHorizontal class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  </div>

  <!-- EXIT HOVER TOOLTIP -->
  <Teleport to="body">
    <Transition name="tooltip">
      <div 
        v-if="hoveredExit" 
        class="fixed z-[110] pointer-events-none transition-all duration-75"
        :style="{ left: (hoveredExitPos.x + 20) + 'px', top: (hoveredExitPos.y - 40) + 'px' }"
      >
        <div class="w-64 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-xl overflow-hidden flex flex-col p-4 animate-tooltip-in">
          <div class="flex items-center justify-between mb-2 pb-2 border-b border-slate-800">
            <span class="text-xs font-black uppercase text-slate-400 tracking-wider">Exit Connection</span>
            <span 
              class="text-[9px] px-2 py-0.5 rounded-full font-black uppercase tracking-tight"
              :class="hoveredExit.is_locked ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'"
            >
              {{ hoveredExit.is_locked ? 'Locked' : 'Unlocked' }}
            </span>
          </div>
          <p class="text-xs font-bold text-white mb-1 uppercase tracking-tight">{{ hoveredExit.label }}</p>
          <p class="text-[10px] font-bold text-slate-500 flex items-center gap-1.5" v-if="hoveredExit.target_scene_id">
            {{ props.currentSceneName || 'Current Location' }} 
            <i class="ra ra-plain-arrow text-slate-600"></i>
            <span class="text-slate-300">{{ hoveredExit.target_scene_id }}</span>
          </p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Tooltip Animations */
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.96) translateY(4px); }

.animate-tooltip-in {
  animation: toolTipIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(6px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.comic-title {
  font-family: 'Acme', sans-serif;
  letter-spacing: 0.05em;
}

.comic-narration-text,
.comic-bubble-text {
  font-family: 'Acme', sans-serif;
  letter-spacing: 0.02em;
}

:deep(.comic-voice-tag) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  padding: 0.125rem 0.4rem;
  margin: 0 0.3rem 0 0;
  border-radius: 0.375rem;
  font-size: 0.6875rem;
  font-weight: 800;
  line-height: 1.25;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  background: rgba(251, 191, 36, 0.15);
  color: rgb(252, 211, 77);
  border: 1px solid rgba(251, 191, 36, 0.3);
}

:deep(.comic-object-tag) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  padding: 0.125rem 0.35rem;
  margin: 0 0.2rem;
  border-radius: 0.375rem;
  font-family: monospace;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1.25;
  background: rgba(56, 189, 248, 0.15);
  color: rgb(56, 189, 248);
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.animate-fade-in {
  animation: comicPop 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.npc-stage-move,
.npc-stage-enter-active,
.npc-stage-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.npc-stage-enter-from,
.npc-stage-leave-to {
  opacity: 0;
  transform: scale(0.92);
}

@keyframes comicPop {
  0% {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
