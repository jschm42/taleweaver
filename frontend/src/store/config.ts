import { reactive } from 'vue'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'

export const configState = reactive({
  appVersion: '0.0.0-loading',
  isLoaded: false,
  hasLlmConfig: false,
  hasT2iConfig: false,
  isBackendReachable: true,
  isTtsEnabled: false,
  lastErrorMessage: '' as string
})

export async function refreshConfig() {
  // Settings endpoint is protected; skip until a token exists.
  if (!authState.token) {
    return
  }

  try {
    const data = await api.getSettings({ includeAvailableConstants: false })
    if (data.app_version) {
      configState.appVersion = data.app_version
    }
    
    configState.hasLlmConfig = !!data.is_llm_configured
    configState.hasT2iConfig = !!data.is_t2i_configured
    const tts = data.tts_settings as any
    configState.isTtsEnabled = !!tts?.enabled
    
    // Synchronize audio service state with the latest user preferences from DB
    const { audioService } = await import('@/services/audioService')
    if (tts) {
      if (typeof tts.use_text_chunking === 'boolean') {
        console.info('[Config] Synchronizing useTextChunking from backend:', tts.use_text_chunking)
        audioService.useTextChunking.value = tts.use_text_chunking
      } else {
        console.warn('[Config] use_text_chunking is missing or not a boolean in backend response:', tts.use_text_chunking)
      }
      if (typeof tts.speech_rate === 'number') {
        audioService.speechRate.value = tts.speech_rate
      }
    }
    
    configState.isLoaded = true
  } catch (error) {
    console.error('Failed to refresh config:', error)
  }
}

