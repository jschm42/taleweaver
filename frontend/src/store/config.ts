import { reactive } from 'vue'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'

export const configState = reactive({
  appVersion: '0.0.0-loading',
  isLoaded: false,
  hasLlmConfig: false,
  hasT2iConfig: false
})

export async function refreshConfig() {
  // Settings endpoint is protected; skip until a token exists.
  if (!authState.token) {
    return
  }

  try {
    const data = await api.getSettings()
    if (data.app_version) {
      configState.appVersion = data.app_version
    }
    
    configState.hasLlmConfig = !!data.is_llm_configured
    configState.hasT2iConfig = !!data.is_t2i_configured
    configState.isLoaded = true
  } catch (error) {
    console.error('Failed to refresh config:', error)
  }
}

