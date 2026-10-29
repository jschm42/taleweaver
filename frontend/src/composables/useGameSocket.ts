/**
 * useGameSocket — Reactive REST-based composable for the TaleWeaver game loop.
 * 
 * Replaces the legacy WebSocket implementation with a robust REST architecture.
 * Manages chat history fetching, message posting, and state synchronization.
 */
import { ref, watch, type Ref } from 'vue'
import { useNotifications } from '@/composables/useNotifications'
import { authState } from '@/store/auth'
import { api } from '@/composables/useApi'
import { registerEntityNames } from '@/utils/entityRefs'
import { carryOverMessageKeys, newMessageKey } from '@/composables/messageKeys'
import { isHiddenPlayerMessage } from '@/composables/silentCommands'
import type { ChatMessage, CharacterSheet, CombatState, PendingDialog } from '@/types'

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'game_over' | 'loading' | 'completed'

export interface TurnErrorState {
  message: string
  action: string
}

export interface AgentLogEntry {
  timestamp: string
  thought: string
  action: string
}

const AGENT_LOG_LIMIT = 50
const AGENT_IDLE_TIMEOUT_MS = 180_000

export interface AgentSettingsPatch {
  active?: boolean
  step_by_step?: boolean
  personality?: string
  custom_personality?: string
  allow_walkthrough?: boolean
  monkey_mode?: boolean
}

export interface UseGameSocket {
  messages: Ref<ChatMessage[]>
  sheet: Ref<CharacterSheet | null>
  mapData: Ref<any | null>
  nodes: Ref<Record<string, any>>
  npcMetadata: Ref<Record<string, any>>
  currentSceneImage: Ref<string | null>
  entities: Ref<any[]>
  combat: Ref<CombatState | null>
  status: Ref<ConnectionStatus>
  gameOverReason: Ref<string>
  autoVisualize: Ref<boolean>
  adventureImage: Ref<string | null>
  quests: Ref<any[]>
  awards: Ref<any[]>
  isCompleted: Ref<boolean>
  isLegacyFormat: Ref<boolean>
  language: Ref<string>
  statusText: Ref<string>
  statusNote: Ref<string>
  inputLocked: Ref<boolean>
  pendingTerminalEpilogue: Ref<boolean>
  pendingDialog: Ref<PendingDialog | null>
  promptSuggestions: Ref<string[]>
  worldMemories: Ref<any[]>
  worldRumors: Ref<any[]>
  debugLogs: Ref<{ timestamp: string, content: string }[]>
  inventoryGlow: Ref<boolean>
  mapGlow: Ref<boolean>
  questGlow: Ref<boolean>
  agentPaused: Ref<boolean>
  agentLog: Ref<AgentLogEntry[]>
  isCheckpointSaving: Ref<boolean>
  isSceneTransitioning: Ref<boolean>
  generatorProposal: Ref<any | null>
  generatorAutoStart: Ref<boolean>
  showGeneratorModal: Ref<boolean>
  turnError: Ref<TurnErrorState | null>
  openGeneratorModal: (proposal?: any) => void
  closeGeneratorModal: () => void
  connect: (gameId: string) => Promise<void>
  disconnect: () => void
  haltActiveOperations: () => void
  refreshSession: (includeMessages?: boolean) => Promise<void>
  sendMessage: (content: string, isRetry?: boolean) => Promise<void>
  retryLastAction: () => Promise<void>
  cancelTurnError: () => void
  emitSystemMessage: (content: string) => void
  runAgentTurn: () => Promise<boolean>
  updateAgentSettings: (patch: AgentSettingsPatch) => Promise<boolean>
  createTerminalEpilogue: () => Promise<void>
  revealIllustration: (name: string, url: string) => void
  deleteMessage: (messageId: string) => Promise<void>
}

let gameSocketSingleton: UseGameSocket | null = null

const ACTIVE_LANGUAGE_KEY = 'tw_bable_fish_lang'

function sessionLanguageKey(gameId: string): string {
  return `${ACTIVE_LANGUAGE_KEY}:${gameId}`
}

