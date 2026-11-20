/**
 * State and actions of the adventure editor (moved unchanged from AdventureEditorView, phase 2 of
 * docs/specs/workbench_ui.md). The view provides the result; editor pages read it with useEditor().
 * Further splitting into thematic composables happens in phases 3 and 4.
 */

import { conversationFormDefaults, conversationFormFromNpc, conversationSavePayload } from '@/components/editor/entity/npcConversationTypes'
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { adventureService } from '@/services/adventureService'
import { visualService } from '@/services/visualService'
import type { VisualKind } from '@/services/visualService'
import type { NarratorVoice } from '@/services/narratorVoiceService'
import { entityService } from '@/services/entityService'
import { notificationService } from '@/services/notificationService'
import { useEntityTransfer } from '@/composables/useEntityTransfer'
import { confirmDialog } from '@/composables/useDialogs'
import { api } from '@/composables/useApi'
import type { TtsVoiceList } from '@/types'
import type { TriggerTreeNode } from '@/services/triggerTree'
import { readWeaponConfig, weaponPayload } from '@/utils/weaponConfig'
// Utilities
import { 
  fixNewlines, 
  isNpcEntity, 
  isObjectEntity, 
  mergeUniqueById, 
  formatBytes,
  makeSafeFilename,
  getImageExtension,
  EDITOR_ID_PREFIXES,
  MAX_EDITOR_ID_LENGTH,
  itemTypePrefix,
  buildDynamicPlaceholderSceneId,
  generateEditorId,
  isValidEditorId,
} from '@/utils/editor_utils'
import type { DynamicGenerationConfig } from '@/components/editor/DynamicGenerationSection.vue'

export interface AdventureEditorProps {
  adventureId: string
}

export function useAdventureEditor(props: AdventureEditorProps) {


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
  is_revealed: false,
  companions_allowed: true,
  lock_description: '',
  code_to_unlock: '',
  item_to_unlock: '',
  rule_to_unlock: '',
  on_open_exit_script: '',
  on_open_exit_text: '',
  on_exit_used_script: '',
  on_exit_used_text: '',
  unlock_expression: '',
  on_unlock_success_script: '',
  on_unlock_success_text: '',
  on_unlock_failure_script: '',
  on_unlock_failure_text: '',
  dynamic_zone: null as any,
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
  npc_type: 'HUMANOID',
  voice: '',
  appearance: '',
  is_killable: true,
  item_type: 'DEFAULT',
  is_portable: true,
  locked: false,
  quest_item: false,
  code_to_unlock: '',
  item_to_unlock: '',
  inventory_input: [] as string[],
  text_log_content: '',
  text_log_format: 'DOCUMENT',
  entity_id: '',
  wearable_slots_input: [] as string[],
  combination_ingredients_input: [] as string[],
  result_item_ids_input: [] as string[],
  kept_ingredients_input: [] as string[],
  reveal_rule: '',
  is_hidden: false,
  spatial_position: '',
  reveals_item_id: '',
  switch_states_json: '[]',
  switch_state_labels: {} as Record<string, string>,
  switch_initial_state: '',
  switch_disabled_states: [] as string[],
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
      return !SECTIONED_ITEM_TYPES.has(t)
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

function openCreateNpc(targetSceneId?: string) {
  const sceneId = String(targetSceneId || activeMapSceneId.value || debugData.value?.adventure?.start_scene_id || debugData.value?.scenes?.[0]?.id || '').trim()
  if (!sceneId) {
    addNotification('No scene available to place the NPC in.', 'error')
    return
  }
  createEntitySceneId.value = sceneId
  createEntityType.value = 'npc'
  isCreateEntityMode.value = true
  editEntityContext.value = { type: 'npc', id: 'NEW_NPC' }

  const takenIds = referenceOptions.value.map((entry) => String(entry.id || '').toUpperCase())
  const candidateId = generateEditorId({
    prefix: EDITOR_ID_PREFIXES.NPC,
    takenIds,
  })

  editForm.value = {
    name: 'New NPC',
    description: 'A mysterious inhabitant of this scene.',
    teaser: '',
    hp: 20,
    stamina: 20,
    mana: 20,
    goal: '',
    character: '',
    npc_type: 'HUMANOID',
    voice: '',
    appearance: '',
    is_killable: true,
    moveable: false,
    allowed_scenes_input: [],
    notes: '',
    item_type: 'DEFAULT',
    is_portable: true,
    locked: false,
    quest_item: false,
    code_to_unlock: '',
    item_to_unlock: '',
    inventory_input: [],
    text_log_content: '',
    text_log_format: 'DOCUMENT',
    entity_id: candidateId,
    wearable_slots_input: [],
    combination_ingredients_input: [],
    result_item_ids_input: [],
    kept_ingredients_input: [],
    reveal_rule: '',
    is_hidden: false,
    spatial_position: '',
    reveals_item_id: '',
    switch_states_json: JSON.stringify(['OFF', 'ON'], null, 2),
    switch_state_labels: {},
    switch_initial_state: 'OFF',
    switch_disabled_states: [],
    switch_transitions_json: JSON.stringify([], null, 2),
    effects_hp: 0,
    effects_stamina: 0,
    effects_mana: 0,
    stat_modifier_strength: 0,
    is_item_type_fixed: false,
    is_wearable_slots_fixed: false,
  }
  showEditModal.value = true
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
  const takenIds = referenceOptions.value.map((entry) => String(entry.id || '').toUpperCase())
  const defaultId = generateEditorId({ prefix, takenIds })

  editForm.value = {
    name: 'New Item',
    description: 'A mysterious object found in this scene.',
    teaser: '',
    hp: 0,
    stamina: 0,
    mana: 0,
    goal: '',
    character: '',
    npc_type: 'HUMANOID',
    voice: '',
    appearance: '',
    is_killable: true,
    item_type: itemType,
    is_portable: !['SWITCH', 'CONTAINER_SWITCH'].includes(String(itemType).toUpperCase()),
    locked: false,
    quest_item: false,
    code_to_unlock: '',
    item_to_unlock: '',
    inventory_input: [],
    text_log_content: '',
    text_log_format: 'DOCUMENT',
    entity_id: defaultId,
    wearable_slots_input: preselectedSlots,
    combination_ingredients_input: [],
    result_item_ids_input: [],
    kept_ingredients_input: [],
    reveal_rule: '',
    is_hidden: false,
    spatial_position: '',
    reveals_item_id: '',
    switch_states_json: '[]',
    switch_state_labels: {},
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
    is_revealed: false,
    companions_allowed: true,
    lock_description: '',
    code_to_unlock: '',
    item_to_unlock: '',
    rule_to_unlock: '',
    on_open_exit_script: '',
    on_open_exit_text: '',
    on_exit_used_script: '',
    on_exit_used_text: '',
    unlock_expression: '',
    on_unlock_success_script: '',
    on_unlock_success_text: '',
    on_unlock_failure_script: '',
    on_unlock_failure_text: '',
    dynamic_zone: null,
  }
}

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const promptError = ref('')
const showDebug = ref(false)
type EditorTabKey = 'world' | 'time' | 'memory' | 'conversations' | 'sequences' | 'protagonist' | 'items' | 'visuals' | 'inhabitants' | 'scenes' | 'map' | 'regions' | 'quest' | 'awards' | 'scripts' | 'triggers' | 'tone' | 'audio' | 'dynamic' | 'advanced' | 'validation'
const activeTab = ref<EditorTabKey>('world')
const sceneEditorReturnTab = ref<EditorTabKey>('scenes')
const exitEditorReturnTab = ref<EditorTabKey>('map')

const selectedVisual = ref<{ kind: VisualKind; id: string; label: string; description: string; hint: string; appearance?: string } | null>(null)
const selectedUploadTarget = ref<{ kind: VisualKind; id: string; label: string } | null>(null)
const visualPrompt = ref('')
const showPromptDialog = ref(false)
const isRegenerating = ref(false)
const isSuggestingPrompt = ref(false)
const isEnhancingPrompt = ref(false)
const useAdvancedModel = ref(false)
const applyStyle = ref(true)
const applyAppearance = ref(true)
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

const showItemTypeChangeModal = ref(false)
const itemTypeChangeTarget = ref<{ id: string; name: string; currentItemType: string } | null>(null)
const isChangingItemType = ref(false)

const showMoveItemModal = ref(false)
const moveEntityTarget = ref<{ type: 'npc' | 'object'; id: string; name: string; currentSceneId: string } | null>(null)
const isMovingItem = ref(false)
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

// Registered while the editor is mounted (they used to stay on window after leaving it).
const handleWindowResize = () => {
  windowHeight.value = window.innerHeight
  windowWidth.value = window.innerWidth
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

const closeMenuOnWindowClick = () => {
  activeMenuId.value = null
}

onMounted(() => {
  window.addEventListener('resize', handleWindowResize)
  window.addEventListener('click', closeMenuOnWindowClick)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleWindowResize)
  window.removeEventListener('click', closeMenuOnWindowClick)
})

const imageStylesCatalog = ref<any[]>([])
const configuredStyleName = computed(() => {
  const styleId = form.value.selected_style_id
  if (!styleId) return ''
  const found = imageStylesCatalog.value.find((s: any) => s.id === styleId)
  return found?.name || styleId
})
const toneCatalog = ref<any[]>([])
// Voice list for NPC voices (ElevenLabs directly; Google / OpenAI-compatible via the admin's voice mapping).
const voiceList = ref<TtsVoiceList | null>(null)

async function fetchVoiceList() {
  try {
    voiceList.value = await api.getTtsVoices()
  } catch (error) {
    console.warn('Could not load the voice list', error)
    voiceList.value = null
  }
}

const editorTabs = [
  { key: 'world', label: 'Overview' },
  { key: 'time', label: 'Time & pacing' },
  { key: 'sequences', label: 'Chapters' },
  { key: 'protagonist', label: 'Protagonist' },
  { key: 'map', label: 'Map' },
  { key: 'regions', label: 'Regions' },
  { key: 'scenes', label: 'Scenes' },
  { key: 'inhabitants', label: 'Characters' },
  { key: 'items', label: 'Items' },
  { key: 'quest', label: 'Side quests' },
  { key: 'awards', label: 'Awards' },
  { key: 'scripts', label: 'Scripts' },
  { key: 'triggers', label: 'Trigger overview' },
  { key: 'visuals', label: 'Visual style' },
  { key: 'tone', label: 'Tone' },
  { key: 'audio', label: 'Audio' },
  { key: 'dynamic', label: 'Dynamic generator' },
  { key: 'advanced', label: 'Advanced' },
  { key: 'validation', label: 'Validation' },
] as const

const validationTabBadge = ref<{
  total: number
  errors: number
  warnings: number
  ai: number
  structural: number
} | null>(null)

function onValidationFindingsCount(
  total: number,
  errors: number,
  warnings: number,
  ai: number,
  structural: number,
) {
  validationTabBadge.value = { total, errors, warnings, ai, structural }
}

function validationBadgeText(): string {
  const badge = validationTabBadge.value
  if (!badge || badge.total <= 0) return ''
  if (badge.errors > 0) {
    return String(badge.errors)
  }
  if (badge.warnings > 0) {
    return String(badge.warnings)
  }
  return String(badge.total)
}


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

function normalizeDynamicGenerationForm(
  raw?: Partial<DynamicGenerationConfig> | null,
): DynamicGenerationConfig {
  return {
    ...(raw || {}),
    scene_image_mode: raw?.scene_image_mode || 'simple',
    npc_image_mode: raw?.npc_image_mode || 'simple',
    item_image_mode: raw?.item_image_mode || 'simple',
    audio_mode: raw?.audio_mode || 'inherit',
    generation_model: raw?.generation_model || 'mechanics',
    max_npcs: raw?.max_npcs ?? 2,
    interlude_quote_enabled: raw?.interlude_quote_enabled ?? true,
  } as DynamicGenerationConfig
}

const form = ref({
  title: '',
  teaser: '',
  version: '',
  creator: '',
  copyright: '',
  license: '',
  license_url: '',
  original_prompt: '',
  rule_enforcement_mode: 'rpg' as 'rpg' | 'story' | 'chat',
  time_per_turn: 5,
  max_time_per_turn: null as number | null,
  gm_time_control: true,
  game_over_rules: null as Record<string, any> | null,
  npc_conversations: null as Record<string, any> | null,
  max_memory_turns: 10,
  clock_enabled: false,
  fast_travel_enabled: true,
  time_system: 'calendar' as string,
  time_config: { start_date: '2026-01-01', start_time: '08:00', day_label: 'Day', unit_name: 'Blobs', initial_value: 0 } as Record<string, any>,
  min_scenes: null as number | null,
  max_scenes: null as number | null,
  min_items: null as number | null,
  max_items: null as number | null,
  container_generation_enabled: true,
  scripts_generation_enabled: true,
  min_containers: null as number | null,
  max_containers: null as number | null,
  text_log_generation_enabled: true,
  min_text_logs: null as number | null,
  max_text_logs: null as number | null,
  awards: [] as any[],
  allow_dynamic_items: false,
  can_damage_npcs: true,
  npcs_can_damage_protagonist: true,
  plot: '',
  rules: '',
  intro_text: '',
  completed_condition: '',
  gameover_condition: '',
  completed_guard_expression: '',
  gameover_guard_expression: '',
  tts_director_notes: '',
  selected_style_id: '',
  selected_tone_id: '',
  narrator_voice: null as NarratorVoice | null,
  is_adventure_generator: false,
  dynamic_generation: {
    scene_image_mode: 'simple',
    npc_image_mode: 'simple',
    item_image_mode: 'simple',
    audio_mode: 'inherit',
    generation_model: 'mechanics',
    max_npcs: 2,
    interlude_quote_enabled: true,
  } as DynamicGenerationConfig,
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
      completed_condition: form.value.completed_condition,
      gameover_condition: form.value.gameover_condition,
      completed_guard_expression: form.value.completed_guard_expression,
      gameover_guard_expression: form.value.gameover_guard_expression,
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
    creator: 100,
    copyright: 100,
    license: 100,
    license_url: 500,
    teaser: 300,
    plot: 5000,
    rules: 5000,
    intro_text: 20000,
    completed_condition: 2000,
    gameover_condition: 2000,
    completed_guard_expression: 2000,
    gameover_guard_expression: 2000,
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
  return source.filter((scene: any) => {
    const id = String(scene?.id || '').trim()
    return !!id && !id.startsWith('DYN_')
  })
})

const editorAllItems = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred)
})

