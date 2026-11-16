/**
 * Browser speech (Web Speech API): the free TTS provider "browser".
 *
 * The browser reads the text itself with the voices of the operating system or browser
 * (Edge: Microsoft "Natural" voices, Chrome: Google voices, Firefox: system voices). No server,
 * no key, no audio file. audioService uses it instead of fetching audio when the admin chose
 * the provider "browser".
 *
 * - The narrator keeps one voice; each character gets its own voice, picked from its voice id
 *   (or name) so it stays the same for the whole session.
 * - The admin can choose the narrator voice and the voices characters use (by name, in the
 *   speech settings). A player's browser uses the chosen voices it has; without any of them
 *   it picks the best voices for the story's language itself.
 * - Vocal tags like [whispers] are removed: browser voices cannot render them.
 * - Text is read sentence by sentence, because Chrome stops long utterances after ~15 seconds.
 */

export const BROWSER_TTS_PROVIDER = 'browser'

/** Longest piece read in one utterance (Chrome cuts off long ones). */
const MAX_CHUNK_LENGTH = 220
/** How long to wait for the voice list, which some browsers load asynchronously. */
const VOICE_LOAD_TIMEOUT_MS = 1500
/** Voice names that mean a neural voice (Edge "Natural"), then other good online voices. */
const VOICE_QUALITY_PATTERNS = [/natural|neural/i, /online|google|premium|enhanced/i]

/** Voices chosen in the admin speech settings (`browser_voice`, `browser_character_voices`). */
export type BrowserVoicePreferences = {
  narrator?: string
  characters?: string[]
}

let preferences: BrowserVoicePreferences = {}

export function setBrowserVoicePreferences(value: BrowserVoicePreferences): void {
  preferences = {
    narrator: value.narrator?.trim() || '',
    characters: (value.characters ?? []).map(name => name.trim()).filter(Boolean),
  }
}

export type BrowserSpeakOptions = {
  /** Character voice id or name; empty for the narrator. */
  voiceKey?: string
  /** Playback speed (1 = normal). */
  rate?: number
  /** Language of the text, e.g. "de" or "en-US". */
  language?: string
}

export function isBrowserTtsSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window
}

