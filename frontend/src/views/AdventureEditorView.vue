<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { adventureService } from '@/services/adventureService'
import { visualService } from '@/services/visualService'
import type { VisualKind } from '@/services/visualService'
import { entityService } from '@/services/entityService'
import { notificationService } from '@/services/notificationService'

// Icons & Assets

// Components
import EditorHeader from '@/components/editor/EditorHeader.vue'
import WorldTab from '@/components/editor/WorldTab.vue'
import ItemsTab from '@/components/editor/ItemsTab.vue'
import VisualsTab from '@/components/editor/VisualsTab.vue'
import ToneTab from '@/components/editor/ToneTab.vue'
import InhabitantsTab from '@/components/editor/InhabitantsTab.vue'
import ScenesTab from '@/components/editor/ScenesTab.vue'
import MapTab from '@/components/editor/MapTab.vue'
import QuestTab from '@/components/editor/QuestTab.vue'
import AwardsTab from '@/components/editor/AwardsTab.vue'
import AdvancedTab from '@/components/editor/AdvancedTab.vue'
import EntityTooltip from '@/components/editor/EntityTooltip.vue'
import NotificationToast from '@/components/editor/NotificationToast.vue'
import EditEntityModal from '@/components/editor/EditEntityModal.vue'
import ManualVisionModal from '@/components/editor/ManualVisionModal.vue'
import DataDebugModal from '@/components/editor/DataDebugModal.vue'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

// Utilities
import { 
  fixNewlines, 
  isNpcEntity, 
  isObjectEntity, 
  mergeUniqueById, 
  formatBytes,
  makeSafeFilename,
  getImageExtension,
} from '@/utils/editor_utils'

const props = defineProps<{
  adventureId: string
}>()

const router = useRouter()
const route = useRoute()
const ASSET_BASE = ''

// Visuals state
const isQuickGenerating = ref<Record<string, boolean>>({})
const isBatchGenerating = ref<Record<string, boolean>>({})
const activeAbortControllers = ref<Map<string, AbortController>>(new Map())
const isGenerating = computed(() => {
  return isRegenerating.value || 
         Object.values(isQuickGenerating.value).some(Boolean) || 
         Object.values(isBatchGenerating.value).some(Boolean)
})

const isSavingText = ref(false)
const showEditModal = ref(false)
const editEntityContext = ref<{ type: string; id: string } | null>(null)
const editForm = ref({
  name: '',
  teaser: '',
  description: '',
  hp: 0,
  stamina: 0,
  mana: 0,
  goal: '',
  character: '',
  is_killable: true,
  item_type: 'PICKABLE',
  is_portable: true,
  locked: false,
  code_to_unlock: '',
  item_to_unlock: '',
  inventory_json: '[]',
  text_log_content: '',
  text_log_format: 'DOCUMENT',
})

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const promptError = ref('')
const showDebug = ref(false)
const activeTab = ref<'world' | 'items' | 'visuals' | 'inhabitants' | 'scenes' | 'map' | 'quest' | 'awards' | 'tone' | 'advanced'>('world')

const selectedVisual = ref<{ kind: VisualKind; id: string; label: string; description: string; hint: string } | null>(null)
const selectedUploadTarget = ref<{ kind: VisualKind; id: string; label: string } | null>(null)
const visualPrompt = ref('')
const showPromptDialog = ref(false)
const isRegenerating = ref(false)
const isSuggestingPrompt = ref(false)
const useAdvancedModel = ref(false)
const showRegenerateAllConfirmDialog = ref(false)
const pendingBatchRegeneration = ref<{ kind: string; missingOnly: boolean } | null>(null)
const isUploading = ref(false)
const isSettingStartScene = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
const visualsCacheVersion = ref(0)
const hoveredEntity = ref<any>(null)
const mousePos = ref({ x: 0, y: 0 })
const activeMenuId = ref<string | null>(null)
const tooltipAlignTop = ref(false)
const windowHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 1000)
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1000)

if (typeof window !== 'undefined') {
  window.addEventListener('resize', () => {
    windowHeight.value = window.innerHeight
    windowWidth.value = window.innerWidth
  })
}

function toggleMenu(id: string, event: MouseEvent) {
  event.stopPropagation()
  if (activeMenuId.value === id) {
    activeMenuId.value = null
  } else {
    activeMenuId.value = id
    hoveredEntity.value = null
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('click', () => {
    activeMenuId.value = null
  })
}

const imageStylesCatalog = ref<any[]>([])
const toneCatalog = ref<any[]>([])
const availableVoices = ref<Array<{ name: string; gender?: string; description?: string }>>([])

const editorTabs = [
  { key: 'world', label: 'World' },
  { key: 'items', label: 'Items' },
  { key: 'visuals', label: 'Visuals' },
  { key: 'inhabitants', label: 'Inhabitants' },
  { key: 'scenes', label: 'Scenes' },
  { key: 'map', label: 'Map' },
  { key: 'quest', label: 'Quest' },
  { key: 'awards', label: 'Awards' },
  { key: 'tone', label: 'Tone' },
  { key: 'advanced', label: 'Advanced' },
] as const

// Use notification service
const notifications = notificationService.all

function addNotification(message: string, type: 'error' | 'success' | 'info' = 'info') {
  notificationService.add(message, type)
}

// clearCreationError is currently unused but kept for future functionality
// async function clearCreationError() {
//   if (!adventure.value) return
//   try {
//     await adventureService.clearCreationError(props.adventureId)
//     adventure.value.creation_error = null
//     addNotification('Generation notice dismissed.', 'success')
//   } catch (error) {
//     console.error('Failed to clear creation error:', error)
//   }
// }

function handleHover(entity: any, event: MouseEvent) {
  if (activeMenuId.value) return
  hoveredEntity.value = entity
  tooltipAlignTop.value = event.clientY > windowHeight.value * 0.6
  let x = event.clientX + 20
  const tooltipWidth = 280
  if (x + tooltipWidth > windowWidth.value) {
    x = event.clientX - tooltipWidth - 20
  }
  mousePos.value = { x, y: event.clientY }
}

function clearHover() {
  hoveredEntity.value = null
}

async function uploadSelectedVisual(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  const target = selectedUploadTarget.value
  if (!file || !target) return
  const spec = visualService.UPLOAD_LIMITS[target.kind]

  // Validate file
  const fileValidation = visualService.validateFile(file)
  if (!fileValidation.valid) {
    addNotification(fileValidation.error || 'Invalid file', 'error')
    input.value = ''
    return
  }

  // Validate file size
  if (file.size > spec.maxBytes) {
    addNotification(`File too large. Max is ${formatBytes(spec.maxBytes)}.`, 'error')
    input.value = ''
    return
  }

  // Validate dimensions
  try {
    const { width, height } = await visualService.getImageDimensions(file)
    const dimValidation = visualService.validateDimensions(width, height, spec)
    if (!dimValidation.valid) {
      addNotification(dimValidation.error || 'Invalid dimensions', 'error')
      input.value = ''
      return
    }
  } catch (error: any) {
    addNotification(error?.message || 'Unable to validate image dimensions.', 'error')
    input.value = ''
    return
  }

  isUploading.value = true
  try {
    await visualService.uploadVisual(props.adventureId, target.kind, target.id, file)
    await fetchDebugInfo()
    addNotification(`Image uploaded for ${target.label}.`, 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Upload failed.', 'error')
  } finally {
    isUploading.value = false
    selectedUploadTarget.value = null
    input.value = ''
  }
}

const form = ref({
  title: '',
  teaser: '',
  version: '',
  original_prompt: '',
  rule_enforcement_mode: 'rpg' as 'rpg' | 'story' | 'chat',
  time_per_turn: 5,
  min_scenes: null as number | null,
  max_scenes: null as number | null,
  min_items: null as number | null,
  max_items: null as number | null,
  container_generation_enabled: true,
  min_containers: null as number | null,
  max_containers: null as number | null,
  text_log_generation_enabled: true,
  min_text_logs: null as number | null,
  max_text_logs: null as number | null,
  awards: [] as any[],
  allow_dynamic_items: true,
  can_damage_npcs: true,
  npcs_can_damage_protagonist: true,
  plot: '',
  rules: '',
  intro_text: '',
  walkthrough: '',
  completed_condition: '',
  gameover_condition: '',
  tts_director_notes: '',
  selected_style_id: '',
  selected_tone_id: '',
  is_adventure_generator: false
})

const editingField = ref<string | null>(null)
const tempValue = ref('')

function startEditing(field: string, value: string) {
  editingField.value = field
  tempValue.value = fixNewlines(value)
}

function cancelEditing() {
  editingField.value = null
  tempValue.value = ''
}

async function saveField() {
  if (!editingField.value) return
  // @ts-ignore
  form.value[editingField.value] = tempValue.value
  await saveChanges()
  editingField.value = null
}

async function fetchCatalogs() {
  try {
    const data = await adventureService.fetchCatalogs()
    imageStylesCatalog.value = data.image_styles_catalog || []
    toneCatalog.value = data.tone_catalog || []
    const voiceCatalog = Array.isArray(data.tts_settings?.voice_catalog)
      ? data.tts_settings.voice_catalog
      : []
    const voiceList = Array.isArray(data.tts_settings?.voice_list)
      ? data.tts_settings.voice_list
      : []
    availableVoices.value = voiceCatalog.length > 0
      ? voiceCatalog
      : voiceList.map((name: string) => ({ name }))
  } catch (error) {
    console.error('Failed to fetch catalogs:', error)
  }
}

const editorNpcs = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.npcs) ? debugData.value.npcs : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isNpcEntity(entity))
  return mergeUniqueById(source, inferred)
})

