import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'

type SpeakOptions = {
  sceneDescription?: string
  adventureId?: string
  sessionId?: string
  title?: string
  sceneName?: string
  tone?: string
  npcMetadata?: Record<string, any>
  segmentedVoices?: boolean
  interruptCurrent?: boolean
  useTextChunking?: boolean
}

class AudioService {
  private static readonly TTS_DEBUG_STORAGE_KEY = 'tts_debug_logs'
  private static readonly TTS_REQUEST_MIN_INTERVAL_MS = 450
  private currentAudio: HTMLAudioElement | null = null
  private currentObjectUrl: string | null = null
  private currentBufferSource: AudioBufferSourceNode | null = null
  private playbackToken = 0
  private lastTtsRequestAt = 0
  private audioContext: AudioContext | null = null
  private speakQueueTail: Promise<void> = Promise.resolve()
  private speakQueueGeneration = 0

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
  public isUnlocked = ref(false)
  public isPlaying = ref(false)
  public isGenerating = ref(false)
  public currentlyGeneratingContent = ref<string | null>(null)
  public lastError = ref<string | null>(null)
  public currentText = ref<string | null>(null)
  public autoSpeechEnabled = ref(false)
  public useTextChunking = ref(localStorage.getItem('tts_use_chunking') !== 'false')
  public speechRate = ref<number>(parseFloat(localStorage.getItem('tts_speech_rate') ?? '1'))
  public ttsDebugEnabled = ref(localStorage.getItem(AudioService.TTS_DEBUG_STORAGE_KEY) === 'true')

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

  private normalizeDialoguePrefixes(text: string): string {
    // Convert markdown-style speaker labels to plain labels for more reliable
    // downstream TTS interpretation.
    const normalizedPrefixes = text.replace(/^\*\*([^*:\n]+)\*\*:\s*/gm, '$1: ')

    // Remove markdown bold markers from the whole prompt so raw "**" never
    // reaches the TTS model.
    return normalizedPrefixes
      .replace(/\*\*([^*\n]+)\*\*/g, '$1')
      .replace(/\*\*/g, '')
  }

  private getSafeSpeechRate(): number {
    const rate = this.speechRate.value
    if (!Number.isFinite(rate)) return 1
    return Math.min(2, Math.max(0.5, rate))
  }

  private splitIntoSpeechSegments(text: string, useChunking = true): Array<{ speaker?: string, text: string }> {
    const normalized = text.replace(/\r\n?/g, '\n').trim()
    if (!normalized) return []

    if (!useChunking) {
      this.logDebug('splitIntoSpeechSegments (No Chunking)', { textLength: normalized.length })
      return [{ text: normalized }]
    }

    // Default chunked behavior (split by paragraphs)
    const paragraphs = normalized
      .split(/\n\s*\n/)
      .map(p => p.trim())
      .filter(Boolean)

    return paragraphs.map(p => ({ text: p }))
  }

