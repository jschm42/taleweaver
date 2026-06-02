<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import EntityReferenceCombobox from '@/components/editor/EntityReferenceCombobox.vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'

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
    inventory_json: string
    text_log_content: string
    text_log_format: string
    entity_id: string
    wearable_slots_input: string[]
    combination_ingredients: string
    switch_states_json: string
    switch_initial_state: string
    switch_transitions_json: string
    effects_json: string
    stat_modifier_strength: number
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

const localForm = ref({ ...props.initialForm })

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

const isFormInvalid = computed(() => {
  const nameInvalid = !(localForm.value.name || '').trim() ||
         (localForm.value.name || '').length > 50
  const descInvalid = !(localForm.value.description || '').trim() ||
         (localForm.value.description || '').length > 1000
  const personaInvalid = (localForm.value.goal || '').length > 200 ||
         (localForm.value.character || '').length > 200
  const teaserInvalid = (localForm.value.teaser || '').length > 300
  const idInvalid = props.isCreateEntityMode
    ? (!(localForm.value.entity_id || '').trim() || (localForm.value.entity_id || '').length > 30)
    : false
  return nameInvalid || descInvalid || personaInvalid || teaserInvalid || idInvalid
})

watch(() => props.initialForm, (newVal) => {
  localForm.value = { ...newVal }
}, { deep: true })

