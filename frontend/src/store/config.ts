import { reactive } from 'vue'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'

export const configState = reactive({
  appVersion: '0.0.0-loading' as string,
  isLoaded: false,
  hasLlmConfig: false,
  hasT2iConfig: false,
  isBackendReachable: true,
  isTtsEnabled: false,
  lastErrorMessage: '' as string
})

const VERSION_PLACEHOLDER = '0.0.0-loading'

export function isAppVersionKnown(): boolean {
  return configState.appVersion !== VERSION_PLACEHOLDER
}

/** Loads the version from the public bootstrap endpoint (works without a token). */
export async function loadPublicAppVersion() {
  if (isAppVersionKnown()) {
    return
  }
  try {
    const bootstrap = await api.getBootstrapStatus()
    if (bootstrap.app_version) {
      configState.appVersion = bootstrap.app_version
    }
  } catch (error) {
    console.error('Failed to load app version:', error)
  }
}

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
      // The provider may have changed: find out again whether it streams.
      audioService.resetProviderCapabilities()
      if (typeof tts.speech_rate === 'number') {
        audioService.speechRate.value = tts.speech_rate
      }
      // Speech starts on its own when TTS is usable (enabled + provider key) and the admin
      // has "start automatically" on; players can still switch it off.
      const ttsConfigured = !!tts.enabled && !!data.keys?.[String(tts.provider || 'google')]
      audioService.applyAutoSpeechDefault(ttsConfigured && tts.auto_speak !== false)
    }
    
    configState.isLoaded = true
  } catch (error) {
    console.error('Failed to refresh config:', error)
  }
}

