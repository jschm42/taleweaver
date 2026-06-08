<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { adventureService } from '@/services/adventureService'
import { visualService } from '@/services/visualService'
import type { VisualKind } from '@/services/visualService'
import { entityService } from '@/services/entityService'
import { notificationService } from '@/services/notificationService'

// Icons & Assets

// Components
import EditorHeader from '@/components/editor/EditorHeader.vue'
import { Save, X, Trash2, ArrowLeft } from 'lucide-vue-next'
import WorldTab from '@/components/editor/WorldTab.vue'
import ProtagonistTab from '@/components/editor/ProtagonistTab.vue'
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
import ItemTypeSelectorModal from '@/components/editor/ItemTypeSelectorModal.vue'
import AddExistingItemModal from '@/components/editor/AddExistingItemModal.vue'
import ManualVisionModal from '@/components/editor/ManualVisionModal.vue'
import DataDebugModal from '@/components/editor/DataDebugModal.vue'
import CreateSceneForm from '@/components/editor/CreateSceneForm.vue'
import SceneRoutePanel from '@/components/editor/SceneRoutePanel.vue'
import ExitRoutePanel from '@/components/editor/ExitRoutePanel.vue'
import EditExitModal from '@/components/editor/EditExitModal.vue'

// Utilities
import { 
  fixNewlines, 
  isNpcEntity, 
  isObjectEntity, 
  mergeUniqueById, 
  formatBytes,
  makeSafeFilename,
  getImageExtension,
  itemTypePrefix,
  buildPrefixedEditorId,
  sanitizeEditorIdToken,
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
const isGeneratingField = ref<Record<string, boolean>>({})
const activeAbortControllers = ref<Map<string, AbortController>>(new Map())
const isGenerating = computed(() => {
  return isRegenerating.value || 
         Object.values(isQuickGenerating.value).some(Boolean) || 
         Object.values(isBatchGenerating.value).some(Boolean)
})

const isSavingText = ref(false)
const showEditModal = ref(false)
const editEntityContext = ref<{ type: string; id: string } | null>(null)
const isCreateEntityMode = ref(false)
const createEntitySceneId = ref<string | null>(null)
const createEntityType = ref<'npc' | 'object' | null>(null)
const pendingProtagonistAssignment = ref<{ type: 'equipment' | 'inventory'; key?: string; index?: number } | null>(null)
const showItemTypeSelector = ref(false)
const itemTypeSelectorSceneLabel = ref('')
const showAddExistingItemModal = ref(false)
const addExistingItemKind = ref<'items' | 'switch' | 'container' | 'text-log' | 'npc'>('items')
const showExitModal = ref(false)
const isCreateExitMode = ref(false)
const activeEditExitId = ref<string | null>(null)
const exitModalForm = ref({
  from_scene_id: '',
  to_scene_id: '',
  label: '',
  exit_type: 'one_way' as 'one_way' | 'bidirectional',
  lock_description: '',
  code_to_unlock: '',
  item_to_unlock: '',
  rule_to_unlock: '',
})
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
  item_type: 'DEFAULT',
  is_portable: true,
  locked: false,
  code_to_unlock: '',
  item_to_unlock: '',
  inventory_input: [] as string[],
  text_log_content: '',
  text_log_format: 'DOCUMENT',
  entity_id: '',
  wearable_slots_input: [],
  combination_ingredients_input: [] as string[],
  switch_states_json: '[]',
  switch_initial_state: '',
  switch_transitions_json: '[]',
  effects_hp: 0,
  effects_stamina: 0,
  effects_mana: 0,
  stat_modifier_strength: 0,
  is_item_type_fixed: false,
  is_wearable_slots_fixed: false,
})

function closeEditEntityModal() {
  showEditModal.value = false
  editEntityContext.value = null
  isCreateEntityMode.value = false
  createEntitySceneId.value = null
  createEntityType.value = null
  pendingProtagonistAssignment.value = null
}

function openAddExistingItem(kind: 'items' | 'switch' | 'container' | 'text-log' | 'npc') {
  addExistingItemKind.value = kind
  showAddExistingItemModal.value = true
}

function closeAddExistingItemModal() {
  showAddExistingItemModal.value = false
}

const editorAllObjects = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred)
})

function matchesItemTypeFilter(itemType: string, kind: 'items' | 'switch' | 'container' | 'text-log' | 'npc'): boolean {
  const t = String(itemType || '').toUpperCase()
  switch (kind) {
    case 'switch':
      return t === 'SWITCH'
    case 'container':
      return t === 'CONTAINER'
    case 'text-log':
      return t === 'READABLE'
    case 'items':
      return t !== 'SWITCH' && t !== 'CONTAINER' && t !== 'READABLE'
    case 'npc':
    default:
      return false
  }
}

const addExistingItemOptions = computed<any[]>(() => {
  const sId = String(activeMapSceneId.value || '').trim()
  if (addExistingItemKind.value === 'npc') {
    return editorNpcs.value.filter((npc: any) => {
      if (!npc?.id) return false
      if (sId && String(npc.current_scene_id || '') === sId) return false
      return true
    })
  }
  return editorAllObjects.value.filter((obj: any) => {
    if (!obj?.id) return false
    if (sId && String(obj.current_scene_id || '') === sId) return false
    return matchesItemTypeFilter(obj.item_type, addExistingItemKind.value)
  })
})

