<script setup lang="ts">
import { ref, watch } from 'vue'

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
    unlock_rule: string
    inventory_json: string
    text_log_content: string
  }
  ruleEnforcementMode: string
  isSaving: boolean
  adventureId?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: any): void
}>()

const localForm = ref({ ...props.initialForm })

watch(() => props.initialForm, (newVal) => {
  localForm.value = { ...newVal }
}, { deep: true })

function handleSave() {
  let parsedInventory: any[] = []
  if (props.context?.type === 'object') {
    const raw = (localForm.value.inventory_json || '').trim()
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        parsedInventory = Array.isArray(parsed) ? parsed : []
      } catch {
        parsedInventory = []
      }
    }
  }

  emit('save', {
    ...localForm.value,
    inventory: parsedInventory,
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
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show && context" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="modal-content w-full max-w-2xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden">
          <div class="p-10 space-y-8">
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
              <div class="space-y-3">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Entity Name</label>
                <input v-model="localForm.name" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-2xl font-bold text-white focus:border-emerald-500 outline-none transition-all shadow-inner" />
              
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
                <textarea v-model="localForm.teaser" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner" placeholder="A short, catchy teaser for your adventure..."></textarea>
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
                  <textarea v-model="localForm.goal" maxlength="200" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner" placeholder="What drives the protagonist? (e.g. 'Seeks revenge for family's death')"></textarea>
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
                  <textarea v-model="localForm.character" maxlength="200" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner" placeholder="How does the protagonist behave? (e.g. 'Sarcastic but loyal, prone to rash decisions')"></textarea>
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
                  <textarea v-model="localForm.goal" maxlength="200" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner" placeholder="What does this NPC want? (e.g. 'Wants to steal the player's gold')"></textarea>
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
                  <textarea v-model="localForm.character" maxlength="200" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner" placeholder="How does this NPC behave? (e.g. 'Grumpy and stubborn')"></textarea>
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
                    <select v-model="localForm.item_type" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-amber-500/50 outline-none transition-all">
                      <option value="PICKABLE">PICKABLE</option>
                      <option value="WEAPON">WEAPON</option>
                      <option value="ARMOR">ARMOR</option>
                      <option value="CONSUMABLE">CONSUMABLE</option>
                      <option value="CONTAINER">CONTAINER</option>
                      <option value="STATIC">STATIC</option>
                    </select>
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

                <div class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Unlock Rule (Optional)</label>
                  <input v-model="localForm.unlock_rule" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white focus:border-amber-500/50 outline-none transition-all" placeholder="e.g. Requires brass key or lockpick" />
                </div>

                <div v-if="String(localForm.item_type || '').toUpperCase() === 'CONTAINER'" class="space-y-2">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Contained Items (JSON Array)</label>
                  <textarea v-model="localForm.inventory_json" rows="4" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-xs text-slate-300 font-mono resize-y focus:border-amber-500/50 outline-none transition-all" placeholder='["ITEM_KEY", {"id":"ITEM_MAP","name":"Old Map","item_type":"PICKABLE"}]'></textarea>
                  <p class="text-[10px] text-slate-500 uppercase tracking-wider">Supports item IDs and inline item objects.</p>
                </div>

                <div v-if="String(localForm.item_type || '').toUpperCase() === 'READABLE'" class="space-y-2">
                  <div class="flex justify-between items-center">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Text Log Content</label>
                    <span :class="['text-xs font-bold tracking-widest', (localForm.text_log_content || '').length > 500 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ (localForm.text_log_content || '').length }} / 500
                    </span>
                  </div>
                  <textarea v-model="localForm.text_log_content" maxlength="500" rows="5" class="w-full bg-black/40 border border-white/5 rounded-2xl px-4 py-3 text-sm text-slate-300 resize-y focus:border-cyan-500/50 outline-none transition-all" placeholder="Readable note text shown to the player."></textarea>
                </div>
              </div>

              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">{{ context.type === 'cover' ? 'Global Context / Premise' : 'Description / Biography' }}</label>
                  <span v-if="['npc', 'protagonist'].includes(context.type)" :class="['text-xs font-bold tracking-widest', (localForm.description || '').length > 400 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ (localForm.description || '').length }} / 400
                  </span>
                </div>
                <textarea v-model="localForm.description" :maxlength="['npc', 'protagonist'].includes(context.type) ? 400 : undefined" rows="8" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-lg text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"></textarea>
              </div>
            </div>

            <div class="flex justify-end gap-6 pt-4">
              <button @click="emit('close')" class="px-8 py-3 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors">Discard</button>
              <button @click="handleSave" :disabled="isSaving" class="px-10 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-black uppercase text-xs tracking-widest rounded-xl shadow-lg shadow-emerald-900/20 disabled:opacity-50 flex items-center gap-3">
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
