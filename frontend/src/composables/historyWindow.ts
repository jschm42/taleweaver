import type { ChatMessage } from '@/types'
import { carryOverMessageKeys, newMessageKey } from '@/composables/messageKeys'
import { isHiddenPlayerMessage } from '@/composables/silentCommands'

/**
 * The story feed holds a window of the chat history: the newest page from the session snapshot,
 * plus older pages loaded while the reader scrolls up (GET /chat/history).
 */

/** Messages per page: the snapshot's newest window and each older page. */
export const HISTORY_PAGE_SIZE = 150

/** Server messages as the feed shows them (silent player commands hidden). */
export function visibleServerMessages(raw: any[]): ChatMessage[] {
  return raw
    .filter((m: any) => !(m.role === 'user' && isHiddenPlayerMessage(m.content)))
    .map((m: any) => ({ ...m, timestamp: new Date() }))
}

/**
 * Applies a reloaded newest window to the shown messages.
 *
 * Older pages loaded before stay in front of it as long as the window still connects to them
 * (its first message is among the shown ones); otherwise the window replaces everything.
 * Returns the merged list and whether older pages were kept.
 */
export function mergeNewestWindow(
  shown: ChatMessage[],
  reloaded: ChatMessage[]
): { messages: ChatMessage[]; keptOlder: boolean } {
  const firstId = reloaded[0]?.id
  const joinAt = firstId ? shown.findIndex((m) => m.id === firstId) : -1
  if (joinAt <= 0) {
    return { messages: carryOverMessageKeys(shown, reloaded), keptOlder: false }
  }
  const older = shown.slice(0, joinAt)
  return {
    messages: [...older, ...carryOverMessageKeys(shown.slice(joinAt), reloaded)],
    keptOlder: true,
  }
}

/** An older page placed in front of the shown messages (render keys of its own). */
export function prependOlderPage(shown: ChatMessage[], older: ChatMessage[]): ChatMessage[] {
  const known = new Set(shown.map((m) => m.id).filter(Boolean))
  const fresh = older.filter((m) => !m.id || !known.has(m.id)).map((m) => ({ ...m, _key: newMessageKey() }))
  return [...fresh, ...shown]
}
