import { ref } from 'vue'
import { api } from '@/composables/useApi'
import { audioService } from '@/services/audioService'
import { catalogService } from '@/services/catalogService'
import { refreshConfig } from '@/store/config'

/**
 * SettingsService manages all admin configuration:
 * - API provider keys and authentication
 * - LLM (Intelligence) model configuration
 * - Text-to-Image (T2I) visual preferences
 * - Text-to-Speech (TTS) audio settings
 * - Game settings (clock format, date format)
 *
 * All settings are fetched from the backend on initialization and saved back
 * when the user submits changes. The service also maintains backend constants
 * (available providers, predefined models).
 */
class SettingsService {
  // ============ CONFIGURATION STATE ============
  configuredKeys = ref<Record<string, { masked: string; is_env: boolean }>>({})

  // Forms for configuration sections
  llmForm = ref({
    small_model: '',
    small_model_provider: 'openai',
    small_max_tokens: 12288,
    small_enable_thinking: false,
    small_max_thinking_tokens: 1024,

    complex_model: '',
    complex_model_provider: 'openai',
    complex_max_tokens: 24576,
    complex_enable_thinking: false,
    complex_max_thinking_tokens: 1024,

    generator_model: '',
    generator_model_provider: 'openai',
    generator_max_tokens: 32768,
    generator_enable_thinking: false,
    generator_max_thinking_tokens: 1024,

    play_agent_model: '',
    play_agent_model_provider: 'openai',
    play_agent_monkey_mode: false,

    preferred_provider: 'openai',
    ollama_url: 'http://localhost:11434',
  })

  t2iForm = ref({
    simple_model: '',
    simple_model_provider: 'openai',
    advanced_model: '',
    advanced_model_provider: 'openai',
    provider: 'openai',
    ollama_url: 'http://localhost:11434',
    stable_diffusion_url: 'http://127.0.0.1:7860',
    width: null as number | null,
    height: null as number | null,
    steps: null as number | null,
    cfg_scale: null as number | null,
    simple_steps: null as number | null,
    simple_cfg_scale: null as number | null,
    advanced_steps: null as number | null,
    advanced_cfg_scale: null as number | null,
    simple_sampler_name: null as string | null,
    simple_scheduler: null as string | null,
    advanced_sampler_name: null as string | null,
    advanced_scheduler: null as string | null,
    simple_min_long_edge: null as number | null,
    advanced_min_long_edge: null as number | null,
    seed: null as number | null,
    image_format: 'jpeg',
    image_quality: 85,
    negative_prompt: '',
    scene_model_quality: 'advanced' as string,
    profile_model_quality: 'advanced' as string,
    protagonist_model_quality: 'advanced' as string,
    asset_model_quality: 'simple' as string,
  })

  gameForm = ref({
    clock_24h: false,
    date_format: 'DD.MM.YY',
  })

  ttsForm = ref({
    enabled: false,
    provider: 'google',
    selected_model: 'gemini-2.5-flash-preview-tts',
    elevenlabs_voice_id: '',
    use_vocal_tags: true,
    use_text_chunking: true,
    voice_catalog: [] as Array<{ name: string; gender?: string; description?: string }>,
    selected_voice: 'Puck',
    sample_context: '',
    speech_rate: 1.0,
  })

  availableConstants = ref({
    llm_providers: [] as { id: string; name: string }[],
    image_providers: [] as { id: string; name: string }[],
    predefined_llm_models: {} as Record<string, string[]>,
    predefined_image_models: {} as Record<string, string[]>,
  })

