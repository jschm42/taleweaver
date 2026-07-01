<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import { Plus, Trash2, Key, FileText, Lock } from 'lucide-vue-next'

const props = defineProps<{
  show: boolean
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
    is_killable: boolean
    item_type: string
    is_portable: boolean
    locked: boolean
    code_to_unlock: string
    item_to_unlock: string
    inventory_input: string[]
    text_log_content: string
    text_log_format: string
    entity_id: string
    wearable_slots_input: string[]
    combination_ingredients_input: string[]
    switch_states_json: string
    switch_initial_state: string
    switch_transitions_json: string
    effects_hp: number
    effects_stamina: number
    effects_mana: number
    stat_modifier_strength: number
    is_item_type_fixed?: boolean
    is_wearable_slots_fixed?: boolean
  }
  referenceOptions?: Array<{ id: string; name?: string; imageUrl?: string | null; type?: string }>
  ruleEnforcementMode: string
  isSaving: boolean
  adventureId?: string
  isCreateEntityMode?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: any): void
}>()

const localForm = ref({
  is_hidden: false,
  reveal_rule: '',
  ...props.initialForm
})
const switchStates = ref<string[]>([])
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

  let transitions: any[] = []
  try {
    const parsed = JSON.parse(localForm.value.switch_transitions_json || '[]')
    transitions = Array.isArray(parsed) ? parsed : []
  } catch {
    transitions = []
  }
  
  switchTransitions.value = transitions.map((t: any) => ({
    from: String(t.from || '').toUpperCase(),
    to: String(t.to || '').toUpperCase(),
    gates: {
      item: t.gates?.item || '',
      code: t.gates?.code || '',
      rule: t.gates?.rule || '',
    },
    fail_message: t.fail_message || '',
  }))
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
  
  if (localForm.value.switch_initial_state === removed) {
    localForm.value.switch_initial_state = switchStates.value[0] || ''
  }
  
  switchTransitions.value = switchTransitions.value.filter(
    t => t.from !== removed && t.to !== removed
  )
}

function updateStateValue(index: number, val: string) {
  const oldVal = switchStates.value[index]
  const cleanVal = val.toUpperCase().replace(/[^A-Z0-9_]/g, '')
  switchStates.value[index] = cleanVal
  
  if (localForm.value.switch_initial_state === oldVal) {
    localForm.value.switch_initial_state = cleanVal
  }
  
  switchTransitions.value.forEach(t => {
    if (t.from === oldVal) t.from = cleanVal
    if (t.to === oldVal) t.to = cleanVal
  })
}

function addTransition() {
  switchTransitions.value.push({
    from: switchStates.value[0] || '',
    to: switchStates.value[1] || switchStates.value[0] || '',
    gates: {
      item: '',
      code: '',
      rule: '',
    },
    fail_message: '',
  })
}

function removeTransition(index: number) {
  switchTransitions.value.splice(index, 1)
}

const itemReferenceOptions = computed(() => {
  const source = props.referenceOptions || []
  return source
    .filter((option) => String(option.type || '').toUpperCase() === 'OBJECT')
    .map((option) => ({
      ...option,
      name: option.name || option.id || '',
    }))
})

const currentItemType = computed(() => String(localForm.value.item_type || '').toUpperCase())

const entityIdError = computed(() => {
  const val = (localForm.value.entity_id || '').trim()
  if (!val) return 'ID is required.'

  const idRegex = /^[A-Z0-9_]+$/
  if (!idRegex.test(val)) {
    return 'ID must contain only uppercase letters, digits, and underscores.'
  }

  // Get original ID (if we are in edit mode, it can remain the same)
  const originalId = String(props.initialForm.entity_id || props.context?.id || '').trim().toUpperCase()

  // Set of all taken IDs in this adventure, excluding the current one being edited
  const takenIds = new Set(
    (props.referenceOptions || [])
      .map((entry) => String(entry.id || '').toUpperCase())
      .filter((id) => id !== originalId)
  )

  if (takenIds.has(val.toUpperCase())) {
    return `ID "${val}" already exists in this adventure.`
  }
  return ''
})

const isFormInvalid = computed(() => {
  const nameInvalid = !(localForm.value.name || '').trim() ||
         (localForm.value.name || '').length > 50
  const descInvalid = !(localForm.value.description || '').trim() ||
         (localForm.value.description || '').length > 1000
  const personaInvalid = (localForm.value.goal || '').length > 200 ||
         (localForm.value.character || '').length > 200
  const teaserInvalid = (localForm.value.teaser || '').length > 300
  const hasEditableId = props.isCreateEntityMode || (props.context && ['npc', 'object', 'scene'].includes(props.context.type))
  const maxIdLen = props.context?.type === 'scene' ? 50 : 30
  const idInvalid = hasEditableId
    ? (!(localForm.value.entity_id || '').trim() || (localForm.value.entity_id || '').length > maxIdLen || !!entityIdError.value)
    : false
  const combinationInvalid = (currentItemType.value === 'COMBINABLE' || currentItemType.value === 'CONSTRUCTABLE') &&
    (!Array.isArray(localForm.value.combination_ingredients_input) ||
     localForm.value.combination_ingredients_input.filter((s: string) => Boolean(s)).length < 2)
  const uniqueStates = new Set(switchStates.value.map(s => s.trim().toUpperCase()))
  const switchInvalid = currentItemType.value === 'SWITCH' && (
    switchStates.value.length < 2 ||
    uniqueStates.size !== switchStates.value.length ||
    switchStates.value.some(s => !s.trim()) ||
    switchTransitions.value.some(t => !t.from || !t.to || !uniqueStates.has(t.from) || !uniqueStates.has(t.to))
  )
  return nameInvalid || descInvalid || personaInvalid || teaserInvalid || idInvalid || combinationInvalid || switchInvalid
})

