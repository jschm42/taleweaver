import { reactive } from 'vue'
import { api } from '@/composables/useApi'

export const configState = reactive({
  appVersion: '0.0.0-loading',
  isLoaded: false,
  hasLlmConfig: false
})

export async function refreshConfig() {
  try {
    const data = await api.getSettings()
    if (data.app_version) {
      configState.appVersion = data.app_version
    }
    
    // Check if at least one LLM provider is configured (has key or is ollama)
    const keys = data.keys || {}
    const llmSettings = data.llm_settings || {}
    
    const smallProvider = llmSettings.small_model_provider || 'openai'
    const complexProvider = llmSettings.complex_model_provider || 'openai'
    const smallModel = llmSettings.small_model
    const complexModel = llmSettings.complex_model
    
    const hasSmallConfig = (smallProvider === 'ollama' || !!keys[smallProvider]) && !!smallModel
    const hasComplexConfig = (complexProvider === 'ollama' || !!keys[complexProvider]) && !!complexModel
    
    configState.hasLlmConfig = hasSmallConfig && hasComplexConfig
    configState.isLoaded = true
  } catch (error) {
    console.error('Failed to refresh config:', error)
  }
}