const editorScenes = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.scenes) ? debugData.value.scenes : []
  return source.filter((scene: any) => !!scene?.id)
})

const editorObjects = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred).filter((entity: any) => {
    const type = String(entity?.item_type || '').toUpperCase()
    return type !== 'READABLE' && type !== 'CONTAINER' && type !== 'SWITCH'
  })
})

const editorSwitches = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred).filter((entity: any) => String(entity?.item_type || '').toUpperCase() === 'SWITCH')
})

const editorContainers = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred).filter((entity: any) => String(entity?.item_type || '').toUpperCase() === 'CONTAINER')
})

const editorTextLogs = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred).filter((entity: any) => String(entity?.item_type || '').toUpperCase() === 'READABLE')
})

async function fetchAdventure() {
  if (!props.adventureId) return
  isLoading.value = true
  errorMsg.value = ''
  try {
    const data = await adventureService.fetchAdventure(props.adventureId)
    adventure.value = data
    form.value.title = data.title
    form.value.teaser = data.teaser || ''
    form.value.version = data.version || ''
    form.value.original_prompt = data.original_prompt || ''
    form.value.rule_enforcement_mode = (data.rule_enforcement_mode as 'rpg' | 'story' | 'chat') || 'rpg'
    form.value.time_per_turn = data.time_per_turn || 5
    form.value.min_scenes = data.min_scenes !== undefined ? data.min_scenes : null
    form.value.max_scenes = data.max_scenes !== undefined ? data.max_scenes : null
    form.value.min_items = data.min_items !== undefined ? data.min_items : null
    form.value.max_items = data.max_items !== undefined ? data.max_items : null
    form.value.container_generation_enabled = data.container_generation_enabled ?? true
    form.value.min_containers = data.min_containers !== undefined ? data.min_containers : null
    form.value.max_containers = data.max_containers !== undefined ? data.max_containers : null
    form.value.text_log_generation_enabled = data.text_log_generation_enabled ?? true
    form.value.min_text_logs = data.min_text_logs !== undefined ? data.min_text_logs : null
    form.value.max_text_logs = data.max_text_logs !== undefined ? data.max_text_logs : null
    form.value.awards = data.awards || []
    form.value.allow_dynamic_items = data.allow_dynamic_items ?? true
    form.value.plot = data.plot || ''
    form.value.can_damage_npcs = data.can_damage_npcs ?? true
    form.value.npcs_can_damage_protagonist = data.npcs_can_damage_protagonist ?? true
    form.value.rules = data.rules || ''
    form.value.intro_text = data.intro_text || ''
    form.value.walkthrough = data.walkthrough || ''
    form.value.completed_condition = data.completed_condition || ''
    form.value.gameover_condition = data.gameover_condition || ''
    form.value.tts_director_notes = data.tts_director_notes || ''

    form.value.selected_style_id = Array.isArray(data.selected_image_styles) && data.selected_image_styles.length > 0 
      ? (typeof data.selected_image_styles[0] === 'string' ? data.selected_image_styles[0] : data.selected_image_styles[0].id)
      : ''
    let rawTone = data.selected_tone
    if (rawTone && typeof rawTone === 'object') {
      form.value.selected_tone_id = rawTone.id || rawTone.name || ''
    } else if (typeof rawTone === 'string' && rawTone.startsWith('{')) {
      try {
        const obj = JSON.parse(rawTone)
        form.value.selected_tone_id = obj.id || obj.name || rawTone
      } catch (e) {
        form.value.selected_tone_id = rawTone
      }
    } else {
      form.value.selected_tone_id = rawTone || ''
    }
    form.value.is_adventure_generator = !!data.is_adventure_generator
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error loading adventure.'
  } finally {
    isLoading.value = false
  }
}

async function fetchDebugInfo() {
  if (!props.adventureId) return
  try {
    const payload = await adventureService.fetchDebugInfo(props.adventureId)
    debugData.value = adventureService.normalizeDebugPayload(payload)
    visualsCacheVersion.value += 1
  } catch (error) {
    console.error('Failed to fetch debug info:', error)
    debugData.value = null
    errorMsg.value = 'Failed to load world assets/debug data.'
  }
}

