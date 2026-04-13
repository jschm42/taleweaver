/**
 * useGameSocket — Reactive WebSocket composable for the TaleWeaver game loop.
 *
 * Manages the WebSocket lifecycle (connect / disconnect / reconnect),
 * parses incoming server messages, and exposes reactive state consumed
 * by the Chat Window and Character Sheet components.
 */
import { ref, type Ref } from 'vue'
import type { ChatMessage, CharacterSheet, WsIncoming } from '@/types'

/** Maximum number of reconnect attempts before giving up. */
const MAX_RECONNECT_ATTEMPTS = 5
/** Base delay (ms) for exponential back-off reconnect strategy. */
const RECONNECT_BASE_DELAY_MS = 1000

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error' | 'game_over'

export interface UseGameSocket {
  messages: Ref<ChatMessage[]>
  sheet: Ref<CharacterSheet | null>
  status: Ref<ConnectionStatus>
  gameOverReason: Ref<string>
  connect: (gameId: string) => void
  disconnect: () => void
  sendMessage: (content: string) => void
}

export function useGameSocket(): UseGameSocket {
  const messages = ref<ChatMessage[]>([])
  const sheet = ref<CharacterSheet | null>(null)
  const status = ref<ConnectionStatus>('disconnected')
  const gameOverReason = ref('')

  let socket: WebSocket | null = null
  let currentGameId = ''
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  // ── Internal helpers ────────────────────────────────────────────────────

  function _pushMessage(role: ChatMessage['role'], content: string): void {
    messages.value.push({ role, content, timestamp: new Date() })
  }

  function _handleMessage(raw: string): void {
    let parsed: WsIncoming
    try {
      parsed = JSON.parse(raw) as WsIncoming
    } catch {
      console.warn('[WS] Received non-JSON message:', raw)
      return
    }

    if ('type' in parsed) {
      if (parsed.type === 'sheet_update') {
        sheet.value = parsed.data
      } else if (parsed.type === 'game_over') {
        gameOverReason.value = parsed.reason
        status.value = 'game_over'
        _pushMessage('system', `☠ GAME OVER: ${parsed.reason}`)
      }
    } else if ('role' in parsed) {
      _pushMessage(parsed.role, parsed.content)
    }
  }

  function _scheduleReconnect(): void {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      status.value = 'error'
      _pushMessage('system', 'Connection lost. Please refresh the page.')
      return
    }
    const delay = RECONNECT_BASE_DELAY_MS * Math.pow(2, reconnectAttempts)
    reconnectAttempts++
    _pushMessage('system', `Connection lost. Reconnecting in ${delay / 1000}s… (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
    reconnectTimer = setTimeout(() => connect(currentGameId), delay)
  }

  // ── Public API ──────────────────────────────────────────────────────────

  /**
   * Opens a WebSocket connection for the given game session.
   * Clears previous messages and resets state on a fresh connect.
   */
  function connect(gameId: string): void {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close()
    }

    currentGameId = gameId
    status.value = 'connecting'

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    const url = `${protocol}://${host}/ws/adventure/${gameId}`

    socket = new WebSocket(url)

    socket.onopen = () => {
      status.value = 'connected'
      reconnectAttempts = 0
      _pushMessage('system', '⚔ Connected to the Game Master. Your adventure begins…')
    }

    socket.onmessage = (event: MessageEvent<string>) => {
      _handleMessage(event.data)
    }

    socket.onclose = (event) => {
      if (status.value === 'game_over') return // intentional end
      if (event.wasClean) {
        status.value = 'disconnected'
      } else {
        _scheduleReconnect()
      }
    }

    socket.onerror = () => {
      // onclose fires right after onerror, so reconnect logic lives there
      console.error('[WS] WebSocket error for game', gameId)
    }
  }

  /** Closes the WebSocket and cancels any pending reconnect timer. */
  function disconnect(): void {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (socket) {
      socket.close(1000, 'User navigated away')
      socket = null
    }
    status.value = 'disconnected'
  }

  /**
   * Sends a player message to the server and optimistically appends it
   * to the local message list so the UI feels instant.
   */
  function sendMessage(content: string): void {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      _pushMessage('system', 'Not connected. Please wait…')
      return
    }
    socket.send(JSON.stringify({ content }))
    _pushMessage('user', content)
  }

  return {
    messages,
    sheet,
    status,
    gameOverReason,
    connect,
    disconnect,
    sendMessage,
  }
}
