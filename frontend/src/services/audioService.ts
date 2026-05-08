import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'

class AudioService {
  private static readonly TTS_DEBUG_STORAGE_KEY = 'tts_debug_logs'
  private currentAudio: HTMLAudioElement | null = null
  private currentObjectUrl: string | null = null
  private playbackToken = 0
  public isPlaying = ref(false)
  public isGenerating = ref(false)
  public currentText = ref<string | null>(null)
  public autoSpeechEnabled = ref(sessionStorage.getItem('autoSpeechEnabled') === 'true')
  public speechRate = ref<number>(parseFloat(localStorage.getItem('tts_speech_rate') ?? '1'))
  public ttsDebugEnabled = ref(localStorage.getItem(AudioService.TTS_DEBUG_STORAGE_KEY) === 'true')

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

  private splitIntoSpeechSegments(text: string): Array<{ speaker?: string, text: string }> {
    const normalized = text.replace(/\r\n?/g, '\n').trim()
    if (!normalized) return []

    const paragraphs = normalized
      .split(/\n\s*\n/)
      .map(p => p.trim())
      .filter(Boolean)

    const speakerPattern = /^(?:\*\*([^*:\n]+)\*\*|([^:\n]+)):\s*([\s\S]*)$/
    const segments: Array<{ speaker?: string, text: string }> = []

    for (const paragraph of paragraphs) {
      const match = paragraph.match(speakerPattern)
      if (match) {
        const speaker = (match[1] || match[2] || '').trim()
        const spokenText = (match[3] || '').trim()
        if (spokenText) {
          segments.push({ speaker, text: spokenText })
        }
      } else {
        segments.push({ text: paragraph })
      }
    }

    return segments
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

  private buildFallbackSegments(text: string): Array<{ speaker?: string, text: string }> {
    const baseSegments = this.splitIntoSpeechSegments(text)
    const seed = baseSegments.length > 0 ? baseSegments : [{ text }]
    const fallback: Array<{ speaker?: string, text: string }> = []

    for (const segment of seed) {
      const chunks = this.chunkSegmentText(segment.text)
      for (const chunk of chunks) {
        fallback.push({ speaker: segment.speaker, text: chunk })
      }
    }

    return fallback
  }

  private buildSegmentRequests(
    segments: Array<{ speaker?: string, text: string }>,
    npcMetadata: Record<string, any> | undefined,
    maxMergedChars = 1800,
  ): Array<{ requestText: string, voiceOverride?: string, speaker?: string }> {
    const requests: Array<{ requestText: string, voiceOverride?: string, speaker?: string }> = []

    for (const segment of segments) {
      const speaker = segment.speaker?.trim() || undefined
      // Single-voice generation: keep only spoken content to avoid reading
      // speaker names out loud.
      const requestText = segment.text
      const voiceOverride = this.resolveNpcVoice(speaker, npcMetadata)

      const previous = requests[requests.length - 1]
      const sameVoice = previous && previous.voiceOverride === voiceOverride
      const mergedLength = sameVoice ? previous.requestText.length + 2 + requestText.length : 0

      if (sameVoice && mergedLength <= maxMergedChars) {
        previous.requestText = `${previous.requestText}\n\n${requestText}`
        continue
      }

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

  private async playAudio(audioUrl: string): Promise<void> {
    const blob = await this.fetchAudioBlob(audioUrl)
    await this.playAudioBlob(blob)
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

    return blob
  }

  private async playAudioBlob(blob: Blob): Promise<void> {
    if (!blob.size) {
      throw new Error('Audio payload is empty')
    }

    this.currentObjectUrl = URL.createObjectURL(blob)
    this.currentAudio = new Audio(this.currentObjectUrl)
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
        if (this.currentObjectUrl) {
          URL.revokeObjectURL(this.currentObjectUrl)
          this.currentObjectUrl = null
        }
        this.currentAudio = null
        reject(new Error('Audio playback failed'))
      }

      this.currentAudio.play().catch(reject)
    })
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
    watch(this.autoSpeechEnabled, (val) => {
      sessionStorage.setItem('autoSpeechEnabled', val ? 'true' : 'false')
    })

    watch(this.speechRate, (val) => {
      localStorage.setItem('tts_speech_rate', String(val))
    })

    watch(this.ttsDebugEnabled, (val) => {
      localStorage.setItem(AudioService.TTS_DEBUG_STORAGE_KEY, val ? 'true' : 'false')
    })

    // Global listener for SPACE key to stop audio
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && this.isPlaying.value) {
        this.stop()
        e.preventDefault()
      }
    })
  }

  async speak(text: unknown, options: { sceneDescription?: string, adventureId?: string, title?: string, sceneName?: string, tone?: string, npcMetadata?: Record<string, any>, segmentedVoices?: boolean } = {}) {
    const normalizedText = this.normalizeText(text)
    if (!normalizedText) return
    const ttsText = this.normalizeDialoguePrefixes(normalizedText)

    // Stop any current playback
    this.stop()
    const token = this.playbackToken
    const { sceneDescription, adventureId, title, sceneName, tone, npcMetadata } = options
    const normalizedSceneDescription = this.normalizeOptionalText(sceneDescription)
    const normalizedAdventureId = this.normalizeOptionalText(adventureId)
    const normalizedTitle = this.normalizeOptionalText(title)
    const normalizedSceneName = this.normalizeOptionalText(sceneName)
    const normalizedTone = this.normalizeOptionalText(tone)
    const segments = this.buildFallbackSegments(ttsText)
    const requests = this.buildSegmentRequests(segments, npcMetadata)

    this.logDebug('TTS plan', {
      totalLength: ttsText.length,
      segments: segments.length,
      requests: requests.length,
      strategy: 'single-voice-segmented',
    })

    try {
      this.currentText.value = ttsText
      this.isPlaying.value = true

      const prepareSegmentAudio = async (index: number): Promise<Blob> => {
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

        const { audio_url } = await api.generateTTS({
          text: request.requestText,
          scene_description: normalizedSceneDescription,
          adventure_id: normalizedAdventureId,
          title: normalizedTitle,
          scene_name: normalizedSceneName,
          tone: normalizedTone,
          voice_override: request.voiceOverride,
        })

        return this.fetchAudioBlob(audio_url)
      }

      // Pipeline mode: while one segment is playing, generate and prefetch the next.
      this.isGenerating.value = true
      let nextAudioPromise: Promise<Blob> | null = prepareSegmentAudio(0)

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
        await this.playAudioBlob(currentAudioBlob)
      }

      this.isGenerating.value = false
    } catch (err) {
      console.error('TTS Playback failed', err)
    } finally {
      if (token === this.playbackToken) {
        this.isPlaying.value = false
        this.isGenerating.value = false
        this.currentText.value = null
      }
    }
  }

  stop() {
    this.playbackToken += 1
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
    this.currentText.value = null
  }

  toggleAutoSpeech() {
    this.autoSpeechEnabled.value = !this.autoSpeechEnabled.value
  }
}

export const audioService = new AudioService()