async function setStartScene(sceneId: string) {
  const normalizedSceneId = String(sceneId || '').trim()
  if (!normalizedSceneId || isSettingStartScene.value) return
  isSettingStartScene.value = true
  try {
    await adventureService.updateEditorStartScene(props.adventureId, normalizedSceneId)
    await fetchDebugInfo()
    addNotification('Start scene updated.', 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Failed to set start scene.', 'error')
  } finally {
    isSettingStartScene.value = false
    activeMenuId.value = null
  }
}

function openTextEdit(type: string, id: string, currentName: string, currentDesc: string, currentTeaser: string = '', hp?: number, stamina?: number, mana?: number, goal?: string, character?: string, isKillable?: boolean) {
  const selectedObject = type === 'object'
    ? ([...(editorObjects.value || []), ...(editorTextLogs.value || []), ...(editorSwitches.value || [])]).find((entry: any) => String(entry.id) === String(id))
    : null

  editEntityContext.value = { type, id }
  const resolvedDescription = type === 'object'
    ? fixNewlines(selectedObject?.description || currentDesc || '')
    : fixNewlines(currentDesc || '')
  editForm.value = { 
    name: currentName || '', 
    description: resolvedDescription,
    teaser: fixNewlines(currentTeaser || ''),
    hp: hp ?? 0,
    stamina: stamina ?? 0,
    mana: mana ?? 0,
    goal: goal || '',
    character: character || '',
    is_killable: isKillable ?? true,
    item_type: selectedObject?.item_type || 'PICKABLE',
    is_portable: selectedObject?.is_portable !== false,
    locked: selectedObject?.locked === true,
    code_to_unlock: selectedObject?.code_to_unlock || '',
    item_to_unlock: selectedObject?.item_to_unlock || '',
    inventory_json: JSON.stringify(selectedObject?.inventory || [], null, 2),
    text_log_content: fixNewlines(selectedObject?.metadata_json?.text_log_content || ''),
    text_log_format: String(selectedObject?.metadata_json?.text_log_format || selectedObject?.text_log_format || 'DOCUMENT').trim().toUpperCase(),
  }
  showEditModal.value = true
}

async function saveEntityText(data: any) {
  if (!editEntityContext.value) return
  
  // Basic validation for stats
  if (data.hp < 0 || data.hp > 999 || data.stamina < 0 || data.stamina > 999 || data.mana < 0 || data.mana > 999) {
    addNotification('Stats must be between 0 and 999.', 'error')
    return
  }

  // Persona validation (NPC and Protagonist)
  if (['npc', 'protagonist'].includes(editEntityContext.value.type)) {
    if ((data.goal || '').length > 200 || (data.character || '').length > 200) {
      addNotification('Motivation and traits must be under 200 characters.', 'error')
      return
    }
  }

  if (editEntityContext.value.type === 'object' && (data.text_log_content || '').length > 500) {
    addNotification('Text logs must be 500 characters or less.', 'error')
    return
  }

  if (
    editEntityContext.value.type === 'object' &&
    String(data.item_type || '').toUpperCase() === 'READABLE' &&
    (data.description || '').length > 200
  ) {
    addNotification('Readable item descriptions must be 200 characters or less.', 'error')
    return
  }

  isSavingText.value = true
  promptError.value = ''
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: editEntityContext.value.type,
      target_id: editEntityContext.value.id,
      name: data.name,
      teaser: editEntityContext.value.type === 'cover' ? data.teaser : undefined,
      description: data.description,
      hp: data.hp || undefined,
      stamina: data.stamina || undefined,
      mana: data.mana || undefined,
      goal: ['npc', 'protagonist'].includes(editEntityContext.value.type) ? data.goal : undefined,
      character: ['npc', 'protagonist'].includes(editEntityContext.value.type) ? data.character : undefined,
      is_killable: editEntityContext.value.type === 'npc' ? data.is_killable : undefined,
      is_portable: editEntityContext.value.type === 'object' ? data.is_portable : undefined,
      locked: editEntityContext.value.type === 'object' ? data.locked : undefined,
      code_to_unlock: editEntityContext.value.type === 'object' ? data.code_to_unlock : undefined,
      item_to_unlock: editEntityContext.value.type === 'object' ? data.item_to_unlock : undefined,
      inventory: editEntityContext.value.type === 'object' ? data.inventory : undefined,
      text_log_content: editEntityContext.value.type === 'object' ? data.text_log_content : undefined,
      text_log_format: editEntityContext.value.type === 'object' && String(data.item_type || '').toUpperCase() === 'READABLE'
        ? data.text_log_format
        : undefined,
    })
    showEditModal.value = false
    editEntityContext.value = null
    await Promise.all([fetchAdventure(), fetchDebugInfo()])
    addNotification('Changes applied successfully.', 'success')
  } catch (error: any) {
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isSavingText.value = false
  }
}

async function saveChanges() {
  isSaving.value = true
  errorMsg.value = ''
  try {
    const fullStyleObj = imageStylesCatalog.value.find(s => s.id === form.value.selected_style_id) || { id: form.value.selected_style_id, name: form.value.selected_style_id }
    const fullToneObj = toneCatalog.value.find(t => t.id === form.value.selected_tone_id) || { id: form.value.selected_tone_id, name: form.value.selected_tone_id }
    const payload = {
      ...form.value,
      selected_image_styles: form.value.selected_style_id ? [fullStyleObj] : [],
      selected_tone: form.value.selected_tone_id ? fullToneObj : null
    }
    await adventureService.updateAdventure(props.adventureId, payload as any)
    await fetchAdventure()
    addNotification('Adventure configuration updated.', 'success')
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error while saving.'
    addNotification(errorMsg.value, 'error')
  } finally {
    isSaving.value = false
  }
}

function buildVisualImageUrl(imagePath?: string | null) {
  return visualService.buildImageUrl(imagePath, visualsCacheVersion.value)
}

function downloadVisualAsset(imagePath: string | null | undefined, filenameLabel: string) {
  if (!imagePath) {
    addNotification('No image available for download.', 'error')
    activeMenuId.value = null
    return
  }
  const url = buildVisualImageUrl(imagePath)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = makeSafeFilename(filenameLabel, getImageExtension(imagePath))
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  activeMenuId.value = null
}

function openRegenerateDialog(kind: any, id: string, label: string) {
  const description = getVisualDescription(kind, id)
  const hint = visualService.UPLOAD_LIMITS[kind as VisualKind].hint
  selectedVisual.value = { kind, id, label, description, hint }
  visualPrompt.value = ''
  useAdvancedModel.value = kind === 'scene' || kind === 'cover'
  promptError.value = ''
  showPromptDialog.value = true
}

function getVisualDescription(kind: any, id: string) {
  if (!debugData.value) return ''
  if (kind === 'cover') return debugData.value.adventure?.plot || debugData.value.adventure?.original_prompt || ''
  if (kind === 'protagonist') {
    const base = debugData.value.protagonist?.description || ''
    const plot = debugData.value.adventure?.plot || ''
    return plot ? `${base}\n\nNarrative context: ${plot}` : base
  }
  if (kind === 'scene') return (debugData.value.scenes || []).find((s: any) => s.id === id)?.description || ''
  if (kind === 'npc') return (debugData.value.npcs || []).find((n: any) => n.id === id)?.description || ''
  return (debugData.value.objects || []).find((o: any) => o.id === id)?.description || ''
}

function openUploadPicker(kind: any, id: string, label: string) {
  selectedUploadTarget.value = { kind, id, label }
  promptError.value = ''
  addNotification(`Upload ${label}: ${visualService.UPLOAD_LIMITS[kind as VisualKind].hint}`, 'info')
  if (uploadInput.value) {
    uploadInput.value.value = ''
    uploadInput.value.click()
  }
}

async function quickRegenerateVisual(kind: any, id: string, skipFetch: boolean = false) {
  const key = `${kind}_${id}`
  isQuickGenerating.value[key] = true
  
  if (activeAbortControllers.value.has(key)) {
    activeAbortControllers.value.get(key)?.abort()
  }
  const controller = new AbortController()
  activeAbortControllers.value.set(key, controller)
  
  try {
     await visualService.quickRegenerateVisual(props.adventureId, kind, id, controller.signal)
    if (!skipFetch) await fetchDebugInfo()
  } catch (error: any) {
    if (error.name === 'AbortError' || (error instanceof DOMException && error.name === 'AbortError')) {
      console.log('Quick regen aborted for', key)
      throw error
    }
    console.error('Quick regen error:', error)
    addNotification(error.message, 'error')
  } finally {
    isQuickGenerating.value[key] = false
    activeAbortControllers.value.delete(key)
  }
}

function requestRegenerateAll(kind: any, missingOnly: boolean = false) {
  if (!missingOnly) {
    pendingBatchRegeneration.value = { kind, missingOnly }
    showRegenerateAllConfirmDialog.value = true
    return
  }
  void regenerateAll(kind, missingOnly)
}

