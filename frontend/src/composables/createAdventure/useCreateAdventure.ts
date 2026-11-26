/**
 * State and actions of the "Generate adventure" page: catalogs, cover source, story idea
 * suggestion, "Surprise me" and the create request. The form logic itself lives in
 * createAdventureForm.ts.
 */
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { findStoryBlueprintError } from '@/composables/storyBlueprint'
import { configState, refreshConfig } from '@/store/config'
import { authState } from '@/store/auth'
import type { CatalogTile } from '@/types'
import {
  applyCoverSource,
  applySimpleDefaults,
  applySurprisePreset,
  buildCreatePayload,
  defaultForm,
  deriveTitle,
  TITLE_MAX_LENGTH,
  type CreateAdventureForm,
  type GeneratorMode,
  type SurprisePreset,
} from '@/composables/createAdventure/createAdventureForm'

const MODE_STORAGE_KEY = 'tw_generator_mode'

function errorText(error: unknown, fallback: string): string {
  return (error as { message?: string })?.message || fallback
}

function readStoredMode(): GeneratorMode {
  try {
    return localStorage.getItem(MODE_STORAGE_KEY) === 'advanced' ? 'advanced' : 'simple'
  } catch {
    return 'simple'
  }
}

export interface CreateAdventureState {
  form: Ref<CreateAdventureForm>
  mode: Ref<GeneratorMode>
  imageStyles: Ref<CatalogTile[]>
  tones: Ref<CatalogTile[]>
  sourceAdventure: Ref<Record<string, any> | null>
  isCoverMode: ComputedRef<boolean>
  isLoadingCatalogs: Ref<boolean>
  isLoadingCoverSource: Ref<boolean>
  isGenerating: Ref<boolean>
  isSuggesting: Ref<boolean>
  isSurprising: Ref<boolean>
  errorMsg: Ref<string>
  hasLlmConfig: ComputedRef<boolean>
  hasT2iConfig: ComputedRef<boolean>
  isConfigLoaded: ComputedRef<boolean>
  setMode: (mode: GeneratorMode) => void
  suggestStoryIdea: () => Promise<void>
  surpriseMe: () => Promise<void>
  create: () => Promise<void>
  init: () => void
}

