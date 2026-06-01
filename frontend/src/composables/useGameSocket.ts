/**
 * useGameSocket — Reactive REST-based composable for the TaleWeaver game loop.
 * 
 * Replaces the legacy WebSocket implementation with a robust REST architecture.
 * Manages chat history fetching, message posting, and state synchronization.
 */
import { ref, watch, type Ref } from 'vue'
import { useNotifications } from '@/composables/useNotifications'
import { authState } from '@/store/auth'
import type { ChatMessage, CharacterSheet, CombatState } from '@/types'

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'game_over' | 'loading' | 'completed'

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
  language: Ref<string>
  statusText: Ref<string>
  statusNote: Ref<string>
  inputLocked: Ref<boolean>
  pendingTerminalEpilogue: Ref<boolean>
  promptSuggestions: Ref<string[]>
  debugLogs: Ref<{ timestamp: string, content: string }[]>
  inventoryGlow: Ref<boolean>
  mapGlow: Ref<boolean>
  questGlow: Ref<boolean>
  agentPaused: Ref<boolean>
  agentStepByStep: Ref<boolean>
  isCheckpointSaving: Ref<boolean>
  connect: (gameId: string) => Promise<void>
  disconnect: () => void
  haltActiveOperations: () => void
  sendMessage: (content: string) => Promise<void>
  emitSystemMessage: (content: string) => void
  runAgentTurn: () => Promise<void>
  createTerminalEpilogue: () => Promise<void>
  revealIllustration: (name: string, url: string) => void
  deleteMessage: (messageId: string) => Promise<void>
}

