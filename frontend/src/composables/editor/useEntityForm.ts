/**
 * State and logic of the entity form (moved unchanged from EditEntityModal, phase 3b of
 * docs/specs/workbench_ui.md). EditEntityModal provides it; the section components in
 * components/editor/entity/ read it with useEntityFormContext().
 */
import { computed, nextTick, ref, watch } from 'vue'
import {
  EDITOR_ID_PREFIXES,
  MAX_EDITOR_ID_LENGTH,
  isValidEditorId,
  itemTypePrefix,
} from '@/utils/editor_utils'
import { DICE_PATTERN, readWeaponConfig, type WeaponConfig } from '@/utils/weaponConfig'
import { AMOUNT_PATTERN } from '@/utils/specialAttacks'
import type { TtsVoiceList } from '@/types'
import { entityService } from '@/services/entityService'

export type EntityFormProps = {
  show: boolean
  /** `page`: rendered inline on the entity detail page instead of as an overlay. */
  variant?: 'modal' | 'page'
  /** Active form tab (simple, combat, companion, advanced); use with v-model:tab. */
  tab?: string
  context: { type: string; id: string } | null
  initialForm: {
    name: string
    teaser: string
    description: string
    hp: number
    stamina: number
    mana: number
    goal: string
    character: string
    npc_type?: string
    voice?: string
    appearance: string
    is_killable: boolean
    item_type: string
    is_portable: boolean
    locked: boolean
    quest_item?: boolean
    code_to_unlock: string
    item_to_unlock: string
    inventory_input: string[]
    text_log_content: string
    text_log_format: string
    entity_id: string
    wearable_slots_input: string[]
    combination_ingredients_input: string[]
    result_item_ids_input?: string[]
    kept_ingredients_input?: string[]
    reveal_rule?: string
    is_hidden?: boolean
    spatial_position: string
    reveals_item_id: string
    pickup_trigger_mode?: string
    pickup_trigger_cue?: string
    switch_states_json: string
    switch_state_labels?: Record<string, string>
    switch_initial_state: string
    switch_disabled_states?: string[]
    switch_transitions_json: string
    switch_status_text?: string
    min_items?: number | null
    max_items?: number | null
    on_success_script?: string
    on_failure_script?: string
    effects_hp: number
    effects_stamina: number
    effects_mana: number
    stat_modifier_strength: number
    is_item_type_fixed?: boolean
    is_wearable_slots_fixed?: boolean
    moveable?: boolean
    allowed_scenes_input?: string[]
    notes?: string
    unlock_expression?: string
    on_unlock_success_script?: string
    on_unlock_success_text?: string
    on_unlock_failure_script?: string
    on_unlock_failure_text?: string
    on_items_added_script?: string
    on_items_added_text?: string
    on_items_removed_script?: string
    on_items_removed_text?: string
    craft_guard_expression?: string
    on_craft_success_script?: string
    on_craft_success_text?: string
    on_craft_failure_script?: string
    on_craft_failure_text?: string
    on_read_script?: string
    weapon_config?: WeaponConfig
    on_read_text?: string
    on_leave_scene_script?: string
    on_leave_scene_text?: string
    helpers_script?: string
  }
  referenceOptions?: Array<{ id: string; name?: string; imageUrl?: string | null; type?: string }>
  ruleEnforcementMode: string
  isSaving: boolean
  adventureId?: string
  isCreateEntityMode?: boolean
  npcData?: any
  voiceList?: TtsVoiceList | null
}

export type EntityFormEmits = {
  (e: 'close'): void
  (e: 'update:tab', tab: string): void
  (e: 'save', data: any): void
  (e: 'combat-saved'): void
}