export function useGameSocket(): UseGameSocket {
  if (gameSocketSingleton) {
    return gameSocketSingleton
  }

  const BASE = '/api'
  const { addNotification } = useNotifications()
  const messages = ref<ChatMessage[]>([])
  const sheet = ref<CharacterSheet | null>(null)
  const mapData = ref<any | null>(null)
  const nodes = ref<Record<string, any>>({})
  const npcMetadata = ref<Record<string, any>>({})
  const currentSceneImage = ref<string | null>(null)
  const entities = ref<any[]>([])
  const combat = ref<CombatState | null>(null)
  const status = ref<ConnectionStatus>('disconnected')
  const gameOverReason = ref('')
  const autoVisualize = ref(false)
  const adventureImage = ref<string | null>(null)
  const quests = ref<any[]>([])
  const activeSequence = ref<any | null>(null)
  const awards = ref<any[]>([])
  const isCompleted = ref(false)
  const isLegacyFormat = ref(false)
  // Babel Fish translation target; chosen per session, empty (no translation) by default.
  const language = ref<string>('')
  const statusText = ref('')
  const statusNote = ref('')
  const inputLocked = ref(false)
  const pendingTerminalEpilogue = ref(false)
  const pendingDialog = ref<PendingDialog | null>(null)
  const promptSuggestions = ref<string[]>([])
  const worldMemories = ref<any[]>([])
  const worldRumors = ref<any[]>([])
  const debugLogs = ref<{ timestamp: string, content: string }[]>([])
  const inventoryGlow = ref(false)
  const mapGlow = ref(false)
  const questGlow = ref(false)
  let currentGameId = ''
  let syncTimer: number | null = null
  let activeAgentController: AbortController | null = null
  let activeChatController: AbortController | null = null
  const agentPaused = ref(false)
  const agentLog = ref<AgentLogEntry[]>([])
  const isCheckpointSaving = ref(false)
  const isSceneTransitioning = ref(false)
  let checkpointPulseTimer: number | null = null
  const generatorProposal = ref<any | null>(null)
  // True when the player already confirmed the blueprint in chat: the modal skips the form.
  const generatorAutoStart = ref(false)
  const showGeneratorModal = ref(false)
  const turnError = ref<TurnErrorState | null>(null)
  const lastUserAction = ref<string>('')

  function openGeneratorModal(proposal?: any): void {
    if (proposal) generatorProposal.value = proposal
    generatorAutoStart.value = false
    showGeneratorModal.value = true
  }

  function closeGeneratorModal(): void {
    showGeneratorModal.value = false
  }

  function triggerCheckpointPulse(): void {
    isCheckpointSaving.value = true
    if (checkpointPulseTimer !== null) {
      clearTimeout(checkpointPulseTimer)
    }
    checkpointPulseTimer = window.setTimeout(() => {
      isCheckpointSaving.value = false
      checkpointPulseTimer = null
    }, 1400)
  }

  watch(() => sheet.value?.agent_active, (active, wasActive) => {
    agentPaused.value = false
    if (active && !wasActive) {
      agentLog.value = []
    }
  })

  function normalizeUiActionInput(rawContent: string): string {
    const content = String(rawContent || '').trim()
    if (!content) return content

    const openMatch = content.match(/^\[?OPEN_CONTAINER\]?\s+(.+)$/i)
    if (openMatch && openMatch[1]) {
      return `/open ${openMatch[1].trim()}`
    }

    const readMatch = content.match(/^\[?OPEN_TEXT_LOG\]?\s+(.+)$/i)
    if (readMatch && readMatch[1]) {
      return `/read ${readMatch[1].trim()}`
    }

    return content
  }

  watch(language, (newLang) => {
    if (currentGameId) localStorage.setItem(sessionLanguageKey(currentGameId), newLang)
    // Mirror of the active session's choice, read by the speech service.
    localStorage.setItem(ACTIVE_LANGUAGE_KEY, newLang)
  })

  // Scene/sequence the session is currently in (from server snapshots). Live messages are
  // stamped with it so the story feed can group pages per scene before the history reloads.
  let currentSceneId: string | null = null
  let currentSequenceId: string | null = null

  function _pushMessage(
    role: ChatMessage['role'],
    content: string,
    itemIds?: string[],
    is_debug?: boolean,
    raw?: boolean
  ): void {
    messages.value.push({
      _key: newMessageKey(),
      role,
      content,
      timestamp: new Date(),
      itemIds,
      is_debug,
      raw,
      scene_id: currentSceneId,
      sequence_id: currentSequenceId,
    } as any)
  }

  function emitSystemMessage(content: string): void {
    const text = String(content || '').trim()
    if (!text) return
    _pushMessage('system', text)
  }

  function authHeaders(includeJson = false): Record<string, string> {
    const headers: Record<string, string> = {}
    if (includeJson) {
      headers['Content-Type'] = 'application/json'
    }
    if (authState.token) {
      headers['Authorization'] = `Bearer ${authState.token}`
    }
    return headers
  }

  async function fetchSessionSnapshot(gameId: string): Promise<any | null> {
    try {
      const res = await fetch(`${BASE}/adventures/${gameId}/chat`, {
        headers: authHeaders(false)
      })
      if (res.status === 401 && authState.isAuthenticated) {
        window.dispatchEvent(new CustomEvent('auth-unauthorized'))
        return null
      }
      if (!res.ok) return null
      return await res.json()
    } catch (err) {
      console.error('[Session] Snapshot load error:', err)
      return null
    }
  }

  async function refreshSession(includeMessages = false): Promise<void> {
    if (!currentGameId) return
    const data = await fetchSessionSnapshot(currentGameId)
    if (data) applySessionSnapshot(data, includeMessages)
  }

  // Names of all session entities (sent with the full chat snapshot only), for ##ID references.
  let entityNameMap: Record<string, string> = {}

  function applySessionSnapshot(data: any, updateMessages = true): void {
    if (!data) return

    if (updateMessages && Array.isArray(data.messages)) {
      const reloaded = data.messages
        .filter((m: any) => !(m.role === 'user' && isHiddenPlayerMessage(m.content)))
        .map((m: any) => ({ ...m, timestamp: new Date() }))
      messages.value = carryOverMessageKeys(messages.value, reloaded)
    }

    if (data.scene_id !== undefined) currentSceneId = data.scene_id || null
    if (data.sequence_id !== undefined) currentSequenceId = data.sequence_id || null
    if (data.sheet) sheet.value = data.sheet
    if (data.map_data) mapData.value = data.map_data
    if (data.nodes) nodes.value = data.nodes
    if (data.npc_metadata) npcMetadata.value = data.npc_metadata
    entities.value = data.entities || []
    if (data.entity_names) entityNameMap = data.entity_names
    registerEntityNames(entityNameMap, entities.value, sheet.value?.inventory)
    if (data.combat !== undefined) {
      combat.value = data.combat || null
    }
    if (data.image_url !== undefined) {
      currentSceneImage.value = data.image_url
    }
    if (data.adventure_image !== undefined) {
      adventureImage.value = data.adventure_image
    }
    if (data.quests !== undefined) {
      quests.value = data.quests || []
    }
    if (data.active_sequence !== undefined) {
      activeSequence.value = data.active_sequence || null
    }
    if (data.is_completed !== undefined) {
      isCompleted.value = !!data.is_completed
    }
    if (data.is_legacy_format !== undefined) {
      isLegacyFormat.value = !!data.is_legacy_format
    }
    if (data.input_locked !== undefined) {
      inputLocked.value = !!data.input_locked
    }
    if (data.pending_terminal_epilogue !== undefined) {
      pendingTerminalEpilogue.value = !!data.pending_terminal_epilogue
    }
    if (data.pending_dialog !== undefined) {
      pendingDialog.value = data.pending_dialog || null
    }
    if (data.awards !== undefined) {
      awards.value = data.awards || []
    }
    if (data.prompt_suggestions !== undefined) {
      promptSuggestions.value = Array.isArray(data.prompt_suggestions) ? data.prompt_suggestions : []
    }
    if (data.world_memories !== undefined) {
      worldMemories.value = Array.isArray(data.world_memories) ? data.world_memories : []
    }
    if (data.world_rumors !== undefined) {
      worldRumors.value = Array.isArray(data.world_rumors) ? data.world_rumors : []
    }

    if (data.status_note !== undefined) {
      statusNote.value = data.status_note || ''
      gameOverReason.value = data.status_note || ''
    }

    if (data.game_over) {
      status.value = 'game_over'
    } else if (data.game_completed) {
      status.value = inputLocked.value ? 'completed' : 'connected'
    } else if (status.value !== 'connecting') {
      status.value = 'connected'
    }
  }

  function startSyncTimer(): void {
    if (syncTimer !== null) {
      clearInterval(syncTimer)
    }

    syncTimer = window.setInterval(async () => {
      if (!currentGameId || status.value === 'disconnected' || status.value === 'connecting' || status.value === 'loading') {
        return
      }

      const snapshot = await fetchSessionSnapshot(currentGameId)
      if (currentGameId) {
        applySessionSnapshot(snapshot, false)
      }
    }, 5000)
  }

  function stopSyncTimer(): void {
    if (syncTimer !== null) {
      clearInterval(syncTimer)
      syncTimer = null
    }
  }

  /**
   * Loads the current session state and history.
   * If history is empty, triggers the initial world description.
   */
  async function connect(gameId: string): Promise<void> {
    currentGameId = gameId
    language.value = localStorage.getItem(sessionLanguageKey(gameId)) || ''
    localStorage.setItem(ACTIVE_LANGUAGE_KEY, language.value)
    status.value = 'loading'
    messages.value = []
    stopSyncTimer()
    
    try {
      const data = await fetchSessionSnapshot(gameId)
      if (data) {
        applySessionSnapshot(data)
        if ((status.value as any) !== 'game_over' || !inputLocked.value) {
          startSyncTimer()
        }

        // Trigger prologue for fresh sessions that only contain system notes (e.g. intro_text).
        const hasUserOrAssistantTurn = messages.value.some(
          (m) => m.role === 'user' || m.role === 'assistant'
        )
        if (!hasUserOrAssistantTurn) {
          await sendMessage('')
        }
      } else {
        status.value = 'error'
      }
    } catch (err) {
      console.error('[Session] Load error:', err)
      status.value = 'error'
    }
  }

  function disconnect(): void {
    currentGameId = ''
    status.value = 'disconnected'
    stopSyncTimer()
    if (checkpointPulseTimer !== null) {
      clearTimeout(checkpointPulseTimer)
      checkpointPulseTimer = null
    }
    isCheckpointSaving.value = false

    // Clear all session-specific states
    messages.value = []
    sheet.value = null
    mapData.value = null
    nodes.value = {}
    npcMetadata.value = {}
    currentSceneImage.value = null
    entities.value = []
    combat.value = null
    quests.value = []
    activeSequence.value = null
    awards.value = []
    adventureImage.value = null
    statusNote.value = ''
    gameOverReason.value = ''
    statusText.value = ''
    inputLocked.value = false
    pendingTerminalEpilogue.value = false
    pendingDialog.value = null
    promptSuggestions.value = []
    worldMemories.value = []
    worldRumors.value = []
    debugLogs.value = []
  }

  function haltActiveOperations(): void {
    if (activeChatController) {
      activeChatController.abort()
      activeChatController = null
    }
    if (activeAgentController) {
      activeAgentController.abort()
      activeAgentController = null
    }
    if (status.value === 'connecting' || status.value === 'loading') {
      status.value = 'connected'
      statusText.value = ''
    }
  }

  /**
   * Posts a player message and processes the GM response.
   */
  /** `/roll` is deterministic: it bypasses the turn pipeline and never interrupts a running turn. */
  async function runRollCommand(args: string): Promise<void> {
    if (!currentGameId) return
    try {
      const result = await api.rollDie(currentGameId, args)
      _pushMessage('system', result.content)
    } catch (err: any) {
      _pushMessage('system', err?.message || 'The die slipped off the table. Try again.')
    }
  }

  async function sendMessage(content: string, isRetry: boolean = false): Promise<void> {
    const normalizedContent = normalizeUiActionInput(content)
    const rollMatch = /^\/roll(?:\s+(.*))?$/i.exec(normalizedContent.trim())
    if (rollMatch) {
      await runRollCommand(rollMatch[1] ?? '')
      return
    }
    const isAgentOff = ['/playagent off', '/play-agent off'].includes(normalizedContent.trim().toLowerCase())
    const hadActiveChat = !!activeChatController

    turnError.value = null

    if (activeChatController) {
      activeChatController.abort()
      activeChatController = null
    }

    // A new player action should replace an in-flight turn immediately.
    // If we just aborted the prior request, clear transient busy state first.
    if (hadActiveChat && (status.value === 'connecting' || status.value === 'loading')) {
      status.value = 'connected'
      statusText.value = ''
    }

    if (isAgentOff) {
      if (sheet.value) {
        sheet.value.agent_active = false
      }
      if (activeAgentController) {
        activeAgentController.abort()
        activeAgentController = null
      }
      status.value = 'connected'
      statusText.value = ''
    }

    const isBusy = (status.value === 'connecting' || status.value === 'loading') && !isAgentOff
    const wasGameOver = status.value === 'game_over'
    if (!currentGameId) return
    if (isBusy) {
      addNotification('The Game Master is still processing your last action.', 'info')
      return
    }
    if (wasGameOver || inputLocked.value) {
      addNotification('This session is finished. Start a new session to continue playing.', 'info')
      return
    }

    const isSilent = isHiddenPlayerMessage(normalizedContent)

    if (normalizedContent && !isSilent) {
      lastUserAction.value = normalizedContent
      if (!isRetry) {
        _pushMessage('user', normalizedContent)
      } else {
        const lastMsg = messages.value[messages.value.length - 1]
        if (!lastMsg || lastMsg.role !== 'user' || lastMsg.content !== normalizedContent) {
          _pushMessage('user', normalizedContent)
        }
      }
    }
    const preTurnMessageCount = messages.value.length

    if (!isAgentOff) {
      status.value = 'connecting' 
      statusText.value = 'Considering...'
    }
    let receivedFinalEvent = false
    let receivedErrorEvent = false
    const controller = new AbortController()
    activeChatController = controller
    const timeoutId = window.setTimeout(() => controller.abort(), 90_000)

    try {
      const res = await fetch(`${BASE}/adventures/${currentGameId}/chat`, {
        method: 'POST',
        headers: authHeaders(true),
        signal: controller.signal,
        body: JSON.stringify({ 
          content: normalizedContent,
          auto_visualize: autoVisualize.value,
          language: language.value || undefined
        })
      })

      const turnId = res.headers.get('x-taleweaver-turn-id') || ''
      if (turnId) {
        debugLogs.value.push({
          timestamp: new Date().toLocaleTimeString(),
          content: `Turn-ID: ${turnId}`
        })
        if (sheet.value?.debug_mode) {
          _pushMessage('system', `[DEBUG] Turn-ID: ${turnId}`, undefined, true)
        }
      }

      if (res.status === 401 && authState.isAuthenticated) {
        window.dispatchEvent(new CustomEvent('auth-unauthorized'))
        status.value = 'error'
        statusText.value = ''
        return
      }

      if (!res.ok) {
        _pushMessage('system', 'The Game Master is currently over capacity. Try once more.')
        status.value = 'connected'
        return
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No reader available')

      const decoder = new TextDecoder()
      let buffer = ''

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.trim()) continue
          const lines = part.split('\n')
          let event = 'message'
          let data = null

          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) {
              try {
                data = JSON.parse(line.slice(5).trim())
              } catch (e) {
                console.error('Failed to parse SSE data', e)
              }
            }
          }

          if (!data) continue

          if (event === 'status') {
            statusText.value = data.content
            debugLogs.value.push({
              timestamp: new Date().toLocaleTimeString(),
              content: data.content
            })
          } else if (event === 'state') {
            // Early turn snapshot: refresh scene/entities before narration streams in.
            applySessionSnapshot(data, false)
          } else if (event === 'system' || event === 'assistant') {
            const role = data.role || (event === 'assistant' ? 'assistant' : 'system')
            // If the backend included a user_msg_id (debug command flow), attach it to the
            // optimistically-pushed user message so the delete button becomes available.
            if (data.user_msg_id) {
              for (let i = messages.value.length - 1; i >= 0; i--) {
                const m = messages.value[i] as any
                if (m.role === 'user' && !m.id) { m.id = data.user_msg_id; break }
              }
            }
            _pushMessage(role, data.content, undefined, data.is_debug, data.raw)
            // Attach the system message DB id (if provided) so it can be deleted.
            if (data.id) {
              const lastMsg = messages.value[messages.value.length - 1]
              if (lastMsg) (lastMsg as any).id = data.id
            }
          } else if (event === 'chunk') {
            let lastMsg = messages.value[messages.value.length - 1]
            // Silent commands (e.g. /traverse_exit) add no player message: never append this
            // turn's narration to the previous turn's GM message.
            const startedThisTurn = messages.value.length > preTurnMessageCount
            if (!lastMsg || lastMsg.role !== 'assistant' || (lastMsg as any).is_debug || !startedThisTurn) {
              _pushMessage('assistant', '')
              lastMsg = messages.value[messages.value.length - 1]
            }
            lastMsg.content += data.content
          } else if (event === 'final') {
            receivedFinalEvent = true
            applySessionSnapshot(data, false)
            if (data.game_over) {
              status.value = 'game_over'
              gameOverReason.value = data.game_over_reason || data.status_note || ''
              stopSyncTimer()
            } else if (data.game_completed) {
              gameOverReason.value = data.status_note || ''
              status.value = data.input_locked ? 'completed' : 'connected'
            } else {
              if (status.value === 'connecting' || status.value === 'loading') {
                status.value = 'connected'
                statusText.value = ''
              }
            }
          } else if (event === 'error') {
            receivedErrorEvent = true
            const detail = data.detail || 'An error occurred.'
            _pushMessage('system', detail)
            addNotification(detail, 'error')
            if (lastUserAction.value) {
              turnError.value = { message: detail, action: lastUserAction.value }
            }
            if (status.value === 'connecting' || status.value === 'loading') {
              status.value = 'connected'
              statusText.value = ''
            }
          } else if (event === 'scene_transition') {
            // The story feed starts a new page per scene; previous scenes stay browsable.
            isSceneTransitioning.value = true
            applySessionSnapshot(data, false)
          } else if (event === 'adventure_generator_proposal') {
            generatorProposal.value = data.request || data
            generatorAutoStart.value = data.auto_start === true
            window.setTimeout(() => {
              showGeneratorModal.value = true
            }, 600)
          } else if (event === 'checkpoint') {
            triggerCheckpointPulse()
          }
        }
      }

      if (receivedFinalEvent) {
        turnError.value = null
        lastUserAction.value = ''
        const snapshot = await fetchSessionSnapshot(currentGameId)
        if (snapshot) {
          // Reload the authoritative history (incl. scene/sequence per message).
          applySessionSnapshot(snapshot, true)
        }
      }

      // Fallback for truncated streams without explicit final/error event.
      if (!receivedFinalEvent && !receivedErrorEvent && (status.value === 'connecting' || isAgentOff)) {
        const snapshot = await fetchSessionSnapshot(currentGameId)
        if (snapshot) {
          applySessionSnapshot(snapshot, false)
          if (status.value === 'connecting') {
            status.value = 'connected'
          }
        } else {
          if (status.value === 'connecting') {
            status.value = 'connected'
          }
        }

        if (!isAgentOff) {
          const postTurnMessages = messages.value.slice(preTurnMessageCount)
          const hasTurnResponse = postTurnMessages.some(m => m.role === 'assistant' || m.role === 'system')
          if (!hasTurnResponse) {
            const fallbackMsg = 'The turn ended unexpectedly without a response. Please try your action again.'
            _pushMessage('system', fallbackMsg)
            addNotification(fallbackMsg, 'error')
            if (lastUserAction.value) {
              turnError.value = { message: fallbackMsg, action: lastUserAction.value }
            }
          }
        }

        statusText.value = ''
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Chat/deactivation fetch request was aborted.')
      } else {
        console.error('[Session] Chat error:', err)
        const errMsg = 'The Game Master did not respond in time. Please try again.'
        _pushMessage('system', errMsg)
        addNotification(errMsg, 'error')
        if (lastUserAction.value) {
          turnError.value = { message: errMsg, action: lastUserAction.value }
        }
        if (status.value === 'connecting' || status.value === 'loading') {
          status.value = 'connected'
          statusText.value = ''
        }
      }
    } finally {
      clearTimeout(timeoutId)
      isSceneTransitioning.value = false
      if (activeChatController === controller) {
        activeChatController = null
      }
      if ((status.value as any) === 'connecting' || (status.value as any) === 'loading') {
        status.value = 'connected'
        statusText.value = ''
      }
    }
  }

  async function retryLastAction(): Promise<void> {
    if (!turnError.value?.action) return
    const actionToRetry = turnError.value.action
    turnError.value = null
    await sendMessage(actionToRetry, true)
  }

  function cancelTurnError(): void {
    turnError.value = null
    if (status.value === 'connecting' || status.value === 'loading') {
      status.value = 'connected'
      statusText.value = ''
    }
  }

  /**
   * Updates play-agent settings for the current session and merges the result into the sheet.
   */
  async function updateAgentSettings(patch: AgentSettingsPatch): Promise<boolean> {
    if (!currentGameId) return false
    try {
      const res = await fetch(`${BASE}/adventures/${currentGameId}/agent/settings`, {
        method: 'PATCH',
        headers: authHeaders(true),
        body: JSON.stringify(patch)
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        addNotification(errData.detail || 'Failed to update Play-Agent settings.', 'error')
        return false
      }
      const agentState = await res.json()
      if (sheet.value) sheet.value = { ...sheet.value, ...agentState }
      return true
    } catch (err) {
      console.error('[Session] Agent settings error:', err)
      addNotification('Failed to update Play-Agent settings.', 'error')
      return false
    }
  }

  /**
   * Runs one play-agent turn. Resolves true when the turn completed normally.
   */
  async function runAgentTurn(): Promise<boolean> {
    const isBusy = status.value === 'connecting' || status.value === 'loading'
    if (!currentGameId) return false
    if (isBusy) return false

    status.value = 'connecting' 
    statusText.value = 'Agent is thinking...'
    let receivedFinalEvent = false
    const controller = new AbortController()
    activeAgentController = controller
    // Idle timeout: an agent turn (decision + full GM turn) can legitimately take long,
    // so only abort when the stream stays silent for too long.
    let timedOut = false
    let timeoutId = 0
    const resetIdleTimeout = () => {
      clearTimeout(timeoutId)
      timeoutId = window.setTimeout(() => {
        timedOut = true
        controller.abort()
      }, AGENT_IDLE_TIMEOUT_MS)
    }
    resetIdleTimeout()

    try {
      const res = await fetch(`${BASE}/adventures/${currentGameId}/agent/turn`, {
        method: 'POST',
        headers: authHeaders(false),
        signal: controller.signal
      })

      if (res.status === 401 && authState.isAuthenticated) {
        window.dispatchEvent(new CustomEvent('auth-unauthorized'))
        status.value = 'error'
        statusText.value = ''
        return false
      }

      if (!res.ok) {
        _pushMessage('system', 'The Agent encountered a connection error. Try once more.')
        status.value = 'connected'
        statusText.value = ''
        return false
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No reader available')

      const decoder = new TextDecoder()
      let buffer = ''

      while (!controller.signal.aborted) {
        const { value, done } = await reader.read()
        if (done) break
        resetIdleTimeout()

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.trim()) continue
          const lines = part.split('\n')
          let event = 'message'
          let data = null

          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) {
              try {
                data = JSON.parse(line.slice(5).trim())
              } catch (e) {
                console.error('Failed to parse SSE data', e)
              }
            }
          }

          if (!data) continue

          if (event === 'status') {
            statusText.value = data.content
            debugLogs.value.push({
              timestamp: new Date().toLocaleTimeString(),
              content: data.content
            })
          } else if (event === 'state') {
            // Early turn snapshot: refresh scene/entities before narration streams in.
            applySessionSnapshot(data, false)
          } else if (event === 'thought') {
            _pushMessage('thought' as any, data.content)
            agentLog.value = [...agentLog.value, { timestamp: new Date().toLocaleTimeString(), thought: data.content, action: '' }].slice(-AGENT_LOG_LIMIT)
          } else if (event === 'player_action') {
            _pushMessage('user', data.content)
            const lastEntry = agentLog.value[agentLog.value.length - 1]
            if (lastEntry && !lastEntry.action) lastEntry.action = data.content
          } else if (event === 'agent_state') {
            if (sheet.value) sheet.value = { ...sheet.value, ...data }
          } else if (event === 'system' || event === 'assistant') {
            const role = data.role || (event === 'assistant' ? 'assistant' : 'system')
            _pushMessage(role, data.content, undefined, data.is_debug, data.raw)
          } else if (event === 'chunk') {
            let lastMsg = messages.value[messages.value.length - 1]
            if (!lastMsg || lastMsg.role !== 'assistant' || (lastMsg as any).is_debug) {
              _pushMessage('assistant', '')
              lastMsg = messages.value[messages.value.length - 1]
            }
            lastMsg.content += data.content
          } else if (event === 'final') {
            receivedFinalEvent = true
            applySessionSnapshot(data, false)
            if (data.game_over) {
              status.value = 'game_over'
              gameOverReason.value = data.game_over_reason || data.status_note || ''
              stopSyncTimer()
            } else if (data.game_completed) {
              gameOverReason.value = data.status_note || ''
              status.value = data.input_locked ? 'completed' : 'connected'
            } else {
              status.value = 'connected'
              statusText.value = ''
            }
          } else if (event === 'error') {
            const detail = data.detail || 'An error occurred.'
            _pushMessage('system', detail)
            addNotification(detail, 'error')
            status.value = 'connected'
            statusText.value = ''
          } else if (event === 'checkpoint') {
            triggerCheckpointPulse()
          }
        }
      }

      if (receivedFinalEvent) {
        const snapshot = await fetchSessionSnapshot(currentGameId)
        if (snapshot) {
          applySessionSnapshot(snapshot, true)
        }
      }
      if (!receivedFinalEvent && (timedOut || !controller.signal.aborted)) {
        _pushMessage('system', timedOut ? 'The Agent did not respond in time.' : 'The Agent turn ended unexpectedly without a result.')
      }
      return receivedFinalEvent
    } catch (err: any) {
      if (err.name === 'AbortError' && timedOut) {
        _pushMessage('system', 'The Agent did not respond in time.')
      } else if (err.name === 'AbortError') {
        console.log('Agent request was aborted by user.')
      } else {
        console.error('[Session] Agent turn error:', err)
        _pushMessage('system', 'The Agent request failed. Please try again.')
        status.value = 'connected'
        statusText.value = ''
      }
      return false
    } finally {
      clearTimeout(timeoutId)
      activeAgentController = null
      if (((status.value as any) === 'connecting' || (status.value as any) === 'loading') && sheet.value?.agent_active) {
        status.value = 'connected'
        statusText.value = ''
      }
    }
  }

  async function createTerminalEpilogue(): Promise<void> {
    if (!currentGameId) return
    try {
      const res = await fetch(`${BASE}/adventures/${currentGameId}/terminal-epilogue`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({ language: language.value || undefined })
      })

      if (res.status === 401 && authState.isAuthenticated) {
        window.dispatchEvent(new CustomEvent('auth-unauthorized'))
        return
      }
      if (!res.ok) return

      const data = await res.json()
      if (data.content) {
        _pushMessage('assistant', data.content)
      }
      applySessionSnapshot(data, false)
    } catch (err) {
      console.error('[Session] Terminal epilogue error:', err)
    }
  }

  async function deleteMessage(messageId: string): Promise<void> {
    if (!currentGameId || !messageId) return
    try {
      const res = await fetch(`${BASE}/adventures/sessions/${currentGameId}/messages/${messageId}`, {
        method: 'DELETE',
        headers: authHeaders(false)
      })
      if (res.ok) {
        messages.value = messages.value.filter(m => (m as any).id !== messageId)
        addNotification('Message deleted.', 'success')
      } else {
        const errData = await res.json().catch(() => ({}))
        addNotification(errData.detail || 'Failed to delete message.', 'error')
      }
    } catch (err) {
      console.error('[Session] Delete message error:', err)
      addNotification('Failed to delete message.', 'error')
    }
  }

  gameSocketSingleton = {
    messages,
    sheet,
    mapData,
    nodes,
    npcMetadata,
    currentSceneImage,
    entities,
    combat,
    status,
    gameOverReason,
    autoVisualize,
    adventureImage,
    quests,
    activeSequence,
    awards,
    isCompleted,
    isLegacyFormat,
    language,
    statusText,
    statusNote,
    inputLocked,
    pendingTerminalEpilogue,
    pendingDialog,
    promptSuggestions,
    worldMemories,
    worldRumors,
    debugLogs,
    inventoryGlow,
    mapGlow,
    questGlow,
    agentPaused,
    agentLog,
    isCheckpointSaving,
    isSceneTransitioning,
    generatorProposal,
    generatorAutoStart,
    showGeneratorModal,
    turnError,
    openGeneratorModal,
    closeGeneratorModal,
    connect,
    disconnect,
    haltActiveOperations,
    refreshSession,
    sendMessage,
    retryLastAction,
    cancelTurnError,
    emitSystemMessage,
    runAgentTurn,
    updateAgentSettings,
    createTerminalEpilogue,
    deleteMessage,
    revealIllustration: (name: string, url: string) => {
      _pushMessage('system', `**Illustration Revealed:** ${name}\n\n![${name}](${url})`)
    }
  }

  return gameSocketSingleton
}