  // ============ UI STATE ============
  isSubmitting = ref(false)
  statusMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null)
  isHydratingSettings = ref(false)
  isLoadingOllamaModels = ref(false)
  isLoadingStableDiffusionModels = ref(false)

  // ============ FETCHING & INITIALIZATION ============

  /**
   * Fetch all settings from the backend and hydrate the local forms.
   * This includes API keys, model configurations, and available constants.
   */
  async fetchSettings() {
    try {
      this.isHydratingSettings.value = true
      const data = await api.getSettings()

      // Hydrate keys
      this.configuredKeys.value = data.keys || {}

      // Hydrate form data
      if (data.llm_settings) this.llmForm.value = { ...data.llm_settings as any }
      if (data.t2i_settings) this.t2iForm.value = { ...data.t2i_settings as any }
      if (data.game_settings) this.gameForm.value = { ...data.game_settings as any }

      // Hydrate admin-managed catalogs used by the styles/tones sections.
      catalogService.hydrateCatalogs(data)

      // Hydrate TTS with special boolean handling
      if (data.tts_settings) {
        const ttsSettings = data.tts_settings as any
        this.ttsForm.value = {
          ...this.ttsForm.value,
          ...ttsSettings,
          use_vocal_tags: ttsSettings.use_vocal_tags !== false,
          use_text_chunking:
            String(ttsSettings.use_text_chunking).toLowerCase() !== 'false' && ttsSettings.use_text_chunking !== null,
        }

        // Sync with audio service
        audioService.speechRate.value = this.ttsForm.value.speech_rate ?? 1.0
        audioService.useTextChunking.value = this.ttsForm.value.use_text_chunking
        console.info('[SettingsService] TTS settings hydrated.', {
          use_text_chunking: this.ttsForm.value.use_text_chunking,
          speech_rate: this.ttsForm.value.speech_rate,
        })
      }

      // Hydrate available constants
      if ((data as any).available_constants) {
        this.availableConstants.value = (data as any).available_constants
      }

      await this.fetchOllamaModels(this.llmForm.value.ollama_url)
      await this.fetchStableDiffusionModels(this.t2iForm.value.stable_diffusion_url)
    } catch (error) {
      console.error('[SettingsService] Failed to fetch settings:', error)
      this.statusMessage.value = {
        type: 'error',
        text: 'Failed to load configuration. Please refresh the page.',
      }
    } finally {
      this.isHydratingSettings.value = false
    }
  }

  async fetchOllamaModels(ollamaUrl?: string) {
    this.isLoadingOllamaModels.value = true
    try {
      const data = await api.getOllamaModels(ollamaUrl)
      const models = Array.isArray(data.models) ? data.models : []
      this.availableConstants.value = {
        ...this.availableConstants.value,
        predefined_llm_models: {
          ...this.availableConstants.value.predefined_llm_models,
          ollama: models,
        },
      }
      return models
    } catch (error) {
      console.error('[SettingsService] Failed to fetch Ollama models:', error)
      this.availableConstants.value = {
        ...this.availableConstants.value,
        predefined_llm_models: {
          ...this.availableConstants.value.predefined_llm_models,
          ollama: [],
        },
      }
      return []
    } finally {
      this.isLoadingOllamaModels.value = false
    }
  }

  async fetchStableDiffusionModels(sdUrl?: string) {
    this.isLoadingStableDiffusionModels.value = true
    try {
      const data = await api.getStableDiffusionModels(sdUrl)
      const models = Array.isArray(data.models) ? data.models : []
      this.availableConstants.value = {
        ...this.availableConstants.value,
        predefined_image_models: {
          ...this.availableConstants.value.predefined_image_models,
          stable_diffusion: models,
        },
      }
      return models
    } catch (error) {
      console.error('[SettingsService] Failed to fetch Stable Diffusion models:', error)
      this.availableConstants.value = {
        ...this.availableConstants.value,
        predefined_image_models: {
          ...this.availableConstants.value.predefined_image_models,
          stable_diffusion: ['default'],
        },
      }
      return ['default']
    } finally {
      this.isLoadingStableDiffusionModels.value = false
    }
  }

  // ============ API KEY MANAGEMENT ============

  /**
   * Save an API key for a provider.
   * The key is sent securely to the backend for storage.
   */
  async saveApiKey(provider: string, apiKey: string) {
    // Special case: Ollama uses local connection, no API key needed
    if (provider === 'ollama') {
      this.statusMessage.value = { type: 'success', text: 'Ollama nutzt lokal keinen API Key.' }
      return
    }

    if (!apiKey.trim()) {
      this.statusMessage.value = { type: 'error', text: 'API Key cannot be empty.' }
      return
    }

    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      await api.saveApiKey(provider, apiKey)
      this.statusMessage.value = { type: 'success', text: `${provider} key saved securely.` }
      await this.fetchSettings()
      await refreshConfig()
    } catch (error) {
      console.error('[SettingsService] Failed to save API key:', error)
      this.statusMessage.value = { type: 'error', text: 'Failed to save key.' }
    } finally {
      this.isSubmitting.value = false
    }
  }

  /**
   * Delete an API key for a provider.
   * Requires user confirmation before deletion.
   */
  async deleteApiKey(provider: string) {
    if (!confirm(`Are you sure you want to remove the API key for ${provider}? This will stop related AI services from functioning.`)) {
      return
    }

    this.isSubmitting.value = true

    try {
      await api.deleteApiKey(provider)
      this.statusMessage.value = { type: 'success', text: `${provider} key removed successfully.` }
      await this.fetchSettings()
    } catch (err: any) {
      console.error('[SettingsService] Failed to delete API key:', err)
      this.statusMessage.value = { type: 'error', text: 'Delete failed: ' + err.message }
    } finally {
      this.isSubmitting.value = false
    }
  }

  // ============ SETTINGS SAVE METHODS ============

  /**
   * Save LLM (Intelligence) configuration.
   * Updates model selections, token limits, and thinking settings.
   */
  async saveLlmSettings(payload: any) {
    this.llmForm.value = { ...payload }
    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      await api.saveLlmSettings(this.llmForm.value)
      this.statusMessage.value = { type: 'success', text: 'Intelligence preferences updated.' }
      await refreshConfig()
    } catch (error) {
      console.error('[SettingsService] Failed to save LLM settings:', error)
      this.statusMessage.value = { type: 'error', text: 'Failed to save intelligence preferences.' }
    } finally {
      this.isSubmitting.value = false
    }
  }

  /**
   * Save Text-to-Image (T2I) configuration.
   * Updates image generation models and quality settings.
   */
  async saveT2iSettings(payload: any) {
    const cleanNum = (val: any) => {
      if (val === null || val === undefined || val === '') return null
      const num = Number(val)
      return isNaN(num) ? null : num
    }

    const cleanStr = (val: any) => {
      if (val === null || val === undefined || String(val).trim() === '') return null
      return String(val).trim()
    }

    const cleanedPayload = {
      ...payload,
      width: cleanNum(payload.width),
      height: cleanNum(payload.height),
      steps: cleanNum(payload.steps),
      cfg_scale: cleanNum(payload.cfg_scale),
      simple_steps: cleanNum(payload.simple_steps),
      simple_cfg_scale: cleanNum(payload.simple_cfg_scale),
      advanced_steps: cleanNum(payload.advanced_steps),
      advanced_cfg_scale: cleanNum(payload.advanced_cfg_scale),
      simple_sampler_name: cleanStr(payload.simple_sampler_name),
      simple_scheduler: cleanStr(payload.simple_scheduler),
      advanced_sampler_name: cleanStr(payload.advanced_sampler_name),
      advanced_scheduler: cleanStr(payload.advanced_scheduler),
      simple_min_long_edge: cleanNum(payload.simple_min_long_edge),
      advanced_min_long_edge: cleanNum(payload.advanced_min_long_edge),
      seed: cleanNum(payload.seed),
      image_quality: cleanNum(payload.image_quality),
    }

    this.t2iForm.value = cleanedPayload
    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      await api.saveT2iSettings(this.t2iForm.value)
      this.statusMessage.value = { type: 'success', text: 'Visual preferences updated.' }
      await refreshConfig()
    } catch (error) {
      console.error('[SettingsService] Failed to save T2I settings:', error)
      this.statusMessage.value = { type: 'error', text: 'Failed to save visual preferences.' }
    } finally {
      this.isSubmitting.value = false
    }
  }

  /**
   * Save Text-to-Speech (TTS) configuration.
   * Updates voice provider, speech rate, and text chunking settings.
   * Also syncs these settings with the global audio service.
   */
  async saveTTSSettings(payload: any) {
    this.ttsForm.value = { ...payload }
    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      console.info('[SettingsService] Saving TTS Settings:', this.ttsForm.value)
      await api.saveTTSSettings(this.ttsForm.value)

      // Sync with audio service
      audioService.speechRate.value = this.ttsForm.value.speech_rate
      audioService.useTextChunking.value = this.ttsForm.value.use_text_chunking

      this.statusMessage.value = { type: 'success', text: 'TTS settings updated.' }
      await refreshConfig()
    } catch (error) {
      console.error('[SettingsService] Failed to save TTS settings:', error)
      this.statusMessage.value = { type: 'error', text: 'Failed to update TTS settings.' }
    } finally {
      this.isSubmitting.value = false
    }
  }

  /**
   * Save game settings.
   * Updates clock format (12/24h) and date format.
   */
  async saveGameSettings(payload: any) {
    this.gameForm.value = { ...payload }
    this.isSubmitting.value = true
    this.statusMessage.value = null

    try {
      await api.saveGameSettings(this.gameForm.value)
      this.statusMessage.value = { type: 'success', text: 'Game preferences updated.' }
      await refreshConfig()
    } catch (error) {
      console.error('[SettingsService] Failed to save game settings:', error)
      this.statusMessage.value = { type: 'error', text: 'Failed to save game preferences.' }
    } finally {
      this.isSubmitting.value = false
    }
  }
}

export const settingsService = new SettingsService()
