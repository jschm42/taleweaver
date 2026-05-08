import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'

class AudioService {
  private currentAudio: HTMLAudioElement | null = null
  public isPlaying = ref(false)
  public isGenerating = ref(false)
  public currentText = ref<string | null>(null)
  public autoSpeechEnabled = ref(sessionStorage.getItem('autoSpeechEnabled') === 'true')

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

    // Global listener for SPACE key to stop audio
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && this.isPlaying.value) {
        this.stop()
        e.preventDefault()
      }
    })
  }

  async speak(text: unknown, options: { sceneDescription?: string, adventureId?: string, title?: string, sceneName?: string, tone?: string } = {}) {
    const normalizedText = this.normalizeText(text)
    if (!normalizedText) return
    
    // Stop any current playback
    this.stop()
    const { sceneDescription, adventureId, title, sceneName, tone } = options
    const normalizedSceneDescription = this.normalizeOptionalText(sceneDescription)
    const normalizedAdventureId = this.normalizeOptionalText(adventureId)
    const normalizedTitle = this.normalizeOptionalText(title)
    const normalizedSceneName = this.normalizeOptionalText(sceneName)
    const normalizedTone = this.normalizeOptionalText(tone)

    try {
      this.isGenerating.value = true
      this.currentText.value = normalizedText
      const { audio_url } = await api.generateTTS({ 
        text: normalizedText,
        scene_description: normalizedSceneDescription,
        adventure_id: normalizedAdventureId,
        title: normalizedTitle,
        scene_name: normalizedSceneName,
        tone: normalizedTone
      })
      this.isGenerating.value = false
      
      this.isPlaying.value = true
      this.currentAudio = new Audio(audio_url)
      
      this.currentAudio.onended = () => {
        this.isPlaying.value = false
        this.currentAudio = null
        this.currentText.value = null
      }

      this.currentAudio.onerror = () => {
        this.isPlaying.value = false
        this.currentAudio = null
        this.currentText.value = null
      }

      await this.currentAudio.play()
    } catch (err) {
      console.error('TTS Playback failed', err)
      this.isPlaying.value = false
      this.isGenerating.value = false
      this.currentText.value = null
    }
  }

  stop() {
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
