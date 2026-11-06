/**
 * Picks the Game Master messages auto-speech still owes the player.
 *
 * One player action can produce several GM messages in a row (script lines, a narration, then
 * a chained reaction turn). All of them belong to the current turn: everything after the last
 * player message. Reading only the newest one skips the rest, e.g. when a teleport's travel
 * overlay interrupts speech while further messages arrive.
 */

export interface AutoSpeakMessage {
  role?: string
  content?: string
  is_debug?: boolean
}

export interface IndexedMessage<T> {
  index: number
  message: T
}

/** Speakable GM messages after the latest player message, oldest first. */
export function currentTurnAssistantMessages<T extends AutoSpeakMessage>(messages: T[]): IndexedMessage<T>[] {
  const found: IndexedMessage<T>[] = []
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const candidate = messages[index]
    if (!candidate) continue
    if (candidate.role === 'user') break
    if (candidate.role !== 'assistant' || candidate.is_debug) continue
    if (!String(candidate.content || '').trim()) continue
    found.push({ index, message: candidate })
  }
  return found.reverse()
}

/** The current turn's GM messages that were not spoken yet, oldest first. */
export function unspokenTurnMessages<T extends AutoSpeakMessage>(
  messages: T[],
  isSpoken: (message: T, index: number) => boolean,
): IndexedMessage<T>[] {
  return currentTurnAssistantMessages(messages).filter(({ message, index }) => !isSpoken(message, index))
}
