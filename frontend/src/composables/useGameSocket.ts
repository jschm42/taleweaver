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
  mermaidData: Ref<string>
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
  debugLogs: Ref<{ timestamp: string, content: string }[]>
  inventoryGlow: Ref<boolean>
  mapGlow: Ref<boolean>
  questGlow: Ref<boolean>
  connect: (gameId: string) => Promise<void>
  disconnect: () => void
  sendMessage: (content: string) => Promise<void>
  revealIllustration: (name: string, url: string) => void
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
  const mermaidData = ref<string>('')
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
  const debugLogs = ref<{ timestamp: string, content: string }[]>([])
  const inventoryGlow = ref(false)
  const mapGlow = ref(false)
  const questGlow = ref(false)
  let currentGameId = ''
  let syncTimer: number | null = null

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
    mermaidData.value = data.mermaid || ''
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
    if (data.awards !== undefined) {
      awards.value = data.awards || []
    }
  }

  function startSyncTimer(): void {
    if (syncTimer !== null) {
      clearInterval(syncTimer)
    }

    syncTimer = window.setInterval(async () => {
      if (!currentGameId || status.value === 'disconnected') {
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
        status.value = 'connected'
        startSyncTimer()

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
  }

  /**
   * Posts a player message and processes the GM response.
   */
  async function sendMessage(content: string): Promise<void> {
    const silentCommands = ['/take_direct', '/rule-pass', '/equip', '/unequip', '/consume']
    const isSilent = silentCommands.some(cmd => content.toLowerCase().startsWith(cmd))
    
    if (content && !isSilent) _pushMessage('user', content)
    
    const wasGameOver = status.value === 'game_over'
    if (wasGameOver) return

    status.value = 'connecting' 
    statusText.value = 'Considering...'

    try {
      const res = await fetch(`${BASE}/adventures/${currentGameId}/chat`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({ 
          content,
          auto_visualize: autoVisualize.value,
          language: language.value || undefined
        })
      })

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
            applySessionSnapshot(data, false)
            if (data.game_over) {
              status.value = 'game_over'
              gameOverReason.value = data.game_over_reason
              stopSyncTimer()
            } else if (data.game_completed) {
              status.value = 'completed'
              gameOverReason.value = data.status_note
              stopSyncTimer()
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
          }
        }
      }
    } catch (err) {
      console.error('[Session] Chat error:', err)
      status.value = 'error'
    }
  }

  gameSocketSingleton = {
    messages,
    sheet,
    mermaidData,
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
    debugLogs,
    inventoryGlow,
    mapGlow,
    questGlow,
    connect,
    disconnect,
    sendMessage,
    revealIllustration: (name: string, url: string) => {
      _pushMessage('system', `**Illustration Revealed:** ${name}\n\n![${name}](${url})`)
    }
  }

  return gameSocketSingleton
}

