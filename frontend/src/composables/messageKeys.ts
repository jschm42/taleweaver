import type { ChatMessage } from '@/types'

/**
 * Stable render keys for story-feed messages.
 *
 * Messages streamed during a turn have no database id yet; after the turn the history is
 * reloaded with ids. Keying the feed by id would then remount every message of the turn and
 * replay its entry animation (visible as flicker). A client key that survives the reload avoids it.
 */

let nextKey = 0

export function newMessageKey(): string {
  nextKey += 1
  return `msg-${nextKey}`
}

/** How far ahead an old message may lie (e.g. client-only debug lines missing from the reload). */
const MATCH_WINDOW = 4

const sameMessage = (a: ChatMessage, b: ChatMessage): boolean =>
  a.role === b.role && String(a.content || '').trim() === String(b.content || '').trim()

/**
 * Gives reloaded messages the key (and timestamp) of the message already shown for them, matching
 * in order by role and content; unmatched messages get a fresh key.
 */
export function carryOverMessageKeys(previous: ChatMessage[], reloaded: ChatMessage[]): ChatMessage[] {
  let cursor = 0
  return reloaded.map((msg) => {
    const window = previous.slice(cursor, cursor + MATCH_WINDOW)
    const offset = window.findIndex((old) => sameMessage(old, msg))
    if (offset < 0) return { ...msg, _key: newMessageKey() }
    const match = previous[cursor + offset]
    cursor += offset + 1
    return { ...msg, _key: match._key || newMessageKey(), timestamp: match.timestamp }
  })
}