function cancelRegenerateAllDialog() {
  showRegenerateAllConfirmDialog.value = false
  pendingBatchRegeneration.value = null
}

function confirmRegenerateAll() {
  if (!pendingBatchRegeneration.value) {
    cancelRegenerateAllDialog()
    return
  }
  const { kind, missingOnly } = pendingBatchRegeneration.value
  showRegenerateAllConfirmDialog.value = false
  pendingBatchRegeneration.value = null
  void regenerateAll(kind, missingOnly)
}

function getRegenerateKindLabel(kind: string): string {
  if (kind === 'scene') return 'locations'
  if (kind === 'npc') return 'inhabitants'
  if (kind === 'container') return 'containers'
  if (kind === 'switch') return 'switches'
  if (kind === 'text-log') return 'text logs'
  if (kind === 'cover') return 'cover art'
  if (kind === 'protagonist') return 'protagonist portraits'
  return 'mystical objects'
}

function isImageMissingForRegeneration(item: any): boolean {
  const raw = String(item?.image_url || '').trim()
  if (!raw) return true
  const lowered = raw.toLowerCase()
  // Legacy/broken paths and generated placeholders should count as missing.
  if (lowered.startsWith('assets/') || lowered.startsWith('/assets/')) return true
  if (lowered.includes('placeholder_') || lowered.includes('/placeholder-')) return true
  return false
}

async function regenerateAll(kind: any, missingOnly: boolean = false) {
  isBatchGenerating.value[kind] = true
  let items: any[] = []
  if (kind === 'cover' && debugData.value?.adventure) items = [debugData.value.adventure]
  if (kind === 'protagonist' && debugData.value?.protagonist) items = [debugData.value.protagonist]
  if (kind === 'scene') items = editorScenes.value
  if (kind === 'npc') items = editorNpcs.value
  if (kind === 'object') items = editorObjects.value
  if (kind === 'container') items = editorContainers.value
  if (kind === 'switch') items = editorSwitches.value
  if (kind === 'text-log') items = editorTextLogs.value

  const targets = missingOnly
    ? items.filter((item: any) => isImageMissingForRegeneration(item))
    : items

  if (targets.length === 0) {
    addNotification(`No ${getRegenerateKindLabel(kind)} are missing images.`, 'info')
    isBatchGenerating.value[kind] = false
    return
  }

  let successCount = 0
  let errorCount = 0
  
  for (const item of targets) {
    try {
      const apiKind = (kind === 'container' || kind === 'text-log' || kind === 'switch') ? 'object' : kind
      await quickRegenerateVisual(apiKind, item.id || props.adventureId)
      successCount += 1
    } catch (error: any) {
      if (error.name === 'AbortError' || (error instanceof DOMException && error.name === 'AbortError')) {
        addNotification('Batch generation stopped.', 'info')
        break
      }
      errorCount += 1
    }
  }
  await fetchDebugInfo()
  if (errorCount > 0) {
    addNotification(`Generated ${successCount} ${getRegenerateKindLabel(kind)} image(s), ${errorCount} failed.`, 'error')
  } else {
    addNotification(`Generated ${successCount} ${getRegenerateKindLabel(kind)} image(s).`, 'success')
  }
  isBatchGenerating.value[kind] = false
}

async function regenerateVisual() {
  if (!selectedVisual.value || isRegenerating.value) return
  isRegenerating.value = true
  promptError.value = ''
  
  const key = `${selectedVisual.value.kind}_${selectedVisual.value.id}`
  if (activeAbortControllers.value.has(key)) {
    activeAbortControllers.value.get(key)?.abort()
  }
  const controller = new AbortController()
  activeAbortControllers.value.set(key, controller)
  
  try {
     await visualService.regenerateVisual(
       props.adventureId,
       selectedVisual.value.kind,
       selectedVisual.value.id,
       visualPrompt.value,
       useAdvancedModel.value,
       controller.signal
     )
     showPromptDialog.value = false
     await fetchDebugInfo()
     addNotification(`Visual for ${selectedVisual.value.label} re-woven.`, 'success')
  } catch (error: any) {
    if (error.name === 'AbortError' || (error instanceof DOMException && error.name === 'AbortError')) {
      console.log('Regen aborted for', key)
      return
    }
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isRegenerating.value = false
    activeAbortControllers.value.delete(key)
  }
}

async function suggestPrompt() {
  if (!selectedVisual.value || isSuggestingPrompt.value) return
  isSuggestingPrompt.value = true
  promptError.value = ''
  try {
     const suggested = await visualService.suggestPrompt(
       props.adventureId,
       selectedVisual.value.kind,
       selectedVisual.value.id
     )
     if (suggested) {
       visualPrompt.value = suggested
       addNotification('AI suggested a prompt based on the description.', 'success')
     } else {
       addNotification('AI returned an empty suggestion.', 'info')
     }
  } catch (error: any) {
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isSuggestingPrompt.value = false
  }
}

function cancelRegeneration() {
  if (selectedVisual.value) {
    const key = `${selectedVisual.value.kind}_${selectedVisual.value.id}`
    if (activeAbortControllers.value.has(key)) {
      activeAbortControllers.value.get(key)?.abort()
    }
  }
  isRegenerating.value = false
  showPromptDialog.value = false
  addNotification('Generation request abandoned.', 'info')
}

function stopAllGenerations() {
  if (activeAbortControllers.value.size === 0) return
  
  for (const [key, controller] of activeAbortControllers.value.entries()) {
    try {
      controller.abort()
    } catch (e) {
      console.error('Failed to abort controller:', e)
    }
  }
  activeAbortControllers.value.clear()
  
  isQuickGenerating.value = {}
  isBatchGenerating.value = {}
  isRegenerating.value = false
  showPromptDialog.value = false
  
  addNotification('All visual generations stopped.', 'info')
}

watch(
  () => props.adventureId,
  async (newId) => {
    if (!newId) {
      adventure.value = null
      debugData.value = null
      return
    }
    await Promise.all([fetchAdventure(), fetchDebugInfo(), fetchCatalogs()])
  },
  { immediate: true }
)

async function handleUpdateQuests(newQuests: any[]) {
  isSaving.value = true
  try {
    await adventureService.updateAdventure(props.adventureId, { quests: newQuests })
    await fetchAdventure()
    addNotification('Quests updated.', 'success')
  } catch (error: any) {
    addNotification(error instanceof Error ? error.message : 'Failed to update quests', 'error')
  } finally {
    isSaving.value = false
  }
}

async function handleUpdateAwards(newAwards: any[]) {
  isSaving.value = true
  try {
    await adventureService.updateAdventure(props.adventureId, { awards: newAwards })
    await fetchAdventure()
    addNotification('Awards updated.', 'success')
  } catch (error: any) {
    addNotification(error instanceof Error ? error.message : 'Failed to update awards', 'error')
  } finally {
    isSaving.value = false
  }
}

const goBack = () => {
  const from = route.query.from as string
  if (from) {
    router.push({ name: 'portal', query: { section: from } })
  } else {
    router.push({ name: 'portal' })
  }
}

const activeMapSceneId = computed<string | null>(() => {
  if (route.name !== 'adventure-editor-scene') return null
  const raw = route.params.sceneId
  return typeof raw === 'string' ? raw : null
})

const activeMapExitId = computed<string | null>(() => {
  if (route.name !== 'adventure-editor-exit') return null
  const raw = route.params.exitId
  return typeof raw === 'string' ? raw : null
})

const editorAllObjects = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred)
})