export function useEntityForm(props: EntityFormProps, emit: EntityFormEmits) {


type FormTab = 'simple' | 'stats' | 'movement' | 'inventory' | 'combat' | 'companion' | 'advanced'
const FORM_TABS: FormTab[] = ['simple', 'stats', 'movement', 'inventory', 'combat', 'companion', 'advanced']
const activeTab = ref<FormTab>('simple')
const isPage = computed(() => props.variant === 'page')

// On the detail page the tab lives in the URL; the page passes it in and receives changes.
watch(
  () => props.tab,
  (tab) => {
    if (tab && (FORM_TABS as string[]).includes(tab)) activeTab.value = tab as FormTab
  },
  { immediate: true },
)
watch(activeTab, (tab) => emit('update:tab', tab))
const editingTransitionIndex = ref<number | null>(null)
const showTransitionGuards = ref<boolean>(false)
const showTransitionScripts = ref<boolean>(false)
const showContainerGuard = ref<boolean>(false)
const showContainerTriggers = ref<boolean>(false)
const showConstructableGuard = ref<boolean>(false)
const showConstructableTriggers = ref<boolean>(false)

function hasActiveGuards(t: any): boolean {
  if (!t || !t.gates) return false
  return Boolean(
    (t.gates.item && String(t.gates.item).trim()) ||
    (t.gates.code && String(t.gates.code).trim()) ||
    (t.gates.rule && String(t.gates.rule).trim()) ||
    (t.gates.expression && String(t.gates.expression).trim())
  )
}

function hasActiveScripts(t: any): boolean {
  if (!t) return false
  return Boolean(
    (t.on_success_script && String(t.on_success_script).trim()) ||
    (t.on_failure_script && String(t.on_failure_script).trim())
  )
}

const localForm = ref({
  npc_type: 'HUMANOID',
  is_hidden: false,
  reveal_rule: '',
  moveable: false,
  allowed_scenes_input: [] as string[],
  notes: '',
  pickup_trigger_mode: 'silent',
  pickup_trigger_cue: '',
  attack_mode: 'PASSIVE',
  unlock_expression: '',
  on_unlock_success_script: '',
  on_unlock_success_text: '',
  on_unlock_failure_script: '',
  on_unlock_failure_text: '',
  on_items_added_script: '',
  on_items_added_text: '',
  on_items_removed_script: '',
  on_items_removed_text: '',
  craft_guard_expression: '',
  on_craft_success_script: '',
  on_craft_success_text: '',
  on_craft_failure_script: '',
  on_craft_failure_text: '',
  on_read_script: '',
  on_read_text: '',
  on_leave_scene_script: '',
  on_leave_scene_text: '',
  helpers_script: '',
  on_pickup_script: '',
  on_pickup_text: '',
  on_drop_script: '',
  on_drop_text: '',
  on_equip_script: '',
  on_equip_text: '',
  on_unequip_script: '',
  on_unequip_text: '',
  on_enter_scene_script: '',
  on_enter_scene_text: '',
  on_open_exit_script: '',
  on_open_exit_text: '',
  on_defeat_script: '',
  on_defeat_text: '',
  on_protagonist_enters_scene_script: '',
  on_protagonist_enters_scene_text: '',
  on_receive_item_script: '',
  on_receive_item_text: '',
  on_recruit_success_script: '',
  on_recruit_success_text: '',
  on_recruit_failure_script: '',
  on_recruit_failure_text: '',
  reveal_guard_expression: '',
  memory_slots: 0,
  on_interact_script: '',
  on_interact_text: '',
  on_success_script: '',
  on_failure_script: '',
  ...props.initialForm
})
const switchStates = ref<string[]>([])
const switchStateLabels = ref<Record<string, string>>({})
const switchDisabledStates = ref<string[]>([])
const switchTransitions = ref<any[]>([])

function syncFromForm() {
  let states: string[] = []
  try {
    const parsed = JSON.parse(localForm.value.switch_states_json || '[]')
    states = Array.isArray(parsed) ? parsed.map((s: any) => String(s).toUpperCase()) : []
  } catch {
    states = []
  }
  if (states.length === 0) {
    states = ['OFF', 'ON']
  }
  switchStates.value = states
  const labels = localForm.value.switch_state_labels || {}
  switchStateLabels.value = Object.fromEntries(
    Object.entries(labels).filter(([state, label]) => states.includes(state.toUpperCase()) && String(label).trim())
  )
  const rawDisabled = Array.isArray(localForm.value.switch_disabled_states)
    ? localForm.value.switch_disabled_states
    : []
  switchDisabledStates.value = rawDisabled
    .map((s: any) => String(s || '').trim().toUpperCase())
    .filter((s: string) => s && states.includes(s))

  const initial = String(localForm.value.switch_initial_state || '').trim().toUpperCase()
  if (!initial || !states.includes(initial)) {
    localForm.value.switch_initial_state = states[0] || ''
  }

  let transitions: any[] = []
  try {
    const parsed = JSON.parse(localForm.value.switch_transitions_json || '[]')
    transitions = Array.isArray(parsed) ? parsed : []
  } catch {
    transitions = []
  }
  
  switchTransitions.value = transitions.map((t: any) => ({
    from: String(t.from || t.from_state || '').toUpperCase(),
    to: String(t.to || t.to_state || '').toUpperCase(),
    gates: {
      item: t.gates?.item || t.required_item || '',
      code: t.gates?.code || t.code || '',
      rule: t.gates?.rule || t.required_rule || '',
      expression: t.gates?.expression || t.gates?.condition || '',
    },
    fail_message: t.fail_message || '',
    success_message: t.success_message || '',
    on_success_script: t.on_success_script || '',
    on_failure_script: t.on_failure_script || '',
  }))

  editingTransitionIndex.value = null
  showTransitionGuards.value = false
  showTransitionScripts.value = false

  localForm.value.on_success_script = props.initialForm?.on_success_script || (props.context as any)?.on_success_script || ''
  localForm.value.on_failure_script = props.initialForm?.on_failure_script || (props.context as any)?.on_failure_script || ''
}

// Initial sync
syncFromForm()

function addState() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  let newName = 'STATE_A'
  for (let i = 0; i < chars.length; i++) {
    const candidate = `STATE_${chars[i]}`
    if (!switchStates.value.includes(candidate)) {
      newName = candidate
      break
    }
  }
  switchStates.value.push(newName)
}

