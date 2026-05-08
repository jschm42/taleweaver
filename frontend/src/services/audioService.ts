import { ref, watch } from 'vue'
import { api } from '@/composables/useApi'

class AudioService {
  private currentAudio: HTMLAudioElement | null = null
  public isPlaying = ref(false)
  public isGenerating = ref(false)
  public currentText = ref<string | null>(null)
  public autoSpeechEnabled = ref(sessionStorage.getItem('autoSpeechEnabled') === 'true')

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

  async speak(text: string, sceneDescription?: string, adventureId?: string) {
    if (!text) return
    
    // Stop any current playback
    this.stop()

    try {
      this.isGenerating.value = true
      this.currentText.value = text
      const { audio_url } = await api.generateTTS({ text, scene_description: sceneDescription, adventure_id: adventureId })
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
