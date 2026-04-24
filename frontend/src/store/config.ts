import { reactive } from 'vue'
import { api } from '@/composables/useApi'

export const configState = reactive({
  appVersion: '0.0.0-loading',
  isLoaded: false
})

export async function refreshConfig() {
  try {
    const data = await api.getSettings()
    if (data.app_version) {
      configState.appVersion = data.app_version
    }
    configState.isLoaded = true
  } catch (error) {
    console.error('Failed to refresh config:', error)
  }
}