const routeSceneDetails = computed<any | null>(() => {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) return null
  return editorScenes.value.find((scene: any) => String(scene.id) === sceneId) || null
})

const routeSceneNpcs = computed<any[]>(() => {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) return []
  return editorNpcs.value.filter((npc: any) => String(npc.current_scene_id || '') === sceneId)
})

const routeSceneObjects = computed<any[]>(() => {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) return []
  return editorAllObjects.value.filter((obj: any) => String(obj.current_scene_id || '') === sceneId)
})

const routeSceneExits = computed<any[]>(() => {
  const sceneId = String(activeMapSceneId.value || '').trim()
  const exits = Array.isArray(debugData.value?.exits) ? debugData.value.exits : []
  if (!sceneId) return []
  return exits.filter((worldExit: any) => {
    return String(worldExit.from_scene_id || '') === sceneId || String(worldExit.to_scene_id || '') === sceneId
  })
})

const routeExitDetails = computed<any | null>(() => {
  const exitId = String(activeMapExitId.value || '').trim()
  const exits = Array.isArray(debugData.value?.exits) ? debugData.value.exits : []
  if (!exitId) return null
  return exits.find((worldExit: any) => String(worldExit.id) === exitId) || null
})

const referenceOptions = computed<Array<{ id: string; name: string; imageUrl?: string | null; type: string }>>(() => {
  const entries: Array<{ id: string; name: string; imageUrl?: string | null; type: string }> = []
  for (const scene of editorScenes.value) {
    entries.push({
      id: String(scene.id || ''),
      name: String(scene.label || scene.name || scene.id || ''),
      imageUrl: scene.image_url ? buildVisualImageUrl(scene.image_url) : null,
      type: 'SCENE',
    })
  }
  for (const npc of editorNpcs.value) {
    entries.push({
      id: String(npc.id || ''),
      name: String(npc.name || npc.id || ''),
      imageUrl: npc.image_url ? buildVisualImageUrl(npc.image_url) : null,
      type: 'NPC',
    })
  }
  for (const obj of editorAllObjects.value) {
    entries.push({
      id: String(obj.id || ''),
      name: String(obj.name || obj.id || ''),
      imageUrl: obj.image_url ? buildVisualImageUrl(obj.image_url) : null,
      type: 'OBJECT',
    })
  }
  return entries.filter((entry) => entry.id)
})

const sceneReferenceOptions = computed(() => {
  return referenceOptions.value.filter((entry) => entry.type === 'SCENE')
})

const canShowSceneRoutePanel = computed(() => route.name === 'adventure-editor-scene')
const canShowExitRoutePanel = computed(() => route.name === 'adventure-editor-exit')

const showCreateNpcForm = ref(false)
const showCreateItemForm = ref(false)
const showCreateExitForm = ref(false)
const isCreatingRouteAsset = ref(false)
const isDeletingRouteAsset = ref(false)

const createNpcForm = ref({
  id: '',
  name: '',
  description: '',
})

const createItemForm = ref({
  id: '',
  name: '',
  description: '',
  item_type: 'PICKABLE',
})

const createExitForm = ref({
  to_scene_id: '',
  label: '',
  exit_type: 'one_way' as 'one_way' | 'bidirectional',
})

const exitEditForm = ref({
  label: '',
  lock_description: '',
  exit_type: 'one_way' as 'one_way' | 'bidirectional',
})

watch(
  () => routeExitDetails.value,
  (exitData) => {
    if (!exitData) {
      exitEditForm.value = {
        label: '',
        lock_description: '',
        exit_type: 'one_way',
      }
      return
    }
    exitEditForm.value = {
      label: String(exitData.label || ''),
      lock_description: String(exitData.lock_description || ''),
      exit_type: String(exitData.exit_type || 'one_way').toLowerCase() === 'bidirectional' ? 'bidirectional' : 'one_way',
    }
  },
  { immediate: true },
)

function openSceneEditorRoute(sceneId: string) {
  const normalized = String(sceneId || '').trim()
  if (!normalized) return
  router.push({
    name: 'adventure-editor-scene',
    params: {
      adventureId: props.adventureId,
      sceneId: normalized,
    },
    query: route.query,
  })
}

function openExitEditorRoute(exitId: string) {
  const normalized = String(exitId || '').trim()
  if (!normalized) return
  router.push({
    name: 'adventure-editor-exit',
    params: {
      adventureId: props.adventureId,
      exitId: normalized,
    },
    query: route.query,
  })
}

function resetRouteCreateForms() {
  createNpcForm.value = { id: '', name: '', description: '' }
  createItemForm.value = { id: '', name: '', description: '', item_type: 'PICKABLE' }
  createExitForm.value = { to_scene_id: '', label: '', exit_type: 'one_way' }
}

function sanitizeEditorIdToken(rawValue: string): string {
  return String(rawValue || '')
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9_-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^[_-]+|[_-]+$/g, '')
    .slice(0, 128)
}

function buildPrefixedEditorId(rawValue: string, prefix: string): string {
  const safePrefix = sanitizeEditorIdToken(prefix)
  const safeValue = sanitizeEditorIdToken(rawValue)
  if (!safeValue) return ''
  if (safeValue.startsWith(safePrefix)) return safeValue
  return `${safePrefix}${safeValue}`.slice(0, 128)
}

function autoFillNpcId() {
  createNpcForm.value.id = buildPrefixedEditorId(createNpcForm.value.id || createNpcForm.value.name, 'NPC_')
}

function autoFillItemId() {
  createItemForm.value.id = buildPrefixedEditorId(createItemForm.value.id || createItemForm.value.name, 'ITEM_')
}

async function createNpcInRouteScene() {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) return
  const normalizedNpcId = buildPrefixedEditorId(createNpcForm.value.id || createNpcForm.value.name, 'NPC_')
  if (!normalizedNpcId || !createNpcForm.value.name.trim() || !createNpcForm.value.description.trim()) {
    addNotification('NPC requires ID, name and description.', 'error')
    return
  }
  isCreatingRouteAsset.value = true
  try {
    await entityService.createEntity(props.adventureId, {
      entity_id: normalizedNpcId,
      entity_type: 'NPC',
      scene_id: sceneId,
      name: createNpcForm.value.name.trim(),
      description: createNpcForm.value.description.trim(),
      hp: 20,
      stamina: 20,
      mana: 20,
    })
    showCreateNpcForm.value = false
    resetRouteCreateForms()
    await fetchDebugInfo()
    addNotification('NPC added to scene.', 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Failed to add NPC.', 'error')
  } finally {
    isCreatingRouteAsset.value = false
  }
}

async function createItemInRouteScene() {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) return
  const normalizedItemId = buildPrefixedEditorId(createItemForm.value.id || createItemForm.value.name, 'ITEM_')
  if (!normalizedItemId || !createItemForm.value.name.trim() || !createItemForm.value.description.trim()) {
    addNotification('Item requires ID, name and description.', 'error')
    return
  }
  isCreatingRouteAsset.value = true
  try {
    await entityService.createEntity(props.adventureId, {
      entity_id: normalizedItemId,
      entity_type: 'OBJECT',
      scene_id: sceneId,
      name: createItemForm.value.name.trim(),
      description: createItemForm.value.description.trim(),
      item_type: createItemForm.value.item_type,
      is_portable: createItemForm.value.item_type !== 'STATIC',
    })
    showCreateItemForm.value = false
    resetRouteCreateForms()
    await fetchDebugInfo()
    addNotification('Item added to scene.', 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Failed to add item.', 'error')
  } finally {
    isCreatingRouteAsset.value = false
  }
}