export function useCreateAdventure(): CreateAdventureState {
  const router = useRouter()
  const route = useRoute()

  const form = ref<CreateAdventureForm>(defaultForm())
  const mode = ref<GeneratorMode>(readStoredMode())
  const imageStyles = ref<CatalogTile[]>([])
  const tones = ref<CatalogTile[]>([])
  const sourceAdventure = ref<Record<string, any> | null>(null)
  const isLoadingCatalogs = ref(true)
  const isLoadingCoverSource = ref(false)
  const isGenerating = ref(false)
  const isSuggesting = ref(false)
  const isSurprising = ref(false)
  const errorMsg = ref('')

  const coverSourceId = computed(() => {
    const raw = route.query.cover_from
    return typeof raw === 'string' ? raw.trim() : ''
  })
  const isCoverMode = computed(() => !!coverSourceId.value)
  const hasLlmConfig = computed(() => configState.hasLlmConfig)
  const hasT2iConfig = computed(() => configState.hasT2iConfig)
  const isConfigLoaded = computed(() => configState.isLoaded)
  const catalogs = (): { styles: CatalogTile[]; tones: CatalogTile[] } => ({ styles: imageStyles.value, tones: tones.value })

  function setMode(next: GeneratorMode): void {
    mode.value = next
    try {
      localStorage.setItem(MODE_STORAGE_KEY, next)
    } catch {
      // Storage may be blocked; the choice then lasts for this visit only.
    }
    if (next === 'simple') applySimpleDefaults(form.value)
  }

  async function loadCatalogs(): Promise<void> {
    isLoadingCatalogs.value = true
    try {
      const data = await api.getSettings()
      imageStyles.value = data.image_styles_catalog || []
      tones.value = data.tone_catalog || []
      form.value.selected_style_id ||= imageStyles.value[0]?.id || ''
      form.value.selected_tone_id ||= tones.value[0]?.id || ''
    } catch (error) {
      errorMsg.value = errorText(error, 'Failed to load the style and tone catalogs.')
    } finally {
      isLoadingCatalogs.value = false
    }
  }

  async function loadCoverSource(): Promise<void> {
    if (!isCoverMode.value) return
    isLoadingCoverSource.value = true
    try {
      sourceAdventure.value = await api.getAdventure(coverSourceId.value)
      applyCoverSource(form.value, sourceAdventure.value as Record<string, any>)
    } catch (error) {
      sourceAdventure.value = null
      errorMsg.value = errorText(error, 'Failed to load the source adventure.')
    } finally {
      isLoadingCoverSource.value = false
    }
  }

  async function suggestStoryIdea(): Promise<void> {
    if (!hasLlmConfig.value || isSuggesting.value) return
    isSuggesting.value = true
    errorMsg.value = ''
    try {
      const suggestion = await api.suggestStoryIdea({
        title: form.value.title,
        story_idea: form.value.storyIdea,
        selected_tone: tones.value.find((tone) => tone.id === form.value.selected_tone_id) || null,
        rule_enforcement_mode: form.value.rule_enforcement_mode,
        language: form.value.language || undefined,
      })
      form.value.title = (suggestion.title || '').slice(0, TITLE_MAX_LENGTH)
      form.value.storyIdea = suggestion.story_idea || ''
    } catch (error) {
      errorMsg.value = errorText(error, 'Failed to generate a story idea.')
    } finally {
      isSuggesting.value = false
    }
  }

  async function surpriseMe(): Promise<void> {
    if (!hasLlmConfig.value || isSurprising.value) return
    isSurprising.value = true
    errorMsg.value = ''
    try {
      const preset = await api.generateSurprisePreset({
        available_tones: tones.value.map((tone) => tone.name || tone.id),
        available_styles: imageStyles.value.map((style) => style.id),
        language: form.value.language || undefined,
      })
      if (preset) applySurprisePreset(form.value, preset as SurprisePreset, catalogs())
    } catch (error) {
      errorMsg.value = errorText(error, 'Failed to generate a surprise preset.')
    } finally {
      isSurprising.value = false
    }
  }

  /** Checks that block the request; returns an error text or "". */
  async function precheck(): Promise<string> {
    const f = form.value
    if (mode.value === 'simple' && !f.storyIdea.trim()) return 'Describe your adventure idea first.'
    if (!f.title.trim() && !f.storyIdea.trim()) return 'Enter a title or a story idea.'
    if (isCoverMode.value && !sourceAdventure.value) return 'The source adventure could not be loaded.'
    return (await findStoryBlueprintError(f.storyIdea.trim())) || ''
  }

  async function create(): Promise<void> {
    if (isGenerating.value) return
    const f = form.value
    f.title = f.title.slice(0, TITLE_MAX_LENGTH)
    if (mode.value === 'simple') {
      // As before: simple mode always uses the script engine and automatic time; limits a
      // "Surprise me" preset set stay.
      f.scripts_generation_enabled = true
      f.time_auto = true
    }
    isGenerating.value = true
    errorMsg.value = await precheck()
    if (errorMsg.value) {
      isGenerating.value = false
      return
    }
    if (!f.title.trim()) f.title = deriveTitle(f.storyIdea)
    const cover = isCoverMode.value ? { id: coverSourceId.value, title: sourceAdventure.value?.title } : null
    const payload = buildCreatePayload(f, catalogs(), cover, crypto.randomUUID())
    try {
      await api.createAdventure(payload as any)
      router.push({ name: 'portal', query: { new_id: payload.id as string, new_title: payload.title as string, section: 'templates' } })
    } catch (error) {
      errorMsg.value = errorText(error, 'Failed to create the adventure.').replace(/^API 409:\s*/, '')
      isGenerating.value = false
    }
  }

  function init(): void {
    void refreshConfig()
    void loadCatalogs()
    if (authState.user?.default_language) form.value.language = authState.user.default_language
    void loadCoverSource()
  }

  return {
    form,
    mode,
    imageStyles,
    tones,
    sourceAdventure,
    isCoverMode,
    isLoadingCatalogs,
    isLoadingCoverSource,
    isGenerating,
    isSuggesting,
    isSurprising,
    errorMsg,
    hasLlmConfig,
    hasT2iConfig,
    isConfigLoaded,
    setMode,
    suggestStoryIdea,
    surpriseMe,
    create,
    init,
  }
}