function removeState(index: number) {
  const removed = switchStates.value[index]
  switchStates.value.splice(index, 1)
  switchStateLabels.value = Object.fromEntries(
    Object.entries(switchStateLabels.value).filter(([state]) => state !== removed)
  )
  switchDisabledStates.value = switchDisabledStates.value.filter(s => s !== removed)
  
  if (localForm.value.switch_initial_state === removed) {
    localForm.value.switch_initial_state = switchStates.value[0] || ''
  }
  
  switchTransitions.value = switchTransitions.value.filter(
    t => t.from !== removed && t.to !== removed
  )

  if (editingTransitionIndex.value !== null && editingTransitionIndex.value >= switchTransitions.value.length) {
    editingTransitionIndex.value = null
  }
}

// State IDs are script keys: A-Z, 0-9, "_" and "-", at most 15 characters.
function updateStateValue(index: number, val: string) {
  const oldVal = switchStates.value[index]
  const cleanVal = val.toUpperCase().replace(/[^A-Z0-9_-]/g, '').slice(0, 15)
  switchStates.value[index] = cleanVal
  if (oldVal in switchStateLabels.value) {
    const { [oldVal]: label, ...rest } = switchStateLabels.value
    switchStateLabels.value = cleanVal ? { ...rest, [cleanVal]: label } : rest
  }
  if (switchDisabledStates.value.includes(oldVal)) {
    switchDisabledStates.value = switchDisabledStates.value
      .map(s => (s === oldVal ? cleanVal : s))
      .filter(Boolean)
  }
  
  if (localForm.value.switch_initial_state === oldVal) {
    localForm.value.switch_initial_state = cleanVal
  }
  
  switchTransitions.value.forEach(t => {
    if (t.from === oldVal) t.from = cleanVal
    if (t.to === oldVal) t.to = cleanVal
  })
}

function startAddTransition() {
  switchTransitions.value.push({
    from: '',
    to: switchStates.value[0] || '',
    gates: {
      item: '',
      code: '',
      rule: '',
      expression: '',
    },
    fail_message: '',
    success_message: '',
    on_success_script: '',
    on_failure_script: '',
  })
  editingTransitionIndex.value = switchTransitions.value.length - 1
  showTransitionGuards.value = false
  showTransitionScripts.value = false
}

function toggleEditTransition(index: number) {
  if (editingTransitionIndex.value === index) {
    editingTransitionIndex.value = null
  } else {
    editingTransitionIndex.value = index
    showTransitionGuards.value = false
    showTransitionScripts.value = false
  }
}

function removeTransition(index: number) {
  switchTransitions.value.splice(index, 1)
  if (editingTransitionIndex.value === index) {
    editingTransitionIndex.value = null
  } else if (editingTransitionIndex.value !== null && editingTransitionIndex.value > index) {
    editingTransitionIndex.value--
  }
}

const itemReferenceOptions = computed(() => {
  const source = props.referenceOptions || []
  return source
    .filter((option) => {
      if (String(option.type || '').toUpperCase() !== 'OBJECT') return false
      const itemType = String((option as any).itemType || '').toUpperCase()
      if (itemType === 'CONTAINER' || itemType === 'CONTAINER_SWITCH') return false
      if (itemType === 'SWITCH') return false
      return true
    })
    .map((option) => ({
      ...option,
      name: option.name || option.id || '',
    }))
})

const currentEntityId = computed(() => String(localForm.value.entity_id || props.initialForm?.entity_id || '').trim().toUpperCase())

/**
 * Items that can gate a transition or unlock: anything the player can carry, so portable
 * switches (e.g. a remote) count, while recipes and the entity itself do not.
 */
const keyItemReferenceOptions = computed(() => {
  return (props.referenceOptions || [])
    .filter((option) => {
      if (String(option.type || '').toUpperCase() !== 'OBJECT') return false
      if (String(option.id || '').toUpperCase() === currentEntityId.value) return false
      return String((option as any).itemType || '').toUpperCase() !== 'CONSTRUCTABLE'
    })
    .map((option) => ({
      ...option,
      name: option.name || option.id || '',
    }))
})

const containedItemReferenceOptions = computed(() => {
  return itemReferenceOptions.value.filter((option) => {
    return String(option.id || '').toUpperCase() !== currentEntityId.value
  })
})

// CONSTRUCTABLE recipes never appear in the game, so physical/item fields are hidden for them.
const isRecipe = computed(() => props.context?.type === 'object' && currentItemType.value === 'CONSTRUCTABLE')

/** Recipes have no player-facing description; one is derived from the recipe for the editor lists. */
function recipeDescription(ingredients: string[], results: string[]): string {
  const from = ingredients.join(' + ') || '?'
  const to = results.join(', ') || '?'
  return `Constructable: ${from} -> ${to}`
}