  private chunkSegmentText(text: string, maxChars = 1200): string[] {
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
      } else {
        for (let i = 0; i < part.length; i += maxChars) {
          chunks.push(part.slice(i, i + maxChars))
        }
        current = ''
      }
    }

    if (current) chunks.push(current)
    return chunks
  }

  private sanitizeSegmentForTts(text: string): string {
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

  private isSpeakableSegment(text: string): boolean {
    const trimmed = String(text || '').trim()
    if (!trimmed) return false
    // Skip punctuation-only fragments such as a lone '[' that can trigger
    // provider moderation/validation failures while conveying no speech.
    return /[\p{L}\p{N}]/u.test(trimmed)
  }

  private buildSafeRetryText(text: string): string {
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

  private buildFallbackSegments(text: string, useChunking = true): Array<{ speaker?: string, text: string }> {
    const baseSegments = this.splitIntoSpeechSegments(text, useChunking)
    
    if (!useChunking) {
      console.info('[AudioService] Chunking DISABLED. Final segments count:', baseSegments.length)
      this.logDebug('Final segments for TTS (No Chunking)', { count: baseSegments.length, baseSegments })
      return baseSegments
    }

    const segments: Array<{ speaker?: string, text: string }> = []
    for (const seg of baseSegments) {
      const chunks = this.chunkSegmentText(seg.text)
      for (const chunk of chunks) {
        segments.push({ speaker: seg.speaker, text: chunk })
      }
    }
    this.logDebug('Final segments for TTS (Chunked)', { count: segments.length, segments })
    return segments
  }

  private buildSegmentRequests(
    segments: Array<{ speaker?: string, text: string }>,
    npcMetadata: Record<string, any> | undefined,
  ): Array<{ requestText: string, voiceOverride?: string, speaker?: string }> {
    const requests: Array<{ requestText: string, voiceOverride?: string, speaker?: string }> = []

    for (const segment of segments) {
      const speaker = segment.speaker?.trim() || undefined
      // Single-voice generation: keep only spoken content to avoid reading
      // speaker names out loud.
      const requestText = this.sanitizeSegmentForTts(segment.text)
      if (!this.isSpeakableSegment(requestText)) {
        continue
      }
      const voiceOverride = this.resolveNpcVoice(speaker, npcMetadata)

      requests.push({ requestText, voiceOverride, speaker })
    }

    return requests
  }

  private logDebug(message: string, payload?: unknown): void {
    if (!this.ttsDebugEnabled.value) return
    if (payload === undefined) {
      console.info(message)
      return
    }
    console.info(message, payload)
  }

  private async waitForTtsRequestSlot(): Promise<void> {
    const now = Date.now()
    const elapsed = now - this.lastTtsRequestAt
    const waitMs = AudioService.TTS_REQUEST_MIN_INTERVAL_MS - elapsed
    if (waitMs > 0) {
      await new Promise<void>((resolve) => setTimeout(resolve, waitMs))
    }
    this.lastTtsRequestAt = Date.now()
  }

  private resolveNpcVoice(speaker: string | undefined, npcMetadata: Record<string, any> | undefined): string | undefined {
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

    const path = new URL(resolvedUrl).pathname.toLowerCase()
    const inferredMimeType = path.endsWith('.wav')
      ? 'audio/wav'
      : path.endsWith('.mp3')
        ? 'audio/mpeg'
        : path.endsWith('.ogg')
          ? 'audio/ogg'
          : ''

    // Header-only WAV files are silent and typically indicate failed upstream synthesis.
    if (inferredMimeType === 'audio/wav' && blob.size <= 44) {
      throw new Error('Audio payload is header-only (silent WAV)')
    }

    if (blob.type || !inferredMimeType) {
      return blob
    }

    return new Blob([blob], { type: inferredMimeType })
  }

  private async playAudioBlobWithHtmlAudio(blob: Blob): Promise<void> {
    this.currentObjectUrl = URL.createObjectURL(blob)
    this.currentAudio = new Audio(this.currentObjectUrl)
    this.currentAudio.muted = false
    this.currentAudio.volume = 1
    this.currentAudio.playbackRate = this.getSafeSpeechRate()

    await new Promise<void>((resolve, reject) => {
      if (!this.currentAudio) {
        resolve()
        return
      }

      this.currentAudio.onended = () => {
        if (this.currentObjectUrl) {
          URL.revokeObjectURL(this.currentObjectUrl)
          this.currentObjectUrl = null
        }
        this.currentAudio = null
        resolve()
      }

      this.currentAudio.onerror = () => {
        const mediaErr = this.currentAudio?.error
        const errMsg = `Audio playback failed - code:${mediaErr?.code ?? '?'} msg:${mediaErr?.message ?? '?'}`
        console.error('[TTS]', errMsg)
        if (this.currentObjectUrl) {
          URL.revokeObjectURL(this.currentObjectUrl)
          this.currentObjectUrl = null
        }
        this.currentAudio = null
        reject(new Error(errMsg))
      }

      this.currentAudio.play().catch(reject)
    })
  }

  private async playAudioBlob(blob: Blob): Promise<void> {
    if (!blob.size) {
      throw new Error('Audio payload is empty')
    }

    if (this.audioContext?.state === 'running') {
      // Prefer Web Audio API: decodeAudioData + BufferSource.
      // This completely avoids HTMLAudioElement.play() autoplay restrictions
      // and correctly handles sample-rate resampling (e.g. 24 kHz WAV in a
      // 44.1/48 kHz AudioContext) without distortion.
      try {
        const arrayBuffer = await blob.arrayBuffer()
        const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer)

        await new Promise<void>((resolve, reject) => {
          if (!this.audioContext) { resolve(); return }

          const source = this.audioContext.createBufferSource()
          source.buffer = audioBuffer
          // For WAV (Gemini 2.5 PCM), allow only a very small speed-up to avoid
          // chipmunk-like pitch artifacts.
          const isWav = (blob.type || '').toLowerCase().includes('wav')
          const requestedRate = this.getSafeSpeechRate()
          const wavSafeRate = Math.min(1.1, Math.max(1.0, requestedRate))
          source.playbackRate.value = isWav ? wavSafeRate : requestedRate
          source.connect(this.audioContext.destination)
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
        return
      } catch (err) {
        this.logDebug('WebAudio decode failed; falling back to HTMLAudio', {
          error: String(err),
          blobType: blob.type,
          blobSize: blob.size,
        })
      }
    }

    // Fallback: HTMLAudioElement (before any user gesture OR when WebAudio decode fails).
    await this.playAudioBlobWithHtmlAudio(blob)
  }

  private normalizeText(value: unknown): string {
    if (typeof value === 'string') return value.trim()
    if (value === null || value === undefined) return ''
    return String(value).trim()
  }

  private normalizeOptionalText(value: unknown): string | undefined {
    if (value === null || value === undefined) return undefined
    if (typeof value === 'string') {
      const normalized = value.trim()
      return normalized || undefined
    }
    if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
      return String(value)
    }
    return undefined
  }

  constructor() {

    watch(this.speechRate, (val) => {
      localStorage.setItem('tts_speech_rate', String(val))
    })

    watch(this.ttsDebugEnabled, (val) => {
      localStorage.setItem(AudioService.TTS_DEBUG_STORAGE_KEY, val ? 'true' : 'false')
    })

    watch(this.useTextChunking, (val) => {
      console.info('[AudioService] useTextChunking state updated:', val)
      localStorage.setItem('tts_use_chunking', val ? 'true' : 'false')
    })

  }

  public enqueueSpeak(text: unknown, options: SpeakOptions = {}): Promise<void> {
    const queuedGeneration = this.speakQueueGeneration
    this.speakQueueTail = this.speakQueueTail
      .catch(() => {})
      .then(async () => {
        if (queuedGeneration !== this.speakQueueGeneration) return
        await this.speak(text, { ...options, interruptCurrent: false })
      })

    return this.speakQueueTail
  }

  /**
   * Generates a TTS audio file and triggers a browser download.
   */
  public async download(text: unknown, options: SpeakOptions = {}): Promise<void> {
    const normalizedText = this.normalizeText(text)
    if (!normalizedText) return
    const ttsText = this.normalizeDialoguePrefixes(normalizedText)

    const {
      sceneDescription,
      adventureId,
      sessionId,
      title,
      sceneName,
      tone,
      npcMetadata,
    } = options

    const normalizedSceneDescription = this.normalizeOptionalText(sceneDescription)
    const normalizedAdventureId = this.normalizeOptionalText(adventureId)
    const normalizedSessionId = this.normalizeOptionalText(sessionId)
    const normalizedTitle = this.normalizeOptionalText(title)
    const normalizedSceneName = this.normalizeOptionalText(sceneName)
    const normalizedTone = this.normalizeOptionalText(tone)

    this.isGenerating.value = true
    this.currentlyGeneratingContent.value = normalizedText

    try {
      // For download, we try to get the whole block as one segment if possible.
      // We use buildFallbackSegments with useChunking=false to get a single request.
      const segments = this.buildFallbackSegments(ttsText, false)
      const requests = this.buildSegmentRequests(segments, npcMetadata)

      if (requests.length === 0) return

      for (let i = 0; i < requests.length; i++) {
        const request = requests[i]
        await this.waitForTtsRequestSlot()
        
        const { audio_url } = await api.generateTTS({
          text: request.requestText,
          scene_description: normalizedSceneDescription,
          adventure_id: normalizedAdventureId,
          session_id: normalizedSessionId,
          title: normalizedTitle,
          scene_name: normalizedSceneName,
          tone: normalizedTone,
          voice_override: request.voiceOverride,
        })

        const blob = await this.fetchAudioBlob(audio_url)
        const url = window.URL.createObjectURL(blob)
        
        const a = document.createElement('a')
        a.href = url
        
        // Generate a descriptive filename
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
        const safeTitle = (normalizedTitle || 'adventure').replace(/[^a-z0-9]/gi, '_').toLowerCase()
        const safeScene = (normalizedSceneName || 'scene').replace(/[^a-z0-9]/gi, '_').toLowerCase()
        
        a.download = `taleweaver_${safeTitle}_${safeScene}_${timestamp}.wav`
        
        document.body.appendChild(a)
        a.click()
        
        // Cleanup
        setTimeout(() => {
          window.URL.revokeObjectURL(url)
          document.body.removeChild(a)
        }, 100)
      }
    } catch (err) {
      console.error('[AudioService] Download failed', err)
      this.setPlaybackError(err)
    } finally {
      this.isGenerating.value = false
      this.currentlyGeneratingContent.value = null
    }
  }

  async speak(text: unknown, options: SpeakOptions = {}) {
    const normalizedText = this.normalizeText(text)
    if (!normalizedText) return
    this.lastError.value = null
    const ttsText = this.normalizeDialoguePrefixes(normalizedText)

    const {
      sceneDescription,
      adventureId,
      sessionId,
      title,
      sceneName,
      tone,
      npcMetadata,
      interruptCurrent = true,
      useTextChunking,
    } = options

    // Direct/manual speak interrupts current playback. Queued speak is serialized.
    if (interruptCurrent) {
      this.stop()
    }

    const token = this.playbackToken
    const normalizedSceneDescription = this.normalizeOptionalText(sceneDescription)
    const normalizedAdventureId = this.normalizeOptionalText(adventureId)
    const normalizedSessionId = this.normalizeOptionalText(sessionId)
    const normalizedTitle = this.normalizeOptionalText(title)
    const normalizedSceneName = this.normalizeOptionalText(sceneName)
    const normalizedTone = this.normalizeOptionalText(tone)
    const shouldUseChunking = typeof useTextChunking === 'boolean' ? useTextChunking : this.useTextChunking.value
    this.logDebug('Starting speak sequence', { textLength: ttsText.length, useChunking: shouldUseChunking })
    const segments = this.buildFallbackSegments(ttsText, shouldUseChunking)
    const requests = this.buildSegmentRequests(segments, npcMetadata)

    this.logDebug('TTS plan', {
      totalLength: ttsText.length,
      segments: segments.length,
      requests: requests.length,
      strategy: 'single-voice-segmented',
    })

    try {
      this.currentlyGeneratingContent.value = normalizedText
      this.currentText.value = ttsText
      this.isPlaying.value = true

      if (requests.length === 0) {
        this.logDebug('TTS skipped: no speakable segments after sanitization')
        return
      }

      const prepareSegmentAudio = async (index: number): Promise<Blob | null> => {
        if (token !== this.playbackToken) {
          throw new Error('TTS playback cancelled before generation.')
        }

        const request = requests[index]

        this.logDebug('TTS segment request', {
          index,
          mode: request.voiceOverride ? 'single-speaker-override' : 'single-speaker-default',
          speaker: request.speaker || null,
          textLength: request.requestText.length,
        })

        try {
          await this.waitForTtsRequestSlot()
          const { audio_url } = await api.generateTTS({
            text: request.requestText,
            scene_description: normalizedSceneDescription,
            adventure_id: normalizedAdventureId,
            session_id: normalizedSessionId,
            title: normalizedTitle,
            scene_name: normalizedSceneName,
            tone: normalizedTone,
            voice_override: request.voiceOverride,
          })

          return await this.fetchAudioBlob(audio_url)
        } catch (err) {
          const retryText = this.buildSafeRetryText(request.requestText)
          if (retryText && retryText !== request.requestText && this.isSpeakableSegment(retryText)) {
            try {
              this.logDebug('TTS segment retry with safe text', {
                index,
                speaker: request.speaker || null,
                originalLength: request.requestText.length,
                retryLength: retryText.length,
              })

              await this.waitForTtsRequestSlot()
              const { audio_url } = await api.generateTTS({
                text: retryText,
                scene_description: normalizedSceneDescription,
                adventure_id: normalizedAdventureId,
                session_id: normalizedSessionId,
                title: normalizedTitle,
                scene_name: normalizedSceneName,
                // Retry with reduced prompt complexity to avoid provider blocks.
                tone: undefined,
                // Any non-null value disables style context server-side.
                // Invalid values are safely ignored and backend falls back to default voice.
                voice_override: request.voiceOverride ?? '__AUTO_RETRY_NO_STYLE__',
              })

              return await this.fetchAudioBlob(audio_url)
            } catch (retryErr) {
              this.logDebug('TTS segment retry failed; skipping', {
                index,
                speaker: request.speaker || null,
                error: String(retryErr),
              })
            }
          }

          // Do not abort full auto-speech because one segment failed upstream.
          this.logDebug('TTS segment failed; skipping', {
            index,
            speaker: request.speaker || null,
            textLength: request.requestText.length,
            error: String(err),
          })
          return null
        }
      }

      // Pipeline mode: while one segment is playing, generate and prefetch the next.
      this.isGenerating.value = true
      let nextAudioPromise: Promise<Blob | null> | null = prepareSegmentAudio(0)

      for (let index = 0; index < requests.length; index++) {
        if (token !== this.playbackToken) return
        if (!nextAudioPromise) break

        const currentAudioBlob = await nextAudioPromise

        const hasNext = index + 1 < requests.length
        if (hasNext) {
          nextAudioPromise = prepareSegmentAudio(index + 1)
        } else {
          nextAudioPromise = null
          this.isGenerating.value = false
        }

        if (token !== this.playbackToken) return
        if (!currentAudioBlob) {
          continue
        }

        try {
          await this.playAudioBlob(currentAudioBlob)
        } catch (err) {
          // Continue with following chunks if one segment fails during playback.
          this.logDebug('TTS chunk playback failed; continuing with next chunk', {
            index,
            error: String(err),
          })
        }
      }

      this.isGenerating.value = false
      this.currentlyGeneratingContent.value = null
    } catch (err) {
      console.error('TTS Playback failed', err)
      this.setPlaybackError(err)
    } finally {
      if (token === this.playbackToken) {
        this.isPlaying.value = false
        this.isGenerating.value = false
        this.currentlyGeneratingContent.value = null
        this.currentText.value = null
      }
    }
  }

  stop() {
    this.speakQueueGeneration += 1
    this.playbackToken += 1
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
    this.isPlaying.value = false
    this.isGenerating.value = false
    this.currentlyGeneratingContent.value = null
    this.currentText.value = null
    this.lastError.value = null
  }

  toggleAutoSpeech() {
    // This is always called from a direct click — use it as an unlock opportunity.
    this.unlock()
    this.autoSpeechEnabled.value = !this.autoSpeechEnabled.value
  }
}

export const audioService = new AudioService()