watch(() => props.initialForm, (newVal) => {
  localForm.value = {
    is_hidden: false,
    reveal_rule: '',
    ...newVal
  }
  syncFromForm()
}, { deep: true })

watch(() => localForm.value.entity_id, (newVal) => {
  if (newVal) {
    localForm.value.entity_id = newVal.toUpperCase()
  }
})

watch(() => localForm.value.item_type, (newType) => {
  if (!props.isCreateEntityMode) return
  const type = String(newType || '').toUpperCase()
  if (type === 'SWITCH') {
    localForm.value.is_portable = false
    if (switchStates.value.length === 0) {
      switchStates.value = ['OFF', 'ON']
    }
  } else if (type === 'WEARABLE') {
    localForm.value.is_portable = true
  } else {
    localForm.value.is_portable = true
  }
  if (type === 'CONSTRUCTABLE') {
    // Constructables materialize only once all ingredients are combined.
    if (!Array.isArray(localForm.value.combination_ingredients_input) ||
        localForm.value.combination_ingredients_input.filter((s: string) => Boolean(s)).length < 2) {
      localForm.value.combination_ingredients_input = ['', '']
    }
  }
})

function handleSave() {
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

    if (currentItemType.value === 'SWITCH') {
      parsedSwitchStates = switchStates.value
        .map(s => s.trim().toUpperCase())
        .filter(Boolean)

      parsedSwitchTransitions = switchTransitions.value.map(t => {
        const gates: Record<string, string> = {}
        if (t.gates?.item) gates.item = t.gates.item.trim().toUpperCase()
        if (t.gates?.code) gates.code = t.gates.code.trim()
        if (t.gates?.rule) gates.rule = t.gates.rule.trim()

        const transition: Record<string, any> = {
          from: t.from.trim().toUpperCase(),
          to: t.to.trim().toUpperCase(),
          gates,
        }
        if (t.fail_message?.trim()) {
          transition.fail_message = t.fail_message.trim()
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

  emit('save', {
    ...localForm.value,
    is_hidden: Boolean(localForm.value.is_hidden),
    reveal_rule: String(localForm.value.reveal_rule || '').trim() || null,
    entity_id: (localForm.value.entity_id || '').trim().toUpperCase(),
    inventory: parsedInventory,
    wearable_slots: parsedWearableSlots,
    switch_states: parsedSwitchStates,
    switch_transitions: parsedSwitchTransitions,
    effects: parsedEffects,
    combination_ingredients: parsedIngredients,
  })
}

import { entityService } from '@/services/entityService'
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
      return 'font-serif tracking-[0.01em] leading-7 text-[1.06rem] text-amber-100/90'
    case 'SCROLL':
      return "font-['Caveat'] tracking-[0.02em] leading-7 text-[1.22rem] text-yellow-100/90"
    case 'SIGN':
      return 'font-mono uppercase tracking-[0.12em] leading-6 text-[1rem] text-cyan-100/90'
    case 'DOCUMENT':
    default:
      return 'font-sans tracking-[0.015em] leading-6 text-[1.02rem] text-slate-200/90'
  }
})

</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show && context" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="modal-content w-full max-w-2xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
          <!-- Fixed Header -->
          <div class="px-8 py-5 flex justify-between items-center border-b border-white/5">
            <div class="space-y-1">
              <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">Editing {{ context.type }}</h3>
              <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">ID: {{ context.id }}</p>
            </div>
            <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
              <i class="ra ra-cancel text-xl"></i>
            </button>
          </div>

          <!-- Scrollable Content -->
          <div class="px-8 py-6 space-y-6 overflow-y-auto flex-1">
              <!-- Editable ID (create mode or scene/npc/object edit mode) -->
              <div v-if="isCreateEntityMode || ['npc', 'object', 'scene'].includes(context.type)" class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">
                    {{ context.type === 'scene' ? 'Scene ID' : 'Entity ID' }} <span class="text-red-400">*</span>
                  </label>
                  <span :class="['text-xs font-bold tracking-widest', (localForm.entity_id || '').length > (context.type === 'scene' ? 50 : 30) || entityIdError ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ (localForm.entity_id || '').length }} / {{ context.type === 'scene' ? 50 : 30 }}
                  </span>
                </div>
                <input
                  v-model="localForm.entity_id"
                  :maxlength="context.type === 'scene' ? 50 : 30"
                  class="w-full bg-black/40 border rounded-2xl px-4 py-3 text-lg font-mono font-bold text-amber-300 focus:border-amber-500 outline-none transition-all shadow-inner uppercase"
                  :class="entityIdError ? 'border-red-500 focus:ring-red-500/50' : 'border-white/5'"
                  placeholder="ITEM_001"
                />
                <p v-if="entityIdError" class="text-xs font-bold text-red-400">{{ entityIdError }}</p>
                <p v-else class="text-[10px] text-slate-500 uppercase tracking-wider">Unique identifier. Only uppercase letters, numbers, and underscores.</p>
              </div>

              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Entity Name <span class="text-red-400">*</span></label>
                  <span :class="['text-xs font-bold tracking-widest', (localForm.name || '').length > 50 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ (localForm.name || '').length }} / 50
                  </span>
                </div>
                <input v-model="localForm.name" maxlength="50" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-xl font-bold text-white focus:border-emerald-500 outline-none transition-all shadow-inner" />
              
              <!-- Stats Inputs -->
              <div v-if="['protagonist', 'npc'].includes(context.type) && ruleEnforcementMode !== 'chat'" class="grid grid-cols-3 gap-4">
                <div class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Health (HP)</label>
                  <input 
                    v-model.number="localForm.hp" 
                    type="number" 
                    min="0"
                    max="999"
                    class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-red-500/50 outline-none transition-all"
                    :class="{ 'border-red-500 text-red-500': localForm.hp < 0 || localForm.hp > 999 }"
                  />
                </div>
                <div class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Stamina (STM)</label>
                  <input 
                    v-model.number="localForm.stamina" 
                    type="number" 
                    min="0"
                    max="999"
                    class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-emerald-500/50 outline-none transition-all"
                    :class="{ 'border-red-500 text-red-500': localForm.stamina < 0 || localForm.stamina > 999 }"
                  />
                </div>
                <div v-if="ruleEnforcementMode === 'rpg'" class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Mana (MAN)</label>
                  <input 
                    v-model.number="localForm.mana" 
                    type="number" 
                    min="0"
                    max="999"
                    class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-blue-500/50 outline-none transition-all"
                    :class="{ 'border-red-500 text-red-500': localForm.mana < 0 || localForm.mana > 999 }"
                  />
                </div>
              </div>
              </div>
              
              <!-- Protagonist Motivation & Traits -->
              <div v-if="context.type === 'protagonist'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="space-y-3">
                  <div class="flex justify-between items-center">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Motivation / Goal</label>
                    <span :class="['text-xs font-bold tracking-widest', (localForm.goal || '').length > 200 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ (localForm.goal || '').length }} / 200
                    </span>
                  </div>
                  <ReferenceTextarea
                    v-model="localForm.goal"
                    :maxlength="200"
                    :rows="2"
                    :options="props.referenceOptions || []"
                    class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
                    placeholder="What drives the protagonist? (e.g. 'Seeks revenge for family's death')"
                  />
                  <button 
                    v-if="localForm.description"
                    @click="handleGenerateTraits('goal')" 
                    :disabled="isGenerating['goal']"
                    class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  >
                    <i class="ra ra-crystals" :class="{ 'animate-spin': isGenerating['goal'] }"></i>
                    <span>Quick-Gen Goal</span>
                  </button>
                </div>
                <div class="space-y-3">
                  <div class="flex justify-between items-center">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Personality / Traits</label>
                    <span :class="['text-xs font-bold tracking-widest', (localForm.character || '').length > 200 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ (localForm.character || '').length }} / 200
                    </span>
                  </div>
                  <ReferenceTextarea
                    v-model="localForm.character"
                    :maxlength="200"
                    :rows="2"
                    :options="props.referenceOptions || []"
                    class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
                    placeholder="How does the protagonist behave? (e.g. 'Sarcastic but loyal, prone to rash decisions')"
                  />
                  <button 
                    v-if="localForm.description"
                    @click="handleGenerateTraits('character')" 
                    :disabled="isGenerating['character']"
                    class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  >
                    <i class="ra ra-crystals" :class="{ 'animate-spin': isGenerating['character'] }"></i>
                    <span>Quick-Gen Traits</span>
                  </button>
                </div>
              </div>
              
              <div v-if="context.type === 'npc'" class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="space-y-3">
                  <div class="flex justify-between items-center">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">NPC Goal / Motivation</label>
                    <span :class="['text-xs font-bold tracking-widest', (localForm.goal || '').length > 200 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ (localForm.goal || '').length }} / 200
                    </span>
                  </div>
                  <ReferenceTextarea
                    v-model="localForm.goal"
                    :maxlength="200"
                    :rows="2"
                    :options="props.referenceOptions || []"
                    class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
                    placeholder="What does this NPC want? (e.g. 'Wants to steal the player's gold')"
                  />
                  <button 
                    v-if="localForm.description"
                    @click="handleGenerateTraits('goal')" 
                    :disabled="isGenerating['goal']"
                    class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  >
                    <i class="ra ra-crystals" :class="{ 'animate-spin': isGenerating['goal'] }"></i>
                    <span>Quick-Gen Goal</span>
                  </button>
                </div>
                <div class="space-y-3">
                  <div class="flex justify-between items-center">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">NPC Character / Traits</label>
                    <span :class="['text-xs font-bold tracking-widest', (localForm.character || '').length > 200 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ (localForm.character || '').length }} / 200
                    </span>
                  </div>
                  <ReferenceTextarea
                    v-model="localForm.character"
                    :maxlength="200"
                    :rows="2"
                    :options="props.referenceOptions || []"
                    class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
                    placeholder="How does this NPC behave? (e.g. 'Grumpy and stubborn')"
                  />
                  <button 
                    v-if="localForm.description"
                    @click="handleGenerateTraits('character')" 
                    :disabled="isGenerating['character']"
                    class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  >
                    <i class="ra ra-crystals" :class="{ 'animate-spin': isGenerating['character'] }"></i>
                    <span>Quick-Gen Traits</span>
                  </button>
                </div>
              </div>

              <div v-if="context.type === 'npc'" class="p-4 bg-black/30 border border-white/10 rounded-2xl">
                <div class="flex items-center justify-between">
                  <div class="space-y-1 pr-4">
                    <p class="text-xs font-black text-slate-200 uppercase tracking-widest">NPC Can Be Killed</p>
                    <p class="text-[10px] text-slate-500 uppercase tracking-tighter">If disabled, the NPC can still fight but is never permanently defeated.</p>
                  </div>
                  <button
                    type="button"
                    @click="localForm.is_killable = !localForm.is_killable"
                    :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', localForm.is_killable ? 'bg-emerald-600' : 'bg-slate-700']"
                  >
                    <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', localForm.is_killable ? 'translate-x-6' : 'translate-x-0']"></div>
                  </button>
                </div>
              </div>

              <!-- NPC Loot / Inventory -->
              <div v-if="context.type === 'npc'" class="p-4 bg-black/30 border border-white/10 rounded-2xl space-y-3">
                <div class="flex items-center gap-2">
                  <i class="ra ra-gem text-amber-400 text-sm"></i>
                  <p class="text-xs font-black text-slate-200 uppercase tracking-widest">Loot / Inventory</p>
                </div>
                <p class="text-[10px] text-slate-500 uppercase tracking-tighter">
                  Items this NPC carries. Dropped as loot when the NPC is defeated in combat.
                </p>
                <div class="space-y-2">
                  <div
                    v-for="(item, idx) in localForm.inventory_input"
                    :key="idx"
                    class="flex items-center gap-2"
                  >
                    <EntityReferenceCombobox
                      v-model="localForm.inventory_input[idx]"
                      :options="itemReferenceOptions"
                      placeholder="Select loot item"
                      :enable-search="true"
                    />
                    <button
                      type="button"
                      @click="localForm.inventory_input = localForm.inventory_input.filter((_: string, i: number) => i !== idx)"
                      class="shrink-0 px-2 py-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 text-[10px] font-bold uppercase tracking-widest transition-all"
                    >
                      <i class="ra ra-cancel"></i>
                    </button>
                  </div>
                  <button
                    type="button"
                    @click="localForm.inventory_input = [...(localForm.inventory_input || []), '']"
                    class="w-full py-2 bg-amber-500/5 border border-amber-500/10 hover:bg-amber-500/10 hover:border-amber-500/30 rounded-xl text-[10px] font-black text-amber-400 uppercase tracking-widest transition-all flex items-center justify-center gap-1.5"
                  >
                    <i class="ra ra-gem text-xs"></i> Add Loot Item
                  </button>
                </div>
                <p v-if="!localForm.inventory_input || localForm.inventory_input.length === 0" class="text-[10px] text-slate-600 italic">
                  No loot configured. The NPC drops nothing on defeat.
                </p>
              </div>

              <div v-if="context.type === 'object'" class="p-4 bg-black/30 border border-white/10 rounded-2xl space-y-5">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Item Type</label>
                    <select
                      v-if="isCreateEntityMode && !localForm.is_item_type_fixed"
                      v-model="localForm.item_type"
                      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold uppercase tracking-widest focus:border-emerald-500/50 outline-none transition-all"
                    >
                      <option value="DEFAULT">DEFAULT</option>
                      <option value="CONSUMABLE">CONSUMABLE</option>
                      <option value="WEARABLE">WEARABLE</option>
                      <option value="WEAPON">WEAPON</option>
                      <option value="COMBINABLE">COMBINABLE (deprecated)</option>
                      <option value="CONSTRUCTABLE">CONSTRUCTABLE</option>
                      <option value="READABLE">READABLE</option>
                      <option value="CONTAINER">CONTAINER</option>
                      <option value="SWITCH">SWITCH</option>
                    </select>
                    <input
                      v-else
                      :value="String(localForm.item_type || '').toUpperCase()"
                      disabled
                      class="w-full bg-black/30 border border-white/5 rounded-xl px-4 py-2 text-slate-300 font-bold uppercase tracking-widest cursor-not-allowed"
                    />
                  </div>
                  <div v-if="currentItemType !== 'WEARABLE'" class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Portable</label>
                    <button
                      type="button"
                      @click="localForm.is_portable = !localForm.is_portable"
                      :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', localForm.is_portable ? 'bg-emerald-600' : 'bg-slate-700']"
                    >
                      <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', localForm.is_portable ? 'translate-x-6' : 'translate-x-0']"></div>
                    </button>
                  </div>
                  <div v-else class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Portable</label>
                    <div class="w-full bg-black/30 border border-white/5 rounded-xl px-4 py-2 text-slate-400 font-bold uppercase tracking-widest">
                      TRUE (Fixed)
                    </div>
                  </div>
                </div>

                <!-- Hidden state & Reveal rule (only for non-constructable types) -->
                <div v-if="props.context?.type === 'object' && ['DEFAULT', 'CONSUMABLE', 'WEARABLE', 'WEAPON', 'READABLE', 'CONTAINER', 'SWITCH'].includes(currentItemType)" class="space-y-4 border-t border-white/5 pt-4">
                  <div class="grid grid-cols-2 gap-4">
                    <div class="space-y-2">
                      <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Start Hidden</label>
                      <button
                        type="button"
                        @click="localForm.is_hidden = !localForm.is_hidden"
                        :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', localForm.is_hidden ? 'bg-emerald-600' : 'bg-slate-700']"
                      >
                        <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', localForm.is_hidden ? 'translate-x-6' : 'translate-x-0']"></div>
                      </button>
                    </div>
                  </div>
                  
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Reveal Rule</label>
                    <input
                      v-model="localForm.reveal_rule"
                      placeholder="e.g. player inspects the desk, player defeats boss"
                      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:border-emerald-500 outline-none transition-all shadow-inner"
                    />
                    <span class="block text-[10px] text-slate-500 leading-normal">
                      Specify the action or event that triggers this item to reveal in the room. Keep empty if visible by default.
                    </span>
                  </div>
                </div>

                <!-- WEAPON / WEARABLE: Wearable Slots -->
                <div v-if="['WEAPON', 'WEARABLE'].includes(currentItemType)" class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Wearable Slots</label>
                  <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    <label
                      v-for="slot in ['Head', 'Neck', 'Chest', 'Hands', 'Legs', 'Feet', 'MainHand', 'OffHand', 'Finger', 'Wrist', 'Back', 'Waist']"
                      :key="slot"
                      :class="[
                        'flex items-center gap-2 p-2 rounded-lg border transition-all select-none',
                        localForm.wearable_slots_input.includes(slot)
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                          : 'border-white/5 bg-black/20 text-slate-500',
                        localForm.is_wearable_slots_fixed
                          ? 'cursor-not-allowed' + (localForm.wearable_slots_input.includes(slot) ? '' : ' opacity-40')
                          : 'cursor-pointer hover:bg-sky-500/10 hover:border-sky-500/20'
                      ]"
                    >
                      <div class="relative flex items-center">
                        <input
                          type="checkbox"
                          :value="slot"
                          :checked="localForm.wearable_slots_input.includes(slot)"
                          :disabled="localForm.is_wearable_slots_fixed"
                          @change="(e: Event) => {
                            const checked = (e.target as HTMLInputElement).checked
                            if (checked) {
                              localForm.wearable_slots_input = [...localForm.wearable_slots_input, slot]
                            } else {
                              localForm.wearable_slots_input = localForm.wearable_slots_input.filter((s: string) => s !== slot)
                            }
                          }"
                          class="w-4 h-4 rounded border-white/20 bg-black/40 text-emerald-500 focus:ring-emerald-500/40 focus:ring-1 disabled:opacity-80"
                        />
                      </div>
                      <span class="text-[10px] font-bold uppercase tracking-widest transition-colors" :class="localForm.wearable_slots_input.includes(slot) ? 'text-emerald-300' : 'text-slate-400'">{{ slot }}</span>
                    </label>
                  </div>
                </div>

                <!-- CONSUMABLE: Effects -->
                <div v-if="currentItemType === 'CONSUMABLE'" class="space-y-4">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Stat Effects When Consumed</label>
                  <div class="grid grid-cols-3 gap-4">
                    <div class="space-y-2">
                      <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Health (HP)</label>
                      <input
                        v-model.number="localForm.effects_hp"
                        type="number"
                        min="-999"
                        max="999"
                        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-red-500/50 outline-none transition-all"
                      />
                    </div>
                    <div class="space-y-2">
                      <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Stamina</label>
                      <input
                        v-model.number="localForm.effects_stamina"
                        type="number"
                        min="-999"
                        max="999"
                        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-emerald-500/50 outline-none transition-all"
                      />
                    </div>
                    <div class="space-y-2">
                      <label class="block text-[10px] font-bold text-slate-500 uppercase tracking-widest">Mana</label>
                      <input
                        v-model.number="localForm.effects_mana"
                        type="number"
                        min="-999"
                        max="999"
                        class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-blue-500/50 outline-none transition-all"
                      />
                    </div>
                  </div>
                  <p class="text-[10px] text-slate-500 uppercase tracking-wider">Positive values restore stats, negative values drain them.</p>
                </div>

                <!-- COMBINABLE / CONSTRUCTABLE: Ingredients -->
                <div v-if="currentItemType === 'COMBINABLE' || currentItemType === 'CONSTRUCTABLE'" class="space-y-3">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">
                    {{ currentItemType === 'CONSTRUCTABLE' ? 'Construction Ingredients' : 'Combination Ingredients' }}
                  </label>
                  <div v-if="currentItemType === 'CONSTRUCTABLE'" class="px-3 py-2 rounded-lg border border-orange-500/30 bg-orange-500/5 text-[11px] text-orange-200/90 leading-relaxed flex items-start gap-2">
                    <i class="ra ra-hammer text-orange-400 mt-0.5 shrink-0"></i>
                    <span>Constructables stay hidden until the player combines ALL ingredients (min. 2). The engine then consumes the ingredients and reveals this item automatically — no reveal rule needed.</span>
                  </div>
                  <div class="space-y-2">
                    <div
                      v-for="(ing, idx) in localForm.combination_ingredients_input"
                      :key="idx"
                      class="flex items-center gap-2"
                    >
                      <EntityReferenceCombobox
                        v-model="localForm.combination_ingredients_input[idx]"
                        :options="itemReferenceOptions"
                        placeholder="Select ingredient item"
                        :enable-search="true"
                      />
                      <button
                        type="button"
                        @click="localForm.combination_ingredients_input = localForm.combination_ingredients_input.filter((_: string, i: number) => i !== idx)"
                        class="shrink-0 px-2 py-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 text-[10px] font-bold uppercase tracking-widest transition-all"
                      >
                        <i class="ra ra-cancel"></i>
                      </button>
                    </div>
                    <button
                      type="button"
                      @click="localForm.combination_ingredients_input = [...(localForm.combination_ingredients_input || []), '']"
                      class="w-full py-2 bg-violet-500/5 border border-violet-500/10 hover:bg-violet-500/10 hover:border-violet-500/30 rounded-xl text-[10px] font-black text-violet-400 uppercase tracking-widest transition-all"
                    >
                      + Add Ingredient
                    </button>
                  </div>
                  <p class="text-[10px] text-slate-500 uppercase tracking-wider">
                    {{ currentItemType === 'CONSTRUCTABLE'
                      ? 'Select ALL item references required to construct this item (min. 2). They are consumed on construction.'
                      : 'Select item references required to combine with this item.' }}
                  </p>
                </div>

                <!-- SWITCH: Visual Configurator -->
                <div v-if="currentItemType === 'SWITCH'" class="space-y-6">
                  <!-- 1. States Management -->
                  <div class="space-y-3 bg-black/20 border border-white/5 p-4 rounded-2xl">
                    <div class="flex justify-between items-center">
                      <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Switch States</label>
                      <span class="text-[10px] text-slate-500 font-bold uppercase tracking-wider">At least 2 required</span>
                    </div>
                    
                    <div class="space-y-2">
                      <div
                        v-for="(state, idx) in switchStates"
                        :key="idx"
                        class="flex items-center gap-2"
                      >
                        <input
                          v-model="switchStates[idx]"
                          @input="(e) => updateStateValue(idx, (e.target as HTMLInputElement).value)"
                          placeholder="e.g. OFF"
                          class="flex-1 bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-white font-mono font-bold focus:border-lime-500 outline-none transition-all"
                        />
                        <button
                          type="button"
                          @click="removeState(idx)"
                          :disabled="switchStates.length <= 2"
                          class="shrink-0 px-2.5 py-2 rounded-xl border border-red-500/20 text-red-400 hover:bg-red-500/10 text-xs font-bold uppercase tracking-widest transition-all disabled:opacity-30 disabled:hover:bg-transparent"
                          title="Remove State"
                        >
                          <Trash2 class="w-4 h-4" />
                        </button>
                      </div>
                      
                      <button
                        type="button"
                        @click="addState"
                        class="w-full py-2 bg-lime-500/5 border border-lime-500/10 hover:bg-lime-500/10 hover:border-lime-500/30 rounded-xl text-[10px] font-black text-lime-400 uppercase tracking-widest flex items-center justify-center gap-1.5 transition-all"
                      >
                        <Plus class="w-3.5 h-3.5" /> Add State
                      </button>
                    </div>
                  </div>

                  <!-- 2. Initial State Selection -->
                  <div class="space-y-2 bg-black/20 border border-white/5 p-4 rounded-2xl">
                    <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Initial State</label>
                    <select
                      v-model="localForm.switch_initial_state"
                      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold uppercase tracking-widest focus:border-lime-500/50 outline-none transition-all"
                    >
                      <option v-for="state in switchStates" :key="state" :value="state">{{ state }}</option>
                    </select>
                  </div>

                  <!-- 3. Transitions Management -->
                  <div class="space-y-3 bg-black/20 border border-white/5 p-4 rounded-2xl">
                    <div class="flex justify-between items-center">
                      <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Transitions & Rules</label>
                      <span class="text-[10px] text-slate-500 font-bold uppercase tracking-wider">{{ switchTransitions.length }} defined</span>
                    </div>

                    <div class="space-y-4">
                      <div
                        v-for="(t, idx) in switchTransitions"
                        :key="idx"
                        class="p-4 bg-black/40 border border-white/5 rounded-2xl space-y-3 relative group"
                      >
                        <button
                          type="button"
                          @click="removeTransition(idx)"
                          class="absolute top-3 right-3 p-1.5 rounded-lg border border-red-500/10 text-red-400 hover:bg-red-500/10 hover:border-red-500/20 transition-all"
                          title="Remove Transition"
                        >
                          <Trash2 class="w-4.5 h-4.5" />
                        </button>

                        <!-- From/To Row -->
                        <div class="grid grid-cols-2 gap-4 mr-8">
                          <div class="space-y-1">
                            <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">From State</span>
                            <select
                              v-model="t.from"
                              class="w-full bg-slate-900 border border-white/5 rounded-lg px-2.5 py-1.5 text-xs text-white font-bold uppercase outline-none"
                            >
                              <option v-for="state in switchStates" :key="state" :value="state">{{ state }}</option>
                            </select>
                          </div>
                          <div class="space-y-1">
                            <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">To State</span>
                            <select
                              v-model="t.to"
                              class="w-full bg-slate-900 border border-white/5 rounded-lg px-2.5 py-1.5 text-xs text-white font-bold uppercase outline-none"
                            >
                              <option v-for="state in switchStates" :key="state" :value="state">{{ state }}</option>
                            </select>
                          </div>
                        </div>

                        <!-- Requirements (Gates) Grid -->
                        <div class="bg-black/20 p-3 rounded-xl space-y-2.5">
                          <div class="flex items-center gap-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                            <Lock class="w-3 h-3 text-lime-500" /> Requirements (Gates)
                          </div>
                          
                          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <!-- Required Item -->
                            <div class="space-y-1">
                              <span class="text-[9px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1"><Key class="w-3 h-3 text-amber-500" /> Required Key Item</span>
                              <EntityReferenceCombobox
                                v-model="t.gates.item"
                                :options="itemReferenceOptions"
                                placeholder="None"
                                :enable-search="true"
                              />
                            </div>
                            
                            <!-- Required Code -->
                            <div class="space-y-1">
                              <span class="text-[9px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1"><Lock class="w-3 h-3 text-cyan-500" /> Required Code / PIN</span>
                              <input
                                v-model="t.gates.code"
                                placeholder="None"
                                class="w-full bg-slate-900 border border-white/5 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:border-cyan-500/50 outline-none"
                              />
                            </div>
                          </div>

                          <!-- Required Story Flag -->
                          <div class="space-y-1">
                            <span class="text-[9px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1"><FileText class="w-3 h-3 text-violet-500" /> Required Story Flag (Rule Key)</span>
                            <input
                              v-model="t.gates.rule"
                              placeholder="None"
                              class="w-full bg-slate-900 border border-white/5 rounded-lg px-2.5 py-1.5 text-xs text-white focus:border-violet-500/50 outline-none"
                            />
                          </div>
                        </div>

                        <!-- Fail Message -->
                        <div class="space-y-1">
                          <span class="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Failure Message</span>
                          <input
                            v-model="t.fail_message"
                            placeholder="e.g. The lever refuses to budge. It seems locked."
                            class="w-full bg-slate-900 border border-white/5 rounded-lg px-2.5 py-1.5 text-xs text-white focus:border-lime-500/50 outline-none"
                          />
                        </div>
                      </div>

                      <div v-if="switchTransitions.length === 0" class="text-xs text-slate-500 italic py-2 text-center">
                        No transitions configured. Any state can be activated freely.
                      </div>

                      <button
                        type="button"
                        @click="addTransition"
                        class="w-full py-2 bg-lime-500/5 border border-lime-500/10 hover:bg-lime-500/10 hover:border-lime-500/30 rounded-xl text-[10px] font-black text-lime-400 uppercase tracking-widest flex items-center justify-center gap-1.5 transition-all"
                      >
                        <Plus class="w-3.5 h-3.5" /> Add Transition Rule
                      </button>
                    </div>
                  </div>
                </div>

                <!-- CONTAINER -->
                <div v-if="currentItemType === 'CONTAINER'" class="p-3 bg-black/20 border border-white/10 rounded-xl">
                  <div class="flex items-center justify-between">
                    <div class="space-y-1 pr-4">
                      <p class="text-xs font-black text-slate-200 uppercase tracking-widest">Locked State</p>
                      <p class="text-[10px] text-slate-500 uppercase tracking-tighter">If enabled, this container needs either a code or a key item.</p>
                    </div>
                    <button
                      type="button"
                      @click="localForm.locked = !localForm.locked"
                      :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', localForm.locked ? 'bg-emerald-600' : 'bg-slate-700']"
                    >
                      <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', localForm.locked ? 'translate-x-6' : 'translate-x-0']"></div>
                    </button>
                  </div>
                </div>

                <div v-if="currentItemType === 'CONTAINER'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Code To Unlock</label>
                    <input
                      v-model="localForm.code_to_unlock"
                      maxlength="20"
                      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white focus:border-amber-500/50 outline-none transition-all"
                      placeholder="ALPHA or 4711"
                    />
                  </div>
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Item ID To Unlock</label>
                    <EntityReferenceCombobox
                      v-model="localForm.item_to_unlock"
                      :options="itemReferenceOptions"
                      placeholder="Select item reference"
                      :enable-search="true"
                    />
                  </div>
                </div>

                <div v-if="currentItemType === 'CONTAINER'" class="space-y-3">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Contained Items</label>
                  <div class="space-y-2">
                    <div
                      v-for="(item, idx) in localForm.inventory_input"
                      :key="idx"
                      class="flex items-center gap-2"
                    >
                      <EntityReferenceCombobox
                        v-model="localForm.inventory_input[idx]"
                        :options="itemReferenceOptions"
                        placeholder="Select contained item"
                        :enable-search="true"
                      />
                      <button
                        type="button"
                        @click="localForm.inventory_input = localForm.inventory_input.filter((_: string, i: number) => i !== idx)"
                        class="shrink-0 px-2 py-1.5 rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 text-[10px] font-bold uppercase tracking-widest transition-all"
                      >
                        <i class="ra ra-cancel"></i>
                      </button>
                    </div>
                    <button
                      type="button"
                      @click="localForm.inventory_input = [...(localForm.inventory_input || []), '']"
                      class="w-full py-2 bg-amber-500/5 border border-amber-500/10 hover:bg-amber-500/10 hover:border-amber-500/30 rounded-xl text-[10px] font-black text-amber-400 uppercase tracking-widest transition-all"
                    >
                      + Add Item
                    </button>
                  </div>
                  <p class="text-[10px] text-slate-500 uppercase tracking-wider">Select items contained inside this container.</p>
                </div>

                <!-- READABLE -->
                <div v-if="currentItemType === 'READABLE'" class="space-y-2">
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Text Log Format</label>
                    <select v-model="localForm.text_log_format" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-cyan-500/50 outline-none transition-all">
                      <option value="DOCUMENT">DOCUMENT</option>
                      <option value="SCROLL">SCROLL</option>
                      <option value="BOOK">BOOK</option>
                      <option value="SIGN">SIGN</option>
                    </select>
                  </div>
                  <div class="flex justify-between items-center">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Text Log Content</label>
                    <span :class="['text-xs font-bold tracking-widest', (localForm.text_log_content || '').length > 1000 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ (localForm.text_log_content || '').length }} / 1000
                    </span>
                  </div>
                  <ReferenceTextarea
                    v-model="localForm.text_log_content"
                    :maxlength="1000"
                    :rows="3"
                    :options="props.referenceOptions || []"
                    :class-name="['w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-y focus:border-cyan-500/50 outline-none transition-all', textLogPreviewClass].join(' ')"
                    placeholder="Readable note text shown to the player."
                  />
                  <button
                    v-if="localForm.name"
                    @click="handleGenerateTextLogContent"
                    :disabled="isGenerating['text_log']"
                    class="w-full py-2 bg-cyan-500/5 border border-cyan-500/10 hover:bg-cyan-500/10 hover:border-cyan-500/30 rounded-xl text-[10px] font-black text-cyan-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50 mt-2"
                  >
                    <i class="ra ra-crystals" :class="{ 'animate-spin': isGenerating['text_log'] }"></i>
                    <span>Quick-Gen Text Log</span>
                  </button>
                </div>
              </div>

              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Description / Biography <span class="text-red-400">*</span></label>
                  <span :class="['text-xs font-bold tracking-widest', (localForm.description || '').length > 1000 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ (localForm.description || '').length }} / 1000
                  </span>
                </div>
                <ReferenceTextarea
                  v-model="localForm.description"
                  :maxlength="1000"
                  :rows="context.type === 'object' ? 3 : 4"
                  :options="props.referenceOptions || []"
                  :class-name="['w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner', context.type === 'object' ? 'text-sm' : 'text-base'].join(' ')"
                />
                <button 
                  v-if="['npc', 'protagonist'].includes(context.type) && localForm.name && localForm.goal && localForm.character"
                  type="button"
                  @click="handleGenerateBiography" 
                  :disabled="isGenerating['biography']"
                  class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50 mt-2"
                >
                  <i class="ra ra-crystals" :class="{ 'animate-spin': isGenerating['biography'] }"></i>
                  <span>Quick-Gen Biography</span>
                </button>
                <button 
                  v-if="context.type === 'object' && localForm.name"
                  type="button"
                  @click="handleGenerateDescription" 
                  :disabled="isGenerating['description']"
                  class="w-full py-2 bg-emerald-500/5 border border-emerald-500/10 hover:bg-emerald-500/10 hover:border-emerald-500/30 rounded-xl text-[10px] font-black text-emerald-500 uppercase tracking-widest flex items-center justify-center gap-2 transition-all disabled:opacity-50 mt-2"
                >
                  <i class="ra ra-crystals" :class="{ 'animate-spin': isGenerating['description'] }"></i>
                  <span>Quick-Gen Description</span>
                </button>
              </div>
            </div>

          <!-- Fixed Footer -->
          <div class="px-8 py-5 border-t border-white/5 flex justify-end gap-4 bg-slate-900/55 rounded-b-[2.5rem]">
            <button @click="emit('close')" class="px-6 py-2.5 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors">Discard</button>
            <button @click="handleSave" :disabled="isSaving || isFormInvalid" class="px-8 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-black uppercase text-xs tracking-widest rounded-xl shadow-lg shadow-emerald-900/20 disabled:opacity-50 flex items-center gap-3">
              <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
              <span>{{ isSaving ? 'Saving...' : 'Apply Changes' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }

.modal-enter-active .modal-content { animation: modalScaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active .modal-content { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); transform: scale(0.95); }

@keyframes modalScaleIn {
  from { opacity: 0; transform: scale(0.9) translateY(40px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>