const recipeIngredientOptions = computed(() => {
  return itemReferenceOptions.value.filter((option) => {
    if (String(option.id || '').toUpperCase() === currentEntityId.value) return false
    return String((option as any).itemType || '').toUpperCase() !== 'CONSTRUCTABLE'
  })
})

const recipeResultOptions = computed(() => {
  return (props.referenceOptions || [])
    .filter((option) => {
      if (String(option.type || '').toUpperCase() !== 'OBJECT') return false
      if (String(option.id || '').toUpperCase() === currentEntityId.value) return false
      return String((option as any).itemType || '').toUpperCase() !== 'CONSTRUCTABLE'
    })
    .map((option) => ({ ...option, name: option.name || option.id || '' }))
})

const entityImageUrl = computed(() => {
  if (props.isCreateEntityMode || !props.context) return null
  const targetId = String(props.context.id || '').toUpperCase()
  const targetType = props.context.type.toUpperCase()
  const match = (props.referenceOptions || []).find(
    (option) => String(option.id || '').toUpperCase() === targetId && option.type === targetType
  )
  return match?.imageUrl || null
})

const currentItemType = computed(() => String(localForm.value.item_type || '').toUpperCase())

const entityIdPrefix = computed(() => {
  if (props.context?.type === 'scene') return EDITOR_ID_PREFIXES.SCENE
  if (props.context?.type === 'npc') return EDITOR_ID_PREFIXES.NPC
  return itemTypePrefix(localForm.value.item_type)
})

const originalEntityId = computed(() =>
  String(props.initialForm.entity_id || props.context?.id || '').trim().toUpperCase(),
)

const takenEntityIds = computed(() =>
  (props.referenceOptions || [])
    .map((entry) => String(entry.id || '').toUpperCase())
    .filter((id) => id !== originalEntityId.value),
)

const entityIdError = computed(() => {
  const val = (localForm.value.entity_id || '').trim().toUpperCase()
  if (!val) return 'ID is required.'

  const isUnchangedLegacy = !props.isCreateEntityMode && val === originalEntityId.value
  if (!isUnchangedLegacy && !isValidEditorId(val, MAX_EDITOR_ID_LENGTH)) {
    return `ID must use uppercase A-Z, 0-9, or _ only (max ${MAX_EDITOR_ID_LENGTH} chars).`
  }

  const takenIds = new Set(takenEntityIds.value)
  if (takenIds.has(val)) {
    return `ID "${val}" already exists in this adventure.`
  }
  return ''
})

const isFormInvalid = computed(() => {
  const nameInvalid = !(localForm.value.name || '').trim() ||
         (localForm.value.name || '').length > 50
  const descInvalid = !isRecipe.value && !(localForm.value.description || '').trim() ||
         (localForm.value.description || '').length > 1000
  const personaInvalid = (localForm.value.goal || '').length > 200 ||
         (localForm.value.character || '').length > 200
  const teaserInvalid = (localForm.value.teaser || '').length > 300 ||
         (localForm.value.appearance || '').length > 100
  const hasEditableId = props.isCreateEntityMode || (props.context && ['npc', 'object', 'scene'].includes(props.context.type))
  const currentIdVal = (localForm.value.entity_id || '').trim().toUpperCase()
  const isUnchangedLegacy = !props.isCreateEntityMode && currentIdVal === originalEntityId.value
  const maxIdLen = isUnchangedLegacy ? 50 : MAX_EDITOR_ID_LENGTH
  const idInvalid = hasEditableId
    ? (!currentIdVal || currentIdVal.length > maxIdLen || !!entityIdError.value)
    : false
  // A recipe needs at least two ingredients and one result.
  const ingredientsCount = Array.isArray(localForm.value.combination_ingredients_input)
    ? localForm.value.combination_ingredients_input.filter((s: string) => Boolean(s)).length
    : 0
  const resultsCount = (localForm.value.result_item_ids_input || []).filter(Boolean).length
  const combinationInvalid = currentItemType.value === 'CONSTRUCTABLE' && (ingredientsCount < 2 || resultsCount < 1)
  const uniqueStates = new Set(switchStates.value.map(s => s.trim().toUpperCase()))
  const switchInvalid = ['SWITCH', 'CONTAINER_SWITCH'].includes(currentItemType.value) && (
    switchStates.value.length < 2 ||
    uniqueStates.size !== switchStates.value.length ||
    switchStates.value.some(s => !s.trim()) ||
    !(localForm.value.switch_initial_state || '').trim() ||
    !uniqueStates.has(String(localForm.value.switch_initial_state).trim().toUpperCase()) ||
    switchTransitions.value.some(t => !t.to || !uniqueStates.has(t.to) || (t.from && !uniqueStates.has(t.from)))
  )
  const minCap = Number(localForm.value.min_items || 0)
  const maxCap = Number(localForm.value.max_items || 0)
  const capacityInvalid = ['CONTAINER', 'CONTAINER_SWITCH'].includes(currentItemType.value) && minCap > 0 && maxCap > 0 && minCap > maxCap
  return nameInvalid || descInvalid || personaInvalid || teaserInvalid || idInvalid || combinationInvalid || switchInvalid || capacityInvalid || weaponInvalid.value
})