const itemsOfType = (type: string) => editorAllItems.value.filter((entity: any) => String(entity?.item_type || '').toUpperCase() === type)

// Item types with their own section in the Items tab; everything else is a plain object.
const SECTIONED_ITEM_TYPES = new Set(['READABLE', 'CONTAINER', 'CONTAINER_SWITCH', 'SWITCH', 'CONSTRUCTABLE'])

const editorObjects = computed<any[]>(() =>
  editorAllItems.value.filter((entity: any) => !SECTIONED_ITEM_TYPES.has(String(entity?.item_type || '').toUpperCase())),
)
const editorSwitches = computed<any[]>(() => itemsOfType('SWITCH'))
const editorContainers = computed<any[]>(() =>
  editorAllItems.value.filter((entity: any) =>
    ['CONTAINER', 'CONTAINER_SWITCH'].includes(String(entity?.item_type || '').toUpperCase()),
  ),
)
const editorTextLogs = computed<any[]>(() => itemsOfType('READABLE'))
/** CONSTRUCTABLE meta items: never appear in the world and have no image. */
const editorConstructables = computed<any[]>(() => itemsOfType('CONSTRUCTABLE'))

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
    form.value.creator = data.creator || ''
    form.value.copyright = data.copyright || ''
    form.value.license = data.license || ''
    form.value.license_url = data.license_url || ''
    form.value.original_prompt = data.original_prompt || ''
    form.value.rule_enforcement_mode = (data.rule_enforcement_mode as 'rpg' | 'story' | 'chat') || 'rpg'
    form.value.time_per_turn = data.time_per_turn || 5
    form.value.max_time_per_turn = data.max_time_per_turn !== undefined ? data.max_time_per_turn : null
    form.value.gm_time_control = data.gm_time_control ?? true
    form.value.game_over_rules = data.game_over_rules ?? null
    form.value.npc_conversations = data.npc_conversations ?? null
    form.value.max_memory_turns = typeof data.max_memory_turns === 'number' ? data.max_memory_turns : 10
    form.value.clock_enabled = data.clock_enabled ?? false
    form.value.fast_travel_enabled = data.fast_travel_enabled !== false
    form.value.time_system = data.time_system === 'units' ? 'units' : 'relative'
    form.value.time_config = data.time_config && typeof data.time_config === 'object'
      ? { ...data.time_config }
      : { start_time: '08:00', day_label: 'Day', initial_day: 1, time_format: '24h', unit_name: 'Blobs', initial_value: 0 }
    if (!form.value.time_config.start_time) form.value.time_config.start_time = '08:00'
    if (!form.value.time_config.day_label) form.value.time_config.day_label = 'Day'
    if (form.value.time_config.initial_day === undefined) form.value.time_config.initial_day = 1
    if (!form.value.time_config.time_format) form.value.time_config.time_format = '24h'
    if (!form.value.time_config.unit_name) form.value.time_config.unit_name = 'Blobs'
    if (form.value.time_config.initial_value === undefined) form.value.time_config.initial_value = 0
    if (!form.value.time_config.calendar_pacing_unit) {
      const t = form.value.time_per_turn || 5
      if (t >= 525600 && t % 525600 === 0) {
        form.value.time_config.calendar_pacing_value = t / 525600
        form.value.time_config.calendar_pacing_unit = 'Years'
      } else if (t >= 10080 && t % 10080 === 0) {
        form.value.time_config.calendar_pacing_value = t / 10080
        form.value.time_config.calendar_pacing_unit = 'Weeks'
      } else if (t >= 1440 && t % 1440 === 0) {
        form.value.time_config.calendar_pacing_value = t / 1440
        form.value.time_config.calendar_pacing_unit = 'Days'
      } else if (t >= 60 && t % 60 === 0) {
        form.value.time_config.calendar_pacing_value = t / 60
        form.value.time_config.calendar_pacing_unit = 'Hours'
      } else {
        form.value.time_config.calendar_pacing_value = t
        form.value.time_config.calendar_pacing_unit = 'Minutes'
      }
    }
    if (!form.value.time_config.calendar_max_unit) {
      const mt = form.value.max_time_per_turn
      if (mt && mt > 0) {
        if (mt >= 525600 && mt % 525600 === 0) {
          form.value.time_config.calendar_max_value = mt / 525600
          form.value.time_config.calendar_max_unit = 'Years'
        } else if (mt >= 10080 && mt % 10080 === 0) {
          form.value.time_config.calendar_max_value = mt / 10080
          form.value.time_config.calendar_max_unit = 'Weeks'
        } else if (mt >= 1440 && mt % 1440 === 0) {
          form.value.time_config.calendar_max_value = mt / 1440
          form.value.time_config.calendar_max_unit = 'Days'
        } else if (mt >= 60 && mt % 60 === 0) {
          form.value.time_config.calendar_max_value = mt / 60
          form.value.time_config.calendar_max_unit = 'Hours'
        } else {
          form.value.time_config.calendar_max_value = mt
          form.value.time_config.calendar_max_unit = 'Minutes'
        }
      } else {
        form.value.time_config.calendar_max_value = null
        form.value.time_config.calendar_max_unit = 'Minutes'
      }
    }
    form.value.min_scenes = data.min_scenes !== undefined ? data.min_scenes : null
    form.value.max_scenes = data.max_scenes !== undefined ? data.max_scenes : null
    form.value.min_items = data.min_items !== undefined ? data.min_items : null
    form.value.max_items = data.max_items !== undefined ? data.max_items : null
    form.value.container_generation_enabled = data.container_generation_enabled ?? true
    form.value.scripts_generation_enabled = data.scripts_generation_enabled ?? true
    form.value.min_containers = data.min_containers !== undefined ? data.min_containers : null
    form.value.max_containers = data.max_containers !== undefined ? data.max_containers : null
    form.value.text_log_generation_enabled = data.text_log_generation_enabled ?? true
    form.value.min_text_logs = data.min_text_logs !== undefined ? data.min_text_logs : null
    form.value.max_text_logs = data.max_text_logs !== undefined ? data.max_text_logs : null
    form.value.awards = data.awards || []
    form.value.allow_dynamic_items = data.allow_dynamic_items ?? false
    form.value.plot = data.plot || ''
    form.value.can_damage_npcs = data.can_damage_npcs ?? true
    form.value.npcs_can_damage_protagonist = data.npcs_can_damage_protagonist ?? true
    form.value.rules = data.rules || ''
    form.value.intro_text = data.intro_text || ''
    form.value.completed_condition = data.completed_condition || ''
    form.value.gameover_condition = data.gameover_condition || ''
    form.value.completed_guard_expression = data.completed_guard_expression || ''
    form.value.gameover_guard_expression = data.gameover_guard_expression || ''
    form.value.tts_director_notes = data.tts_director_notes || ''

    form.value.selected_style_id = Array.isArray(data.selected_image_styles) && data.selected_image_styles.length > 0 
      ? (typeof data.selected_image_styles[0] === 'string' ? data.selected_image_styles[0] : data.selected_image_styles[0].id)
      : ''
    const rawTone = data.selected_tone
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
    form.value.narrator_voice = data.narrator_voice || null
    form.value.is_adventure_generator = !!data.is_adventure_generator
    form.value.dynamic_generation = normalizeDynamicGenerationForm(data.dynamic_generation)
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error loading adventure.'
  } finally {
    isLoading.value = false
  }
}

