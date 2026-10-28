/**
 * Classification helpers for system messages shown in the story feed and the System tab.
 */
import type { ChatMessage } from '@/types'

export type TurnError = { message: string; action: string } | null | undefined

type SystemMessage = Pick<ChatMessage, 'content'> & { is_debug?: boolean }

export function isDebugMessage(msg: SystemMessage | null | undefined): boolean {
  if (msg?.is_debug) {
    return true
  }
  const content = String(msg?.content || '').trim()
  return content.startsWith('[DEBUG') || content.startsWith('DEBUG:') || content.startsWith('--- DEBUG')
}

/** Failed-turn announcements stay inline in the story because they carry Retry/Cancel actions. */
export function isTurnErrorMessage(msg: SystemMessage | null | undefined, turnError: TurnError): boolean {
  return Boolean(turnError?.message && String(msg?.content || '').includes(turnError.message))
}

export type SystemNoteKind = 'error' | 'dice' | 'item' | 'vitals' | 'quest' | 'reward' | 'info'

// First match wins; English and German engine wording (word prefixes, so inflections match).
const NOTE_KIND_PATTERNS: [SystemNoteKind, RegExp][] = [
  // Failed adventure scripts (backend SCRIPT_ERROR_PREFIX), shown even without debug mode.
  ['error', /^\s*script error/i],
  ['dice', /\b(roll|dice|d20|skill check|saving throw|würfel|probe)/i],
  ['reward', /\b(xp\b|experience|award|achievement|erfahrung|auszeichnung)/i],
  ['quest', /\b(quest|objective|aufgabe)/i],
  ['vitals', /\b(hp\b|health|damage|heal|stamina|mana\b|schaden|geheilt|lebenspunkt|ausdauer)/i],
  ['item', /\b(item|inventory|added|received|picked up|obtained|gegenstand|inventar|erhalten|aufgenommen)/i],
]

/** Picks an icon category for a compact system note in the story feed. */
export function systemNoteKind(content: string): SystemNoteKind {
  const match = NOTE_KIND_PATTERNS.find(([, pattern]) => pattern.test(content))
  return match ? match[0] : 'info'
}

/** Removes inline debug trigger markers from regular system messages. */
export function cleanSystemContent(msg: SystemMessage | null | undefined): string {
  const content = String(msg?.content || '')
  if (isDebugMessage(msg)) {
    return content
  }
  return content
    .replace(/\s*\[DEBUG:\s*Trigger fired\][^\n]*/gi, '')
    .replace(/\s*\[DEBUG\][^\n]*/gi, '')
    .trim()
}