const weaponInvalid = computed(() => {
  const config = localForm.value.weapon_config as WeaponConfig | undefined
  if (currentItemType.value !== 'WEAPON' || !config) return false
  return !DICE_PATTERN.test(config.damage_dice.replace(/\s/g, ''))
    || config.effects.some((e) => !AMOUNT_PATTERN.test(e.amount.replace(/\s/g, '')))
})

// Items switched to WEAPON in the editor start with the default combat settings.
watch(currentItemType, (type) => {
  if (type === 'WEAPON' && !localForm.value.weapon_config) localForm.value.weapon_config = readWeaponConfig()
})

watch(() => props.initialForm, (newVal) => {
  localForm.value = {
    is_hidden: false,
    reveal_rule: '',
    moveable: false,
    allowed_scenes_input: [],
    notes: '',
    pickup_trigger_mode: 'silent',
    pickup_trigger_cue: '',
    attack_mode: 'PASSIVE',
    on_pickup_script: '',
    on_pickup_text: '',
    on_drop_script: '',
    on_drop_text: '',
    on_equip_script: '',
    on_equip_text: '',
    on_unequip_script: '',
    on_unequip_text: '',
    on_enter_scene_script: '',
    on_enter_scene_text: '',
    on_open_exit_script: '',
    on_open_exit_text: '',
    on_defeat_script: '',
    on_defeat_text: '',
    on_protagonist_enters_scene_script: '',
    on_protagonist_enters_scene_text: '',
    on_receive_item_script: '',
    on_receive_item_text: '',
    on_recruit_success_script: '',
    on_recruit_success_text: '',
    on_recruit_failure_script: '',
    on_recruit_failure_text: '',
    reveal_guard_expression: '',
    memory_slots: 0,
    on_interact_script: '',
    on_interact_text: '',
    ...newVal
  }
  syncFromForm()
}, { deep: true })

watch(() => props.show, (newVal) => {
  if (newVal) {
    activeTab.value = isPage.value && props.tab && (FORM_TABS as string[]).includes(props.tab) ? (props.tab as FormTab) : 'simple'
    localForm.value = {
      npc_type: 'HUMANOID',
      is_hidden: false,
      reveal_rule: '',
      moveable: false,
      allowed_scenes_input: [],
      notes: '',
      pickup_trigger_mode: 'silent',
      pickup_trigger_cue: '',
      attack_mode: 'PASSIVE',
      on_pickup_script: '',
      on_pickup_text: '',
      on_drop_script: '',
      on_drop_text: '',
      on_equip_script: '',
      on_equip_text: '',
      on_unequip_script: '',
      on_unequip_text: '',
      on_enter_scene_script: '',
      on_enter_scene_text: '',
      on_open_exit_script: '',
      on_open_exit_text: '',
      on_defeat_script: '',
      on_defeat_text: '',
      on_protagonist_enters_scene_script: '',
      on_protagonist_enters_scene_text: '',
      on_receive_item_script: '',
      on_receive_item_text: '',
      on_recruit_success_script: '',
      on_recruit_success_text: '',
      on_recruit_failure_script: '',
      on_recruit_failure_text: '',
      reveal_guard_expression: '',
      memory_slots: 0,
      on_interact_script: '',
      on_interact_text: '',
      ...props.initialForm
    }
    syncFromForm()
  }
})

watch(() => activeTab.value, () => {
  nextTick(() => {
    window.dispatchEvent(new Event('resize'))
  })
})

const sceneReferenceOptions = computed(() => {
  return (props.referenceOptions || []).filter(
    (entry) => String(entry.type || '').toUpperCase() === 'SCENE'
  )
})

function isSceneAllowed(sceneId: string): boolean {
  const list = localForm.value.allowed_scenes_input || []
  return list.some((id: string) => String(id).toUpperCase() === String(sceneId).toUpperCase())
}

function toggleAllowedScene(sceneId: string): void {
  const current = localForm.value.allowed_scenes_input || []
  const upper = String(sceneId).toUpperCase()
  if (isSceneAllowed(sceneId)) {
    localForm.value.allowed_scenes_input = current.filter((id: string) => String(id).toUpperCase() !== upper)
  } else {
    localForm.value.allowed_scenes_input = [...current, upper]
  }
}

watch(() => localForm.value.entity_id, (newVal) => {
  if (newVal) {
    localForm.value.entity_id = newVal.toUpperCase()
  }
})

