import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'
import {
  buildSafeRetryText,
  buildSegmentRequests,
  buildSpeechSegments,
  buildWholeTextSegment,
  isSpeakableSegment,
  normalizeDialoguePrefixes,
  resolveNpcVoice,
  type SegmentRequest,
} from '@/services/ttsText'
import {
  StreamingUnavailableError,
  playStreamElement,
  prepareStreamElement,
  releaseStreamElement,
} from '@/services/ttsStream'

type SpeakOptions = {
  sceneDescription?: string
  adventureId?: string
  sessionId?: string
  title?: string
  sceneName?: string
  tone?: string
  npcMetadata?: Record<string, any>
  interruptCurrent?: boolean
  style?: string
  /** Fallback voice (or NPC name resolvable via npcMetadata) for segments without a speaker voice. */
  voiceOverride?: string
}

type RequestContext = {
  scene_description?: string
  adventure_id?: string
  session_id?: string
  title?: string
  scene_name?: string
  tone?: string
  language?: string
}

type QueuedSegment = {
  request: SegmentRequest
  context: RequestContext
  /** Raw text of the speak() call this segment belongs to (used by UI highlighting). */
  displayText: string
  /** Normalized text of the speak() call (used for "is this bubble speaking" checks). */
  ttsText: string
}

/** A streaming <audio> element (ElevenLabs) or a whole clip (Gemini, fallback). */
type PlayableAudio = HTMLAudioElement | Blob
type PreparedSegment = { segment: QueuedSegment, audio: Promise<PlayableAudio | null> }

// Retrying with simplified text cannot help when the provider is overloaded or rate-limited.
const NON_RETRYABLE_STATUSES = new Set([429, 503, 504])
const BABEL_FISH_LANG_KEY = 'tw_bable_fish_lang'

function normalizeText(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (value === null || value === undefined) return ''
  return String(value).trim()
}

function normalizeOptionalText(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined
  if (typeof value === 'string') return value.trim() || undefined
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return String(value)
  }
  return undefined
}

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* storage unavailable (private mode) */
  }
}

function errorStatus(err: unknown): number | undefined {
  const status = (err as { status?: unknown } | null)?.status
  return typeof status === 'number' ? status : undefined
}

function inferAudioMimeType(url: string): string {
  const path = new URL(url).pathname.toLowerCase()
  if (path.endsWith('.wav')) return 'audio/wav'
  if (path.endsWith('.mp3')) return 'audio/mpeg'
  if (path.endsWith('.ogg')) return 'audio/ogg'
  return ''
}

function buildRequestContext(options: SpeakOptions): RequestContext {
  return {
    scene_description: normalizeOptionalText(options.sceneDescription),
    adventure_id: normalizeOptionalText(options.adventureId),
    session_id: normalizeOptionalText(options.sessionId),
    title: normalizeOptionalText(options.title),
    scene_name: normalizeOptionalText(options.sceneName),
    tone: normalizeOptionalText(options.tone),
    language: readStorage(BABEL_FISH_LANG_KEY) || undefined,
  }
}

class AudioService {
  private static readonly TTS_DEBUG_STORAGE_KEY = 'tts_debug_logs'
  private static readonly TTS_REQUEST_MIN_INTERVAL_MS = 450
  /** Segments generated ahead of playback, so short NPC lines follow each other without gaps. */
  private static readonly TTS_LOOKAHEAD = 3
  private static readonly TTS_STREAM_LOOKAHEAD = 1
  /** null = unknown until the first request; false = provider does not stream (Gemini). */
  private streamingAvailable: boolean | null = null
  private streamElements = new Set<HTMLAudioElement>()
  private autoSpeechChosenByPlayer = false
  private unlockListenerInstalled = false
  private currentAudio: HTMLAudioElement | null = null
  private currentObjectUrl: string | null = null
  private currentBufferSource: AudioBufferSourceNode | null = null
  private resolveCurrentPlayback: (() => void) | null = null
  private playbackToken = 0
  private lastTtsRequestAt = 0
  private audioContext: AudioContext | null = null
  private segmentQueue: QueuedSegment[] = []
  private pipeline: { token: number, promise: Promise<void> } | null = null