/** Removes vocal tags ([excited], <sigh>) and markdown emphasis the voices would read aloud. */
export function cleanForBrowserSpeech(text: string): string {
  return text
    .replace(/\[[^\]\n]{1,40}\]/g, ' ')
    .replace(/<[^>\n]{1,40}>/g, ' ')
    .replace(/[*_#`~]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Sentences joined up to MAX_CHUNK_LENGTH; overlong sentences are cut at commas or spaces. */
export function splitIntoChunks(text: string, maxLength = MAX_CHUNK_LENGTH): string[] {
  const sentences = text.match(/[^.!?…]+[.!?…]+["'»”)]*\s*|[^.!?…]+$/g) ?? [text]
  const chunks: string[] = []
  let current = ''
  for (const sentence of sentences.map(s => s.trim()).filter(Boolean)) {
    for (const piece of cutLongSentence(sentence, maxLength)) {
      if (current && current.length + piece.length + 1 > maxLength) {
        chunks.push(current)
        current = piece
      } else {
        current = current ? `${current} ${piece}` : piece
      }
    }
  }
  if (current) chunks.push(current)
  return chunks
}

function cutLongSentence(sentence: string, maxLength: number): string[] {
  const pieces: string[] = []
  let rest = sentence
  while (rest.length > maxLength) {
    const window = rest.slice(0, maxLength)
    const cut = Math.max(window.lastIndexOf(', '), window.lastIndexOf(' '))
    const at = cut > maxLength / 3 ? cut + 1 : maxLength
    pieces.push(rest.slice(0, at).trim())
    rest = rest.slice(at).trim()
  }
  if (rest) pieces.push(rest)
  return pieces
}

function hashString(value: string): number {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0
  }
  return Math.abs(hash)
}

let voicesPromise: Promise<SpeechSynthesisVoice[]> | null = null

/** The browser's voices; waits briefly for browsers that load them asynchronously. */
export function loadBrowserVoices(): Promise<SpeechSynthesisVoice[]> {
  if (!isBrowserTtsSupported()) return Promise.resolve([])
  const ready = window.speechSynthesis.getVoices()
  if (ready.length) return Promise.resolve(ready)
  voicesPromise ??= new Promise((resolve) => {
    const finish = (): void => {
      window.speechSynthesis.removeEventListener('voiceschanged', finish)
      voicesPromise = null
      resolve(window.speechSynthesis.getVoices())
    }
    window.speechSynthesis.addEventListener('voiceschanged', finish)
    window.setTimeout(finish, VOICE_LOAD_TIMEOUT_MS)
  })
  return voicesPromise
}

/** Voices for the language (best first), else all voices. */
function voicesForLanguage(voices: SpeechSynthesisVoice[], language?: string): SpeechSynthesisVoice[] {
  const prefix = (language || document.documentElement.lang || navigator.language || 'en')
    .slice(0, 2)
    .toLowerCase()
  const matching = voices.filter(v => v.lang.toLowerCase().startsWith(prefix))
  const pool = matching.length ? matching : voices
  const rank = (v: SpeechSynthesisVoice): number => {
    const index = VOICE_QUALITY_PATTERNS.findIndex(pattern => pattern.test(v.name))
    return index === -1 ? VOICE_QUALITY_PATTERNS.length : index
  }
  return [...pool].sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
}

function byName(voices: SpeechSynthesisVoice[], names: string[]): SpeechSynthesisVoice[] {
  return names
    .map(name => voices.find(v => v.name === name))
    .filter((v): v is SpeechSynthesisVoice => Boolean(v))
}

/**
 * The narrator gets the chosen voice, else the best voice of the language. A character gets a
 * stable voice from its key: from the chosen character voices this browser has, else from the
 * language's voices, other than the narrator's whenever more than one is available.
 */
export function pickVoice(
  voices: SpeechSynthesisVoice[],
  voiceKey?: string,
  language?: string,
  chosen: BrowserVoicePreferences = preferences,
): SpeechSynthesisVoice | null {
  const pool = voicesForLanguage(voices, language)
  const narrator = byName(voices, chosen.narrator ? [chosen.narrator] : [])[0] ?? pool[0] ?? null
  if (!voiceKey) return narrator
  const preferred = byName(voices, chosen.characters ?? [])
  const candidates = preferred.length ? preferred : pool
  if (!candidates.length) return narrator
  const others = candidates.filter(v => v !== narrator)
  const characters = others.length ? others : candidates
  return characters[hashString(voiceKey.toLowerCase()) % characters.length]
}

/** Reads a sample with one voice (admin voice preview). */
export async function previewBrowserVoice(voiceName: string, text: string): Promise<void> {
  cancelBrowserSpeech()
  const voice = byName(await loadBrowserVoices(), [voiceName])[0] ?? null
  await speakChunk(cleanForBrowserSpeech(text), voice, 1)
}

let activeCancel: (() => void) | null = null

function speakChunk(text: string, voice: SpeechSynthesisVoice | null, rate: number): Promise<boolean> {
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text)
    if (voice) {
      utterance.voice = voice
      utterance.lang = voice.lang
    }
    utterance.rate = rate
    let settled = false
    const settle = (completed: boolean): void => {
      if (settled) return
      settled = true
      activeCancel = null
      resolve(completed)
    }
    activeCancel = () => settle(false)
    utterance.onend = () => settle(true)
    utterance.onerror = (event) => settle(event.error !== 'interrupted' && event.error !== 'canceled')
    window.speechSynthesis.speak(utterance)
  })
}

/**
 * Reads the text aloud; resolves when it was spoken or cancelled (cancelBrowserSpeech).
 * Throws when the browser has no speech synthesis.
 */
export async function speakWithBrowser(text: string, options: BrowserSpeakOptions = {}): Promise<void> {
  if (!isBrowserTtsSupported()) {
    throw new Error('This browser has no built-in speech. Use Edge, Chrome or Firefox, or ask the admin for another TTS provider.')
  }
  const chunks = splitIntoChunks(cleanForBrowserSpeech(text))
  if (!chunks.length) return
  const voice = pickVoice(await loadBrowserVoices(), options.voiceKey, options.language)
  const rate = Math.min(2, Math.max(0.5, options.rate ?? 1))
  for (const chunk of chunks) {
    const completed = await speakChunk(chunk, voice, rate)
    if (!completed) return
  }
}

/** Stops speaking and drops what the browser still had queued. */
export function cancelBrowserSpeech(): void {
  if (!isBrowserTtsSupported()) return
  const cancel = activeCancel
  activeCancel = null
  window.speechSynthesis.cancel()
  cancel?.()
}

export function pauseBrowserSpeech(): void {
  if (isBrowserTtsSupported()) window.speechSynthesis.pause()
}

export function resumeBrowserSpeech(): void {
  if (isBrowserTtsSupported()) window.speechSynthesis.resume()
}
