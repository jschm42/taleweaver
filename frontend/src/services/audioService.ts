import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'

class AudioService {
  private currentAudio: HTMLAudioElement | null = null
  private currentObjectUrl: string | null = null
  private playbackToken = 0
  public isPlaying = ref(false)
  public isGenerating = ref(false)
  public currentText = ref<string | null>(null)
  public autoSpeechEnabled = ref(sessionStorage.getItem('autoSpeechEnabled') === 'true')
  public speechRate = ref<number>(parseFloat(localStorage.getItem('tts_speech_rate') ?? '1'))

  private normalizeDialoguePrefixes(text: string): string {
    // Convert markdown-style speaker labels to plain labels for more reliable
    // downstream TTS interpretation.
    return text.replace(/^\*\*([^*:\n]+)\*\*:\s*/gm, '$1: ')
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

  private buildSpeakerVoiceMap(text: string, npcMetadata: Record<string, any> | undefined): Record<string, string> | undefined {
    if (!npcMetadata) return undefined

    // Gemini multi-speaker expects explicit "Name: text" labels that match the
    // speaker config exactly. Extract speakers line-by-line to avoid losing names
    // when several dialogue lines are in the same paragraph block.
    const speakerPattern = /^\s*(?:\*\*([^*:\n]+)\*\*|([^:\n]+)):\s*.+$/gm
    const mapping: Record<string, string> = {}
    let match: RegExpExecArray | null
    while ((match = speakerPattern.exec(text)) !== null) {
      const speaker = (match[1] || match[2] || '').trim()
      if (!speaker || mapping[speaker]) continue
      const voice = this.resolveNpcVoice(speaker, npcMetadata)
      if (voice) {
        mapping[speaker] = voice
      }
    }

    const mappedSpeakers = Object.keys(mapping)
    if (!mappedSpeakers.length) return undefined

    // Gemini TTS multi-speaker supports at most two speakers per request.
    if (mappedSpeakers.length > 2) {
      const limited = mappedSpeakers.slice(0, 2)
      console.info('TTS multi-speaker limited to first two speakers:', limited)
      return {
        [limited[0]]: mapping[limited[0]],
        [limited[1]]: mapping[limited[1]],
      }
    }

    return mapping
  }

  private isRetryableTtsError(err: unknown): boolean {
    const msg = err instanceof Error ? err.message : String(err)
    const lowered = msg.toLowerCase()
    return lowered.includes('api 504') || lowered.includes('timed out') || lowered.includes('timeout')
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
    const { sceneDescription, adventureId, title, sceneName, tone, npcMetadata, segmentedVoices } = options
    const normalizedSceneDescription = this.normalizeOptionalText(sceneDescription)
    const normalizedAdventureId = this.normalizeOptionalText(adventureId)
    const normalizedTitle = this.normalizeOptionalText(title)
    const normalizedSceneName = this.normalizeOptionalText(sceneName)
    const normalizedTone = this.normalizeOptionalText(tone)
    const segments = segmentedVoices ? this.splitIntoSpeechSegments(ttsText) : []

    try {
      this.currentText.value = ttsText
      this.isPlaying.value = true

      if (!segments.length) {
        // Fast path: generate one audio file for the complete narration block.
        try {
          this.isGenerating.value = true
          const speakerVoices = this.buildSpeakerVoiceMap(ttsText, npcMetadata)
          const { audio_url } = await api.generateTTS({
            text: ttsText,
            scene_description: normalizedSceneDescription,
            adventure_id: normalizedAdventureId,
            title: normalizedTitle,
            scene_name: normalizedSceneName,
            tone: normalizedTone,
            speaker_voices: speakerVoices,
          })
          this.isGenerating.value = false

          if (token !== this.playbackToken) return
          await this.playAudio(audio_url)
        } catch (err) {
          this.isGenerating.value = false
          if (!this.isRetryableTtsError(err)) throw err

          // Fallback: recover from timeout by generating smaller chunks.
          const fallbackSegments = this.buildFallbackSegments(ttsText)
          for (const segment of fallbackSegments) {
            if (token !== this.playbackToken) return

            this.isGenerating.value = true
            const voiceOverride = this.resolveNpcVoice(segment.speaker, npcMetadata)
            const { audio_url } = await api.generateTTS({
              text: segment.text,
              scene_description: normalizedSceneDescription,
              adventure_id: normalizedAdventureId,
              title: normalizedTitle,
              scene_name: normalizedSceneName,
              tone: normalizedTone,
              voice_override: voiceOverride,
            })
            this.isGenerating.value = false

            if (token !== this.playbackToken) return
            await this.playAudio(audio_url)
          }
        }
      } else {
        for (const segment of segments) {
          if (token !== this.playbackToken) return

          this.isGenerating.value = true
          const voiceOverride = this.resolveNpcVoice(segment.speaker, npcMetadata)
          const { audio_url } = await api.generateTTS({
            text: segment.text,
            scene_description: normalizedSceneDescription,
            adventure_id: normalizedAdventureId,
            title: normalizedTitle,
            scene_name: normalizedSceneName,
            tone: normalizedTone,
            voice_override: voiceOverride,
          })
          this.isGenerating.value = false

          if (token !== this.playbackToken) return
          await this.playAudio(audio_url)
        }
      }
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