watch(() => localForm.value.item_type, (newType) => {
  if (!props.isCreateEntityMode) return
  const type = String(newType || '').toUpperCase()
  if (type === 'STATIC') {
    localForm.value.is_portable = false
  } else if (type === 'SWITCH') {
    localForm.value.is_portable = false
  } else if (['PICKABLE', 'CONSUMABLE', 'WEARABLE', 'WEAPON', 'TOOL', 'KEY', 'COMBINABLE'].includes(type)) {
    localForm.value.is_portable = true
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

  if (props.context?.type === 'object') {
    const rawInv = (localForm.value.inventory_json || '').trim()
    if (rawInv) {
      try {
        const parsed = JSON.parse(rawInv)
        parsedInventory = Array.isArray(parsed) ? parsed : []
      } catch {
        parsedInventory = []
      }
    }

    parsedWearableSlots = Array.isArray(localForm.value.wearable_slots_input)
      ? localForm.value.wearable_slots_input
      : []

    const rawStates = (localForm.value.switch_states_json || '').trim()
    if (rawStates) {
      try {
        const parsed = JSON.parse(rawStates)
        parsedSwitchStates = Array.isArray(parsed) ? parsed : []
      } catch {
        parsedSwitchStates = []
      }
    }

    const rawTransitions = (localForm.value.switch_transitions_json || '').trim()
    if (rawTransitions) {
      try {
        const parsed = JSON.parse(rawTransitions)
        parsedSwitchTransitions = Array.isArray(parsed) ? parsed : []
      } catch {
        parsedSwitchTransitions = []
      }
    }

    const rawEffects = (localForm.value.effects_json || '').trim()
    if (rawEffects) {
      try {
        const parsed = JSON.parse(rawEffects)
        parsedEffects = typeof parsed === 'object' && parsed !== null ? parsed : {}
      } catch {
        parsedEffects = {}
      }
    }

    const rawIngredients = (localForm.value.combination_ingredients || '').trim()
    if (rawIngredients) {
      parsedIngredients = rawIngredients.split(',').map(s => s.trim()).filter(Boolean)
    }
  }

  emit('save', {
    ...localForm.value,
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
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show && context" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="modal-content w-full max-w-2xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
          <div class="p-6 space-y-5 overflow-y-auto flex-1">
            <div class="flex justify-between items-center">
              <div class="space-y-1">
                <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">Editing {{ context.type }}</h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">ID: {{ context.id }}</p>
              </div>
              <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>

            <div class="space-y-6">
              <!-- Editable ID (create mode only) -->
              <div v-if="isCreateEntityMode" class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Entity ID <span class="text-red-400">*</span></label>
                  <span :class="['text-xs font-bold tracking-widest', (localForm.entity_id || '').length > 30 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ (localForm.entity_id || '').length }} / 30
                  </span>
                </div>
                <input
                  v-model="localForm.entity_id"
                  maxlength="30"
                  class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-lg font-mono font-bold text-amber-300 focus:border-amber-500 outline-none transition-all shadow-inner uppercase"
                  placeholder="ITEM_001"
                />
                <p class="text-[10px] text-slate-500 uppercase tracking-wider">Unique identifier. Only uppercase letters, numbers, and underscores.</p>
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
              
              <div v-if="context.type === 'cover'" class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Teaser (Max 300 Characters)</label>
                  <span :class="['text-xs font-bold tracking-widest', localForm.teaser.length > 300 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ localForm.teaser.length }} / 300
                  </span>
                </div>
                  <ReferenceTextarea
                    v-model="localForm.teaser"
                    :rows="3"
                    :options="props.referenceOptions || []"
                    class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
                    placeholder="A short, catchy teaser for your adventure..."
                  />
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

              <div v-if="context.type === 'object'" class="p-4 bg-black/30 border border-white/10 rounded-2xl space-y-5">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Item Type</label>
                    <select
                      v-if="isCreateEntityMode"
                      v-model="localForm.item_type"
                      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold uppercase tracking-widest focus:border-emerald-500/50 outline-none transition-all"
                    >
                      <option value="PICKABLE">PICKABLE</option>
                      <option value="CONSUMABLE">CONSUMABLE</option>
                      <option value="WEARABLE">WEARABLE</option>
                      <option value="WEAPON">WEAPON</option>
                      <option value="TOOL">TOOL</option>
                      <option value="KEY">KEY</option>
                      <option value="STATIC">STATIC</option>
                      <option value="COMBINABLE">COMBINABLE</option>
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
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Portable</label>
                    <button
                      type="button"
                      @click="localForm.is_portable = !localForm.is_portable"
                      :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', localForm.is_portable ? 'bg-emerald-600' : 'bg-slate-700']"
                    >
                      <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', localForm.is_portable ? 'translate-x-6' : 'translate-x-0']"></div>
                    </button>
                  </div>
                </div>

                <!-- WEAPON / WEARABLE / TOOL: Wearable Slots -->
                <div v-if="['WEAPON', 'WEARABLE', 'TOOL'].includes(currentItemType)" class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Wearable Slots</label>
                  <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    <label
                      v-for="slot in ['Head', 'Neck', 'Chest', 'Hands', 'Legs', 'Feet', 'MainHand', 'OffHand', 'Finger', 'Wrist', 'Back', 'Waist']"
                      :key="slot"
                      class="flex items-center gap-2 p-2 rounded-lg border border-white/5 bg-black/20 hover:bg-sky-500/10 hover:border-sky-500/20 cursor-pointer transition-all select-none"
                    >
                      <div class="relative flex items-center">
                        <input
                          type="checkbox"
                          :value="slot"
                          :checked="localForm.wearable_slots_input.includes(slot)"
                          @change="(e: Event) => {
                            const checked = (e.target as HTMLInputElement).checked
                            if (checked) {
                              localForm.wearable_slots_input = [...localForm.wearable_slots_input, slot]
                            } else {
                              localForm.wearable_slots_input = localForm.wearable_slots_input.filter((s: string) => s !== slot)
                            }
                          }"
                          class="w-4 h-4 rounded border-white/20 bg-black/40 text-sky-500 focus:ring-sky-500/40 focus:ring-1"
                        />
                      </div>
                      <span class="text-[10px] font-bold text-slate-300 uppercase tracking-widest">{{ slot }}</span>
                    </label>
                  </div>
                </div>

                <!-- CONSUMABLE: Effects & Stat Modifier -->
                <div v-if="currentItemType === 'CONSUMABLE'" class="space-y-4">
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Effects (JSON)</label>
                    <textarea v-model="localForm.effects_json" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-xs text-slate-300 font-mono resize-y focus:border-rose-500/50 outline-none transition-all" placeholder='{"hp": 20, "stamina": 10, "mana": 5}'></textarea>
                    <p class="text-[10px] text-slate-500 uppercase tracking-wider">JSON object with stat changes applied when consumed.</p>
                  </div>
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Stat Modifier Strength</label>
                    <input
                      v-model.number="localForm.stat_modifier_strength"
                      type="number"
                      min="-999"
                      max="999"
                      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-rose-500/50 outline-none transition-all"
                    />
                  </div>
                </div>

                <!-- COMBINABLE: Ingredients -->
                <div v-if="currentItemType === 'COMBINABLE'" class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Combination Ingredients</label>
                  <input
                    v-model="localForm.combination_ingredients"
                    class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white focus:border-violet-500/50 outline-none transition-all"
                    placeholder="ITEM_IRON, ITEM_WOOD, ITEM_FLINT"
                  />
                  <p class="text-[10px] text-slate-500 uppercase tracking-wider">Comma-separated item IDs required to combine with this item.</p>
                </div>

                <!-- SWITCH: States & Transitions -->
                <div v-if="currentItemType === 'SWITCH'" class="space-y-4">
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Switch States (JSON Array)</label>
                    <textarea v-model="localForm.switch_states_json" rows="2" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-xs text-slate-300 font-mono resize-y focus:border-lime-500/50 outline-none transition-all" placeholder='["off", "on", "broken"]'></textarea>
                  </div>
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Initial State</label>
                    <input
                      v-model="localForm.switch_initial_state"
                      maxlength="50"
                      class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white focus:border-lime-500/50 outline-none transition-all"
                      placeholder="off"
                    />
                  </div>
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Switch Transitions (JSON Array)</label>
                    <textarea v-model="localForm.switch_transitions_json" rows="4" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-xs text-slate-300 font-mono resize-y focus:border-lime-500/50 outline-none transition-all" placeholder='[{"from":"off","to":"on","gates":{}},{"from":"on","to":"off","gates":{}}]'></textarea>
                    <p class="text-[10px] text-slate-500 uppercase tracking-wider">Array of transition objects with from, to, gates, and optional fail_message.</p>
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
                      :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', localForm.locked ? 'bg-amber-600' : 'bg-emerald-600']"
                    >
                      <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', localForm.locked ? 'translate-x-0' : 'translate-x-6']"></div>
                    </button>
                  </div>
                </div>

                <div v-if="currentItemType === 'CONTAINER'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Code To Unlock</label>
                    <input
                      v-model="localForm.code_to_unlock"
                      maxlength="32"
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

                <div v-if="currentItemType === 'CONTAINER'" class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Contained Items (JSON Array)</label>
                  <textarea v-model="localForm.inventory_json" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-xs text-slate-300 font-mono resize-y focus:border-amber-500/50 outline-none transition-all" placeholder='["ITEM_KEY", {"id":"ITEM_MAP","name":"Old Map","item_type":"PICKABLE"}]'></textarea>
                  <p class="text-[10px] text-slate-500 uppercase tracking-wider">Supports item IDs and inline item objects.</p>
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
                    <span :class="['text-xs font-bold tracking-widest', (localForm.text_log_content || '').length > 500 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ (localForm.text_log_content || '').length }} / 500
                    </span>
                  </div>
                  <ReferenceTextarea
                    v-model="localForm.text_log_content"
                    :maxlength="500"
                    :rows="3"
                    :options="props.referenceOptions || []"
                    class-name="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-y focus:border-cyan-500/50 outline-none transition-all"
                    placeholder="Readable note text shown to the player."
                  />
                </div>
              </div>

              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">{{ context.type === 'cover' ? 'Global Context / Premise' : 'Description / Biography' }} <span class="text-red-400">*</span></label>
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
              </div>
            </div>

            <div class="flex justify-end gap-4 pt-3 border-t border-white/5 mt-2">
              <button @click="emit('close')" class="px-6 py-2.5 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors">Discard</button>
              <button @click="handleSave" :disabled="isSaving || isFormInvalid" class="px-8 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-black uppercase text-xs tracking-widest rounded-xl shadow-lg shadow-emerald-900/20 disabled:opacity-50 flex items-center gap-3">
                <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                <span>{{ isSaving ? 'Saving...' : 'Apply Changes' }}</span>
              </button>
            </div>
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