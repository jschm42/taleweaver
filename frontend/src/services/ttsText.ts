/**
 * Pure text helpers that turn assistant markdown into TTS segment requests.
 */

export type SpeechSegment = { speaker?: string, text: string }
export type SegmentRequest = { requestText: string, voiceOverride?: string, speaker?: string }

const SPEAKER_PATTERN = /^(?:\*\*([^*:\n]+)\*\*|([^:\n]+)):\s*([\s\S]*)$/
const NON_SPEAKER_LABELS = new Set(['note', 'warning', 'caution', 'info', 'location', 'status', 'time', 'goal', 'quest', 'tip', 'hinweis'])
// Hard cap per request: ElevenLabs v3 accepts 5,000 characters; normal lines are far shorter.
const MAX_REQUEST_CHARS = 2500

export function normalizeDialoguePrefixes(text: string): string {
  // Convert markdown-style speaker labels to plain labels for more reliable
  // downstream TTS interpretation.
  const normalizedPrefixes = text.replace(/^\*\*([^*:\n]+)\*\*:\s*/gm, '$1: ')

  // Remove markdown bold markers from the whole prompt so raw "**" never
  // reaches the TTS model.
  return normalizedPrefixes
    .replace(/\*\*([^*\n]+)\*\*/g, '$1')
    .replace(/\*\*/g, '')
}

function looksLikeSpeakerLabel(value: string): boolean {
  const normalized = String(value || '').trim()
  if (!normalized || normalized.length > 50) return false
  const words = normalized.split(/\s+/).filter(Boolean)
  if (words.length > 6) return false
  return /^[\p{L}\p{N}][\p{L}\p{N} '\-.,()]*$/u.test(normalized)
}

function parseParagraph(paragraph: string): SpeechSegment {
  const match = paragraph.match(SPEAKER_PATTERN)
  if (!match) return { text: paragraph }
  const rawSpeaker = (match[1] || match[2] || '').trim()
  const spokenText = (match[3] || '').trim()
  if (!spokenText || NON_SPEAKER_LABELS.has(rawSpeaker.toLowerCase()) || !looksLikeSpeakerLabel(rawSpeaker)) {
    return { text: paragraph }
  }
  return { speaker: rawSpeaker, text: spokenText }
}

function splitIntoSpeechSegments(text: string): SpeechSegment[] {
  const normalized = text.replace(/\r\n?/g, '\n').trim()
  if (!normalized) return []

  return normalized
    .split(/\n\s*\n/)
    .map(p => p.trim())
    .filter(Boolean)
    .map(parseParagraph)
}

function capSegmentText(text: string, maxChars = MAX_REQUEST_CHARS): string[] {
  const normalized = text.trim()
  if (!normalized) return []
  if (normalized.length <= maxChars) return [normalized]

  const sentenceParts = normalized.split(/(?<=[.!?])\s+/)
  const chunks: string[] = []
  let current = ''

  for (const part of sentenceParts) {
    const candidate = current ? `${current} ${part}` : part
    if (candidate.length <= maxChars) {
      current = candidate
      continue
    }

    if (current) chunks.push(current)

    if (part.length <= maxChars) {
      current = part
      continue
    }
    for (let i = 0; i < part.length; i += maxChars) {
      chunks.push(part.slice(i, i + maxChars))
    }
    current = ''
  }

  if (current) chunks.push(current)
  return chunks
}

/**
 * One segment per paragraph, each with its speaker (needed for per-character voices). Only
 * paragraphs over the provider limit are split further, at sentence ends.
 */
export function buildSpeechSegments(text: string): SpeechSegment[] {
  return splitIntoSpeechSegments(text)
    .flatMap(seg => capSegmentText(seg.text).map(part => ({ speaker: seg.speaker, text: part })))
}

/** The whole text as one segment (downloads produce a single file). */
export function buildWholeTextSegment(text: string): SpeechSegment[] {
  const normalized = text.replace(/\r\n?/g, '\n').trim()
  return normalized ? [{ text: normalized }] : []
}

function sanitizeSegmentForTts(text: string): string {
  return String(text || '')
    // Keep image alt text but drop URLs from markdown images.
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    // Drop standalone portrait marker lines that should never be spoken.
    .replace(/^\s*[^\n]*-portrait\s*$/gim, '')
    // Normalize excessive whitespace after removals.
    .replace(/\s{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function isSpeakableSegment(text: string): boolean {
  const trimmed = String(text || '').trim()
  if (!trimmed) return false
  // Skip punctuation-only fragments such as a lone '[' that can trigger
  // provider moderation/validation failures while conveying no speech.
  return /[\p{L}\p{N}]/u.test(trimmed)
}

export function buildSafeRetryText(text: string): string {
  return String(text || '')
    // Drop inline direction tags for retry if provider blocks the original.
    .replace(/\[[^\]\n]{1,120}\]/g, ' ')
    // Keep retry payload compatible with provider speaker parsing quirks.
    .replace(/(\d{1,2}):(\d{2})/g, '$1__TW_TIME_COLON__$2')
    .replace(/:\s+/g, ', ')
    .replace(/__TW_TIME_COLON__/g, ':')
    // Remove repeated punctuation noise that may be flagged.
    .replace(/[!?.]{4,}/g, '...')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

export function resolveNpcVoice(speaker: string | undefined, npcMetadata: Record<string, any> | undefined): string | undefined {
  if (!speaker || !npcMetadata) return undefined

  const exact = npcMetadata[speaker]
  if (exact?.voice) return String(exact.voice)

  const loweredSpeaker = speaker.toLowerCase()
  for (const [key, value] of Object.entries(npcMetadata)) {
    if (key.toLowerCase() === loweredSpeaker && value && typeof value === 'object' && value.voice) {
      return String(value.voice)
    }
  }

  return undefined
}

export function buildSegmentRequests(
  segments: SpeechSegment[],
  npcMetadata: Record<string, any> | undefined,
): SegmentRequest[] {
  const requests: SegmentRequest[] = []

  for (const segment of segments) {
    const speaker = segment.speaker?.trim() || undefined
    // Single-voice generation: keep only spoken content to avoid reading
    // speaker names out loud.
    const requestText = sanitizeSegmentForTts(segment.text)
    if (!isSpeakableSegment(requestText)) continue
    requests.push({ requestText, voiceOverride: resolveNpcVoice(speaker, npcMetadata), speaker })
  }

  return requests
}
