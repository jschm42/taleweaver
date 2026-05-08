import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'

class AudioService {
  private currentAudio: HTMLAudioElement | null = null
  private playbackToken = 0
  public isPlaying = ref(false)
  public isGenerating = ref(false)
  public currentText = ref<string | null>(null)
  public autoSpeechEnabled = ref(sessionStorage.getItem('autoSpeechEnabled') === 'true')
  public speechRate = ref<number>(parseFloat(localStorage.getItem('tts_speech_rate') ?? '1'))

  private splitIntoSpeechSegments(text: string): Array<{ speaker?: string, text: string }> {
    const normalized = text.replace(/\r\n?/g, '\n').trim()
    if (!normalized) return []

    const paragraphs = normalized
      .split(/\n\s*\n/)
      .map(p => p.trim())
      .filter(Boolean)

    const speakerPattern = /^\*\*([^*:\n]+)\*\*:\s*([\s\S]*)$/
    const segments: Array<{ speaker?: string, text: string }> = []

    for (const paragraph of paragraphs) {
      const match = paragraph.match(speakerPattern)
      if (match) {
        const speaker = match[1].trim()
        const spokenText = (match[2] || '').trim()
        if (spokenText) {
          segments.push({ speaker, text: spokenText })
        }
      } else {
        segments.push({ text: paragraph })
      }
    }

    return segments
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
    this.currentAudio = new Audio(audioUrl)
    this.currentAudio.playbackRate = this.speechRate.value

    await new Promise<void>((resolve, reject) => {
      if (!this.currentAudio) {
        resolve()
        return
      }

      this.currentAudio.onended = () => {
        this.currentAudio = null
        resolve()
      }

      this.currentAudio.onerror = () => {
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

  async speak(text: unknown, options: { sceneDescription?: string, adventureId?: string, title?: string, sceneName?: string, tone?: string, npcMetadata?: Record<string, any> } = {}) {
    const normalizedText = this.normalizeText(text)
    if (!normalizedText) return

    // Stop any current playback
    this.stop()
    const token = this.playbackToken
    const { sceneDescription, adventureId, title, sceneName, tone, npcMetadata } = options
    const normalizedSceneDescription = this.normalizeOptionalText(sceneDescription)
    const normalizedAdventureId = this.normalizeOptionalText(adventureId)
    const normalizedTitle = this.normalizeOptionalText(title)
    const normalizedSceneName = this.normalizeOptionalText(sceneName)
    const normalizedTone = this.normalizeOptionalText(tone)
    const segments = this.splitIntoSpeechSegments(normalizedText)

    try {
      this.currentText.value = normalizedText
      this.isPlaying.value = true

      for (const segment of (segments.length ? segments : [{ text: normalizedText }])) {
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
    this.isPlaying.value = false
    this.isGenerating.value = false
    this.currentText.value = null
  }

  toggleAutoSpeech() {
    this.autoSpeechEnabled.value = !this.autoSpeechEnabled.value
  }
}

export const audioService = new AudioService()