async function handleAddExistingItemSelected(itemId: string) {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) {
    addNotification('No active scene selected.', 'error')
    return
  }
  const candidateId = String(itemId || '').trim().toUpperCase()
  if (!candidateId) {
    addNotification('No entry selected.', 'error')
    return
  }
  const isNpc = addExistingItemKind.value === 'npc'
  isSavingText.value = true
  promptError.value = ''
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: isNpc ? 'npc' : 'object',
      target_id: candidateId,
      current_scene_id: sceneId,
    })
    showAddExistingItemModal.value = false
    await fetchDebugInfo()
    addNotification(isNpc ? 'NPC placed in scene.' : 'Item placed in scene.', 'success')
  } catch (error: any) {
    promptError.value = error?.message || (isNpc ? 'Failed to place NPC in scene.' : 'Failed to place item in scene.')
    addNotification(promptError.value, 'error')
  } finally {
    isSavingText.value = false
  }
}

function openCreateItem(itemType?: string) {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) {
    addNotification('No active scene selected for item creation.', 'error')
    return
  }
  createEntitySceneId.value = sceneId
  createEntityType.value = 'object'
  if (itemType) {
    handleItemTypeSelected(itemType, true)
  } else {
    showItemTypeSelector.value = true
  }
}

function createNewItemForProtagonist(target: { type: 'equipment' | 'inventory'; key?: string; index?: number }) {
  const startSceneId = debugData.value?.adventure?.start_scene_id || (debugData.value?.scenes?.[0]?.id)
  if (!startSceneId) {
    addNotification('No scenes exist in the chronicle to associate the item with.', 'error')
    return
  }
  pendingProtagonistAssignment.value = target
  createEntitySceneId.value = startSceneId
  createEntityType.value = 'object'
  
  if (target.type === 'equipment' && target.key) {
    const itemType = target.key === 'MainHand' ? 'WEAPON' : 'WEARABLE'
    let mappedSlot = target.key
    if (target.key === 'Arms') {
      mappedSlot = 'Wrist'
    } else if (target.key === 'Ring_1' || target.key === 'Ring_2') {
      mappedSlot = 'Finger'
    }
    handleItemTypeSelected(itemType, true, [mappedSlot], true)
  } else {
    showItemTypeSelector.value = true
  }
}

function handleItemTypeSelected(itemType: string, isFixed = false, preselectedSlots: string[] = [], isSlotsFixed = false) {
  showItemTypeSelector.value = false
  const sceneId = String(createEntitySceneId.value || activeMapSceneId.value || '').trim()
  if (!sceneId) return
  isCreateEntityMode.value = true
  createEntityType.value = 'object'
  editEntityContext.value = { type: 'object', id: `NEW_${String(itemType).toUpperCase()}` }
  const prefix = itemTypePrefix(String(itemType).toUpperCase())
  const randomSuffix = Math.random().toString(36).slice(2, 8).toUpperCase()
  const defaultId = `${sanitizeEditorIdToken(prefix)}${randomSuffix}`

  editForm.value = {
    name: 'New Item',
    description: 'A mysterious object found in this scene.',
    teaser: '',
    hp: 0,
    stamina: 0,
    mana: 0,
    goal: '',
    character: '',
    is_killable: true,
    item_type: itemType,
    is_portable: String(itemType).toUpperCase() !== 'SWITCH',
    locked: false,
    code_to_unlock: '',
    item_to_unlock: '',
    inventory_input: [],
    text_log_content: '',
    text_log_format: 'DOCUMENT',
    entity_id: defaultId,
    wearable_slots_input: preselectedSlots,
    combination_ingredients_input: [],
    switch_states_json: '[]',
    switch_initial_state: '',
    switch_transitions_json: '[]',
    effects_hp: 0,
    effects_stamina: 0,
    effects_mana: 0,
    stat_modifier_strength: 0,
    is_item_type_fixed: isFixed,
    is_wearable_slots_fixed: isSlotsFixed,
  }
  showEditModal.value = true
}

function closeExitEditModal() {
  showExitModal.value = false
  isCreateExitMode.value = false
  activeEditExitId.value = null
  exitModalForm.value = {
    from_scene_id: '',
    to_scene_id: '',
    label: '',
    exit_type: 'one_way',
    lock_description: '',
  }
}

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const promptError = ref('')
const showDebug = ref(false)
const activeTab = ref<'world' | 'protagonist' | 'items' | 'visuals' | 'inhabitants' | 'scenes' | 'map' | 'quest' | 'awards' | 'tone' | 'advanced'>('world')
const sceneEditorReturnTab = ref<'world' | 'protagonist' | 'items' | 'visuals' | 'inhabitants' | 'scenes' | 'map' | 'quest' | 'awards' | 'tone' | 'advanced'>('scenes')
const exitEditorReturnTab = ref<'world' | 'protagonist' | 'items' | 'visuals' | 'inhabitants' | 'scenes' | 'map' | 'quest' | 'awards' | 'tone' | 'advanced'>('map')

const selectedVisual = ref<{ kind: VisualKind; id: string; label: string; description: string; hint: string } | null>(null)
const selectedUploadTarget = ref<{ kind: VisualKind; id: string; label: string } | null>(null)
const visualPrompt = ref('')
const showPromptDialog = ref(false)
const isRegenerating = ref(false)
const isSuggestingPrompt = ref(false)
const useAdvancedModel = ref(false)
const showRegenerateAllConfirmDialog = ref(false)
const pendingBatchRegeneration = ref<{ kind: string; missingOnly: boolean } | null>(null)
type PendingDeleteTarget = {
  kind: 'scene' | 'exit' | 'entity'
  id: string
  title: string
  description: string
}
const showDeleteConfirmDialog = ref(false)
const pendingDeleteTarget = ref<PendingDeleteTarget | null>(null)
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
  { key: 'protagonist', label: 'Protagonist' },
  { key: 'map', label: 'Map' },
  { key: 'scenes', label: 'Scenes' },
  { key: 'inhabitants', label: 'Inhabitants' },
  { key: 'items', label: 'Items' },
  { key: 'quest', label: 'Quests' },
  { key: 'awards', label: 'Awards' },
  { key: 'visuals', label: 'Visual Style' },
  { key: 'tone', label: 'Tone' },
  { key: 'advanced', label: 'Advanced' },
] as const