async function createExitFromRouteScene() {
  const fromSceneId = String(activeMapSceneId.value || '').trim()
  if (!fromSceneId) return
  if (!createExitForm.value.to_scene_id.trim() || !createExitForm.value.label.trim()) {
    addNotification('Exit requires target scene and label.', 'error')
    return
  }
  isCreatingRouteAsset.value = true
  try {
    await entityService.createExit(props.adventureId, {
      from_scene_id: fromSceneId,
      to_scene_id: createExitForm.value.to_scene_id.trim(),
      label: createExitForm.value.label.trim(),
      exit_type: createExitForm.value.exit_type,
    })
    showCreateExitForm.value = false
    resetRouteCreateForms()
    await fetchDebugInfo()
    addNotification('Exit created.', 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Failed to create exit.', 'error')
  } finally {
    isCreatingRouteAsset.value = false
  }
}

async function deleteRouteScene() {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) return
  const confirmed = window.confirm(`Delete scene ${sceneId}? This also removes linked exits and entities in that scene.`)
  if (!confirmed) return
  isDeletingRouteAsset.value = true
  try {
    await entityService.deleteScene(props.adventureId, sceneId)
    await fetchDebugInfo()
    addNotification('Scene deleted.', 'success')
    router.push({ name: 'adventure-editor', params: { adventureId: props.adventureId }, query: route.query })
  } catch (error: any) {
    addNotification(error?.message || 'Failed to delete scene.', 'error')
  } finally {
    isDeletingRouteAsset.value = false
  }
}

async function deleteRouteExit() {
  const exitId = String(activeMapExitId.value || '').trim()
  if (!exitId) return
  const confirmed = window.confirm(`Delete exit ${exitId}?`)
  if (!confirmed) return
  isDeletingRouteAsset.value = true
  try {
    await entityService.deleteExit(props.adventureId, exitId)
    await fetchDebugInfo()
    addNotification('Exit deleted.', 'success')
    router.push({ name: 'adventure-editor', params: { adventureId: props.adventureId }, query: route.query })
  } catch (error: any) {
    addNotification(error?.message || 'Failed to delete exit.', 'error')
  } finally {
    isDeletingRouteAsset.value = false
  }
}

async function deleteRouteEntity(entityId: string) {
  const normalized = String(entityId || '').trim()
  if (!normalized) return
  const confirmed = window.confirm(`Delete entity ${normalized}?`)
  if (!confirmed) return
  isDeletingRouteAsset.value = true
  try {
    await entityService.deleteEntity(props.adventureId, normalized)
    await fetchDebugInfo()
    addNotification('Entity deleted.', 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Failed to delete entity.', 'error')
  } finally {
    isDeletingRouteAsset.value = false
  }
}

async function saveRouteExit() {
  const exit = routeExitDetails.value
  if (!exit) return
  if (!exitEditForm.value.label.trim()) {
    addNotification('Exit label is required.', 'error')
    return
  }
  isSaving.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'exit',
      target_id: String(exit.id),
      name: exitEditForm.value.label.trim(),
      description: exitEditForm.value.lock_description.trim(),
      exit_type: exitEditForm.value.exit_type,
    })
    await fetchDebugInfo()
    addNotification('Exit updated.', 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Failed to update exit.', 'error')
  } finally {
    isSaving.value = false
  }
}