const { exportEntity, importEntity } = useEntityTransfer(() => props.adventureId, fetchDebugInfo)

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

async function handleCreateScene(data: {
  sceneId: string
  name: string
  description: string
  dynamicZone?: Record<string, any> | null
}) {
  isSavingText.value = true
  try {
    await entityService.createScene(props.adventureId, {
      scene_id: data.sceneId,
      label: data.name,
      description: data.description,
      dynamic_zone: data.dynamicZone ?? null,
    })
    await fetchDebugInfo()
    addNotification(`Scene "${data.name}" created.`, 'success')
    isCreatingScene.value = false
  } catch (error: any) {
    addNotification(error?.message || 'Failed to create scene.', 'error')
  } finally {
    isSavingText.value = false
  }
}

function resolveEditAppearance(type: string, entity: any): string {
  if (type === 'cover') return debugData.value?.adventure?.cover_appearance || ''
  if (type === 'protagonist') return debugData.value?.protagonist?.appearance || ''
  return entity?.appearance || ''
}

/** Stored voice of the NPC or protagonist ('' = automatic); other entities have none. */
function resolveEditVoice(type: string, npc: any): string {
  if (type === 'protagonist') return String(debugData.value?.protagonist?.voice || '')
  if (type === 'npc') return String(npc?.voice || '')
  return ''
}

/** Fills the entity form (context and editForm) without opening anything. */
function loadEntityEditor(type: string, id: string, currentName: string, currentDesc: string, currentTeaser: string = '', hp?: number, stamina?: number, mana?: number, goal?: string, character?: string, isKillable?: boolean) {
  if (type === 'npc' && (id === 'NEW_NPC' || id.startsWith('NEW_'))) {
    openCreateNpc()
    return
  }
  if (type === 'object' && id.startsWith('NEW_')) {
    openCreateItem()
    return
  }

  isCreateEntityMode.value = false
  createEntityType.value = null
  createEntitySceneId.value = null

  const selectedObject = type === 'object'
    ? editorAllItems.value.find((entry: any) => String(entry.id) === String(id))
    : null
  const selectedNpc = type === 'npc'
    ? (debugData.value?.npcs || []).find((entry: any) => String(entry.id) === String(id))
    : null
  const selectedScene = type === 'scene'
    ? (editorScenes.value || []).find((entry: any) => String(entry.id) === String(id))
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
    appearance: resolveEditAppearance(type, selectedNpc || selectedObject),
    hp: hp ?? 0,
    stamina: stamina ?? 0,
    mana: mana ?? 0,
    goal: goal || '',
    character: character || '',
    npc_type: type === 'npc' ? String(selectedNpc?.npc_type || 'HUMANOID').trim().toUpperCase() : 'HUMANOID',
    voice: resolveEditVoice(type, selectedNpc),
    is_killable: isKillable ?? true,
    moveable: selectedNpc?.moveable != null ? Boolean(selectedNpc.moveable) : (String(selectedNpc?.movement_type || '').toUpperCase() === 'MOVABLE'),
    allowed_scenes_input: Array.isArray(selectedNpc?.allowed_scenes) ? [...selectedNpc.allowed_scenes] : [],
    notes: selectedNpc?.notes || '',
    item_type: selectedObject?.item_type || 'DEFAULT',
    is_portable: selectedObject?.is_portable !== false,
    locked: selectedObject?.locked === true,
    quest_item: selectedObject?.quest_item === true,
    code_to_unlock: selectedObject?.code_to_unlock || '',
    item_to_unlock: selectedObject?.item_to_unlock || '',
    inventory_input: Array.isArray(selectedObject?.inventory)
      ? [...selectedObject.inventory.map((item: any) => typeof item === 'string' ? item : (item?.id || ''))]
      : Array.isArray(selectedNpc?.inventory)
        ? [...selectedNpc.inventory.map((item: any) => typeof item === 'string' ? item : (item?.id || ''))]
        : [],
    text_log_content: fixNewlines(metadata?.text_log_content || ''),
    text_log_format: String(metadata?.text_log_format || selectedObject?.text_log_format || 'DOCUMENT').trim().toUpperCase(),
    entity_id: String(selectedObject?.id || selectedNpc?.id || selectedScene?.id || id || ''),
    wearable_slots_input: selectedObject?.wearable_slots || [],
    combination_ingredients_input: Array.isArray(selectedObject?.combination_ingredients)
      ? [...selectedObject.combination_ingredients]
      : (metadata?.combination_ingredients ? [...metadata.combination_ingredients] : []),
    result_item_ids_input: Array.isArray(selectedObject?.result_item_ids ?? metadata?.result_item_ids)
      ? [...(selectedObject?.result_item_ids ?? metadata.result_item_ids)]
      : [],
    kept_ingredients_input: Array.isArray(selectedObject?.kept_ingredients ?? metadata?.kept_ingredients)
      ? [...(selectedObject?.kept_ingredients ?? metadata.kept_ingredients)]
      : [],
    reveal_rule: type === 'npc' ? String(selectedNpc?.reveal_rule || '') : String(selectedObject?.reveal_rule || metadata?.reveal_rule || ''),
    is_hidden: type === 'npc' ? !!(selectedNpc?.is_hidden ?? false) : !!(selectedObject?.is_hidden ?? metadata?.is_hidden ?? false),
    spatial_position: type === 'npc' ? String(selectedNpc?.spatial_position || '') : String(selectedObject?.spatial_position || metadata?.spatial_position || ''),
    reveals_item_id: String(selectedObject?.reveals_item_id || metadata?.reveals_item_id || ''),
    pickup_trigger_mode: String(metadata?.pickup_trigger?.mode || 'silent'),
    pickup_trigger_cue: String(metadata?.pickup_trigger?.cue || ''),
    switch_states_json: JSON.stringify(selectedObject?.switch_states || metadata?.switch?.states || metadata?.switch_states || [], null, 2),
    switch_state_labels: { ...(selectedObject?.switch_state_labels || metadata?.switch?.state_labels || {}) },
    switch_initial_state: String(selectedObject?.switch_initial_state || metadata?.switch?.initial_state || metadata?.switch_initial_state || ''),
    switch_disabled_states: Array.isArray(selectedObject?.switch_disabled_states ?? metadata?.switch?.disabled_states)
      ? [...(selectedObject?.switch_disabled_states ?? metadata.switch.disabled_states)]
      : [],
    switch_status_text: String(selectedObject?.switch_status_text ?? metadata?.switch?.status_text ?? ''),
    switch_transitions_json: JSON.stringify(selectedObject?.switch_transitions || metadata?.switch?.transitions || metadata?.switch_transitions || [], null, 2),
    effects_hp: selectedObject?.effects?.hp || metadata?.effects?.hp || 0,
    effects_stamina: selectedObject?.effects?.stamina || metadata?.effects?.stamina || 0,
    effects_mana: selectedObject?.effects?.mana || metadata?.effects?.mana || 0,
    stat_modifier_strength: selectedObject?.stat_modifier_strength || metadata?.stat_modifier_strength || 0,
    is_item_type_fixed: false,
    is_wearable_slots_fixed: false,
    on_pickup_script: selectedObject?.on_pickup_script || metadata?.on_pickup_script || '',
    on_pickup_text: selectedObject?.on_pickup_text || metadata?.on_pickup_text || '',
    on_drop_script: selectedObject?.on_drop_script || metadata?.on_drop_script || '',
    on_drop_text: selectedObject?.on_drop_text || metadata?.on_drop_text || '',
    on_equip_script: selectedObject?.on_equip_script || metadata?.on_equip_script || '',
    on_equip_text: selectedObject?.on_equip_text || metadata?.on_equip_text || '',
    on_unequip_script: selectedObject?.on_unequip_script || metadata?.on_unequip_script || '',
    on_unequip_text: selectedObject?.on_unequip_text || metadata?.on_unequip_text || '',
    on_enter_scene_script: selectedScene?.on_enter_scene_script || selectedObject?.on_enter_scene_script || metadata?.on_enter_scene_script || '',
    on_enter_scene_text: selectedScene?.on_enter_scene_text || selectedObject?.on_enter_scene_text || metadata?.on_enter_scene_text || '',
    on_open_exit_script: selectedObject?.on_open_exit_script || metadata?.on_open_exit_script || '',
    on_open_exit_text: selectedObject?.on_open_exit_text || metadata?.on_open_exit_text || '',
    on_exit_used_script: selectedObject?.on_exit_used_script || metadata?.on_exit_used_script || '',
    on_exit_used_text: selectedObject?.on_exit_used_text || metadata?.on_exit_used_text || '',
    on_defeat_script: selectedNpc?.on_defeat_script || metadata?.on_defeat_script || '',
    on_defeat_text: selectedNpc?.on_defeat_text || metadata?.on_defeat_text || '',
    on_protagonist_enters_scene_script: selectedNpc?.on_protagonist_enters_scene_script || metadata?.on_protagonist_enters_scene_script || '',
    on_protagonist_enters_scene_text: selectedNpc?.on_protagonist_enters_scene_text || metadata?.on_protagonist_enters_scene_text || '',
    on_receive_item_script: selectedNpc?.on_receive_item_script || metadata?.on_receive_item_script || '',
    on_receive_item_text: selectedNpc?.on_receive_item_text || metadata?.on_receive_item_text || '',
    on_recruit_success_script: selectedNpc?.on_recruit_success_script || metadata?.on_recruit_success_script || '',
    on_recruit_success_text: selectedNpc?.on_recruit_success_text || metadata?.on_recruit_success_text || '',
    on_recruit_failure_script: selectedNpc?.on_recruit_failure_script || metadata?.on_recruit_failure_script || '',
    on_recruit_failure_text: selectedNpc?.on_recruit_failure_text || metadata?.on_recruit_failure_text || '',
    reveal_guard_expression: selectedNpc?.reveal_guard_expression || metadata?.reveal_guard_expression || '',
    memory_slots: Number(selectedNpc?.memory_slots ?? metadata?.memory_slots ?? 0) || 0,
    ...(selectedNpc ? conversationFormFromNpc(selectedNpc, metadata) : conversationFormDefaults()),
    on_interact_script: selectedNpc?.on_interact_script || selectedObject?.on_interact_script || metadata?.on_interact_script || '',
    on_interact_text: selectedNpc?.on_interact_text || selectedObject?.on_interact_text || metadata?.on_interact_text || '',
    unlock_expression: selectedObject?.unlock_expression || metadata?.unlock_expression || '',
    on_unlock_success_script: selectedObject?.on_unlock_success_script || metadata?.on_unlock_success_script || '',
    on_unlock_success_text: selectedObject?.on_unlock_success_text || metadata?.on_unlock_success_text || '',
    on_unlock_failure_script: selectedObject?.on_unlock_failure_script || metadata?.on_unlock_failure_script || '',
    on_unlock_failure_text: selectedObject?.on_unlock_failure_text || metadata?.on_unlock_failure_text || '',
    on_items_added_script: selectedObject?.on_items_added_script || metadata?.on_items_added_script || '',
    on_items_added_text: selectedObject?.on_items_added_text || metadata?.on_items_added_text || '',
    on_items_removed_script: selectedObject?.on_items_removed_script || metadata?.on_items_removed_script || '',
    on_items_removed_text: selectedObject?.on_items_removed_text || metadata?.on_items_removed_text || '',
    min_items: selectedObject?.min_items ?? metadata?.min_items ?? null,
    max_items: selectedObject?.max_items ?? metadata?.max_items ?? null,
    craft_guard_expression: selectedObject?.craft_guard_expression || metadata?.craft_guard_expression || '',
    on_craft_success_script: selectedObject?.on_craft_success_script || metadata?.on_craft_success_script || '',
    on_craft_success_text: selectedObject?.on_craft_success_text || metadata?.on_craft_success_text || '',
    on_craft_failure_script: selectedObject?.on_craft_failure_script || metadata?.on_craft_failure_script || '',
    on_craft_failure_text: selectedObject?.on_craft_failure_text || metadata?.on_craft_failure_text || '',
    on_read_script: selectedObject?.on_read_script || metadata?.on_read_script || '',
    on_read_text: selectedObject?.on_read_text || metadata?.on_read_text || '',
    on_leave_scene_script: selectedScene?.on_leave_scene_script || metadata?.on_leave_scene_script || '',
    on_leave_scene_text: selectedScene?.on_leave_scene_text || metadata?.on_leave_scene_text || '',
    helpers_script: selectedScene?.helpers_script || '',
    weapon_config: type === 'object' ? readWeaponConfig(metadata, selectedObject) : undefined,
  }

}