watch(() => localForm.value.item_type, (newType) => {
  const type = String(newType || '').toUpperCase()
  if (type === 'SWITCH' || type === 'CONTAINER_SWITCH') {
    localForm.value.is_portable = false
    if (switchStates.value.length === 0) {
      switchStates.value = ['OFF', 'ON']
    }
    if (!localForm.value.switch_initial_state) {
      localForm.value.switch_initial_state = switchStates.value[0] || 'OFF'
    }
  } else if (type === 'WEARABLE') {
    localForm.value.is_portable = true
  } else if (props.isCreateEntityMode) {
    localForm.value.is_portable = true
  }
  if (type === 'CONSTRUCTABLE') {
    localForm.value.is_portable = false
    // A recipe starts with two ingredient slots and one result slot.
    if (!Array.isArray(localForm.value.combination_ingredients_input) ||
        localForm.value.combination_ingredients_input.length === 0) {
      localForm.value.combination_ingredients_input = ['', '']
    }
    if (!localForm.value.result_item_ids_input?.length) {
      localForm.value.result_item_ids_input = ['']
    }
  }
})

function handleSave() {
  if (isRecipe.value) {
    const ingredients = (localForm.value.combination_ingredients_input || []).filter(Boolean)
    const results = (localForm.value.result_item_ids_input || []).filter(Boolean)
    localForm.value.description = recipeDescription(ingredients, results)
    localForm.value.appearance = ''
    localForm.value.is_portable = false
    localForm.value.on_pickup_script = ''
    localForm.value.on_pickup_text = ''
    localForm.value.on_drop_script = ''
    localForm.value.on_drop_text = ''
    localForm.value.pickup_trigger_mode = 'silent'
    localForm.value.pickup_trigger_cue = ''
  }
  if (!(localForm.value.name || '').trim() || !(localForm.value.description || '').trim()) {
    return
  }

  let parsedInventory: any[] = []
  let parsedWearableSlots: string[] = []
  let parsedSwitchStates: string[] = []
  let parsedSwitchTransitions: any[] = []
  let parsedEffects: Record<string, any> = {}
  let parsedIngredients: string[] = []

  if (props.context?.type === 'npc' || props.context?.type === 'object') {
    parsedInventory = Array.isArray(localForm.value.inventory_input)
      ? localForm.value.inventory_input.filter((s: string) => Boolean(s))
      : []
  }

  if (props.context?.type === 'object') {
    parsedWearableSlots = Array.isArray(localForm.value.wearable_slots_input)
      ? localForm.value.wearable_slots_input
      : []

    if (['SWITCH', 'CONTAINER_SWITCH'].includes(currentItemType.value)) {
      parsedSwitchStates = switchStates.value
        .map(s => s.trim().toUpperCase())
        .filter(Boolean)

      parsedSwitchTransitions = switchTransitions.value.map(t => {
        const gates: Record<string, string> = {}
        if (t.gates?.item) gates.item = t.gates.item.trim().toUpperCase()
        if (t.gates?.code) gates.code = t.gates.code.trim()
        if (t.gates?.rule) gates.rule = t.gates.rule.trim()
        if (t.gates?.expression) {
          gates.expression = t.gates.expression.trim()
          gates.condition = t.gates.expression.trim()
        }

        const transition: Record<string, any> = {
          to: t.to.trim().toUpperCase(),
          gates,
        }
        if (t.from && String(t.from).trim()) {
          transition.from = String(t.from).trim().toUpperCase()
        }
        if (t.fail_message?.trim()) {
          transition.fail_message = t.fail_message.trim()
        }
        if (t.success_message?.trim()) {
          transition.success_message = t.success_message.trim()
        }
        if (t.on_success_script?.trim()) {
          transition.on_success_script = t.on_success_script.trim()
        }
        if (t.on_failure_script?.trim()) {
          transition.on_failure_script = t.on_failure_script.trim()
        }
        return transition
      })

      let initial = String(localForm.value.switch_initial_state || '').trim().toUpperCase()
      if (!parsedSwitchStates.includes(initial)) {
        initial = parsedSwitchStates[0] || 'OFF'
      }
      localForm.value.switch_initial_state = initial
    }

    parsedEffects = {
      hp: Number(localForm.value.effects_hp || 0),
      stamina: Number(localForm.value.effects_stamina || 0),
      mana: Number(localForm.value.effects_mana || 0),
    }

    parsedIngredients = Array.isArray(localForm.value.combination_ingredients_input)
      ? localForm.value.combination_ingredients_input.filter((s: string) => Boolean(s))
      : []
  }

  // Normalize the four combinable metadata fields here so the form state and
  // backend stay in sync (e.g. reveals_item_id is upper-cased to match the
  // entity-id convention; an empty string becomes `null` server-side so the
  // combination has no revealed item).
  const revealsItemId = currentItemType.value === 'SWITCH'
    ? ''
    : String(localForm.value.reveals_item_id || '').trim().toUpperCase()
  const revealRule = String(localForm.value.reveal_rule || '').trim()
  const spatialPosition = String(localForm.value.spatial_position || '').trim()

  emit('save', {
    ...localForm.value,
    entity_id: (localForm.value.entity_id || '').trim().toUpperCase(),
    npc_type: String(localForm.value.npc_type || 'HUMANOID').trim().toUpperCase(),
    inventory: parsedInventory,
    wearable_slots: parsedWearableSlots,
    switch_states: parsedSwitchStates,
    switch_state_labels: Object.fromEntries(
      Object.entries(switchStateLabels.value)
        .filter(([state, label]) => parsedSwitchStates.includes(state) && label.trim())
        .map(([state, label]) => [state, label.trim().slice(0, 20)])
    ),
    switch_disabled_states: switchDisabledStates.value.filter((state) => parsedSwitchStates.includes(state)),
    switch_status_text: String(localForm.value.switch_status_text || '').trim().slice(0, 300),
    switch_transitions: parsedSwitchTransitions,
    on_success_script: String(localForm.value.on_success_script || '').trim(),
    on_failure_script: String(localForm.value.on_failure_script || '').trim(),
    effects: parsedEffects,
    combination_ingredients: parsedIngredients,
    result_item_ids: (localForm.value.result_item_ids_input || []).map((s: string) => String(s).trim().toUpperCase()).filter(Boolean),
    kept_ingredients: (localForm.value.kept_ingredients_input || [])
      .map((s: string) => String(s).trim().toUpperCase())
      .filter((id: string) => parsedIngredients.some((ing: string) => ing.toUpperCase() === id)),
    reveal_rule: revealRule,
    is_hidden: Boolean(localForm.value.is_hidden),
    spatial_position: spatialPosition,
    reveals_item_id: revealsItemId,
    appearance: String(localForm.value.appearance || '').trim(),
    moveable: Boolean(localForm.value.moveable),
    allowed_scenes: (localForm.value.allowed_scenes_input || []).map((s: any) => String(s).trim().toUpperCase()).filter(Boolean),
    notes: String(localForm.value.notes || '').trim(),
    attack_mode: localForm.value.attack_mode,
    unlock_expression: String(localForm.value.unlock_expression || '').trim(),
    on_unlock_success_script: String(localForm.value.on_unlock_success_script || '').trim(),
    on_unlock_success_text: String(localForm.value.on_unlock_success_text || '').trim(),
    on_unlock_failure_script: String(localForm.value.on_unlock_failure_script || '').trim(),
    on_unlock_failure_text: String(localForm.value.on_unlock_failure_text || '').trim(),
    on_items_added_script: String(localForm.value.on_items_added_script || '').trim(),
    on_items_added_text: String(localForm.value.on_items_added_text || '').trim(),
    on_items_removed_script: String(localForm.value.on_items_removed_script || '').trim(),
    on_items_removed_text: String(localForm.value.on_items_removed_text || '').trim(),
    min_items: Number(localForm.value.min_items || 0) > 0 ? Math.floor(Number(localForm.value.min_items)) : null,
    max_items: Number(localForm.value.max_items || 0) > 0 ? Math.floor(Number(localForm.value.max_items)) : null,
    craft_guard_expression: String(localForm.value.craft_guard_expression || '').trim(),
    on_craft_success_script: String(localForm.value.on_craft_success_script || '').trim(),
    on_craft_success_text: String(localForm.value.on_craft_success_text || '').trim(),
    on_craft_failure_script: String(localForm.value.on_craft_failure_script || '').trim(),
    on_craft_failure_text: String(localForm.value.on_craft_failure_text || '').trim(),
    on_read_script: String(localForm.value.on_read_script || '').trim(),
    on_read_text: String(localForm.value.on_read_text || '').trim(),
    on_leave_scene_script: String(localForm.value.on_leave_scene_script || '').trim(),
    on_leave_scene_text: String(localForm.value.on_leave_scene_text || '').trim(),
    helpers_script: String(localForm.value.helpers_script || '').trim(),
    on_pickup_script: localForm.value.on_pickup_script,
    on_pickup_text: localForm.value.on_pickup_text,
    on_drop_script: localForm.value.on_drop_script,
    on_drop_text: localForm.value.on_drop_text,
    on_equip_script: localForm.value.on_equip_script,
    on_equip_text: localForm.value.on_equip_text,
    on_unequip_script: localForm.value.on_unequip_script,
    on_unequip_text: localForm.value.on_unequip_text,
    on_enter_scene_script: localForm.value.on_enter_scene_script,
    on_enter_scene_text: localForm.value.on_enter_scene_text,
    on_open_exit_script: localForm.value.on_open_exit_script,
    on_open_exit_text: localForm.value.on_open_exit_text,
    on_defeat_script: localForm.value.on_defeat_script,
    on_defeat_text: localForm.value.on_defeat_text,
    on_protagonist_enters_scene_script: localForm.value.on_protagonist_enters_scene_script,
    on_protagonist_enters_scene_text: localForm.value.on_protagonist_enters_scene_text,
    on_receive_item_script: localForm.value.on_receive_item_script,
    on_receive_item_text: localForm.value.on_receive_item_text,
    on_recruit_success_script: localForm.value.on_recruit_success_script,
    on_recruit_success_text: localForm.value.on_recruit_success_text,
    on_recruit_failure_script: localForm.value.on_recruit_failure_script,
    on_recruit_failure_text: localForm.value.on_recruit_failure_text,
    reveal_guard_expression: String(localForm.value.reveal_guard_expression || '').trim(),
    memory_slots: Number(localForm.value.memory_slots) || 0,
    on_interact_script: localForm.value.on_interact_script,
    on_interact_text: localForm.value.on_interact_text,
  })
}
const isGenerating = ref<Record<string, boolean>>({})

