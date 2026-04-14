/**
 * useGameSocket — Reactive REST-based composable for the TaleWeaver game loop.
 * 
 * Replaces the legacy WebSocket implementation with a robust REST architecture.
 * Manages chat history fetching, message posting, and state synchronization.
 */
import { ref, type Ref } from 'vue'
import type { ChatMessage, CharacterSheet } from '@/types'

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'game_over' | 'loading'

export interface UseGameSocket {
  messages: Ref<ChatMessage[]>
  sheet: Ref<CharacterSheet | null>
  mermaidData: Ref<string>
  currentSceneImage: Ref<string | null>
  entities: Ref<any[]>
  status: Ref<ConnectionStatus>
  gameOverReason: Ref<string>
  autoVisualize: Ref<boolean>
  connect: (gameId: string) => Promise<void>
  disconnect: () => void
  sendMessage: (content: string) => Promise<void>
  revealIllustration: (name: string, url: string) => void
}

export function useGameSocket(): UseGameSocket {
  const messages = ref<ChatMessage[]>([])
  const sheet = ref<CharacterSheet | null>(null)
  const mermaidData = ref<string>('')
  const currentSceneImage = ref<string | null>(null)
  const entities = ref<any[]>([])
  const status = ref<ConnectionStatus>('disconnected')
  const gameOverReason = ref('')
  const autoVisualize = ref(false)
  let currentGameId = ''

  function _pushMessage(role: ChatMessage['role'], content: string): void {
    messages.value.push({ role, content, timestamp: new Date() })
  }

  /**
   * Loads the current session state and history.
   * If history is empty, triggers the initial world description.
   */
  async function connect(gameId: string): Promise<void> {
    currentGameId = gameId
    status.value = 'loading'
    messages.value = []
    
    try {
      const res = await fetch(`http://localhost:8000/api/adventures/${gameId}/chat`)
      if (res.ok) {
        const data = await res.json()
        messages.value = data.messages.map((m: any) => ({ ...m, timestamp: new Date() }))
        sheet.value = data.sheet
        mermaidData.value = data.mermaid || ''
        entities.value = data.entities || []
        
        status.value = 'connected'

        // If no history, trigger prologue automatically
        if (messages.value.length === 0) {
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
  }

  /**
   * Posts a player message and processes the GM response.
   */
  async function sendMessage(content: string): Promise<void> {
    if (content) _pushMessage('user', content)
    
    const wasGameOver = status.value === 'game_over'
    if (wasGameOver) return

    status.value = 'connecting' 

    try {
      const res = await fetch(`http://localhost:8000/api/adventures/${currentGameId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          content,
          auto_visualize: autoVisualize.value
        })
      })

      if (res.ok) {
        const data = await res.json()
        
        // Append only new messages (if content was provided, we already pushed user msg)
        // Actually, the server returns all messages generated in this turn (Assistant + System)
        for (const m of data.messages) {
          _pushMessage(m.role as any, m.content)
        }
        
        sheet.value = data.sheet
        if (data.mermaid) mermaidData.value = data.mermaid
        if (data.image_url) currentSceneImage.value = data.image_url
        entities.value = data.entities || []
        
        if (data.game_over) {
          status.value = 'game_over'
          gameOverReason.value = data.game_over_reason
        } else {
          status.value = 'connected'
        }
      } else {
        _pushMessage('system', 'The Game Master is currently over capacity. Try once more.')
        status.value = 'connected'
      }
    } catch (err) {
      console.error('[Session] Chat error:', err)
      status.value = 'error'
    }
  }

  return {
    messages,
    sheet,
    mermaidData,
    currentSceneImage,
    entities,
    status,
    gameOverReason,
    autoVisualize,
    connect,
    disconnect,
    sendMessage,
    revealIllustration: (name: string, url: string) => {
      _pushMessage('system', `**Illustration Revealed:** ${name}\n\n![${name}](${url})`)
    }
  }
}