  public isUnlocked = ref(false)
  public isPlaying = ref(false)
  public isPaused = ref(false)
  private pauseWaiters: Array<() => void> = []
  public isGenerating = ref(false)
  public currentlyGeneratingContent = ref<string | null>(null)
  public lastError = ref<string | null>(null)
  public currentText = ref<string | null>(null)
  public autoSpeechEnabled = ref(false)
  public speechRate = ref<number>(parseFloat(readStorage('tts_speech_rate') ?? '1'))
  public ttsDebugEnabled = ref(readStorage(AudioService.TTS_DEBUG_STORAGE_KEY) === 'true')

  constructor() {
    watch(this.speechRate, (val) => writeStorage('tts_speech_rate', String(val)))
    watch(this.ttsDebugEnabled, (val) => writeStorage(AudioService.TTS_DEBUG_STORAGE_KEY, val ? 'true' : 'false'))
  }

  /** Call this once from any direct user-gesture handler (e.g. send button).
   *  Resumes the AudioContext so that subsequent async play() calls are allowed. */
  public unlock(): void {
    if (!this.audioContext) {
      this.audioContext = new AudioContext()
    }
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume().catch(() => {})
    }
    this.isUnlocked.value = true
  }

  private setPlaybackError(err: unknown): void {
    const rawMessage = err instanceof Error ? err.message : String(err)
    const normalized = rawMessage.toLowerCase()
    if (
      normalized.includes('notallowederror')
      || normalized.includes('user didn\'t interact')
      || normalized.includes('audiocontext was not allowed to start')
      || normalized.includes('suspended')
    ) {
      this.lastError.value = 'Audio blocked by browser autoplay policy. Click once in the game to unlock voice playback.'
      return
    }
    this.lastError.value = rawMessage
  }

  private getSafeSpeechRate(): number {
    const rate = this.speechRate.value
    if (!Number.isFinite(rate)) return 1
    return Math.min(2, Math.max(0.5, rate))
  }

  private logDebug(message: string, payload?: unknown): void {
    if (!this.ttsDebugEnabled.value) return
    if (payload === undefined) {
      console.info(message)
      return
    }
    console.info(message, payload)
  }

  /** Reserves the next request slot synchronously so parallel lookahead fetches stay spaced out. */
  private async waitForTtsRequestSlot(): Promise<void> {
    const now = Date.now()
    const slot = Math.max(now, this.lastTtsRequestAt + AudioService.TTS_REQUEST_MIN_INTERVAL_MS)
    this.lastTtsRequestAt = slot
    if (slot > now) {
      await new Promise<void>((resolve) => setTimeout(resolve, slot - now))
    }
  }

  private async fetchAudioBlob(audioUrl: string): Promise<Blob> {
    if (!audioUrl || !audioUrl.trim()) {
      throw new Error('Audio URL is empty')
    }

    const resolvedUrl = new URL(audioUrl, window.location.origin).toString()
    const response = await fetch(resolvedUrl, { cache: 'no-store' })
    if (!response.ok) {
      throw new Error(`Audio fetch failed (${response.status}) for ${resolvedUrl}`)
    }

    const blob = await response.blob()
    if (!blob.size) {
      throw new Error('Audio payload is empty')
    }

    const inferredMimeType = inferAudioMimeType(resolvedUrl)
    // Header-only WAV files are silent and typically indicate failed upstream synthesis.
    if (inferredMimeType === 'audio/wav' && blob.size <= 44) {
      throw new Error('Audio payload is header-only (silent WAV)')
    }
    if (blob.type || !inferredMimeType) {
      return blob
    }
    return new Blob([blob], { type: inferredMimeType })
  }

  private async requestAudio(text: string, context: RequestContext, voiceOverride?: string): Promise<{ blob: Blob, url: string }> {
    await this.waitForTtsRequestSlot()
    const { audio_url } = await api.generateTTS({ ...context, text, voice_override: voiceOverride })
    return { blob: await this.fetchAudioBlob(audio_url), url: audio_url }
  }

  private async fetchSegmentAudio(segment: QueuedSegment, token: number): Promise<Blob | null> {
    if (token !== this.playbackToken) return null
    const { request, context } = segment
    this.logDebug('TTS segment request', {
      speaker: request.speaker || null,
      voice: request.voiceOverride || null,
      textLength: request.requestText.length,
    })

    const retryText = buildSafeRetryText(request.requestText)
    try {
      return (await this.requestAudio(request.requestText, context, request.voiceOverride)).blob
    } catch (err) {
      const status = errorStatus(err)
      const isNonRetryable = status !== undefined && NON_RETRYABLE_STATUSES.has(status)
      const canRetry = !isNonRetryable && retryText !== request.requestText && isSpeakableSegment(retryText)
      if (isNonRetryable) this.setPlaybackError(err)
      if (!canRetry || token !== this.playbackToken) {
        // Do not abort the whole queue because one segment failed upstream.
        this.logDebug('TTS segment failed; skipping', { status, error: String(err) })
        return null
      }
    }

    try {
      // Retry without vocal tags / tone in case the provider blocked the original prompt.
      this.logDebug('TTS segment retry with safe text', { retryLength: retryText.length })
      return (await this.requestAudio(retryText, { ...context, tone: undefined }, request.voiceOverride)).blob
    } catch (retryErr) {
      this.logDebug('TTS segment retry failed; skipping', { error: String(retryErr) })
      return null
    }
  }

  private async playAudioBlobWithHtmlAudio(blob: Blob): Promise<void> {
    this.currentObjectUrl = URL.createObjectURL(blob)
    const audio = new Audio(this.currentObjectUrl)
    this.currentAudio = audio
    audio.playbackRate = this.getSafeSpeechRate()

    const releaseObjectUrl = () => {
      if (this.currentObjectUrl) {
        URL.revokeObjectURL(this.currentObjectUrl)
        this.currentObjectUrl = null
      }
      this.currentAudio = null
      this.resolveCurrentPlayback = null
    }

    await new Promise<void>((resolve, reject) => {
      // stop()/skip() pause the element, which never fires 'ended'; let them settle the promise instead.
      this.resolveCurrentPlayback = () => {
        releaseObjectUrl()
        resolve()
      }
      audio.onended = () => {
        releaseObjectUrl()
        resolve()
      }
      audio.onerror = () => {
        const errMsg = `Audio playback failed - code:${audio.error?.code ?? '?'} msg:${audio.error?.message ?? '?'}`
        console.error('[TTS]', errMsg)
        releaseObjectUrl()
        reject(new Error(errMsg))
      }
      audio.play().catch(reject)
    })
  }

  private async playAudioBufferWithWebAudio(context: AudioContext, blob: Blob): Promise<void> {
    const audioBuffer = await context.decodeAudioData(await blob.arrayBuffer())

    await new Promise<void>((resolve, reject) => {
      const source = context.createBufferSource()
      source.buffer = audioBuffer
      // WebAudio playbackRate also shifts pitch; keep WAV (Gemini PCM) within a
      // small speed-up range to avoid chipmunk-like artifacts.
      const isWav = (blob.type || '').toLowerCase().includes('wav')
      const requestedRate = this.getSafeSpeechRate()
      source.playbackRate.value = isWav ? Math.min(1.1, Math.max(1.0, requestedRate)) : requestedRate
      source.connect(context.destination)
      this.currentBufferSource = source
      source.onended = () => {
        this.currentBufferSource = null
        resolve()
      }
      try {
        source.start()
      } catch (err) {
        this.currentBufferSource = null
        reject(err)
      }
    })
  }

  private async playAudioBlob(blob: Blob): Promise<void> {
    const context = this.audioContext
    if (context?.state === 'running') {
      // Prefer Web Audio: avoids HTMLAudioElement autoplay restrictions and
      // resamples 24 kHz WAV correctly.
      try {
        await this.playAudioBufferWithWebAudio(context, blob)
        return
      } catch (err) {
        this.logDebug('WebAudio decode failed; falling back to HTMLAudio', { error: String(err), blobType: blob.type })
      }
    }
    await this.playAudioBlobWithHtmlAudio(blob)
  }

  private planSegments(normalizedText: string, options: SpeakOptions): QueuedSegment[] {
    const ttsText = normalizeDialoguePrefixes(normalizedText)
    const requests = buildSegmentRequests(buildSpeechSegments(ttsText), options.npcMetadata)
    const fallbackVoice = resolveNpcVoice(options.voiceOverride, options.npcMetadata) ?? options.voiceOverride
    const context = buildRequestContext(options)
    this.logDebug('TTS plan', { totalLength: ttsText.length, requests: requests.length })

    return requests.map(request => ({
      request: { ...request, voiceOverride: request.voiceOverride ?? fallbackVoice },
      context,
      displayText: normalizedText,
      ttsText,
    }))
  }

  private prepareNext(token: number): PreparedSegment | null {
    const segment = this.segmentQueue.shift()
    if (!segment) return null
    this.isGenerating.value = true
    this.currentlyGeneratingContent.value = segment.displayText
    return { segment, audio: this.prepareSegmentAudio(segment, token) }
  }

  /** A streaming <audio> element (ElevenLabs), else the whole clip as a blob (Gemini, fallback). */
  private async prepareSegmentAudio(segment: QueuedSegment, token: number): Promise<PlayableAudio | null> {
    if (this.streamingAvailable === false) return this.fetchSegmentAudio(segment, token)
    try {
      await this.waitForTtsRequestSlot()
      if (token !== this.playbackToken) return null
      const element = await prepareStreamElement(segment.request.requestText, segment.request.voiceOverride)
      this.streamingAvailable = true
      this.streamElements.add(element)
      return element
    } catch (err) {
      if (err instanceof StreamingUnavailableError) {
        this.streamingAvailable = false
      } else {
        this.logDebug('TTS stream could not start; using whole-clip request', { error: String(err) })
      }
      return this.fetchSegmentAudio(segment, token)
    }
  }

  private async playStream(element: HTMLAudioElement, segment: QueuedSegment, token: number): Promise<void> {
    this.currentAudio = element
    try {
      await playStreamElement(element, this.getSafeSpeechRate(), (settle) => {
        this.resolveCurrentPlayback = settle
      })
    } catch (err) {
      // A failed stream (e.g. rate limit) is retried once as a whole clip.
      this.logDebug('TTS stream playback failed; retrying as whole clip', { error: String(err) })
      const blob = token === this.playbackToken ? await this.fetchSegmentAudio(segment, token) : null
      if (blob && token === this.playbackToken) await this.playAudioBlob(blob)
    } finally {
      this.streamElements.delete(element)
      releaseStreamElement(element)
      if (this.currentAudio === element) this.currentAudio = null
      this.resolveCurrentPlayback = null
    }
  }

  private async playPrepared(playable: PlayableAudio, segment: QueuedSegment, token: number): Promise<void> {
    this.currentText.value = segment.ttsText
    if (playable instanceof HTMLAudioElement) {
      await this.playStream(playable, segment, token)
      return
    }
    await this.playAudioBlob(playable)
  }

  /** Starts generating queued segments until the lookahead window is full. Streams start
   *  playing almost at once, so one segment ahead is enough and keeps upstream concurrency low. */
  private fillLookahead(pending: PreparedSegment[], token: number): void {
    const lookahead = this.streamingAvailable === false ? AudioService.TTS_LOOKAHEAD : AudioService.TTS_STREAM_LOOKAHEAD
    while (pending.length < lookahead) {
      const next = this.prepareNext(token)
      if (!next) return
      pending.push(next)
    }
  }

  /** Plays queued segments in order while generating the next few in the background,
   *  including across separate speak()/enqueueSpeak() calls. */
  private async runPipeline(token: number): Promise<void> {
    this.isPlaying.value = true
    const pending: PreparedSegment[] = []
    try {
      this.fillLookahead(pending, token)
      let current = pending.shift()
      while (current) {
        const { segment, audio } = current
        const playable = await audio
        if (token !== this.playbackToken) return

        this.fillLookahead(pending, token)
        if (pending.length === 0) {
          this.isGenerating.value = false
          this.currentlyGeneratingContent.value = null
        }
        // Paused between lines: hold the next one until the player continues.
        await this.waitWhilePaused()
        if (token !== this.playbackToken) return
        if (playable) {
          await this.playPrepared(playable, segment, token).catch((err) => {
            this.logDebug('TTS segment playback failed; continuing', { error: String(err) })
          })
        }
        if (token !== this.playbackToken) return
        // Items enqueued while the last segment was playing.
        this.fillLookahead(pending, token)
        current = pending.shift()
      }
    } catch (err) {
      console.error('TTS Playback failed', err)
      this.setPlaybackError(err)
    } finally {
      if (token === this.playbackToken) {
        this.resetPlaybackState()
      }
    }
  }

  private ensurePipeline(): Promise<void> {
    const token = this.playbackToken
    if (this.pipeline?.token === token) return this.pipeline.promise

    const promise = this.runPipeline(token).finally(() => {
      if (this.pipeline?.promise === promise) this.pipeline = null
    })
    this.pipeline = { token, promise }
    return promise
  }

  private resetPlaybackState(): void {
    this.isPlaying.value = false
    this.isGenerating.value = false
    this.currentlyGeneratingContent.value = null
    this.currentText.value = null
  }

  /** Queue text behind whatever is currently playing (used by auto-speak). */
  public enqueueSpeak(text: unknown, options: SpeakOptions = {}): Promise<void> {
    return this.speak(text, { ...options, interruptCurrent: false })
  }

  async speak(text: unknown, options: SpeakOptions = {}): Promise<void> {
    const normalizedText = normalizeText(text)
    if (!normalizedText) return
    // Direct/manual speak interrupts current playback. Queued speak is appended.
    if (options.interruptCurrent ?? true) {
      this.stop()
    }
    this.lastError.value = null

    const segments = this.planSegments(normalizedText, options)
    if (segments.length === 0) {
      this.logDebug('TTS skipped: no speakable segments after sanitization')
      return
    }
    this.segmentQueue.push(...segments)
    return this.ensurePipeline()
  }

  /**
   * Generates a TTS audio file for the whole text and triggers a browser download.
   */
  public async download(text: unknown, options: SpeakOptions = {}): Promise<void> {
    const normalizedText = normalizeText(text)
    if (!normalizedText) return

    const [request] = buildSegmentRequests(buildWholeTextSegment(normalizeDialoguePrefixes(normalizedText)), options.npcMetadata)
    if (!request) return

    this.isGenerating.value = true
    this.currentlyGeneratingContent.value = normalizedText
    try {
      const voice = request.voiceOverride ?? resolveNpcVoice(options.voiceOverride, options.npcMetadata) ?? options.voiceOverride
      const { blob, url } = await this.requestAudio(request.requestText, buildRequestContext(options), voice)
      const extension = new URL(url, window.location.origin).pathname.split('.').pop() || 'wav'
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
      const safeTitle = (normalizeOptionalText(options.title) || 'adventure').replace(/[^a-z0-9]/gi, '_').toLowerCase()
      const safeScene = (normalizeOptionalText(options.sceneName) || 'scene').replace(/[^a-z0-9]/gi, '_').toLowerCase()

      const objectUrl = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = `taleweaver_${safeTitle}_${safeScene}_${timestamp}.${extension}`
      document.body.appendChild(anchor)
      anchor.click()
      setTimeout(() => {
        URL.revokeObjectURL(objectUrl)
        anchor.remove()
      }, 100)
    } catch (err) {
      console.error('[AudioService] Download failed', err)
      this.setPlaybackError(err)
    } finally {
      this.isGenerating.value = false
      this.currentlyGeneratingContent.value = null
    }
  }

  /** Pauses speech mid-line; the queue waits until resume(). */
  pause() {
    if (this.isPaused.value) return
    this.isPaused.value = true
    this.currentAudio?.pause()
    if (this.audioContext?.state === 'running') {
      this.audioContext.suspend().catch(() => {})
    }
  }

  resume() {
    if (!this.isPaused.value) return
    this.isPaused.value = false
    if (this.audioContext?.state === 'suspended') {
      this.audioContext.resume().catch(() => {})
    }
    this.currentAudio?.play().catch((err) => this.logDebug('TTS resume failed', { error: String(err) }))
    this.releasePauseWaiters()
  }

  togglePause() {
    if (this.isPaused.value) {
      this.resume()
      return
    }
    this.pause()
  }

  /** Ends the current line and continues with the next one. */
  skip() {
    this.resume()
    if (this.currentBufferSource) {
      try { this.currentBufferSource.stop() } catch { /* already stopped */ }
    }
    if (this.currentAudio) {
      this.currentAudio.pause()
      const settle = this.resolveCurrentPlayback
      this.resolveCurrentPlayback = null
      settle?.()
    }
  }

  private waitWhilePaused(): Promise<void> {
    if (!this.isPaused.value) return Promise.resolve()
    return new Promise<void>((resolve) => this.pauseWaiters.push(resolve))
  }

  private releasePauseWaiters() {
    const waiters = this.pauseWaiters
    this.pauseWaiters = []
    for (const release of waiters) release()
  }

  /** Forget whether the provider streams (call after the speech settings change). */
  public resetProviderCapabilities(): void {
    this.streamingAvailable = null
  }

  stop() {
    this.playbackToken += 1
    this.segmentQueue = []
    // A paused queue is dropped too; release it and leave the audio context usable.
    if (this.isPaused.value) {
      this.isPaused.value = false
      if (this.audioContext?.state === 'suspended') this.audioContext.resume().catch(() => {})
      this.releasePauseWaiters()
    }
    // Prepared streams keep downloading (and costing credits) unless released.
    for (const element of this.streamElements) releaseStreamElement(element)
    this.streamElements.clear()
    if (this.currentBufferSource) {
      try { this.currentBufferSource.stop() } catch { /* already stopped */ }
      this.currentBufferSource = null
    }
    if (this.currentAudio) {
      this.currentAudio.pause()
      this.currentAudio = null
    }
    if (this.currentObjectUrl) {
      URL.revokeObjectURL(this.currentObjectUrl)
      this.currentObjectUrl = null
    }
    const resolvePlayback = this.resolveCurrentPlayback
    this.resolveCurrentPlayback = null
    resolvePlayback?.()
    this.resetPlaybackState()
    this.lastError.value = null
  }

  toggleAutoSpeech() {
    // This is always called from a direct click — use it as an unlock opportunity.
    this.unlock()
    this.autoSpeechChosenByPlayer = true
    this.autoSpeechEnabled.value = !this.autoSpeechEnabled.value
  }

  /**
   * Admin default for auto-speech (on when TTS is configured and "start automatically" is set).
   * A player's own toggle wins for the rest of the page session.
   */
  applyAutoSpeechDefault(enabled: boolean) {
    if (this.autoSpeechChosenByPlayer) return
    this.autoSpeechEnabled.value = enabled
    if (enabled) this.unlockOnFirstInteraction()
  }

  /** Browsers only allow audio after a user gesture: unlock on the first click or key press. */
  private unlockOnFirstInteraction() {
    if (this.isUnlocked.value || this.unlockListenerInstalled || typeof document === 'undefined') return
    this.unlockListenerInstalled = true
    const unlockOnce = () => {
      document.removeEventListener('pointerdown', unlockOnce, true)
      document.removeEventListener('keydown', unlockOnce, true)
      this.unlock()
    }
    document.addEventListener('pointerdown', unlockOnce, true)
    document.addEventListener('keydown', unlockOnce, true)
  }
}

export const audioService = new AudioService()