async function handleGenerateTraits(field: 'goal' | 'character') {
  if (!props.adventureId || !localForm.value.description) return
  isGenerating.value[field] = true
  try {
    const result = await entityService.generateTraits(
      props.adventureId,
      localForm.value.name,
      localForm.value.description,
      props.context?.type || 'npc',
      field
    )
    if (field === 'goal') localForm.value.goal = result.goal
    if (field === 'character') localForm.value.character = result.character
  } catch (error) {
    console.error('Failed to generate traits:', error)
  } finally {
    isGenerating.value[field] = false
  }
}

async function handleGenerateBiography() {
  if (!props.adventureId || !localForm.value.name || !localForm.value.goal || !localForm.value.character) return
  const targetType = props.context?.type
  if (targetType !== 'npc' && targetType !== 'protagonist') return
  isGenerating.value['biography'] = true
  try {
    const result = await entityService.generateBiography(
      props.adventureId,
      localForm.value.name,
      localForm.value.goal,
      localForm.value.character,
      targetType
    )
    localForm.value.description = result.description
  } catch (error) {
    console.error('Failed to generate biography:', error)
  } finally {
    isGenerating.value['biography'] = false
  }
}

async function handleGenerateDescription() {
  if (!props.adventureId || !localForm.value.name) return
  isGenerating.value['description'] = true
  try {
    const result = await entityService.generateSceneDescription(
      props.adventureId,
      localForm.value.name
    )
    localForm.value.description = result.description
  } catch (error) {
    console.error('Failed to generate description:', error)
  } finally {
    isGenerating.value['description'] = false
  }
}