function getTabLabel(key: string): string {
  const tab = editorTabs.find((t) => t.key === key)
  return tab ? tab.label : 'Scenes'
}

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

async function handleGenerateField(field: string) {
  if (!props.adventureId) return
  isGeneratingField.value[field] = true
  try {
    const result = await adventureService.generateTemplateField(props.adventureId, {
      field: field,
      title: form.value.title,
      original_prompt: form.value.original_prompt,
      plot: form.value.plot,
      rules: form.value.rules,
      intro_text: form.value.intro_text,
      walkthrough: form.value.walkthrough,
      completed_condition: form.value.completed_condition,
      gameover_condition: form.value.gameover_condition,
      tts_director_notes: form.value.tts_director_notes
    })
    tempValue.value = fixNewlines(result.generated_text)
    addNotification(`AI generated content for ${field}.`, 'success')
  } catch (error: any) {
    addNotification(error?.message || `Failed to generate ${field}.`, 'error')
  } finally {
    isGeneratingField.value[field] = false
  }
}

async function saveField() {
  if (!editingField.value) return
  const trimmed = tempValue.value.trim()

  const FIELD_LIMITS: Record<string, number> = {
    title: 50,
    version: 15,
    teaser: 300,
    plot: 5000,
    rules: 5000,
    intro_text: 20000,
    walkthrough: 20000,
    completed_condition: 2000,
    gameover_condition: 2000,
    tts_director_notes: 5000
  }

  const limit = FIELD_LIMITS[editingField.value]
  if (limit !== undefined && tempValue.value.length > limit) {
    addNotification(`Field content exceeds limit of ${limit} characters.`, 'error')
    return
  }

  if (editingField.value === 'title') {
    if (!trimmed) {
      addNotification('Chronicle title is required.', 'error')
      return
    }
  }
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

async function handleCreateScene(data: { sceneId: string; name: string; description: string }) {
  isSavingText.value = true
  try {
    await entityService.createScene(props.adventureId, {
      scene_id: data.sceneId,
      label: data.name,
      description: data.description,
    })
    await fetchDebugInfo()
    addNotification(`Scene "${data.name}" created.`, 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Failed to create scene.', 'error')
  } finally {
    isSavingText.value = false
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
  const metadata = selectedObject?.metadata_json || {}
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
    item_type: selectedObject?.item_type || 'DEFAULT',
    is_portable: selectedObject?.is_portable !== false,
    locked: selectedObject?.locked === true,
    code_to_unlock: selectedObject?.code_to_unlock || '',
    item_to_unlock: selectedObject?.item_to_unlock || '',
    inventory_input: Array.isArray(selectedObject?.inventory)
      ? [...selectedObject.inventory.map((item: any) => typeof item === 'string' ? item : (item?.id || ''))]
      : [],
    text_log_content: fixNewlines(metadata?.text_log_content || ''),
    text_log_format: String(metadata?.text_log_format || selectedObject?.text_log_format || 'DOCUMENT').trim().toUpperCase(),
    entity_id: String(selectedObject?.id || id || ''),
    wearable_slots_input: selectedObject?.wearable_slots || [],
    combination_ingredients_input: Array.isArray(selectedObject?.combination_ingredients)
      ? [...selectedObject.combination_ingredients]
      : (metadata?.combination_ingredients ? [...metadata.combination_ingredients] : []),
    switch_states_json: JSON.stringify(selectedObject?.switch_states || metadata?.switch_states || [], null, 2),
    switch_initial_state: String(selectedObject?.switch_initial_state || metadata?.switch_initial_state || ''),
    switch_transitions_json: JSON.stringify(selectedObject?.switch_transitions || metadata?.switch_transitions || [], null, 2),
    effects_hp: selectedObject?.effects?.hp || metadata?.effects?.hp || 0,
    effects_stamina: selectedObject?.effects?.stamina || metadata?.effects?.stamina || 0,
    effects_mana: selectedObject?.effects?.mana || metadata?.effects?.mana || 0,
    stat_modifier_strength: selectedObject?.stat_modifier_strength || metadata?.stat_modifier_strength || 0,
    is_item_type_fixed: false,
    is_wearable_slots_fixed: false,
  }
  showEditModal.value = true
}

async function saveEntityText(data: any) {
  if (!editEntityContext.value) return

  if (isCreateEntityMode.value) {
    const sceneId = String(createEntitySceneId.value || activeMapSceneId.value || '').trim()
    if (!sceneId) {
      addNotification('No active scene selected for creation.', 'error')
      return
    }

    const entityName = String(data.name || '').trim()
    const entityDescription = String(data.description || '').trim()
    if (!entityName || !entityDescription) {
      addNotification('Name and description are required.', 'error')
      return
    }
    if (entityName.length > 50) {
      addNotification('Name must be 50 characters or less.', 'error')
      return
    }
    if (entityDescription.length > 1000) {
      addNotification('Description must be 1000 characters or less.', 'error')
      return
    }

    const creationType = createEntityType.value
    if (!creationType) {
      addNotification('Missing creation type.', 'error')
      return
    }

    let candidateId = String(data.entity_id || '').trim().toUpperCase()
    if (!candidateId) {
      addNotification('Entity ID is required.', 'error')
      return
    }
    if (candidateId.length > 30) {
      addNotification('Entity ID must be 30 characters or less.', 'error')
      return
    }

    const takenIds = new Set(referenceOptions.value.map((entry) => String(entry.id || '').toUpperCase()))
    if (takenIds.has(candidateId)) {
      addNotification(`An entity with ID "${candidateId}" already exists.`, 'error')
      return
    }

    isSavingText.value = true
    promptError.value = ''
    try {
      if (creationType === 'npc') {
        await entityService.createEntity(props.adventureId, {
          entity_id: candidateId,
          entity_type: 'NPC',
          scene_id: sceneId,
          name: entityName,
          description: entityDescription,
          hp: Number(data.hp || 20),
          stamina: Number(data.stamina || 20),
          mana: Number(data.mana || 20),
          goal: String(data.goal || '').trim() || undefined,
          character: String(data.character || '').trim() || undefined,
          is_killable: Boolean(data.is_killable),
        })
      } else {
        const itemType = String(data.item_type || 'DEFAULT').toUpperCase()
        if (itemType === 'READABLE' && !String(data.text_log_content || '').trim()) {
          addNotification('Readable items require text-log content.', 'error')
          return
        }

        const createPayload: any = {
          entity_id: candidateId,
          entity_type: 'OBJECT',
          scene_id: sceneId,
          name: entityName,
          description: entityDescription,
          item_type: itemType,
          is_portable: itemType !== 'SWITCH',
          inventory: data.inventory || [],
          wearable_slots: data.wearable_slots || undefined,
          combination_ingredients: data.combination_ingredients || undefined,
          stat_modifier_strength: data.stat_modifier_strength || undefined,
        }
        if (itemType === 'READABLE') {
          createPayload.metadata_json = {
            text_log_content: String(data.text_log_content || '').trim(),
            text_log_format: String(data.text_log_format || 'DOCUMENT').toUpperCase(),
          }
        }
        if (itemType === 'SWITCH') {
          createPayload.metadata_json = {
            ...(createPayload.metadata_json || {}),
            switch_states: data.switch_states || [],
            switch_initial_state: data.switch_initial_state || '',
            switch_transitions: data.switch_transitions || [],
          }
        }
        if (itemType === 'CONSUMABLE') {
          createPayload.metadata_json = {
            ...(createPayload.metadata_json || {}),
            effects: data.effects || {},
          }
        }
        await entityService.createEntity(props.adventureId, createPayload)
      }

      if (pendingProtagonistAssignment.value) {
        const target = pendingProtagonistAssignment.value
        const p = debugData.value?.protagonist
        if (p) {
          if (target.type === 'equipment' && target.key) {
            const currentEquipment = p.equipment || {}
            const updatedEquipment = Object.entries(currentEquipment).reduce((acc: any, [k, v]: [string, any]) => {
              acc[k] = v ? (typeof v === 'string' ? v : (v?.id || null)) : null
              return acc
            }, {})
            updatedEquipment[target.key] = candidateId
            await saveProtagonistField('equipment', updatedEquipment)
          } else if (target.type === 'inventory') {
            const currentInventory = p.inventory || []
            const idsList = currentInventory.map((i: any) => typeof i === 'string' ? i : (i?.id || ''))
            if (target.index !== undefined && target.index >= 0 && target.index < idsList.length) {
              idsList[target.index] = candidateId
            } else {
              idsList.push(candidateId)
            }
            await saveProtagonistField('inventory', idsList)
          }
        }
      }

      closeEditEntityModal()
      await fetchDebugInfo()
      addNotification('Entity created.', 'success')
    } catch (error: any) {
      promptError.value = error?.message || 'Failed to create entity.'
      addNotification(promptError.value, 'error')
    } finally {
      isSavingText.value = false
    }
    return
  }
  
  const entityName = String(data.name || '').trim()
  const entityDescription = String(data.description || '').trim()
  if (!entityName || !entityDescription) {
    addNotification('Name and description are required.', 'error')
    return
  }
  if (entityName.length > 50) {
    addNotification('Name must be 50 characters or less.', 'error')
    return
  }
  if (entityDescription.length > 1000) {
    addNotification('Description must be 1000 characters or less.', 'error')
    return
  }

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

  isSavingText.value = true
  promptError.value = ''
  try {
    const oldId = editEntityContext.value.id
    const newId = data.entity_id ? String(data.entity_id).trim().toUpperCase() : ''

    await entityService.saveEntityText(props.adventureId, {
      target_type: editEntityContext.value.type,
      target_id: oldId,
      new_id: newId || undefined,
      name: data.name,
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
      wearable_slots: editEntityContext.value.type === 'object' ? data.wearable_slots : undefined,
      combination_ingredients: editEntityContext.value.type === 'object' ? data.combination_ingredients : undefined,
      switch_states: editEntityContext.value.type === 'object' ? data.switch_states : undefined,
      switch_initial_state: editEntityContext.value.type === 'object' ? data.switch_initial_state : undefined,
      switch_transitions: editEntityContext.value.type === 'object' ? data.switch_transitions : undefined,
      effects: editEntityContext.value.type === 'object' ? data.effects : undefined,
      stat_modifier_strength: editEntityContext.value.type === 'object' ? data.stat_modifier_strength : undefined,
    })
    closeEditEntityModal()
    await Promise.all([fetchAdventure(), fetchDebugInfo()])

    // Redirect if we renamed the scene we are currently viewing
    if (editEntityContext.value.type === 'scene' && newId && oldId !== newId && activeMapSceneId.value === oldId) {
      router.replace({
        name: 'adventure-editor-scene',
        params: {
          adventureId: props.adventureId,
          sceneId: newId,
        },
        query: route.query,
      })
    }

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
    const teaserOrPlotChanged = (form.value.teaser || '') !== (adventure.value?.teaser || '')
      || (form.value.plot || '') !== (adventure.value?.plot || '')

    const fullStyleObj = imageStylesCatalog.value.find(s => s.id === form.value.selected_style_id) || { id: form.value.selected_style_id, name: form.value.selected_style_id }
    const fullToneObj = toneCatalog.value.find(t => t.id === form.value.selected_tone_id) || { id: form.value.selected_tone_id, name: form.value.selected_tone_id }
    const payload = {
      ...form.value,
      selected_image_styles: form.value.selected_style_id ? [fullStyleObj] : [],
      selected_tone: form.value.selected_tone_id ? fullToneObj : null
    }
    await adventureService.updateAdventure(props.adventureId, payload as any)
    await fetchAdventure()
    if (teaserOrPlotChanged) {
      await fetchDebugInfo()
    }
    addNotification('Adventure configuration updated.', 'success')
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error while saving.'
    addNotification(errorMsg.value, 'error')
  } finally {
    isSaving.value = false
  }
}

async function saveProtagonistField(field: string, newValue: any) {
  const p = debugData.value?.protagonist
  if (!p) return
  isSavingText.value = true
  try {
    const updatePayload = {
      target_type: 'protagonist',
      target_id: p.id,
      name: field === 'name' ? String(newValue).trim() : p.name,
      description: field === 'description' ? String(newValue).trim() : p.description,
      hp: field === 'hp' ? Number(newValue) : p.hp,
      stamina: field === 'stamina' ? Number(newValue) : p.stamina,
      mana: field === 'mana' ? Number(newValue) : p.mana,
      goal: field === 'goal' ? String(newValue).trim() : p.goal,
      character: field === 'character' ? String(newValue).trim() : p.character,
      strength: field === 'strength' ? Number(newValue) : p.strength,
      intelligence: field === 'intelligence' ? Number(newValue) : p.intelligence,
      wisdom: field === 'wisdom' ? Number(newValue) : p.wisdom,
      dexterity: field === 'dexterity' ? Number(newValue) : p.dexterity,
      charisma: field === 'charisma' ? Number(newValue) : p.charisma,
      armor_class: field === 'armor_class' ? Number(newValue) : p.armor_class,
      exp: field === 'exp' ? Number(newValue) : p.exp,
      inventory: field === 'inventory' ? newValue : (p.inventory ? p.inventory.map((i: any) => typeof i === 'string' ? i : (i?.id || '')) : []),
      equipment: field === 'equipment' ? newValue : (p.equipment ? Object.entries(p.equipment).reduce((acc: any, [k, v]: [string, any]) => {
        acc[k] = v ? (typeof v === 'string' ? v : (v?.id || null)) : null
        return acc
      }, {}) : {}),
    }
    await entityService.saveEntityText(props.adventureId, updatePayload as any)
    await Promise.all([fetchAdventure(), fetchDebugInfo()])
    addNotification('Protagonist updated successfully.', 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Failed to update protagonist.', 'error')
  } finally {
    isSavingText.value = false
  }
}

function buildVisualImageUrl(imagePath?: string | null) {
  return visualService.buildImageUrl(imagePath, visualsCacheVersion.value)
}

function hasMissingImage(entity: any): boolean {
  const raw = String(entity?.image_url || '').trim()
  if (!raw) return true
  const lowered = raw.toLowerCase()
  if (lowered.startsWith('assets/') || lowered.startsWith('/assets/')) return true
  if (lowered.includes('placeholder_') || lowered.includes('/placeholder-')) return true
  return false
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
    await adventureService.updateAdventure(props.adventureId, { quests: newQuests } as any)
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
    await adventureService.updateAdventure(props.adventureId, { awards: newAwards } as any)
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

function handleSceneIdChanged(oldId: string, newId: string) {
  if (activeMapSceneId.value === oldId) {
    router.replace({
      name: 'adventure-editor-scene',
      params: { adventureId: props.adventureId, sceneId: newId },
      query: route.query,
    })
  }
}

const activeMapExitId = computed<string | null>(() => {
  if (route.name !== 'adventure-editor-exit') return null
  const raw = route.params.exitId
  return typeof raw === 'string' ? raw : null
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

const routeSceneSwitches = computed<any[]>(() => {
  return routeSceneObjects.value.filter((obj: any) => String(obj.item_type || '').toUpperCase() === 'SWITCH')
})

const routeSceneContainers = computed<any[]>(() => {
  return routeSceneObjects.value.filter((obj: any) => String(obj.item_type || '').toUpperCase() === 'CONTAINER')
})

const routeSceneTextLogs = computed<any[]>(() => {
  return routeSceneObjects.value.filter((obj: any) => String(obj.item_type || '').toUpperCase() === 'READABLE')
})

const routeSceneItems = computed<any[]>(() => {
  return routeSceneObjects.value.filter((obj: any) => {
    const itemType = String(obj.item_type || '').toUpperCase()
    return itemType !== 'SWITCH' && itemType !== 'CONTAINER' && itemType !== 'READABLE'
  })
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
  
  const editorNpcs = Array.isArray(debugData.value?.npcs) ? debugData.value.npcs : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const npcInferred = allEntities.filter((entity: any) => isNpcEntity(entity))
  const npcs = mergeUniqueById(editorNpcs, npcInferred)

  const objInferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  const editorObjects = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const objects = mergeUniqueById(editorObjects, objInferred)

  for (const scene of editorScenes.value) {
    entries.push({
      id: String(scene.id || ''),
      name: String(scene.label || scene.name || scene.id || ''),
      imageUrl: scene.image_url ? buildVisualImageUrl(scene.image_url) : null,
      type: 'SCENE',
    })
  }
  for (const npc of npcs) {
    entries.push({
      id: String(npc.id || ''),
      name: String(npc.name || npc.id || ''),
      imageUrl: npc.image_url ? buildVisualImageUrl(npc.image_url) : null,
      type: 'NPC',
    })
  }
  for (const obj of objects) {
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

const isCreatingRouteAsset = ref(false)
const isDeletingRouteAsset = ref(false)

const isCreatingScene = ref(false)
const createSceneForm = ref({ sceneId: '', name: '', description: '' })
const createSceneFormError = ref('')

function openCreateSceneForm() {
  isCreatingScene.value = true
  activeTab.value = 'scenes'
}

function cancelCreateScene() {
  isCreatingScene.value = false
}

async function saveCreateScene() {
  const sceneId = createSceneForm.value.sceneId.trim()
  const name = createSceneForm.value.name.trim()
  const description = createSceneForm.value.description.trim()

  if (!sceneId) {
    createSceneFormError.value = 'Scene ID is required.'
    return
  }
  if (!name) {
    createSceneFormError.value = 'Scene name is required.'
    return
  }
  if (name.length > 100) {
    createSceneFormError.value = 'Scene name must be 100 characters or less.'
    return
  }
  if (!description) {
    createSceneFormError.value = 'Scene description is required.'
    return
  }
  if (description.length > 1000) {
    createSceneFormError.value = 'Scene description must be 1000 characters or less.'
    return
  }

  const existingIds = new Set(editorScenes.value.map((s: any) => String(s.id || '').toUpperCase()))
  if (existingIds.has(sceneId.toUpperCase())) {
    createSceneFormError.value = `A scene with ID "${sceneId}" already exists.`
    return
  }

  isSavingText.value = true
  createSceneFormError.value = ''
  try {
    await entityService.createScene(props.adventureId, {
      scene_id: sceneId,
      label: name,
      description,
    })
    await fetchDebugInfo()
    addNotification(`Scene "${name}" created.`, 'success')
    isCreatingScene.value = false
    createSceneForm.value = { sceneId: '', name: '', description: '' }
  } catch (error: any) {
    createSceneFormError.value = error?.message || 'Failed to create scene.'
    addNotification(createSceneFormError.value, 'error')
  } finally {
    isSavingText.value = false
  }
}

function openSceneEditorRoute(sceneId: string) {
  const normalized = String(sceneId || '').trim()
  if (!normalized) return
  clearHover()
  activeMenuId.value = null
  sceneEditorReturnTab.value = activeTab.value
  activeTab.value = 'scenes'
  router.push({
    name: 'adventure-editor-scene',
    params: {
      adventureId: props.adventureId,
      sceneId: normalized,
    },
    query: route.query,
  })
}

function closeSceneEditorDialog() {
  activeTab.value = sceneEditorReturnTab.value
  router.push({
    name: 'adventure-editor',
    params: {
      adventureId: props.adventureId,
    },
    query: route.query,
  })
}

function openExitEditorRoute(exitId: string) {
  const normalized = String(exitId || '').trim()
  if (!normalized) return
  exitEditorReturnTab.value = activeTab.value
  router.push({
    name: 'adventure-editor-exit',
    params: {
      adventureId: props.adventureId,
      exitId: normalized,
    },
    query: route.query,
  })
}

function closeExitEditorRoute() {
  activeTab.value = exitEditorReturnTab.value
  router.push({
    name: 'adventure-editor',
    params: {
      adventureId: props.adventureId,
    },
    query: route.query,
  })
}

function openCreateExitModal() {
  isCreateExitMode.value = true
  activeEditExitId.value = null
  exitModalForm.value = {
    from_scene_id: String(activeMapSceneId.value || ''),
    to_scene_id: '',
    label: '',
    exit_type: 'one_way',
    lock_description: '',
    code_to_unlock: '',
    item_to_unlock: '',
    rule_to_unlock: '',
  }
  showExitModal.value = true
}

function requestDeleteRouteExit(exitId: string) {
  const normalized = String(exitId || '').trim()
  if (!normalized) return
  pendingDeleteTarget.value = {
    kind: 'exit',
    id: normalized,
    title: `Delete Exit ${normalized}?`,
    description: 'This removes the exit route between scenes.',
  }
  showDeleteConfirmDialog.value = true
}

function requestDeleteRouteEntity(entityId: string) {
  const normalized = String(entityId || '').trim()
  if (!normalized) return
  pendingDeleteTarget.value = {
    kind: 'entity',
    id: normalized,
    title: `Delete Entity ${normalized}?`,
    description: 'This permanently removes the entity from the world.',
  }
  showDeleteConfirmDialog.value = true
}

async function handleCloneRouteEntity(entityType: 'npc' | 'object', entityId: string) {
  const normalized = String(entityId || '').trim()
  if (!normalized) return
  activeMenuId.value = null
  isSavingText.value = true
  promptError.value = ''
  try {
    const { new_id } = await entityService.cloneEntity(props.adventureId, normalized)
    await fetchDebugInfo()
    addNotification(`${entityType === 'npc' ? 'NPC' : 'Item'} cloned as ${new_id}.`, 'success')
  } catch (error: any) {
    promptError.value = error?.message || 'Failed to clone entity.'
    addNotification(promptError.value, 'error')
  } finally {
    isSavingText.value = false
  }
}

function closeDeleteConfirmDialog() {
  showDeleteConfirmDialog.value = false
  pendingDeleteTarget.value = null
}

function openEditExitModal(exitId: string) {
  const normalized = String(exitId || '').trim()
  if (!normalized) return
  const exits = Array.isArray(debugData.value?.exits) ? debugData.value.exits : []
  const exit = exits.find((entry: any) => String(entry.id || '') === normalized)
  if (!exit) {
    addNotification('Exit not found.', 'error')
    return
  }
  isCreateExitMode.value = false
  activeEditExitId.value = normalized
  exitModalForm.value = {
    from_scene_id: String(exit.from_scene_id || ''),
    to_scene_id: String(exit.to_scene_id || ''),
    label: String(exit.label || ''),
    exit_type: (String(exit.exit_type || 'one_way') as 'one_way' | 'bidirectional'),
    lock_description: String(exit.lock_description || ''),
    code_to_unlock: String(exit.code_to_unlock || ''),
    item_to_unlock: String(exit.item_to_unlock || ''),
    rule_to_unlock: String(exit.rule_to_unlock || ''),
  }
  showExitModal.value = true
}

async function saveExitModal(formData: any) {
  const fromSceneId = String(formData.from_scene_id || activeMapSceneId.value || '').trim()
  const toSceneId = String(formData.to_scene_id || '').trim()
  const label = String(formData.label || '').trim()
  const lockDescription = String(formData.lock_description || '').trim()

  if (!fromSceneId || !label) {
    addNotification('Exit requires a source scene and label.', 'error')
    return
  }

  if (isCreateExitMode.value && !toSceneId) {
    addNotification('Exit requires a destination scene.', 'error')
    return
  }

  if (isCreateExitMode.value && toSceneId === fromSceneId) {
    addNotification('Exit destination must be a different scene.', 'error')
    return
  }

  isSavingText.value = true
  promptError.value = ''
  try {
    if (isCreateExitMode.value) {
      await entityService.createExit(props.adventureId, {
        from_scene_id: fromSceneId,
        to_scene_id: toSceneId,
        label,
        exit_type: formData.exit_type,
        lock_description: lockDescription || undefined,
        code_to_unlock: formData.code_to_unlock || undefined,
        item_to_unlock: formData.item_to_unlock || undefined,
        rule_to_unlock: formData.rule_to_unlock || undefined,
      })
      addNotification('Exit created.', 'success')
    } else {
      const exitId = String(activeEditExitId.value || '').trim()
      if (!exitId) {
        addNotification('Missing exit id for edit.', 'error')
        return
      }
      await entityService.saveEntityText(props.adventureId, {
        target_type: 'exit',
        target_id: exitId,
        name: label,
        description: lockDescription,
        exit_type: formData.exit_type,
        code_to_unlock: formData.code_to_unlock,
        item_to_unlock: formData.item_to_unlock,
        rule_to_unlock: formData.rule_to_unlock,
      })
      addNotification('Exit updated.', 'success')
    }
    closeExitEditModal()
    await fetchDebugInfo()
  } catch (error: any) {
    promptError.value = error?.message || 'Failed to save exit.'
    addNotification(promptError.value, 'error')
  } finally {
    isSavingText.value = false
  }
}

function requestDeleteRouteScene() {
  const sceneId = String(activeMapSceneId.value || '').trim()
  if (!sceneId) return
  pendingDeleteTarget.value = {
    kind: 'scene',
    id: sceneId,
    title: `Delete Scene ${sceneId}?`,
    description: 'This also removes linked exits and entities in that scene.',
  }
  showDeleteConfirmDialog.value = true
}

async function confirmDeleteRouteAsset() {
  const target = pendingDeleteTarget.value
  if (!target) return

  isDeletingRouteAsset.value = true
  try {
    if (target.kind === 'scene') {
      await entityService.deleteScene(props.adventureId, target.id)
      await fetchDebugInfo()
      addNotification('Scene deleted.', 'success')
      router.push({ name: 'adventure-editor', params: { adventureId: props.adventureId }, query: route.query })
    } else if (target.kind === 'exit') {
      await entityService.deleteExit(props.adventureId, target.id)
      await fetchDebugInfo()
      addNotification('Exit deleted.', 'success')
      router.push({ name: 'adventure-editor', params: { adventureId: props.adventureId }, query: route.query })
    } else {
      await entityService.deleteEntity(props.adventureId, target.id)
      await fetchDebugInfo()
      addNotification('Entity deleted.', 'success')
    }
    closeDeleteConfirmDialog()
  } catch (error: any) {
    if (target.kind === 'scene') {
      addNotification(error?.message || 'Failed to delete scene.', 'error')
    } else if (target.kind === 'exit') {
      addNotification(error?.message || 'Failed to delete exit.', 'error')
    } else {
      addNotification(error?.message || 'Failed to delete entity.', 'error')
    }
  } finally {
    isDeletingRouteAsset.value = false
  }
}

async function refreshData() {
  await Promise.all([fetchAdventure(), fetchDebugInfo()])
}

watch(
  () => route.name,
  (name) => {
    if (name === 'adventure-editor-scene') {
      clearHover()
      activeMenuId.value = null
      activeTab.value = 'scenes'
    } else if (name === 'adventure-editor-exit') {
      activeTab.value = 'map'
    }
  },
  { immediate: true },
)

watch(
  () => activeMapSceneId.value,
  () => {
    // routeSceneSearch is local to SceneRoutePanel
  },
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

          <div class="space-y-10 min-w-0 relative">
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
              :is-generating-field="isGeneratingField"
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
              @generate-field="handleGenerateField"
              @update:temp-value="tempValue = $event"
              @update:pacing="form.time_per_turn = $event"
              @update:mode="form.rule_enforcement_mode = $event as any"
              @save-changes="saveChanges"
            />

            <ProtagonistTab
              v-if="activeTab === 'protagonist'"
              :debug-data="debugData"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :visuals-cache-version="visualsCacheVersion"
              :rule-enforcement-mode="form.rule_enforcement_mode"
              :is-saving-text="isSavingText"
              :reference-options="referenceOptions"
              @quick-regen="quickRegenerateVisual"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @toggle-menu="toggleMenu"
              @save-field="saveProtagonistField"
              @create-new-item="createNewItemForProtagonist"
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
              v-if="activeTab === 'scenes' && !canShowSceneRoutePanel && !isCreatingScene"
              :editor-scenes="editorScenes"
              :debug-data="debugData"
              :adventure-id="adventureId"
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
              @open-scene="openSceneEditorRoute"
              @toggle-menu="toggleMenu"
              @handle-hover="handleHover"
              @clear-hover="clearHover"
              @create-new-scene="openCreateSceneForm"
            />

            <CreateSceneForm
              v-if="activeTab === 'scenes' && isCreatingScene"
              :is-saving="isSavingText"
              :editor-scenes="editorScenes"
              :reference-options="referenceOptions"
              @close="cancelCreateScene"
              @create="handleCreateScene"
            />

            <SceneRoutePanel
              v-if="activeTab === 'scenes' && canShowSceneRoutePanel"
              :adventure-id="adventureId"
              :scene-id="activeMapSceneId || ''"
              :debug-data="debugData"
              :reference-options="referenceOptions"
              :is-saving-text="isSavingText"
              :is-deleting-route-asset="isDeletingRouteAsset"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :visuals-cache-version="visualsCacheVersion"
              :rule-enforcement-mode="form.rule_enforcement_mode"
              :return-tab-label="getTabLabel(sceneEditorReturnTab)"
              @back="closeSceneEditorDialog"
              @open-text-edit="openTextEdit"
              @open-create-item="openCreateItem"
              @open-add-existing="openAddExistingItem"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @toggle-menu="toggleMenu"
              @handle-hover="handleHover"
              @clear-hover="clearHover"
              @open-exit="openExitEditorRoute"
              @open-create-exit="openCreateExitModal"
              @open-edit-exit="openEditExitModal"
              @request-delete-scene="requestDeleteRouteScene"
              @request-delete-exit="requestDeleteRouteExit"
              @request-delete-entity="requestDeleteRouteEntity"
              @clone-entity="handleCloneRouteEntity"
              @quick-regen="quickRegenerateVisual"
              @regen-all="requestRegenerateAll"
              @refresh="refreshData"
              @scene-id-changed="handleSceneIdChanged"
            />

            <ExitRoutePanel
              v-if="activeTab === 'map' && canShowExitRoutePanel"
              :adventure-id="adventureId"
              :exit-id="activeMapExitId || ''"
              :debug-data="debugData"
              :reference-options="referenceOptions"
              :is-saving="isSaving"
              :is-deleting-route-asset="isDeletingRouteAsset"
              :return-tab-label="getTabLabel(exitEditorReturnTab)"
              @refresh="fetchDebugInfo"
              @request-delete-exit="requestDeleteRouteExit"
              @back="closeExitEditorRoute"
            />

            <MapTab
              v-if="activeTab === 'map' && !canShowExitRoutePanel"
              :debug-data="debugData"
              :editor-scenes="editorScenes"
              :visuals-cache-version="visualsCacheVersion"
              :active-scene-id="activeMapSceneId"
              :active-exit-id="activeMapExitId"
              @open-scene="openSceneEditorRoute"
              @open-exit="openExitEditorRoute"
            />

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
      :hovered-entity="canShowSceneRoutePanel ? null : hoveredEntity"
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
      :is-create-entity-mode="isCreateEntityMode"
      @close="closeEditEntityModal"
      @save="saveEntityText"
    />

    <ItemTypeSelectorModal
      :show="showItemTypeSelector"
      :scene-label="routeSceneDetails?.label || routeSceneDetails?.name || createEntitySceneId || ''"
      @close="showItemTypeSelector = false"
      @select="handleItemTypeSelected"
    />

    <AddExistingItemModal
      :show="showAddExistingItemModal"
      :kind="addExistingItemKind"
      :scene-label="routeSceneDetails?.label || routeSceneDetails?.name || activeMapSceneId || ''"
      :items="addExistingItemOptions"
      :visuals-cache-version="visualsCacheVersion"
      @close="closeAddExistingItemModal"
      @select="handleAddExistingItemSelected"
    />

    <EditExitModal
      :show="showExitModal"
      :is-create-mode="isCreateExitMode"
      :from-scene-id="exitModalForm.from_scene_id || activeMapSceneId || ''"
      :active-edit-exit-id="activeEditExitId"
      :initial-form="exitModalForm"
      :scene-reference-options="sceneReferenceOptions"
      :reference-options="referenceOptions"
      :is-saving-text="isSavingText"
      @close="closeExitEditModal"
      @save="saveExitModal"
    />

    <DataDebugModal 
      :show="showDebug"
      :adventure="adventure"
      :debug-data="debugData"
      @close="showDebug = false"
    />

    <div
      v-if="showDeleteConfirmDialog"
      class="fixed inset-0 z-[320] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
      @click="closeDeleteConfirmDialog"
    >
      <div class="w-full max-w-lg rounded-2xl border border-red-500/30 bg-slate-900 shadow-2xl overflow-hidden" @click.stop>
        <div class="px-6 py-5 border-b border-white/10 flex items-start gap-3">
          <div class="w-10 h-10 rounded-full border border-red-400/40 bg-red-500/15 flex items-center justify-center shrink-0">
            <i class="ra ra-skull text-red-300"></i>
          </div>
          <div>
            <h3 class="text-lg font-black text-white">{{ pendingDeleteTarget?.title }}</h3>
            <p class="text-xs text-slate-400 mt-1">{{ pendingDeleteTarget?.description }}</p>
          </div>
        </div>

        <div class="px-6 py-5 space-y-2">
          <p class="text-sm text-slate-200">Target: <span class="font-bold text-red-300">{{ pendingDeleteTarget?.id }}</span></p>
        </div>

        <div class="px-6 py-4 border-t border-white/10 flex items-center justify-end gap-3">
          <button
            class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors"
            @click="closeDeleteConfirmDialog"
          >
            Cancel
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-black uppercase tracking-wider hover:bg-red-400 transition-colors disabled:opacity-50"
            :disabled="isDeletingRouteAsset"
            @click="confirmDeleteRouteAsset"
          >
            Delete
          </button>
        </div>
      </div>
    </div>

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
