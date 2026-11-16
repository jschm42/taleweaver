/**
 * Whether the text before a colon can be a speaker's name ("Tina: ...").
 *
 * A name needs at least one letter, and a colon between two digits belongs to a time:
 * "16:30 sharp: Kevin is here" or "The clock struck 18:00 in ..." are narration, not a
 * character called "16" or "The clock struck 18".
 */
const HAS_LETTER = /\p{L}/u

export function canBeSpeakerName(value: string, textAfterColon = ''): boolean {
  const name = String(value || '').trim()
  if (!HAS_LETTER.test(name)) return false
  return !(/\d$/.test(name) && /^\d/.test(String(textAfterColon || '').trim()))
}
