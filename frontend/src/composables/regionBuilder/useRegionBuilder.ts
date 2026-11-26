/**
 * State and actions of the Region Builder page: the form of one planned region, the debounced
 * token preview and starting the build. The region's name and description are saved with the
 * region list first, then the build starts in the background and the page returns to Regions,
 * which polls until the region is built. Spec: docs/specs/region_builder.md.
 */
import { computed, onBeforeUnmount, ref, watch, type ComputedRef, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useEditor } from '@/composables/editor/editorContext'
import { useToast } from '@/composables/useToast'
import {
  applySimpleDefaults,
  buildPayload,
  formFor,
  gatewaysChanged,
  type RegionBuilderForm,
  type RegionMode,
} from '@/composables/regionBuilder/regionBuilderForm'
import {
  sectionService,
  sectionsOf,
  type RegionPromptBlock,
  type RegionPromptPreview,
  type WorldSection,
} from '@/services/sectionService'

const PREVIEW_DELAY_MS = 400

export interface RegionBuilderState {
  form: Ref<RegionBuilderForm | null>
  section: ComputedRef<WorldSection | null>
  sections: ComputedRef<WorldSection[]>
  preview: Ref<RegionPromptPreview | null>
  previewError: Ref<string>
  blocks: ComputedRef<Record<string, RegionPromptBlock>>
  starting: Ref<boolean>
  canBuild: ComputedRef<boolean>
  blockReason: ComputedRef<string>
  setMode: (mode: RegionMode) => void
  build: () => Promise<void>
  loadPrompt: () => Promise<string>
  backToRegions: () => void
}

export function useRegionBuilder(sectionId: Ref<string>): RegionBuilderState {
  const editor = useEditor()
  const router = useRouter()
  const toast = useToast()

  const sections = computed(() => sectionsOf(editor.debugData?.adventure))
  const section = computed(() => sections.value.find((s) => s.id === sectionId.value) || null)
  const form = ref<RegionBuilderForm | null>(null)
  const preview = ref<RegionPromptPreview | null>(null)
  const previewError = ref('')
  const starting = ref(false)

  watch(
    section,
    (value) => {
      if (value && !form.value) form.value = formFor(value)
    },
    { immediate: true },
  )

  const blocks = computed(() => Object.fromEntries((preview.value?.blocks || []).map((b) => [b.id, b])))
  const blueprintErrors = computed(() => (preview.value?.blueprint?.issues || []).filter((i) => i.severity === 'error'))

  const blockReason = computed(() => {
    if (!section.value) return 'This region does not exist (any more).'
    if (section.value.status === 'built') return 'This region is already built.'
    if (section.value.status === 'generating') return 'The World-Builder is building this region.'
    if (!form.value?.label.trim()) return 'Give the region a name.'
    if (blueprintErrors.value.length) return 'Fix the blueprint errors in the region idea first.'
    return ''
  })
  const canBuild = computed(() => !blockReason.value && !starting.value)

  // Token preview: measured on the server whenever the payload changes (debounced).
  let timer: ReturnType<typeof setTimeout> | null = null
  let request = 0
  async function loadPreview(): Promise<void> {
    if (!form.value || !section.value || section.value.status === 'built') return
    const current = ++request
    try {
      const result = await sectionService.previewSection(editor.adventureId, section.value.id, buildPayload(form.value))
      if (current !== request) return
      preview.value = result
      previewError.value = ''
    } catch (error: unknown) {
      if (current === request) previewError.value = error instanceof Error ? error.message : 'The estimate failed.'
    }
  }
  watch(
    () => (form.value ? JSON.stringify(buildPayload(form.value)) : ''),
    () => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => void loadPreview(), PREVIEW_DELAY_MS)
    },
    { immediate: true },
  )
  onBeforeUnmount(() => {
    if (timer) clearTimeout(timer)
  })

  function setMode(mode: RegionMode): void {
    if (!form.value) return
    form.value.mode = mode
    if (mode === 'simple') applySimpleDefaults(form.value)
  }

  /**
   * Name, description and picked gateway scenes belong to the region list; save them before
   * the build reads them.
   */
  async function saveRegionFields(value: RegionBuilderForm, target: WorldSection): Promise<void> {
    const label = value.label.trim()
    const description = value.description.trim()
    const sameText = label === target.label && description === target.description
    if (sameText && !gatewaysChanged(value, target)) return
    const planned_links = target.planned_links.map((l) => ({ ...l, gateway_scene_ids: value.gateways[l.to_section_id] || [] }))
    const next = sections.value.map((s) => (s.id === target.id ? { ...s, label, description, planned_links } : s))
    await sectionService.saveSections(editor.adventureId, next)
  }

  function backToRegions(): void {
    void router.push({ name: 'adventure-editor', params: { adventureId: editor.adventureId }, query: { tab: 'regions' } })
  }

  async function build(): Promise<void> {
    const value = form.value
    const target = section.value
    if (!value || !target || !canBuild.value) return
    starting.value = true
    try {
      await saveRegionFields(value, target)
      await sectionService.generateSection(editor.adventureId, target.id, buildPayload(value))
      await editor.fetchDebugInfo()
      toast.info(`Building ${value.label.trim()}... This takes a few minutes.`)
      backToRegions()
    } catch (error: unknown) {
      toast.error(error instanceof Error ? error.message : 'Failed to start the region generation.')
    } finally {
      starting.value = false
    }
  }

  async function loadPrompt(): Promise<string> {
    if (!form.value || !section.value) return ''
    const result = await sectionService.previewSection(editor.adventureId, section.value.id, buildPayload(form.value), true)
    return result.prompt || ''
  }

  return {
    form,
    section,
    sections,
    preview,
    previewError,
    blocks,
    starting,
    canBuild,
    blockReason,
    setMode,
    build,
    loadPrompt,
    backToRegions,
  }
}