let gameSocketSingleton: UseGameSocket | null = null

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
  const awards = ref<any[]>([])
  const isCompleted = ref(false)
  const language = ref<string>(localStorage.getItem('tw_bable_fish_lang') || '')
  const statusText = ref('')
  const statusNote = ref('')
  const inputLocked = ref(false)
  const pendingTerminalEpilogue = ref(false)
  const promptSuggestions = ref<string[]>([])
  const debugLogs = ref<{ timestamp: string, content: string }[]>([])
  const inventoryGlow = ref(false)
  const mapGlow = ref(false)
  const questGlow = ref(false)
  let currentGameId = ''
  let syncTimer: number | null = null
  let activeAgentController: AbortController | null = null
  let activeChatController: AbortController | null = null
  const agentPaused = ref(false)
  const agentStepByStep = ref(localStorage.getItem('tw_agent_step_by_step') === 'true')
  const isCheckpointSaving = ref(false)
  let checkpointPulseTimer: number | null = null

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

  watch(agentStepByStep, (val) => {
    localStorage.setItem('tw_agent_step_by_step', String(val))
  })

  watch(() => sheet.value?.agent_active, (active) => {
    if (!active) {
      agentPaused.value = false
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

  // Sync with User Profile default if no local preference exists
  watch(() => authState.user?.default_language, (newDef) => {
    if (localStorage.getItem('tw_bable_fish_lang') === null && newDef) {
      language.value = newDef
    }
  }, { immediate: true })

  watch(language, (newLang) => {
    localStorage.setItem('tw_bable_fish_lang', newLang)
  })

  function _pushMessage(role: ChatMessage['role'], content: string, itemIds?: string[], is_debug?: boolean): void {
    messages.value.push({ role, content, timestamp: new Date(), itemIds, is_debug } as any)
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

  function applySessionSnapshot(data: any, updateMessages = true): void {
    if (!data) return

    if (updateMessages && Array.isArray(data.messages)) {
      messages.value = data.messages.map((m: any) => ({ ...m, timestamp: new Date() }))
    }

    if (data.sheet) sheet.value = data.sheet
    if (data.map_data) mapData.value = data.map_data
    if (data.nodes) nodes.value = data.nodes
    if (data.npc_metadata) npcMetadata.value = data.npc_metadata
    entities.value = data.entities || []
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
    if (data.is_completed !== undefined) {
      isCompleted.value = !!data.is_completed
    }
    if (data.input_locked !== undefined) {
      inputLocked.value = !!data.input_locked
    }
    if (data.pending_terminal_epilogue !== undefined) {
      pendingTerminalEpilogue.value = !!data.pending_terminal_epilogue
    }
    if (data.awards !== undefined) {
      awards.value = data.awards || []
    }
    if (data.prompt_suggestions !== undefined) {
      promptSuggestions.value = Array.isArray(data.prompt_suggestions) ? data.prompt_suggestions : []
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
    awards.value = []
    adventureImage.value = null
    statusNote.value = ''
    gameOverReason.value = ''
    statusText.value = ''
    inputLocked.value = false
    pendingTerminalEpilogue.value = false
    promptSuggestions.value = []
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
  async function sendMessage(content: string): Promise<void> {
    const normalizedContent = normalizeUiActionInput(content)
    const isAgentOff = normalizedContent.trim().toLowerCase() === '/agent off'
    const hadActiveChat = !!activeChatController

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

    const silentCommands = ['/take_direct', '/rule-pass', '/equip', '/unequip', '/consume', '/shuffle', '/suggest', '/suggestions']
    const isSilent = silentCommands.some(cmd => normalizedContent.toLowerCase().startsWith(cmd))

    if (normalizedContent && !isSilent) _pushMessage('user', normalizedContent)
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
          } else if (event === 'system') {
            const role = data.role || 'system'
            // If the backend included a user_msg_id (debug command flow), attach it to the
            // optimistically-pushed user message so the delete button becomes available.
            if (data.user_msg_id) {
              for (let i = messages.value.length - 1; i >= 0; i--) {
                const m = messages.value[i] as any
                if (m.role === 'user' && !m.id) { m.id = data.user_msg_id; break }
              }
            }
            _pushMessage(role, data.content, undefined, data.is_debug)
            // Attach the system message DB id (if provided) so it can be deleted.
            if (data.id) {
              const lastMsg = messages.value[messages.value.length - 1]
              if (lastMsg) (lastMsg as any).id = data.id
            }
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
            if (status.value === 'connecting' || status.value === 'loading') {
              status.value = 'connected'
              statusText.value = ''
            }
          } else if (event === 'checkpoint') {
            triggerCheckpointPulse()
          }
        }
      }

      if (receivedFinalEvent) {
        const snapshot = await fetchSessionSnapshot(currentGameId)
        if (snapshot && Array.isArray(snapshot.messages)) {
          messages.value = snapshot.messages.map((m: any) => ({ ...m, timestamp: new Date() }))
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
          }
        }

        statusText.value = ''
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Chat/deactivation fetch request was aborted.')
      } else {
        console.error('[Session] Chat error:', err)
        _pushMessage('system', 'The Game Master did not respond in time. Please try again.')
        if (status.value === 'connecting' || status.value === 'loading') {
          status.value = 'connected'
          statusText.value = ''
        }
      }
    } finally {
      clearTimeout(timeoutId)
      if (activeChatController === controller) {
        activeChatController = null
      }
      if ((status.value as any) === 'connecting' || (status.value as any) === 'loading') {
        status.value = 'connected'
        statusText.value = ''
      }
    }
  }

  async function runAgentTurn(): Promise<void> {
    const isBusy = status.value === 'connecting' || status.value === 'loading'
    if (!currentGameId) return
    if (isBusy) return

    status.value = 'connecting' 
    statusText.value = 'Agent is thinking...'
    let receivedFinalEvent = false
    const controller = new AbortController()
    activeAgentController = controller
    const timeoutId = window.setTimeout(() => controller.abort(), 90_000)

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
        return
      }

      if (!res.ok) {
        _pushMessage('system', 'The Agent encountered a connection error. Try once more.')
        status.value = 'connected'
        return
      }

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No reader available')

      const decoder = new TextDecoder()
      let buffer = ''

      while (!controller.signal.aborted) {
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
          } else if (event === 'thought') {
            _pushMessage('thought' as any, data.content)
          } else if (event === 'player_action') {
            _pushMessage('user', data.content)
          } else if (event === 'system') {
            const role = data.role || 'system'
            _pushMessage(role, data.content, undefined, data.is_debug)
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
        if (snapshot && Array.isArray(snapshot.messages)) {
          messages.value = snapshot.messages.map((m: any) => ({ ...m, timestamp: new Date() }))
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Agent request was aborted by user.')
      } else {
        console.error('[Session] Agent turn error:', err)
        _pushMessage('system', 'The Agent request failed. Please try again.')
        status.value = 'connected'
        statusText.value = ''
      }
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
    awards,
    isCompleted,
    language,
    statusText,
    statusNote,
    inputLocked,
    pendingTerminalEpilogue,
    promptSuggestions,
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
    sendMessage,
    emitSystemMessage,
    runAgentTurn,
    createTerminalEpilogue,
    deleteMessage,
    revealIllustration: (name: string, url: string) => {
      _pushMessage('system', `**Illustration Revealed:** ${name}\n\n![${name}](${url})`)
    }
  }

  return gameSocketSingleton
}
