/**
 * Actions of the admin console: saving settings, provider tests, user and catalog editing.
 * Keeps AdminView a pure page composition (docs/specs/workbench_ui.md, section 7).
 */
import { ref, type Ref } from 'vue'
import type { CatalogTile } from '@/types'
import { settingsService } from '@/services/settingsService'
import { userService } from '@/services/userService'
import { catalogService } from '@/services/catalogService'
import { testService } from '@/services/testService'

export type CatalogType = 'styles' | 'tones'

export interface LlmTestPayload {
  key: string
  model: string
  provider: string
  openrouterProvider?: string
  customOpenaiUrl?: string
  customOpenaiResponseFormat?: string
  customOpenaiTimeout?: number
  /** Run the pass-specific capability probes instead of the plain connection test. */
  capabilities?: boolean
}

const emptyCatalogItem = (): CatalogTile => ({ id: '', name: '', description: '', instruction: '', image_url: '' })
const emptyUser = (): Record<string, unknown> => ({ username: '', password: '', role: 'user', bio: '' })

export function useSettingsActions() {
  return {
    saveApiKey: async (provider: string, apiKey: string): Promise<void> => {
      settingsService.statusMessage.value = null
      await settingsService.saveApiKey(provider, apiKey)
    },
    deleteApiKey: (provider: string) => settingsService.deleteApiKey(provider),
    saveLlm: (payload: any) => settingsService.saveLlmSettings(payload),
    saveT2i: (payload: any) => settingsService.saveT2iSettings(payload),
    saveTts: (payload: any) => settingsService.saveTTSSettings(payload),
    saveGame: (payload: any) => settingsService.saveGameSettings(payload),
    refreshOllamaModels: (url?: string) => settingsService.fetchOllamaModels(url),
    refreshStableDiffusionModels: (url?: string) => settingsService.fetchStableDiffusionModels(url),
    testLlm: (p: LlmTestPayload) =>
      testService.testLlm(
        p.key,
        p.model,
        p.provider,
        settingsService.llmForm.value.ollama_url,
        p.openrouterProvider,
        p.customOpenaiUrl,
        p.customOpenaiResponseFormat,
        p.customOpenaiTimeout,
        p.capabilities,
      ),
    testVision: (p: any) =>
      testService.testVision(
        p.key, p.model, p.provider, p.ollama_url, p.stable_diffusion_url, p.steps, p.cfg_scale, p.width,
        p.height, p.sampler_name, p.scheduler, p.min_long_edge, p.comfyui_url, p.comfyui_timeout, p.comfyui_workflow,
      ),
    // The backend tests the saved settings, so the form is saved first; otherwise a provider
    // switched in the form would still be tested with the previous one.
    testTts: async (payload: any): Promise<void> => {
      await settingsService.saveTTSSettings(payload)
      if (settingsService.statusMessage.value?.type === 'error') return
      await testService.testTTS()
    },
  }
}

export function useUserEditing() {
  const isOpen = ref(false)
  const user: Ref<any> = ref(emptyUser())
  const isExisting = ref(false)

  function open(existing?: any): void {
    user.value = existing ? { ...existing, password: '' } : emptyUser()
    isExisting.value = Boolean(existing)
    isOpen.value = true
  }

  async function save(data: any): Promise<void> {
    user.value = data
    if (isExisting.value) {
      await userService.updateUser(data.id, data)
    } else {
      await userService.createUser(data)
    }
    isOpen.value = false
  }

  const remove = (target: any) => userService.deleteUser(target.id, target.username)

  return { isOpen, user, isExisting, open, save, remove }
}

export function useCatalogEditing() {
  const isOpen = ref(false)
  const type = ref<CatalogType>('styles')
  const item = ref<CatalogTile>(emptyCatalogItem())
  const index = ref<number | null>(null)
  const isPromptOpen = ref(false)
  const promptData = ref<{ type: CatalogType; item: CatalogTile; index: number } | null>(null)

  function open(catalogType: CatalogType, existing?: CatalogTile, existingIndex?: number): void {
    type.value = catalogType
    item.value = existing ? JSON.parse(JSON.stringify(existing)) : emptyCatalogItem()
    index.value = existing ? (existingIndex ?? null) : null
    isOpen.value = true
  }

  async function save(saved: CatalogTile): Promise<void> {
    catalogService.saveItem(type.value, saved, index.value)
    isOpen.value = false
    await catalogService.saveCurrentCatalog(type.value)
  }

  async function remove(catalogType: CatalogType, removeIndex: number): Promise<void> {
    if (await catalogService.removeItem(catalogType, removeIndex)) {
      await catalogService.saveCurrentCatalog(catalogType)
    }
  }

  function openPrompt(catalogType: CatalogType, target: CatalogTile, targetIndex: number): void {
    promptData.value = { type: catalogType, item: target, index: targetIndex }
    isPromptOpen.value = true
  }

  async function generateImage(
    catalogType: CatalogType,
    target: CatalogTile,
    targetIndex: number | null = null,
    prompt: string | null = null,
  ): Promise<void> {
    await catalogService.generateImage(catalogType, target, settingsService.t2iForm.value.simple_model, targetIndex, prompt)
    isPromptOpen.value = false
  }

  const uploadImage = (event: Event, catalogType: CatalogType, target: CatalogTile, targetIndex: number | null = null) =>
    catalogService.uploadImage(event, catalogType, target, targetIndex)

  return { isOpen, type, item, index, isPromptOpen, promptData, open, save, remove, openPrompt, generateImage, uploadImage }
}