const ENTITY_PAGE_TYPES = new Set(['npc', 'object'])

/**
 * Opens an entity for editing: characters and items get their detail page
 * (route adventure-editor-entity); scenes, cover and protagonist keep the modal.
 */
function openTextEdit(type: string, id: string, currentName: string, currentDesc: string, currentTeaser: string = '', hp?: number, stamina?: number, mana?: number, goal?: string, character?: string, isKillable?: boolean) {
  if (ENTITY_PAGE_TYPES.has(type) && !id.startsWith('NEW_')) {
    openEntityPage(type, id)
    return
  }
  loadEntityEditor(type, id, currentName, currentDesc, currentTeaser, hp, stamina, mana, goal, character, isKillable)
  if (editEntityContext.value) {
    showEditModal.value = true
  }
}

function openEntityPage(type: string, id: string) {
  activeMenuId.value = null
  clearHover()
  router.push({
    name: 'adventure-editor-entity',
    params: { adventureId: props.adventureId, entityId: id },
    query: { ...route.query, tab: type === 'npc' ? 'inhabitants' : 'items' },
  })
}

/** Loads a character or item into the entity form by id; returns its type, or null when unknown. */
function loadEntityFromWorld(id: string): 'npc' | 'object' | null {
  const npc = (debugData.value?.npcs || []).find((entry: any) => String(entry.id) === String(id))
  if (npc) {
    loadEntityEditor('npc', npc.id, npc.name, npc.description, '', npc.hp, npc.stamina, npc.mana, npc.goal, npc.character, npc.is_killable)
    return 'npc'
  }
  const item = editorAllItems.value.find((entry: any) => String(entry.id) === String(id))
  if (item) {
    loadEntityEditor('object', item.id, item.name, item.description || '')
    return 'object'
  }
  return null
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

    const candidateId = String(data.entity_id || '').trim().toUpperCase()
    if (!candidateId) {
      addNotification('Entity ID is required.', 'error')
      return
    }
    if (!isValidEditorId(candidateId, MAX_EDITOR_ID_LENGTH)) {
      addNotification(
        `Entity ID must use uppercase A-Z, 0-9, or _ only (${MAX_EDITOR_ID_LENGTH} chars max).`,
        'error',
      )
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
          npc_type: String(data.npc_type || 'HUMANOID').trim().toUpperCase(),
          appearance: String(data.appearance || '').trim() || undefined,
          is_killable: Boolean(data.is_killable),
          moveable: Boolean(data.moveable),
          allowed_scenes: data.allowed_scenes || [],
          notes: String(data.notes || '').trim() || undefined,
          is_hidden: Boolean(data.is_hidden),
          reveal_rule: String(data.reveal_rule || '').trim() || undefined,
          spatial_position: String(data.spatial_position || '').trim() || undefined,
          inventory: data.inventory || [],
          on_defeat_script: data.on_defeat_script || undefined,
          on_defeat_text: data.on_defeat_text || undefined,
          on_protagonist_enters_scene_script: data.on_protagonist_enters_scene_script || undefined,
          on_protagonist_enters_scene_text: data.on_protagonist_enters_scene_text || undefined,
          on_receive_item_script: data.on_receive_item_script || undefined,
          on_receive_item_text: data.on_receive_item_text || undefined,
          on_recruit_success_script: data.on_recruit_success_script || undefined,
          on_recruit_success_text: data.on_recruit_success_text || undefined,
          on_recruit_failure_script: data.on_recruit_failure_script || undefined,
          on_recruit_failure_text: data.on_recruit_failure_text || undefined,
          reveal_guard_expression: data.reveal_guard_expression || undefined,
          on_interact_script: data.on_interact_script || undefined,
          on_interact_text: data.on_interact_text || undefined,
          metadata_json: {
            ...(Number(data.memory_slots) > 0 ? { memory_slots: Number(data.memory_slots) } : {}),
            ...conversationSavePayload(data),
          },
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
          appearance: String(data.appearance || '').trim() || undefined,
          item_type: itemType,
          is_portable: !['SWITCH', 'CONTAINER_SWITCH'].includes(itemType) && data.is_portable !== false,
          inventory: data.inventory || [],
          wearable_slots: data.wearable_slots || undefined,
          combination_ingredients: data.combination_ingredients || undefined,
          result_item_ids: itemType === 'CONSTRUCTABLE' ? data.result_item_ids : undefined,
          kept_ingredients: itemType === 'CONSTRUCTABLE' ? data.kept_ingredients : undefined,
          stat_modifier_strength: data.stat_modifier_strength || undefined,
          is_hidden: data.is_hidden,
          reveal_rule: data.reveal_rule || undefined,
          on_pickup_script: data.on_pickup_script || undefined,
          on_interact_script: data.on_interact_script || undefined,
          on_interact_text: data.on_interact_text || undefined,
          on_pickup_text: data.on_pickup_text || undefined,
          on_drop_script: data.on_drop_script || undefined,
          on_drop_text: data.on_drop_text || undefined,
          on_equip_script: data.on_equip_script || undefined,
          on_equip_text: data.on_equip_text || undefined,
          on_unequip_script: data.on_unequip_script || undefined,
          on_unequip_text: data.on_unequip_text || undefined,
        }
        if (data.locked) {
          createPayload.metadata_json = {
            ...(createPayload.metadata_json || {}),
            locked: true,
          }
        }
        if (data.quest_item) {
          createPayload.metadata_json = {
            ...(createPayload.metadata_json || {}),
            quest_item: true,
          }
        }
        if (['CONTAINER', 'CONTAINER_SWITCH'].includes(itemType)) {
          createPayload.metadata_json = {
            ...(createPayload.metadata_json || {}),
            locked: Boolean(data.locked || data.code_to_unlock || data.item_to_unlock || data.unlock_expression),
            ...(data.code_to_unlock ? { code_to_unlock: String(data.code_to_unlock).trim() } : {}),
            ...(data.item_to_unlock ? { item_to_unlock: String(data.item_to_unlock).trim().toUpperCase() } : {}),
            ...(data.unlock_expression ? { unlock_expression: String(data.unlock_expression).trim() } : {}),
            ...(data.on_unlock_success_script ? { on_unlock_success_script: String(data.on_unlock_success_script).trim() } : {}),
            ...(data.on_unlock_success_text ? { on_unlock_success_text: String(data.on_unlock_success_text).trim() } : {}),
            ...(data.on_unlock_failure_script ? { on_unlock_failure_script: String(data.on_unlock_failure_script).trim() } : {}),
            ...(data.on_unlock_failure_text ? { on_unlock_failure_text: String(data.on_unlock_failure_text).trim() } : {}),
            ...(data.on_items_added_script ? { on_items_added_script: String(data.on_items_added_script).trim() } : {}),
            ...(data.on_items_added_text ? { on_items_added_text: String(data.on_items_added_text).trim() } : {}),
            ...(data.on_items_removed_script ? { on_items_removed_script: String(data.on_items_removed_script).trim() } : {}),
            ...(data.on_items_removed_text ? { on_items_removed_text: String(data.on_items_removed_text).trim() } : {}),
            ...(Number(data.min_items || 0) > 0 ? { min_items: Math.floor(Number(data.min_items)) } : {}),
            ...(Number(data.max_items || 0) > 0 ? { max_items: Math.floor(Number(data.max_items)) } : {}),
          }
        }
        if (itemType === 'READABLE') {
          createPayload.metadata_json = {
            ...(createPayload.metadata_json || {}),
            text_log_content: String(data.text_log_content || '').trim(),
            text_log_format: String(data.text_log_format || 'DOCUMENT').toUpperCase(),
          }
        }
        if (['SWITCH', 'CONTAINER_SWITCH'].includes(itemType)) {
          createPayload.metadata_json = {
            ...(createPayload.metadata_json || {}),
            switch_states: data.switch_states || [],
            switch_initial_state: data.switch_initial_state || '',
            switch_disabled_states: data.switch_disabled_states || [],
            switch_status_text: data.switch_status_text || '',
            switch_transitions: data.switch_transitions || [],
            ...(data.on_success_script ? { on_success_script: String(data.on_success_script).trim() } : {}),
            ...(data.on_failure_script ? { on_failure_script: String(data.on_failure_script).trim() } : {}),
            switch: {
              states: data.switch_states || [],
              state_labels: data.switch_state_labels || {},
              initial_state: data.switch_initial_state || '',
              disabled_states: data.switch_disabled_states || [],
              status_text: data.switch_status_text || '',
              transitions: data.switch_transitions || [],
              outcomes: [],
              ...(data.on_success_script ? { on_success_script: String(data.on_success_script).trim() } : {}),
              ...(data.on_failure_script ? { on_failure_script: String(data.on_failure_script).trim() } : {}),
            }
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

  if (editEntityContext.value.type === 'object' && (data.text_log_content || '').length > 1000) {
    addNotification('Text logs must be 1000 characters or less.', 'error')
    return
  }

  isSavingText.value = true
  promptError.value = ''
  try {
    const oldId = editEntityContext.value.id
    const newId = data.entity_id ? String(data.entity_id).trim().toUpperCase() : ''
    if (
      newId &&
      newId !== String(oldId || '').trim().toUpperCase() &&
      !isValidEditorId(newId, MAX_EDITOR_ID_LENGTH)
    ) {
      addNotification(
        `New entity ID must use uppercase A-Z, 0-9, or _ only (${MAX_EDITOR_ID_LENGTH} chars max).`,
        'error',
      )
      return
    }

    await entityService.saveEntityText(props.adventureId, {
      target_type: editEntityContext.value.type,
      target_id: oldId,
      new_id: newId || undefined,
      name: data.name,
      description: data.description,
      item_type: editEntityContext.value.type === 'object' ? data.item_type : undefined,
      hp: data.hp || undefined,
      stamina: data.stamina || undefined,
      mana: data.mana || undefined,
      goal: ['npc', 'protagonist'].includes(editEntityContext.value.type) ? data.goal : undefined,
      character: ['npc', 'protagonist'].includes(editEntityContext.value.type) ? data.character : undefined,
      npc_type: editEntityContext.value.type === 'npc' ? String(data.npc_type || 'HUMANOID').trim().toUpperCase() : undefined,
      voice: ['npc', 'protagonist'].includes(editEntityContext.value.type) ? String(data.voice || '') : undefined,
      appearance: ['cover', 'npc', 'object', 'protagonist'].includes(editEntityContext.value.type) ? (data.appearance ?? '') : undefined,
      is_killable: editEntityContext.value.type === 'npc' ? data.is_killable : undefined,
      moveable: editEntityContext.value.type === 'npc' ? data.moveable : undefined,
      allowed_scenes: editEntityContext.value.type === 'npc' ? data.allowed_scenes : undefined,
      notes: editEntityContext.value.type === 'npc' ? data.notes : undefined,
      is_portable: editEntityContext.value.type === 'object' ? data.is_portable : undefined,
      locked: editEntityContext.value.type === 'object' ? data.locked : undefined,
      quest_item: editEntityContext.value.type === 'object' ? Boolean(data.quest_item) : undefined,
      code_to_unlock: editEntityContext.value.type === 'object' ? data.code_to_unlock : undefined,
      item_to_unlock: editEntityContext.value.type === 'object' ? data.item_to_unlock : undefined,
      inventory: ['npc', 'object'].includes(editEntityContext.value.type) ? data.inventory : undefined,
      text_log_content: editEntityContext.value.type === 'object' ? data.text_log_content : undefined,
      text_log_format: editEntityContext.value.type === 'object' && String(data.item_type || '').toUpperCase() === 'READABLE'
        ? data.text_log_format
        : undefined,
      wearable_slots: editEntityContext.value.type === 'object' ? data.wearable_slots : undefined,
      combination_ingredients: editEntityContext.value.type === 'object' ? data.combination_ingredients : undefined,
      result_item_ids: editEntityContext.value.type === 'object' ? data.result_item_ids : undefined,
      kept_ingredients: editEntityContext.value.type === 'object' ? data.kept_ingredients : undefined,
      spatial_position: ['npc', 'object'].includes(editEntityContext.value.type) ? data.spatial_position : undefined,
      reveals_item_id: editEntityContext.value.type === 'object' ? data.reveals_item_id : undefined,
      pickup_trigger_mode: editEntityContext.value.type === 'object' ? (data.pickup_trigger_mode || 'silent') : undefined,
      pickup_trigger_cue: editEntityContext.value.type === 'object' ? String(data.pickup_trigger_cue || '') : undefined,
      switch_states: editEntityContext.value.type === 'object' ? data.switch_states : undefined,
      switch_state_labels: editEntityContext.value.type === 'object' ? data.switch_state_labels : undefined,
      switch_initial_state: editEntityContext.value.type === 'object' ? data.switch_initial_state : undefined,
      switch_disabled_states: editEntityContext.value.type === 'object' ? data.switch_disabled_states : undefined,
      switch_status_text: editEntityContext.value.type === 'object' ? data.switch_status_text : undefined,
      switch_transitions: editEntityContext.value.type === 'object' ? data.switch_transitions : undefined,
      on_success_script: editEntityContext.value.type === 'object' ? data.on_success_script : undefined,
      on_failure_script: editEntityContext.value.type === 'object' ? data.on_failure_script : undefined,
      effects: editEntityContext.value.type === 'object' ? data.effects : undefined,
      stat_modifier_strength: editEntityContext.value.type === 'object' ? data.stat_modifier_strength : undefined,
      is_hidden: ['npc', 'object'].includes(editEntityContext.value.type) ? data.is_hidden : undefined,
      reveal_rule: ['npc', 'object'].includes(editEntityContext.value.type) ? data.reveal_rule : undefined,
      on_pickup_script: editEntityContext.value.type === 'object' ? data.on_pickup_script : undefined,
      on_pickup_text: editEntityContext.value.type === 'object' ? data.on_pickup_text : undefined,
      on_drop_script: editEntityContext.value.type === 'object' ? data.on_drop_script : undefined,
      on_drop_text: editEntityContext.value.type === 'object' ? data.on_drop_text : undefined,
      on_equip_script: editEntityContext.value.type === 'object' ? data.on_equip_script : undefined,
      on_equip_text: editEntityContext.value.type === 'object' ? data.on_equip_text : undefined,
      on_unequip_script: editEntityContext.value.type === 'object' ? data.on_unequip_script : undefined,
      on_unequip_text: editEntityContext.value.type === 'object' ? data.on_unequip_text : undefined,
      on_defeat_script: editEntityContext.value.type === 'npc' ? data.on_defeat_script : undefined,
      on_defeat_text: editEntityContext.value.type === 'npc' ? data.on_defeat_text : undefined,
      on_protagonist_enters_scene_script: editEntityContext.value.type === 'npc' ? data.on_protagonist_enters_scene_script : undefined,
      on_protagonist_enters_scene_text: editEntityContext.value.type === 'npc' ? data.on_protagonist_enters_scene_text : undefined,
      on_receive_item_script: editEntityContext.value.type === 'npc' ? data.on_receive_item_script : undefined,
      on_receive_item_text: editEntityContext.value.type === 'npc' ? data.on_receive_item_text : undefined,
      on_recruit_success_script: editEntityContext.value.type === 'npc' ? data.on_recruit_success_script : undefined,
      on_recruit_success_text: editEntityContext.value.type === 'npc' ? data.on_recruit_success_text : undefined,
      on_recruit_failure_script: editEntityContext.value.type === 'npc' ? data.on_recruit_failure_script : undefined,
      on_recruit_failure_text: editEntityContext.value.type === 'npc' ? data.on_recruit_failure_text : undefined,
      reveal_guard_expression: editEntityContext.value.type === 'npc' ? data.reveal_guard_expression : undefined,
      memory_slots: editEntityContext.value.type === 'npc' ? Number(data.memory_slots) || 0 : undefined,
      ...(editEntityContext.value.type === 'npc' ? conversationSavePayload(data) : {}),
      on_interact_script: ['npc', 'object'].includes(editEntityContext.value.type) ? data.on_interact_script : undefined,
      on_interact_text: ['npc', 'object'].includes(editEntityContext.value.type) ? data.on_interact_text : undefined,
      on_enter_scene_script: editEntityContext.value.type === 'scene' ? data.on_enter_scene_script : undefined,
      on_enter_scene_text: editEntityContext.value.type === 'scene' ? data.on_enter_scene_text : undefined,
      on_leave_scene_script: editEntityContext.value.type === 'scene' ? data.on_leave_scene_script : undefined,
      on_leave_scene_text: editEntityContext.value.type === 'scene' ? data.on_leave_scene_text : undefined,
      helpers_script: editEntityContext.value.type === 'scene' ? data.helpers_script : undefined,
      unlock_expression: editEntityContext.value.type === 'object' ? data.unlock_expression : undefined,
      on_unlock_success_script: editEntityContext.value.type === 'object' ? data.on_unlock_success_script : undefined,
      on_unlock_success_text: editEntityContext.value.type === 'object' ? data.on_unlock_success_text : undefined,
      on_unlock_failure_script: editEntityContext.value.type === 'object' ? data.on_unlock_failure_script : undefined,
      on_unlock_failure_text: editEntityContext.value.type === 'object' ? data.on_unlock_failure_text : undefined,
      on_items_added_script: editEntityContext.value.type === 'object' ? data.on_items_added_script : undefined,
      on_items_added_text: editEntityContext.value.type === 'object' ? data.on_items_added_text : undefined,
      on_items_removed_script: editEntityContext.value.type === 'object' ? data.on_items_removed_script : undefined,
      on_items_removed_text: editEntityContext.value.type === 'object' ? data.on_items_removed_text : undefined,
      min_items: editEntityContext.value.type === 'object' ? data.min_items : undefined,
      max_items: editEntityContext.value.type === 'object' ? data.max_items : undefined,
      craft_guard_expression: editEntityContext.value.type === 'object' ? data.craft_guard_expression : undefined,
      on_craft_success_script: editEntityContext.value.type === 'object' ? data.on_craft_success_script : undefined,
      on_craft_success_text: editEntityContext.value.type === 'object' ? data.on_craft_success_text : undefined,
      on_craft_failure_script: editEntityContext.value.type === 'object' ? data.on_craft_failure_script : undefined,
      on_craft_failure_text: editEntityContext.value.type === 'object' ? data.on_craft_failure_text : undefined,
      on_read_script: editEntityContext.value.type === 'object' ? data.on_read_script : undefined,
      on_read_text: editEntityContext.value.type === 'object' ? data.on_read_text : undefined,
      // The backend only keeps these for WEAPON items.
      ...(editEntityContext.value.type === 'object' && String(data.item_type || '').toUpperCase() === 'WEAPON'
        ? weaponPayload(data.weapon_config)
        : {}),
    })

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

    closeEditEntityModal()
    await Promise.all([fetchAdventure(), fetchDebugInfo()])
    addNotification('Changes applied successfully.', 'success')
  } catch (error: any) {
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isSavingText.value = false
  }
}

/**
 * The adventure style (RPG / Story / Chat) has no save button of its own: a click saves only
 * this field, so other unsaved form edits are not stored by accident.
 */
async function handleUpdateRuleMode(mode: 'rpg' | 'story' | 'chat'): Promise<void> {
  const previous = form.value.rule_enforcement_mode
  if (mode === previous && mode === adventure.value?.rule_enforcement_mode) return
  form.value.rule_enforcement_mode = mode
  isSaving.value = true
  try {
    const updated = await adventureService.updateAdventure(props.adventureId, { rule_enforcement_mode: mode })
    if (adventure.value) {
      adventure.value.rule_enforcement_mode = updated?.rule_enforcement_mode ?? mode
    }
    addNotification(`Adventure style set to ${mode.toUpperCase()}.`, 'success')
  } catch (error: any) {
    form.value.rule_enforcement_mode = previous
    addNotification(error instanceof Error ? error.message : 'Failed to save the adventure style', 'error')
  } finally {
    isSaving.value = false
  }
}

async function saveChanges() {
  isSaving.value = true
  errorMsg.value = ''
  try {
    const teaserOrPlotChanged = (form.value.teaser || '') !== (adventure.value?.teaser || '')
      || (form.value.plot || '') !== (adventure.value?.plot || '')

    const existingStyle = Array.isArray(adventure.value?.selected_image_styles) ? adventure.value.selected_image_styles[0] : null
    const fullStyleObj = imageStylesCatalog.value.find(s => s.id === form.value.selected_style_id)
      || (existingStyle && typeof existingStyle === 'object' && existingStyle.id === form.value.selected_style_id ? existingStyle : { id: form.value.selected_style_id, name: form.value.selected_style_id })
    const existingTone = adventure.value?.selected_tone
    const fullToneObj = toneCatalog.value.find(t => t.id === form.value.selected_tone_id)
      || (existingTone && typeof existingTone === 'object' && (existingTone as any).id === form.value.selected_tone_id ? existingTone : { id: form.value.selected_tone_id, name: form.value.selected_tone_id })
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

    // Auto-run structural validation after every save. Only structural —
    // AI validation remains a manual action in the Validation tab to keep
    // save latency low and avoid uncontrolled LLM costs.
    if (activeTab.value === 'validation') {
      try {
        await adventureService.runValidation(props.adventureId, false)
      } catch {
        // Silent: validation is best-effort; user can retry manually.
      }
    }
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error while saving.'
    addNotification(errorMsg.value, 'error')
  } finally {
    isSaving.value = false
  }
}

const specialAttacksNpc = ref<any | null>(null)

async function onSpecialAttacksSaved() {
  await fetchDebugInfo()
  if (specialAttacksNpc.value) {
    const refreshed = editorNpcs.value.find((npc: any) => npc.id === specialAttacksNpc.value?.id)
    specialAttacksNpc.value = refreshed ?? null
  }
  addNotification('Combat & talent settings saved.', 'success')
}

/** Saves one protagonist field, or several at once when `field` is a map of field -> value. */
async function saveProtagonistField(field: string | Record<string, any>, newValue?: any) {
  const p = debugData.value?.protagonist
  if (!p) return
  const changes: Record<string, any> = typeof field === 'string' ? { [field]: newValue } : field
  isSavingText.value = true
  try {
    const updatePayload = {
      target_type: 'protagonist',
      target_id: p.id,
      name: 'name' in changes ? String(changes.name).trim() : p.name,
      description: 'description' in changes ? String(changes.description).trim() : p.description,
      hp: 'hp' in changes ? Number(changes.hp) : p.hp,
      stamina: 'stamina' in changes ? Number(changes.stamina) : p.stamina,
      mana: 'mana' in changes ? Number(changes.mana) : p.mana,
      goal: 'goal' in changes ? String(changes.goal).trim() : p.goal,
      character: 'character' in changes ? String(changes.character).trim() : p.character,
      appearance: 'appearance' in changes ? String(changes.appearance || '').trim() : p.appearance,
      voice: 'voice' in changes ? String(changes.voice || '') : (p.voice ?? undefined),
      strength: 'strength' in changes ? Number(changes.strength) : p.strength,
      intelligence: 'intelligence' in changes ? Number(changes.intelligence) : p.intelligence,
      wisdom: 'wisdom' in changes ? Number(changes.wisdom) : p.wisdom,
      dexterity: 'dexterity' in changes ? Number(changes.dexterity) : p.dexterity,
      charisma: 'charisma' in changes ? Number(changes.charisma) : p.charisma,
      armor_class: 'armor_class' in changes ? Number(changes.armor_class) : p.armor_class,
      exp: 'exp' in changes ? Number(changes.exp) : p.exp,
      inventory: 'inventory' in changes ? changes.inventory : (p.inventory ? p.inventory.map((i: any) => typeof i === 'string' ? i : (i?.id || '')) : []),
      equipment: 'equipment' in changes ? changes.equipment : (p.equipment ? Object.entries(p.equipment).reduce((acc: any, [k, v]: [string, any]) => {
        acc[k] = v ? (typeof v === 'string' ? v : (v?.id || null)) : null
        return acc
      }, {}) : {}),
      on_hp_change_script: 'on_hp_change_script' in changes ? String(changes.on_hp_change_script || '') : p.on_hp_change_script,
      on_hp_change_text: 'on_hp_change_text' in changes ? String(changes.on_hp_change_text || '') : p.on_hp_change_text,
      on_status_change_script: 'on_status_change_script' in changes ? String(changes.on_status_change_script || '') : p.on_status_change_script,
      on_status_change_text: 'on_status_change_text' in changes ? String(changes.on_status_change_text || '') : p.on_status_change_text,
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

function getVisualAppearance(kind: any, id: string): string {
  if (!debugData.value) return ''
  if (kind === 'protagonist') return debugData.value.protagonist?.appearance || ''
  if (kind === 'npc') return (debugData.value.npcs || []).find((n: any) => n.id === id)?.appearance || ''
  if (kind === 'cover') return debugData.value.adventure?.cover_appearance || ''
  if (kind === 'object') return (debugData.value.objects || []).find((o: any) => o.id === id)?.appearance || ''
  return ''
}

function openRegenerateDialog(kind: any, id: string, label: string) {
  const description = getVisualDescription(kind, id)
  const appearance = getVisualAppearance(kind, id)
  const hint = visualService.UPLOAD_LIMITS[kind as VisualKind].hint
  selectedVisual.value = { kind, id, label, description, hint, appearance }
  visualPrompt.value = ''
  useAdvancedModel.value = kind === 'scene' || kind === 'cover'
  applyStyle.value = true
  applyAppearance.value = true
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
    void askRegenerateAllConfirmation()
    return
  }
  void regenerateAll(kind, missingOnly)
}

/** Asks through the app-wide confirm dialog before images of a whole section are replaced. */
async function askRegenerateAllConfirmation(): Promise<void> {
  const pending = pendingBatchRegeneration.value
  if (!pending) return
  const confirmed = await confirmDialog({
    title: `Regenerate all ${getRegenerateKindLabel(pending.kind)} images?`,
    message: 'Existing images in this section are replaced one by one.',
    confirmLabel: 'Regenerate all',
  })
  if (confirmed) {
    confirmRegenerateAll()
  } else {
    cancelRegenerateAllDialog()
  }
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
       controller.signal,
       applyStyle.value,
       applyAppearance.value
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

async function enhancePrompt() {
  if (!selectedVisual.value || isEnhancingPrompt.value) return
  const currentPrompt = visualPrompt.value.trim()
  if (!currentPrompt) return
  isEnhancingPrompt.value = true
  promptError.value = ''
  try {
    const enhanced = await visualService.enhancePrompt(
      props.adventureId,
      currentPrompt,
      selectedVisual.value.kind,
      selectedVisual.value.id,
      applyAppearance.value,
      selectedVisual.value.appearance
    )
    if (enhanced) {
      visualPrompt.value = enhanced
      addNotification('Prompt enhanced with AI.', 'success')
    } else {
      addNotification('AI returned an empty enhanced prompt.', 'info')
    }
  } catch (error: any) {
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isEnhancingPrompt.value = false
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
       selectedVisual.value.id,
       applyAppearance.value
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
  
  for (const controller of activeAbortControllers.value.values()) {
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
    await Promise.all([fetchAdventure(), fetchDebugInfo(), fetchCatalogs(), fetchVoiceList()])
  },
  { immediate: true }
)

async function handleUpdateSequences(newSequences: any[]) {
  isSaving.value = true
  try {
    await adventureService.updateAdventure(props.adventureId, { sequences: newSequences } as any)
    await fetchAdventure()
    addNotification('Sequences updated.', 'success')
  } catch (error: any) {
    addNotification(error instanceof Error ? error.message : 'Failed to update sequences', 'error')
  } finally {
    isSaving.value = false
  }
}

async function handleUpdateProgressionMode(mode: 'linear' | 'dynamic') {
  isSaving.value = true
  try {
    const updated = await adventureService.updateAdventure(props.adventureId, { sequence_progression_mode: mode } as any)
    if (updated) {
      adventure.value = updated
    }
    await fetchAdventure()
    addNotification(`Progression mode set to ${mode}.`, 'success')
  } catch (error: any) {
    addNotification(error instanceof Error ? error.message : 'Failed to update progression mode', 'error')
  } finally {
    isSaving.value = false
  }
}

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

let dynamicSaveSeq = 0

async function handleUpdateDynamicGeneration(nextConfig?: DynamicGenerationConfig) {
  const payload = normalizeDynamicGenerationForm(nextConfig ?? form.value.dynamic_generation)
  form.value.dynamic_generation = payload
  const seq = ++dynamicSaveSeq
  isSaving.value = true
  errorMsg.value = ''
  try {
    const updated = await adventureService.updateAdventure(props.adventureId, {
      dynamic_generation: payload,
    })
    if (seq !== dynamicSaveSeq) return
    if (updated?.dynamic_generation) {
      form.value.dynamic_generation = normalizeDynamicGenerationForm(updated.dynamic_generation)
      if (adventure.value) {
        adventure.value.dynamic_generation = updated.dynamic_generation
      }
    }
    addNotification('Dynamic Generator settings saved.', 'success')
  } catch (error: any) {
    if (seq !== dynamicSaveSeq) return
    errorMsg.value = error?.message || 'Failed to save Dynamic Generator settings.'
    addNotification(errorMsg.value, 'error')
  } finally {
    if (seq === dynamicSaveSeq) {
      isSaving.value = false
    }
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

// Trigger overview "Edit": entity editors open as modal, the rest switch to their tab.
const TRIGGER_OWNER_TABS = { global: 'scripts', protagonist: 'protagonist', sequence: 'sequences', exit: 'map' } as const

function handleTriggerTreeEdit(node: TriggerTreeNode): void {
  const tab = TRIGGER_OWNER_TABS[node.kind as keyof typeof TRIGGER_OWNER_TABS]
  if (tab) {
    activeTab.value = tab
    return
  }
  const id = String(node.id || '')
  if (node.kind === 'scene') {
    const scene = editorScenes.value.find((s: any) => String(s.id) === id)
    openTextEdit('scene', id, scene?.label || scene?.name || id, scene?.description || '')
    return
  }
  if (node.kind === 'npc') {
    const npc = editorNpcs.value.find((n: any) => String(n.id) === id)
    openTextEdit('npc', id, npc?.name || id, npc?.description || '', '', npc?.hp, npc?.stamina, npc?.mana, npc?.goal, npc?.character, npc?.is_killable)
    return
  }
  const item = editorAllItems.value.find((o: any) => String(o.id) === id)
  openTextEdit('object', id, item?.name || id, item?.description || '')
}

async function handleUpdateInitScript(initScript: string): Promise<void> {
  isSaving.value = true
  try {
    await adventureService.updateAdventure(props.adventureId, { init_script: initScript })
    await fetchAdventure()
    addNotification('Init script updated.', 'success')
  } catch (error: any) {
    addNotification(error instanceof Error ? error.message : 'Failed to update init script', 'error')
  } finally {
    isSaving.value = false
  }
}

async function handleUpdateScripts(newScripts: any[]) {
  isSaving.value = true
  try {
    await adventureService.updateAdventure(props.adventureId, { scripts: newScripts } as any)
    await fetchAdventure()
    addNotification('Scripts updated.', 'success')
  } catch (error: any) {
    addNotification(error instanceof Error ? error.message : 'Failed to update scripts', 'error')
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

// Objects carry their scene so pickers can sort and label them by location.
type ReferenceEntry = {
  id: string
  name: string
  imageUrl?: string | null
  type: string
  itemType?: string
  sceneLabel?: string
  sceneOrder?: number
}

const referenceOptions = computed<ReferenceEntry[]>(() => {
  const entries: ReferenceEntry[] = []
  
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
  const sceneIndex = new Map<string, number>(editorScenes.value.map((scene: any, i: number) => [String(scene.id), i]))
  for (const obj of objects) {
    const sceneId = String(obj.current_scene_id || '')
    const sceneOrder = sceneIndex.get(sceneId)
    const scene = sceneOrder === undefined ? null : editorScenes.value[sceneOrder]
    entries.push({
      id: String(obj.id || ''),
      name: String(obj.name || obj.id || ''),
      imageUrl: obj.image_url ? buildVisualImageUrl(obj.image_url) : null,
      type: 'OBJECT',
      itemType: String(obj.item_type || '').toUpperCase(),
      sceneLabel: scene ? String(scene.label || scene.name || scene.id) : undefined,
      sceneOrder,
    })
  }
  return entries.filter((entry) => entry.id)
})

const sceneReferenceOptions = computed(() => {
  return referenceOptions.value.filter((entry) => entry.type === 'SCENE')
})

const canShowSceneRoutePanel = computed(() => route.name === 'adventure-editor-scene')
const canShowExitRoutePanel = computed(() => route.name === 'adventure-editor-exit')
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

function openSceneEditorRoute(sceneId: string) {
  const normalized = String(sceneId || '').trim()
  if (!normalized || normalized.startsWith('DYN_')) return
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

function openAudioLibrary() {
  closeSceneEditorDialog()
  activeTab.value = 'audio'
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
    is_revealed: false,
    companions_allowed: true,
    lock_description: '',
    code_to_unlock: '',
    item_to_unlock: '',
    rule_to_unlock: '',
    on_open_exit_script: '',
    on_open_exit_text: '',
    on_exit_used_script: '',
    on_exit_used_text: '',
    unlock_expression: '',
    on_unlock_success_script: '',
    on_unlock_success_text: '',
    on_unlock_failure_script: '',
    on_unlock_failure_text: '',
    dynamic_zone: null,
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
  void askDeleteConfirmation()
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
  void askDeleteConfirmation()
}

function requestDeleteItem(itemId: string, itemName?: string) {
  const normalized = String(itemId || '').trim()
  if (!normalized) return
  activeMenuId.value = null
  pendingDeleteTarget.value = {
    kind: 'entity',
    id: normalized,
    title: `Delete Item "${itemName || normalized}"?`,
    description:
      'This permanently removes the item from the world. References to this item (e.g. container inventories, unlock requirements) will need to be re-attached afterwards.',
  }
  void askDeleteConfirmation()
}

function requestChangeItemType(itemId: string, itemName: string, currentItemType: string) {
  const normalized = String(itemId || '').trim()
  if (!normalized) return
  activeMenuId.value = null
  itemTypeChangeTarget.value = {
    id: normalized,
    name: String(itemName || normalized),
    currentItemType: String(currentItemType || 'DEFAULT').toUpperCase(),
  }
  showItemTypeChangeModal.value = true
}

function closeChangeItemTypeModal() {
  if (isChangingItemType.value) return
  showItemTypeChangeModal.value = false
  itemTypeChangeTarget.value = null
}

async function confirmChangeItemType(newItemType: string) {
  const target = itemTypeChangeTarget.value
  if (!target) return
  const normalized = String(newItemType || '').trim().toUpperCase()
  if (!normalized || normalized === target.currentItemType) {
    closeChangeItemTypeModal()
    return
  }
  isChangingItemType.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'object',
      target_id: target.id,
      item_type: normalized,
    })
    await Promise.all([fetchAdventure(), fetchDebugInfo()])
    addNotification(`Item "${target.name}" is now ${normalized}.`, 'success')
    // closeChangeItemTypeModal() refuses to close while the change is still running.
    isChangingItemType.value = false
    closeChangeItemTypeModal()
  } catch (error: any) {
    addNotification(error?.message || 'Failed to change item type.', 'error')
  } finally {
    isChangingItemType.value = false
  }
}

function requestMoveItemToScene(itemId: string, itemName: string, currentSceneId: string) {
  requestMoveEntityToScene('object', itemId, itemName, currentSceneId)
}

function requestMoveNpcToScene(npcId: string, npcName: string, currentSceneId: string) {
  requestMoveEntityToScene('npc', npcId, npcName, currentSceneId)
}

function requestMoveEntityToScene(type: 'npc' | 'object', entityId: string, entityName: string, currentSceneId: string) {
  const normalized = String(entityId || '').trim()
  if (!normalized) return
  activeMenuId.value = null
  moveEntityTarget.value = {
    type,
    id: normalized,
    name: String(entityName || normalized),
    currentSceneId: String(currentSceneId || '').trim().toUpperCase(),
  }
  showMoveItemModal.value = true
}

function closeMoveItemModal() {
  if (isMovingItem.value) return
  showMoveItemModal.value = false
  moveEntityTarget.value = null
}

async function confirmMoveEntityToScene(targetSceneId: string) {
  const target = moveEntityTarget.value
  if (!target) return
  const normalizedSceneId = String(targetSceneId || '').trim().toUpperCase()
  if (
    !normalizedSceneId ||
    normalizedSceneId === target.currentSceneId
  ) {
    return
  }
  isMovingItem.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: target.type,
      target_id: target.id,
      current_scene_id: normalizedSceneId,
    })
    await fetchDebugInfo()
    const label = target.type === 'npc' ? 'NPC' : 'Item'
    addNotification(`${label} "${target.name}" moved to ${normalizedSceneId}.`, 'success')
    // closeMoveItemModal() refuses to close while a move is still running.
    isMovingItem.value = false
    closeMoveItemModal()
  } catch (error: any) {
    addNotification(error?.message || `Failed to move ${target.type === 'npc' ? 'NPC' : 'item'}.`, 'error')
  } finally {
    isMovingItem.value = false
  }
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

/** Asks through the app-wide confirm dialog, then deletes the pending scene, exit or entity. */
async function askDeleteConfirmation(): Promise<void> {
  const target = pendingDeleteTarget.value
  if (!target) return
  const confirmed = await confirmDialog({
    title: target.title,
    message: `${target.description}\n\nTarget: ${target.id}`,
    confirmLabel: 'Delete',
    danger: true,
  })
  if (confirmed) {
    await confirmDeleteRouteAsset()
  } else {
    closeDeleteConfirmDialog()
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
    is_revealed: Boolean(exit.is_revealed),
    companions_allowed: exit.companions_allowed !== false,
    lock_description: String(exit.lock_description || ''),
    code_to_unlock: String(exit.code_to_unlock || ''),
    item_to_unlock: String(exit.item_to_unlock || ''),
    rule_to_unlock: String(exit.rule_to_unlock || ''),
    on_open_exit_script: String(exit.on_open_exit_script || ''),
    on_open_exit_text: String(exit.on_open_exit_text || ''),
    on_exit_used_script: String(exit.on_exit_used_script || ''),
    on_exit_used_text: String(exit.on_exit_used_text || ''),
    unlock_expression: String(exit.unlock_expression || ''),
    on_unlock_success_script: String(exit.on_unlock_success_script || ''),
    on_unlock_success_text: String(exit.on_unlock_success_text || ''),
    on_unlock_failure_script: String(exit.on_unlock_failure_script || ''),
    on_unlock_failure_text: String(exit.on_unlock_failure_text || ''),
    dynamic_zone: exit.dynamic_zone
      ? {
          ...exit.dynamic_zone,
          instructions: exit.dynamic_zone.instructions ?? '',
          cluster_consistency:
            exit.dynamic_zone.cluster_consistency !== undefined
              ? Boolean(exit.dynamic_zone.cluster_consistency)
              : true,
        }
      : null,
  }
  showExitModal.value = true

}

async function saveExitModal(formData: any) {
  const fromSceneId = String(formData.from_scene_id || activeMapSceneId.value || '').trim()
  const isDynamic = Boolean(formData.dynamic_zone)
  let toSceneId = String(formData.to_scene_id || '').trim()
  if (isDynamic && (!toSceneId || !toSceneId.startsWith('DYN_'))) {
    toSceneId = buildDynamicPlaceholderSceneId(
      formData.dynamic_zone?.zone_id || 'ZONE_WILD',
      Number(formData.dynamic_zone?.depth || 1),
      1,
    )
  }
  const label = String(formData.label || '').trim()
  const lockDescription = String(formData.lock_description || '').trim()

  if (!fromSceneId || !label) {
    addNotification('Exit requires a source scene and label.', 'error')
    return
  }

  if (isCreateExitMode.value && !isDynamic && !toSceneId) {
    addNotification('Exit requires a destination scene.', 'error')
    return
  }

  if (isCreateExitMode.value && !isDynamic && toSceneId === fromSceneId) {
    addNotification('Exit destination must be a different scene.', 'error')
    return
  }

  isSavingText.value = true
  promptError.value = ''
  const wasCreate = isCreateExitMode.value
  try {
    if (wasCreate) {
      await entityService.createExit(props.adventureId, {
        from_scene_id: fromSceneId,
        to_scene_id: toSceneId,
        label,
        exit_type: formData.exit_type,
        is_revealed: Boolean(formData.is_revealed),
        dynamic_zone: formData.dynamic_zone ?? null,
        companions_allowed: formData.companions_allowed !== false,
        lock_description: lockDescription || undefined,
        code_to_unlock: formData.code_to_unlock || undefined,
        item_to_unlock: formData.item_to_unlock || undefined,
        rule_to_unlock: formData.rule_to_unlock || undefined,
        on_open_exit_script: formData.on_open_exit_script || undefined,
        on_open_exit_text: formData.on_open_exit_text || undefined,
        on_exit_used_script: formData.on_exit_used_script || undefined,
        on_exit_used_text: formData.on_exit_used_text || undefined,
        unlock_expression: formData.unlock_expression || undefined,
        on_unlock_success_script: formData.on_unlock_success_script || undefined,
        on_unlock_success_text: formData.on_unlock_success_text || undefined,
        on_unlock_failure_script: formData.on_unlock_failure_script || undefined,
        on_unlock_failure_text: formData.on_unlock_failure_text || undefined,
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
        revealed: Boolean(formData.is_revealed),
        dynamic_zone: formData.dynamic_zone ?? null,
        companions_allowed: formData.companions_allowed !== false,
        code_to_unlock: formData.code_to_unlock,
        item_to_unlock: formData.item_to_unlock,
        rule_to_unlock: formData.rule_to_unlock,
        on_open_exit_script: formData.on_open_exit_script,
        on_open_exit_text: formData.on_open_exit_text,
        on_exit_used_script: formData.on_exit_used_script,
        on_exit_used_text: formData.on_exit_used_text,
        unlock_expression: formData.unlock_expression,
        on_unlock_success_script: formData.on_unlock_success_script,
        on_unlock_success_text: formData.on_unlock_success_text,
        on_unlock_failure_script: formData.on_unlock_failure_script,
        on_unlock_failure_text: formData.on_unlock_failure_text,
        locked:
          formData.locked !== undefined
            ? formData.locked
            : Boolean(
                formData.code_to_unlock ||
                  formData.item_to_unlock ||
                  formData.rule_to_unlock ||
                  formData.unlock_expression,
              ),
      })
      addNotification('Exit updated.', 'success')

    }
    activeEditExitId.value = null
    isCreateExitMode.value = false
    showExitModal.value = false
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
  void askDeleteConfirmation()
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
      // Only leave the page when it showed the deleted exit; the scene editor stays open.
      if (activeMapExitId.value === target.id) {
        router.push({ name: 'adventure-editor', params: { adventureId: props.adventureId }, query: route.query })
      }
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

  return {
    router,
    route,
    ASSET_BASE,
    isQuickGenerating,
    isBatchGenerating,
    isGeneratingField,
    activeAbortControllers,
    isGenerating,
    isSavingText,
    showEditModal,
    editEntityContext,
    isCreateEntityMode,
    createEntitySceneId,
    createEntityType,
    pendingProtagonistAssignment,
    showItemTypeSelector,
    showAddExistingItemModal,
    addExistingItemKind,
    showExitModal,
    isCreateExitMode,
    activeEditExitId,
    exitModalForm,
    editForm,
    closeEditEntityModal,
    openAddExistingItem,
    closeAddExistingItemModal,
    editorAllObjects,
    matchesItemTypeFilter,
    addExistingItemOptions,
    handleAddExistingItemSelected,
    openCreateItem,
    openCreateNpc,
    createNewItemForProtagonist,
    handleItemTypeSelected,
    closeExitEditModal,
    adventure,
    debugData,
    isLoading,
    isSaving,
    errorMsg,
    promptError,
    showDebug,
    activeTab,
    sceneEditorReturnTab,
    exitEditorReturnTab,
    selectedVisual,
    selectedUploadTarget,
    visualPrompt,
    showPromptDialog,
    isRegenerating,
    isSuggestingPrompt,
    isEnhancingPrompt,
    useAdvancedModel,
    applyStyle,
    applyAppearance,
    showRegenerateAllConfirmDialog,
    pendingBatchRegeneration,
    showDeleteConfirmDialog,
    pendingDeleteTarget,
    showItemTypeChangeModal,
    itemTypeChangeTarget,
    isChangingItemType,
    showMoveItemModal,
    moveEntityTarget,
    isMovingItem,
    isUploading,
    isSettingStartScene,
    uploadInput,
    visualsCacheVersion,
    hoveredEntity,
    mousePos,
    activeMenuId,
    tooltipAlignTop,
    windowHeight,
    windowWidth,
    toggleMenu,
    imageStylesCatalog,
    configuredStyleName,
    toneCatalog,
    voiceList,
    fetchVoiceList,
    editorTabs,
    validationTabBadge,
    onValidationFindingsCount,
    validationBadgeText,
    getTabLabel,
    notifications,
    addNotification,
    handleHover,
    clearHover,
    uploadSelectedVisual,
    normalizeDynamicGenerationForm,
    form,
    editingField,
    tempValue,
    startEditing,
    cancelEditing,
    handleGenerateField,
    saveField,
    fetchCatalogs,
    editorNpcs,
    editorScenes,
    editorAllItems,
    itemsOfType,
    SECTIONED_ITEM_TYPES,
    editorObjects,
    editorSwitches,
    editorContainers,
    editorTextLogs,
    editorConstructables,
    fetchAdventure,
    exportEntity,
    importEntity,
    fetchDebugInfo,
    setStartScene,
    handleCreateScene,
    resolveEditAppearance,
    resolveEditVoice,
    openTextEdit,
    loadEntityEditor,
    openEntityPage,
    loadEntityFromWorld,
    saveEntityText,
    handleUpdateRuleMode,
    saveChanges,
    specialAttacksNpc,
    onSpecialAttacksSaved,
    saveProtagonistField,
    buildVisualImageUrl,
    downloadVisualAsset,
    getVisualAppearance,
    openRegenerateDialog,
    getVisualDescription,
    openUploadPicker,
    quickRegenerateVisual,
    requestRegenerateAll,
    cancelRegenerateAllDialog,
    confirmRegenerateAll,
    getRegenerateKindLabel,
    isImageMissingForRegeneration,
    regenerateAll,
    regenerateVisual,
    enhancePrompt,
    suggestPrompt,
    cancelRegeneration,
    stopAllGenerations,
    handleUpdateSequences,
    handleUpdateProgressionMode,
    handleUpdateQuests,
    dynamicSaveSeq,
    handleUpdateDynamicGeneration,
    handleUpdateAwards,
    TRIGGER_OWNER_TABS,
    handleTriggerTreeEdit,
    handleUpdateInitScript,
    handleUpdateScripts,
    goBack,
    activeMapSceneId,
    handleSceneIdChanged,
    activeMapExitId,
    routeSceneDetails,
    referenceOptions,
    sceneReferenceOptions,
    canShowSceneRoutePanel,
    canShowExitRoutePanel,
    isDeletingRouteAsset,
    isCreatingScene,
    createSceneForm,
    createSceneFormError,
    openCreateSceneForm,
    cancelCreateScene,
    openSceneEditorRoute,
    openAudioLibrary,
    closeSceneEditorDialog,
    openExitEditorRoute,
    closeExitEditorRoute,
    openCreateExitModal,
    requestDeleteRouteExit,
    requestDeleteRouteEntity,
    requestDeleteItem,
    requestChangeItemType,
    closeChangeItemTypeModal,
    confirmChangeItemType,
    requestMoveItemToScene,
    requestMoveNpcToScene,
    requestMoveEntityToScene,
    closeMoveItemModal,
    confirmMoveEntityToScene,
    handleCloneRouteEntity,
    closeDeleteConfirmDialog,
    openEditExitModal,
    saveExitModal,
    requestDeleteRouteScene,
    confirmDeleteRouteAsset,
    refreshData,
  }
}

export type AdventureEditor = ReturnType<typeof useAdventureEditor>