watch(
  () => route.name,
  (name) => {
    if (name === 'adventure-editor-scene' || name === 'adventure-editor-exit') {
      activeTab.value = 'map'
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="h-screen bg-slate-950 text-slate-200 font-sans flex flex-col relative overflow-x-hidden overflow-y-auto">
    <!-- Ambient Background -->
    <div v-if="debugData?.adventure?.image_url" class="absolute inset-0 pointer-events-none z-0 opacity-20">
      <img :src="ASSET_BASE + debugData.adventure.image_url" class="w-full h-full object-cover blur-3xl scale-110" />
      <div class="absolute inset-0 bg-slate-950/60"></div>
    </div>

    <EditorHeader 
      :adventure="adventure" 
      :adventure-id="adventureId" 
      :cover-source-name="adventure?.cover_source_adventure_name || ''"
      :is-generating="isGenerating"
      @go-back="goBack"
      @stop-generation="stopAllGenerations"
    />

    <main class="flex-grow p-6 max-w-[1400px] mx-auto w-full relative z-10 pb-16">
      <div v-if="isLoading" class="flex flex-col justify-center items-center py-40 gap-6">
        <div class="relative w-20 h-20">
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500/20"></div>
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin"></div>
        </div>
        <p class="text-xs font-bold text-emerald-500 uppercase tracking-[0.3em]">Loading Chronicles...</p>
      </div>
      
      <div v-else class="space-y-6">
        <nav class="lg:hidden flex gap-2 overflow-x-auto pb-2">
          <button
            v-for="tab in editorTabs"
            :key="tab.key"
            @click="activeTab = tab.key"
            :class="[
              'shrink-0 px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-[0.15em] transition-all border',
              activeTab === tab.key
                ? 'bg-emerald-600/80 border-emerald-500 text-white'
                : 'bg-slate-900/50 border-white/10 text-slate-400 hover:text-slate-200'
            ]"
          >
            {{ tab.label }}
          </button>
        </nav>

        <div class="lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-6">
          <aside class="hidden lg:block">
            <div class="sticky top-24 bg-slate-900/40 border border-white/5 rounded-2xl p-3 backdrop-blur-md">
              <div class="space-y-1">
                <button
                  v-for="tab in editorTabs"
                  :key="tab.key"
                  @click="activeTab = tab.key"
                  :class="[
                    'w-full text-left px-3 py-2 rounded-xl text-xs font-black uppercase tracking-[0.18em] transition-all',
                    activeTab === tab.key
                      ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-lg'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  ]"
                >
                  {{ tab.label }}
                </button>
              </div>
            </div>
          </aside>

          <div class="space-y-10 min-w-0">
            <WorldTab
              v-if="activeTab === 'world'"
              :form="form"
              :adventure="adventure"
              :debug-data="debugData"
              :reference-options="referenceOptions"
              :editing-field="editingField"
              :temp-value="tempValue"
              :is-saving="isSaving"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :fix-newlines="fixNewlines"
              @quick-regen="quickRegenerateVisual"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @open-text-edit="openTextEdit"
              @toggle-menu="toggleMenu"
              @start-edit="startEditing"
              @save-field="saveField"
              @cancel-edit="cancelEditing"
              @update:temp-value="tempValue = $event"
              @update:pacing="form.time_per_turn = $event"
              @update:mode="form.rule_enforcement_mode = $event as any"
              @save-changes="saveChanges"
            />

            <ItemsTab 
              v-if="activeTab === 'items'"
              :editor-objects="editorObjects"
              :editor-switches="editorSwitches"
              :editor-containers="editorContainers"
              :editor-text-logs="editorTextLogs"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :rule-enforcement-mode="form.rule_enforcement_mode"
              :visuals-cache-version="visualsCacheVersion"
              @quick-regen="quickRegenerateVisual"
              @regen-all="requestRegenerateAll"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @open-text-edit="openTextEdit"
              @toggle-menu="toggleMenu"
              @handle-hover="handleHover"
              @clear-hover="clearHover"
            />

            <InhabitantsTab
              v-if="activeTab === 'inhabitants'"
              :form="form"
              :adventure="adventure"
              :debug-data="debugData"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :editor-npcs="editorNpcs"
              :rule-enforcement-mode="form.rule_enforcement_mode"
              :visuals-cache-version="visualsCacheVersion"
              @quick-regen="quickRegenerateVisual"
              @regen-all="requestRegenerateAll"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @open-text-edit="openTextEdit"
              @toggle-menu="toggleMenu"
              @handle-hover="handleHover"
              @clear-hover="clearHover"
            />

            <ScenesTab
              v-if="activeTab === 'scenes'"
              :editor-scenes="editorScenes"
              :debug-data="debugData"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :visuals-cache-version="visualsCacheVersion"
              :is-setting-start-scene="isSettingStartScene"
              @quick-regen="quickRegenerateVisual"
              @regen-all="requestRegenerateAll"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @open-text-edit="openTextEdit"
              @set-start-scene="setStartScene"
              @toggle-menu="toggleMenu"
              @handle-hover="handleHover"
              @clear-hover="clearHover"
            />

            <MapTab
              v-if="activeTab === 'map'"
              :debug-data="debugData"
              :editor-scenes="editorScenes"
              :visuals-cache-version="visualsCacheVersion"
              :active-scene-id="activeMapSceneId"
              :active-exit-id="activeMapExitId"
              @open-scene="openSceneEditorRoute"
              @open-exit="openExitEditorRoute"
            />

            <section
              v-if="activeTab === 'map' && canShowSceneRoutePanel"
              class="bg-slate-900/40 border border-white/10 rounded-2xl p-5 space-y-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div>
                  <p class="text-xs uppercase tracking-widest text-emerald-300">Scene Route</p>
                  <h3 class="text-lg font-bold text-white">{{ routeSceneDetails?.label || routeSceneDetails?.id || activeMapSceneId }}</h3>
                  <p class="text-sm text-slate-300 mt-1">{{ routeSceneDetails?.description || 'No description.' }}</p>
                </div>
                <button
                  class="px-3 py-2 text-xs font-bold rounded-lg border border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50"
                  :disabled="isDeletingRouteAsset"
                  @click="deleteRouteScene"
                >
                  Delete Scene
                </button>
              </div>

              <div class="grid md:grid-cols-3 gap-4">
                <div class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
                  <div class="flex items-center justify-between mb-2">
                    <p class="text-xs font-bold uppercase tracking-wide text-slate-300">NPCs ({{ routeSceneNpcs.length }})</p>
                    <button class="text-xs text-emerald-300" @click="showCreateNpcForm = !showCreateNpcForm">+ Add</button>
                  </div>
                  <ul class="space-y-1 text-sm text-slate-300 max-h-52 overflow-auto">
                    <li v-for="npc in routeSceneNpcs" :key="npc.id" class="flex items-center justify-between gap-2">
                      <span class="truncate">{{ npc.name || npc.id }}</span>
                      <div class="flex items-center gap-2">
                        <span class="text-xs text-slate-500">{{ npc.id }}</span>
                        <button class="text-xs text-red-300 hover:text-red-200" @click="deleteRouteEntity(npc.id)">Delete</button>
                      </div>
                    </li>
                    <li v-if="routeSceneNpcs.length === 0" class="text-xs text-slate-500">No NPCs in this scene.</li>
                  </ul>
                  <div v-if="showCreateNpcForm" class="mt-3 space-y-2">
                    <div class="flex gap-2">
                      <input v-model="createNpcForm.id" class="flex-1 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm" placeholder="NPC_ID" />
                      <button class="px-2 py-1 text-xs rounded border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10" @click="autoFillNpcId">Auto ID</button>
                    </div>
                    <input v-model="createNpcForm.name" class="w-full bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm" placeholder="Name" />
                    <ReferenceTextarea
                      v-model="createNpcForm.description"
                      :rows="2"
                      :options="referenceOptions"
                      class-name="w-full bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm"
                      placeholder="Description"
                    />
                    <button class="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded px-2 py-1 disabled:opacity-50" :disabled="isCreatingRouteAsset" @click="createNpcInRouteScene">Create NPC</button>
                  </div>
                </div>

                <div class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
                  <div class="flex items-center justify-between mb-2">
                    <p class="text-xs font-bold uppercase tracking-wide text-slate-300">Items/Switches ({{ routeSceneObjects.length }})</p>
                    <button class="text-xs text-emerald-300" @click="showCreateItemForm = !showCreateItemForm">+ Add</button>
                  </div>
                  <ul class="space-y-1 text-sm text-slate-300 max-h-52 overflow-auto">
                    <li v-for="obj in routeSceneObjects" :key="obj.id" class="flex items-center justify-between gap-2">
                      <span class="truncate">{{ obj.name || obj.id }}</span>
                      <div class="flex items-center gap-2">
                        <span class="text-xs text-slate-500">{{ obj.item_type || 'OBJECT' }}</span>
                        <button class="text-xs text-red-300 hover:text-red-200" @click="deleteRouteEntity(obj.id)">Delete</button>
                      </div>
                    </li>
                    <li v-if="routeSceneObjects.length === 0" class="text-xs text-slate-500">No items in this scene.</li>
                  </ul>
                  <div v-if="showCreateItemForm" class="mt-3 space-y-2">
                    <div class="flex gap-2">
                      <input v-model="createItemForm.id" class="flex-1 bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm" placeholder="ITEM_ID" />
                      <button class="px-2 py-1 text-xs rounded border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10" @click="autoFillItemId">Auto ID</button>
                    </div>
                    <input v-model="createItemForm.name" class="w-full bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm" placeholder="Name" />
                    <select v-model="createItemForm.item_type" class="w-full bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm">
                      <option value="PICKABLE">PICKABLE</option>
                      <option value="KEY">KEY</option>
                      <option value="WEAPON">WEAPON</option>
                      <option value="CONTAINER">CONTAINER</option>
                      <option value="READABLE">READABLE</option>
                      <option value="SWITCH">SWITCH</option>
                      <option value="STATIC">STATIC</option>
                    </select>
                    <ReferenceTextarea
                      v-model="createItemForm.description"
                      :rows="2"
                      :options="referenceOptions"
                      class-name="w-full bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm"
                      placeholder="Description"
                    />
                    <button class="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded px-2 py-1 disabled:opacity-50" :disabled="isCreatingRouteAsset" @click="createItemInRouteScene">Create Item</button>
                  </div>
                </div>

                <div class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
                  <div class="flex items-center justify-between mb-2">
                    <p class="text-xs font-bold uppercase tracking-wide text-slate-300">Exits ({{ routeSceneExits.length }})</p>
                    <button class="text-xs text-emerald-300" @click="showCreateExitForm = !showCreateExitForm">+ Add</button>
                  </div>
                  <ul class="space-y-1 text-sm text-slate-300 max-h-52 overflow-auto">
                    <li v-for="worldExit in routeSceneExits" :key="worldExit.id" class="flex items-center justify-between gap-2">
                      <button class="truncate text-left hover:text-emerald-300" @click="openExitEditorRoute(worldExit.id)">{{ worldExit.label || worldExit.id }}</button>
                      <span class="text-xs text-slate-500">{{ worldExit.exit_type || 'one_way' }}</span>
                    </li>
                    <li v-if="routeSceneExits.length === 0" class="text-xs text-slate-500">No exits for this scene.</li>
                  </ul>
                  <div v-if="showCreateExitForm" class="mt-3 space-y-2">
                    <EntityReferenceCombobox
                      v-model="createExitForm.to_scene_id"
                      :options="sceneReferenceOptions.filter((scene) => scene.id !== activeMapSceneId)"
                      placeholder="Select destination scene"
                      :enable-search="true"
                    />
                    <input v-model="createExitForm.label" class="w-full bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm" placeholder="Exit label" />
                    <select v-model="createExitForm.exit_type" class="w-full bg-slate-900 border border-white/10 rounded px-2 py-1 text-sm">
                      <option value="one_way">one_way</option>
                      <option value="bidirectional">bidirectional</option>
                    </select>
                    <button class="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded px-2 py-1 disabled:opacity-50" :disabled="isCreatingRouteAsset" @click="createExitFromRouteScene">Create Exit</button>
                  </div>
                </div>
              </div>
            </section>

            <section
              v-if="activeTab === 'map' && canShowExitRoutePanel"
              class="bg-slate-900/40 border border-white/10 rounded-2xl p-5 space-y-4"
            >
              <div class="flex items-start justify-between gap-4">
                <div>
                  <p class="text-xs uppercase tracking-widest text-emerald-300">Exit Route</p>
                  <h3 class="text-lg font-bold text-white">{{ routeExitDetails?.label || routeExitDetails?.id || activeMapExitId }}</h3>
                  <p class="text-sm text-slate-300 mt-1">
                    {{ routeExitDetails?.from_scene_id }} -> {{ routeExitDetails?.to_scene_id }}
                  </p>
                </div>
                <button
                  class="px-3 py-2 text-xs font-bold rounded-lg border border-red-500/40 text-red-300 hover:bg-red-500/10 disabled:opacity-50"
                  :disabled="isDeletingRouteAsset"
                  @click="deleteRouteExit"
                >
                  Delete Exit
                </button>
              </div>

              <div class="grid md:grid-cols-2 gap-3">
                <label class="text-xs text-slate-300 space-y-1">
                  <span>Label</span>
                  <input v-model="exitEditForm.label" class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm" />
                </label>
                <label class="text-xs text-slate-300 space-y-1">
                  <span>Type</span>
                  <select v-model="exitEditForm.exit_type" class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm">
                    <option value="one_way">one_way</option>
                    <option value="bidirectional">bidirectional</option>
                  </select>
                </label>
              </div>

              <label class="text-xs text-slate-300 space-y-1 block">
                <span>Lock Description</span>
                <ReferenceTextarea
                  v-model="exitEditForm.lock_description"
                  :rows="3"
                  :options="referenceOptions"
                  class-name="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm"
                />
              </label>

              <div class="flex justify-end">
                <button class="px-3 py-2 text-xs font-bold rounded bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50" :disabled="isSaving" @click="saveRouteExit">
                  Save Exit
                </button>
              </div>
            </section>

            <QuestTab
              v-if="activeTab === 'quest'"
              :adventure="adventure"
              :reference-options="referenceOptions"
              @update-quests="handleUpdateQuests"
              @notify="addNotification"
            />

            <AwardsTab
              v-if="activeTab === 'awards'"
              :adventure="adventure"
              :reference-options="referenceOptions"
              @update-awards="handleUpdateAwards"
              @notify="addNotification"
            />

            <VisualsTab
              v-if="activeTab === 'visuals'"
              :form="form"
              :adventure="adventure"
              :image-styles-catalog="imageStylesCatalog"
              @update:style="form.selected_style_id = $event"
              @save-changes="saveChanges"
            />

            <ToneTab
              v-if="activeTab === 'tone'"
              :form="form"
              :adventure="adventure"
              :debug-data="debugData"
              :tone-catalog="toneCatalog"
              :is-saving="isSaving"
              @update:tone="form.selected_tone_id = $event"
              @save-changes="saveChanges"
            />

            <AdvancedTab 
              v-if="activeTab === 'advanced'"
              :form="form"
              @update:generator="form.is_adventure_generator = $event; saveChanges()"
              @update:dynamic-items="form.allow_dynamic_items = $event; saveChanges()"
              @update:can-damage-npcs="form.can_damage_npcs = $event; saveChanges()"
              @update:npcs-can-damage-protagonist="form.npcs_can_damage_protagonist = $event; saveChanges()"
              @show-debug="showDebug = true"
              @save-changes="saveChanges"
            />
          </div>
        </div>
      </div>
    </main>

    <EntityTooltip 
      :hovered-entity="hoveredEntity"
      :active-menu-id="activeMenuId"
      :mouse-pos="mousePos"
      :tooltip-align-top="tooltipAlignTop"
      :window-height="windowHeight"
      :rule-enforcement-mode="form.rule_enforcement_mode"
      :build-visual-image-url="buildVisualImageUrl"
      :fix-newlines="fixNewlines"
    />

    <ManualVisionModal 
      :show="showPromptDialog"
      :selected-visual="selectedVisual"
      v-model:visual-prompt="visualPrompt"
      v-model:use-advanced-model="useAdvancedModel"
      :is-suggesting-prompt="isSuggestingPrompt"
      :is-regenerating="isRegenerating"
      :upload-limits="visualService.UPLOAD_LIMITS"
      :format-bytes="formatBytes"
      :fix-newlines="fixNewlines"
      @close="showPromptDialog = false"
      @suggest="suggestPrompt"
      @regenerate="regenerateVisual"
      @cancel-regen="cancelRegeneration"
    />

    <EditEntityModal 
      :show="showEditModal"
      :context="editEntityContext"
      :initial-form="editForm"
      :reference-options="referenceOptions"
      :rule-enforcement-mode="form.rule_enforcement_mode"
      :is-saving="isSavingText"
      :adventure-id="adventureId"
      @close="showEditModal = false"
      @save="saveEntityText"
    />

    <DataDebugModal 
      :show="showDebug"
      :adventure="adventure"
      :debug-data="debugData"
      @close="showDebug = false"
    />

    <div
      v-if="showRegenerateAllConfirmDialog"
      class="fixed inset-0 z-[90] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
      @click="cancelRegenerateAllDialog"
    >
      <div class="w-full max-w-lg rounded-2xl border border-amber-500/25 bg-slate-900 shadow-2xl overflow-hidden" @click.stop>
        <div class="px-6 py-5 border-b border-white/10 flex items-start gap-3">
          <div class="w-10 h-10 rounded-full border border-amber-400/40 bg-amber-500/15 flex items-center justify-center shrink-0">
            <i class="ra ra-warning text-amber-300"></i>
          </div>
          <div>
            <h3 class="text-lg font-black text-white">Confirm Visual Overwrite</h3>
            <p class="text-xs text-slate-400 mt-1">This action will replace existing generated images.</p>
          </div>
        </div>

        <div class="px-6 py-5 space-y-3">
          <p class="text-sm text-slate-200">
            Regenerate all
            <span class="font-bold text-amber-300">{{ getRegenerateKindLabel(pendingBatchRegeneration?.kind || '') }}</span>
            visuals now?
          </p>
          <p class="text-xs text-slate-400">
            Existing images in this section will be overwritten one by one.
          </p>
        </div>

        <div class="px-6 py-4 border-t border-white/10 flex items-center justify-end gap-3">
          <button
            class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors"
            @click="cancelRegenerateAllDialog"
          >
            Cancel
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-amber-500 text-slate-950 text-sm font-black uppercase tracking-wider hover:bg-amber-400 transition-colors"
            @click="confirmRegenerateAll"
          >
            Yes, regenerate all
          </button>
        </div>
      </div>
    </div>

    <NotificationToast 
      :notifications="notifications"
      @close="notificationService.remove($event)"
    />

    <input
      ref="uploadInput"
      type="file"
      accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
      class="hidden"
      @change="uploadSelectedVisual"
    />
  </div>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

input, textarea {
  transition: all 0.3s ease;
}

.shadow-inner {
  box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.4);
}
</style>