async function handleGenerateTextLogContent() {
  if (!props.adventureId || !localForm.value.name) return
  isGenerating.value['text_log'] = true
  try {
    const result = await entityService.generateSceneDescription(
      props.adventureId,
      `Text log for ${localForm.value.name}`
    )
    localForm.value.text_log_content = result.description.slice(0, 1000)
  } catch (error) {
    console.error('Failed to generate text log content:', error)
  } finally {
    isGenerating.value['text_log'] = false
  }
}

const textLogPreviewClass = computed(() => {
  const fmt = String(localForm.value.text_log_format || 'DOCUMENT').toUpperCase()
  switch (fmt) {
    case 'BOOK':
      return 'font-serif tracking-[0.01em] leading-7 text-[1.06rem] text-amber-100/90' // workbench-ui-ignore: in-game readable preview
    case 'SCROLL':
      return "font-['Caveat'] tracking-[0.02em] leading-7 text-[1.22rem] text-yellow-100/90" // workbench-ui-ignore: in-game readable preview
    case 'SIGN':
      return 'font-mono uppercase tracking-[0.12em] leading-6 text-[1rem] text-cyan-100/90' // workbench-ui-ignore: in-game readable preview
    case 'DOCUMENT':
    default:
      return 'font-sans tracking-[0.015em] leading-6 text-[1.02rem] text-slate-200/90' // workbench-ui-ignore: in-game readable preview
  }
})

  return {
    FORM_TABS,
    activeTab,
    isPage,
    editingTransitionIndex,
    showTransitionGuards,
    showTransitionScripts,
    showContainerGuard,
    showContainerTriggers,
    showConstructableGuard,
    showConstructableTriggers,
    hasActiveGuards,
    hasActiveScripts,
    localForm,
    switchStates,
    switchStateLabels,
    switchDisabledStates,
    switchTransitions,
    syncFromForm,
    addState,
    removeState,
    updateStateValue,
    startAddTransition,
    toggleEditTransition,
    removeTransition,
    itemReferenceOptions,
    currentEntityId,
    keyItemReferenceOptions,
    containedItemReferenceOptions,
    isRecipe,
    recipeDescription,
    recipeIngredientOptions,
    recipeResultOptions,
    entityImageUrl,
    currentItemType,
    entityIdPrefix,
    originalEntityId,
    takenEntityIds,
    entityIdError,
    isFormInvalid,
    weaponInvalid,
    sceneReferenceOptions,
    isSceneAllowed,
    toggleAllowedScene,
    handleSave,
    isGenerating,
    handleGenerateTraits,
    handleGenerateBiography,
    handleGenerateDescription,
    handleGenerateTextLogContent,
    textLogPreviewClass,
  }
}
