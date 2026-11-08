/**
 * Track IDs of the audio library: letters, digits and underscores, at most 30 characters,
 * upper case (e.g. CRYPT_THEME). Mirrors backend/engine/audio/audio_library.py, which checks
 * them again and keeps them unique.
 */
export const TRACK_ID_MAX = 30
const TRACK_ID_RE = /^[A-Z0-9_]{1,30}$/

/** "crypt theme.mp3" -> "CRYPT_THEME" (unique among ``taken``: CRYPT_THEME_2, ...). */
export function suggestTrackId(text: string, taken: Iterable<string> = []): string {
  const used = new Set(taken)
  const plain = text.normalize('NFKD').replace(/[̀-ͯ]/g, '')
  const base = plain.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '').toUpperCase().slice(0, TRACK_ID_MAX) || 'TRACK'
  let candidate = base
  for (let n = 2; used.has(candidate); n += 1) {
    const suffix = `_${n}`
    candidate = base.slice(0, TRACK_ID_MAX - suffix.length).replace(/_+$/, '') + suffix
  }
  return candidate
}

/** What the input field keeps while typing: upper case, only allowed characters. */
export function cleanTrackIdInput(value: string): string {
  return value.toUpperCase().replace(/[^A-Z0-9_]/g, '').slice(0, TRACK_ID_MAX)
}

/** Error text for an id, or '' when it is fine. */
export function trackIdError(value: string, taken: Iterable<string> = []): string {
  if (!TRACK_ID_RE.test(value)) return 'Use letters, digits and underscores (max. 30).'
  if (new Set(taken).has(value)) return 'This ID is already used in this adventure.'
  return ''
}
