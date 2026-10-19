<script setup lang="ts">
import { computed, ref } from 'vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import ScriptEditor from '@/components/editor/ScriptEditor.vue'
import { formatObjectIds } from '@/utils/editor_utils'
import { ShieldCheck, Package, MapPin, Swords } from 'lucide-vue-next'
import bronzeTrophy from '@/assets/svg/bronze-award-trophy.svg'
import silverTrophy from '@/assets/svg/silver-award-trophy.svg'
import goldTrophy from '@/assets/svg/gold-award-trophy.svg'

const props = defineProps<{
  adventure: any
  referenceOptions?: Array<{ id: string; name?: string; imageUrl?: string | null }>
  editorObjects?: any[]
  editorScenes?: any[]
  editorNpcs?: any[]
}>()

const emit = defineEmits<{
  (e: 'update-awards', awards: any[]): void
  (e: 'notify', message: string, type?: 'error' | 'success' | 'info'): void
}>()

const availableItems = computed(() => {
  const list =
    props.editorObjects && props.editorObjects.length > 0
      ? props.editorObjects
      : props.adventure?.objects || []
  return list
    .map((item: any) => ({
      id: String(item.id || item.entity_id || '').trim(),
      name: item.name || item.id || 'Unnamed Item',
    }))
    .filter((i: any) => Boolean(i.id))
})

const availableScenes = computed(() => {
  const list =
    props.editorScenes && props.editorScenes.length > 0
      ? props.editorScenes
      : props.adventure?.scenes || []
  return list
    .map((scene: any) => ({
      id: String(scene.id || '').trim(),
      name: scene.label || scene.name || scene.id || 'Unnamed Scene',
    }))
    .filter((s: any) => Boolean(s.id))
})

const availableNpcs = computed(() => {
  const list =
    props.editorNpcs && props.editorNpcs.length > 0
      ? props.editorNpcs
      : props.adventure?.npcs || []
  return list
    .map((npc: any) => ({
      id: String(npc.id || npc.entity_id || '').trim(),
      name: npc.name || npc.id || 'Unnamed NPC',
    }))
    .filter((n: any) => Boolean(n.id))
})

const awards = computed<any[]>(() => {
  const raw = props.adventure?.awards
  if (Array.isArray(raw)) return raw
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
})

function getAwardIcon(tier: string) {
  const t = (tier || '').toLowerCase()
  if (t === 'gold') return goldTrophy
  if (t === 'silver') return silverTrophy
  return bronzeTrophy
}

function hasHardRules(award: any): boolean {
  if (!award) return false
  return Boolean(
    award.required_item_id ||
    award.required_scene_id ||
    award.required_defeated_npc_id ||
    (award.guard_expression && String(award.guard_expression).trim())
  )
}

const showModal = ref(false)
const isNewAward = ref(false)
const showDeleteConfirmModal = ref(false)
const pendingDeleteAwardKey = ref<string | null>(null)

const modalAward = ref<any>({
  key: '',
  title: '',
  description: '',
  tier: 'bronze',
  requirement: '',
  is_earned: false,
  required_item_id: '',
  required_scene_id: '',
  required_defeated_npc_id: '',
  guard_expression: '',
})

function openAddModal() {
  isNewAward.value = true
  modalAward.value = {
    key: 'award_' + Math.random().toString(36).substring(2, 11),
    title: '',
    description: '',
    tier: 'bronze',
    requirement: '',
    is_earned: false,
    required_item_id: '',
    required_scene_id: '',
    required_defeated_npc_id: '',
    guard_expression: '',
  }
  showModal.value = true
}

function openEditModal(award: any) {
  isNewAward.value = false
  modalAward.value = {
    key: award.key || '',
    title: award.title || '',
    description: award.description || '',
    tier: award.tier || 'bronze',
    requirement: award.requirement || '',
    is_earned: award.is_earned || false,
    required_item_id: award.required_item_id || '',
    required_scene_id: award.required_scene_id || '',
    required_defeated_npc_id: award.required_defeated_npc_id || '',
    guard_expression: award.guard_expression || '',
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

function saveAward() {
  if (!(modalAward.value.title || '').trim() || !(modalAward.value.description || '').trim()) {
    emit('notify', 'Award title and description are required.', 'error')
    return
  }
  const updated = [...awards.value]
  if (isNewAward.value) {
    updated.push({ ...modalAward.value })
  } else {
    const idx = updated.findIndex((award) => String(award.key) === String(modalAward.value.key))
    if (idx !== -1) {
      updated[idx] = { ...modalAward.value }
    }
  }
  emit('update-awards', updated)
  closeModal()
}

function requestDeleteAward(key: string) {
  pendingDeleteAwardKey.value = key
  showDeleteConfirmModal.value = true
}

function cancelDeleteAward() {
  pendingDeleteAwardKey.value = null
  showDeleteConfirmModal.value = false
}

function confirmDeleteAward() {
  if (!pendingDeleteAwardKey.value) {
    cancelDeleteAward()
    return
  }
  const updated = awards.value.filter((award) => String(award.key) !== String(pendingDeleteAwardKey.value))
  emit('update-awards', updated)
  cancelDeleteAward()
}
</script>

<template>
  <section class="space-y-6 animate-page-in">
    <div class="flex items-center justify-between border-b border-white/5 pb-4">
      <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Achievements & Awards ({{ awards.length }})</h3>
      <button
        class="px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-black uppercase text-[10px] tracking-widest rounded-xl transition-all shadow-lg"
        @click="openAddModal"
      >
        + Add Award
      </button>
    </div>
    <p v-if="awards.length === 0" class="text-xs text-slate-500 uppercase tracking-widest">No awards generated for this adventure yet.</p>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="award in awards" :key="'award_' + (award.key || award.title)" class="bg-slate-900/40 border border-white/5 rounded-2xl p-5 hover:border-emerald-500/20 transition-all group flex items-start gap-4">
        <div :class="[
          'w-12 h-12 rounded-xl flex items-center justify-center border shrink-0',
          award.tier === 'gold' ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' :
          award.tier === 'silver' ? 'bg-slate-300/10 border-slate-300/20 text-slate-300' :
          'bg-orange-700/10 border-orange-700/20 text-orange-700'
        ]">
          <img :src="getAwardIcon(award.tier)" class="w-8 h-8 object-contain" alt="Trophy" />
        </div>
        <div class="space-y-1 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <h4 class="text-sm font-black text-white uppercase tracking-tight">{{ award.title }}</h4>
            <span :class="[
              'text-xs font-black uppercase px-1.5 py-0.5 rounded border',
              award.tier === 'gold' ? 'bg-amber-500/20 border-amber-500/30 text-amber-500' :
              award.tier === 'silver' ? 'bg-slate-300/20 border-slate-300/30 text-slate-300' :
              'bg-orange-700/20 border-orange-700/30 text-orange-700'
            ]">{{ award.tier }}</span>
            <span
              v-if="hasHardRules(award)"
              class="px-2 py-0.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[9px] font-bold uppercase rounded-md tracking-wider flex items-center gap-1"
            >
              <ShieldCheck class="w-3 h-3" />
              Hard Rules Active
            </span>
          </div>
          <p class="text-xs text-slate-400 leading-relaxed" v-html="formatObjectIds(award.description)"></p>
          <p class="text-xs text-slate-500 italic mt-1" v-html="'Requirement: ' + formatObjectIds(award.requirement)"></p>
          <div class="flex justify-end gap-3 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button class="text-[10px] font-black text-slate-400 hover:text-emerald-300 uppercase" @click="openEditModal(award)">Edit</button>
            <button class="text-[10px] font-black text-slate-500 hover:text-red-300 uppercase" @click="requestDeleteAward(award.key)">Delete</button>
          </div>
        </div>
      </div>
    </div>
  </section>

  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showModal" class="fixed inset-0 z-[200] flex items-center justify-center p-4 md:p-6 backdrop-blur-xl bg-slate-950/70 overflow-y-auto">
        <div class="w-full max-w-2xl max-h-[90vh] bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden flex flex-col my-auto">
          <div class="p-6 md:p-8 overflow-y-auto space-y-6 custom-scrollbar">
            <div class="flex items-center justify-between border-b border-white/5 pb-4">
              <h3 class="text-xs font-black text-emerald-400 uppercase tracking-widest">{{ isNewAward ? 'Add Award' : 'Edit Award' }}</h3>
              <button @click="closeModal" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>

            <!-- Award Key, Title, Tier -->
            <div class="space-y-4">
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div class="space-y-2">
                  <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Key</label>
                  <input v-model="modalAward.key" :disabled="!isNewAward" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white disabled:opacity-60 outline-none" />
                </div>
                <div class="sm:col-span-2 space-y-2">
                  <div class="flex items-center justify-between">
                    <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Title <span class="text-red-400">*</span></label>
                    <span :class="['text-[10px] font-bold tracking-widest', (modalAward.title || '').length > 100 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ (modalAward.title || '').length }} / 100
                    </span>
                  </div>
                  <input v-model="modalAward.title" maxlength="100" placeholder="e.g. Master of the Ruins" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:border-emerald-500 outline-none" />
                </div>
              </div>

              <div class="space-y-2">
                <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Tier</label>
                <select v-model="modalAward.tier" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:border-emerald-500 outline-none">
                  <option value="bronze">bronze</option>
                  <option value="silver">silver</option>
                  <option value="gold">gold</option>
                </select>
              </div>

              <!-- Description -->
              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Description <span class="text-red-400">*</span></label>
                  <span :class="['text-[10px] font-bold tracking-widest', (modalAward.description || '').length > 1000 ? 'text-red-500' : 'text-emerald-500/50']">
                    {{ (modalAward.description || '').length }} / 1000
                  </span>
                </div>
                <ReferenceTextarea
                  v-model="modalAward.description"
                  :maxlength="1000"
                  :rows="3"
                  :options="props.referenceOptions || []"
                  placeholder="Explain why this achievement is granted..."
                  class-name="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none"
                />
              </div>

              <!-- Soft Rule: Narrative Requirement -->
              <div class="space-y-1.5 p-4 rounded-2xl bg-black/40 border border-white/5">
                <div class="flex items-center justify-between">
                  <label class="block text-xs font-black text-amber-400 uppercase tracking-widest">
                    Narrative Requirement (Soft Rule)
                  </label>
                  <span class="text-[10px] text-slate-500 font-mono">Evaluated by GM LLM</span>
                </div>
                <p class="text-[11px] text-slate-400">
                  Narrative requirement evaluated by the GM LLM to grant this award during gameplay.
                </p>
                <ReferenceTextarea
                  v-model="modalAward.requirement"
                  :rows="2"
                  :options="props.referenceOptions || []"
                  placeholder="e.g. Successfully solve the riddle of the sphinx without using violence."
                  class-name="w-full bg-slate-900/90 border border-white/10 focus:border-amber-500/60 rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all placeholder:text-slate-600"
                />
              </div>

              <!-- Hard Rules: Deterministic Award Triggers -->
              <div class="space-y-3.5 p-4 rounded-2xl bg-black/40 border border-white/5">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <ShieldCheck class="w-4 h-4 text-emerald-400" />
                    <label class="block text-xs font-black text-emerald-400 uppercase tracking-widest">
                      Deterministic Award Triggers (Hard Rules)
                    </label>
                  </div>
                  <span class="text-[10px] text-slate-500 font-mono">Engine Enforced</span>
                </div>
                <p class="text-[11px] text-slate-400">
                  Optional hard conditions evaluated deterministically by the game engine. When configured, the award is automatically granted when these conditions are fulfilled.
                </p>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
                  <!-- Item Hard Rule -->
                  <div class="space-y-1.5 p-3 rounded-xl bg-slate-900/80 border border-white/5">
                    <div class="flex items-center justify-between">
                      <span class="flex items-center gap-1.5 text-[11px] font-bold text-slate-300">
                        <Package class="w-3.5 h-3.5 text-emerald-400" />
                        Obtain Item
                      </span>
                      <button
                        v-if="modalAward.required_item_id"
                        type="button"
                        @click="modalAward.required_item_id = ''"
                        class="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                      >
                        Clear
                      </button>
                    </div>
                    <select
                      v-model="modalAward.required_item_id"
                      class="w-full bg-black/60 border border-white/10 focus:border-emerald-500/60 rounded-xl px-3 py-2 text-xs text-white outline-none transition-all"
                    >
                      <option value="" class="bg-slate-900 text-slate-400">-- None (Optional) --</option>
                      <option
                        v-for="item in availableItems"
                        :key="item.id"
                        :value="item.id"
                        class="bg-slate-900 text-white"
                      >
                        {{ item.name }} ({{ item.id }})
                      </option>
                      <option
                        v-if="modalAward.required_item_id && !availableItems.some(i => i.id === modalAward.required_item_id)"
                        :value="modalAward.required_item_id"
                        class="bg-slate-900 text-amber-300"
                      >
                        {{ modalAward.required_item_id }} (Custom ID)
                      </option>
                    </select>
                    <span class="block text-[10px] text-slate-500">Protagonist acquires item X</span>
                  </div>

                  <!-- Scene Hard Rule -->
                  <div class="space-y-1.5 p-3 rounded-xl bg-slate-900/80 border border-white/5">
                    <div class="flex items-center justify-between">
                      <span class="flex items-center gap-1.5 text-[11px] font-bold text-slate-300">
                        <MapPin class="w-3.5 h-3.5 text-sky-400" />
                        Enter Scene
                      </span>
                      <button
                        v-if="modalAward.required_scene_id"
                        type="button"
                        @click="modalAward.required_scene_id = ''"
                        class="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                      >
                        Clear
                      </button>
                    </div>
                    <select
                      v-model="modalAward.required_scene_id"
                      class="w-full bg-black/60 border border-white/10 focus:border-sky-500/60 rounded-xl px-3 py-2 text-xs text-white outline-none transition-all"
                    >
                      <option value="" class="bg-slate-900 text-slate-400">-- None (Optional) --</option>
                      <option
                        v-for="scene in availableScenes"
                        :key="scene.id"
                        :value="scene.id"
                        class="bg-slate-900 text-white"
                      >
                        {{ scene.name }} ({{ scene.id }})
                      </option>
                      <option
                        v-if="modalAward.required_scene_id && !availableScenes.some(s => s.id === modalAward.required_scene_id)"
                        :value="modalAward.required_scene_id"
                        class="bg-slate-900 text-amber-300"
                      >
                        {{ modalAward.required_scene_id }} (Custom ID)
                      </option>
                    </select>
                    <span class="block text-[10px] text-slate-500">Protagonist enters Scene X</span>
                  </div>

                  <!-- NPC Defeat Hard Rule -->
                  <div class="space-y-1.5 p-3 rounded-xl bg-slate-900/80 border border-white/5">
                    <div class="flex items-center justify-between">
                      <span class="flex items-center gap-1.5 text-[11px] font-bold text-slate-300">
                        <Swords class="w-3.5 h-3.5 text-rose-400" />
                        Defeat NPC
                      </span>
                      <button
                        v-if="modalAward.required_defeated_npc_id"
                        type="button"
                        @click="modalAward.required_defeated_npc_id = ''"
                        class="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                      >
                        Clear
                      </button>
                    </div>
                    <select
                      v-model="modalAward.required_defeated_npc_id"
                      class="w-full bg-black/60 border border-white/10 focus:border-rose-500/60 rounded-xl px-3 py-2 text-xs text-white outline-none transition-all"
                    >
                      <option value="" class="bg-slate-900 text-slate-400">-- None (Optional) --</option>
                      <option
                        v-for="npc in availableNpcs"
                        :key="npc.id"
                        :value="npc.id"
                        class="bg-slate-900 text-white"
                      >
                        {{ npc.name }} ({{ npc.id }})
                      </option>
                      <option
                        v-if="modalAward.required_defeated_npc_id && !availableNpcs.some(n => n.id === modalAward.required_defeated_npc_id)"
                        :value="modalAward.required_defeated_npc_id"
                        class="bg-slate-900 text-amber-300"
                      >
                        {{ modalAward.required_defeated_npc_id }} (Custom ID)
                      </option>
                    </select>
                    <span class="block text-[10px] text-slate-500">Protagonist defeats NPC X</span>
                  </div>
                </div>

                <!-- Scripting Guard Expression -->
                <div class="space-y-2 p-3 rounded-xl bg-slate-900/80 border border-white/5 mt-3">
                  <ScriptEditor
                    v-model="modalAward.guard_expression"
                    label="Deterministic Guard Rule (Python Expression)"
                    help-text="Optional deterministic Python boolean condition. The award is automatically granted when this condition evaluates to True."
                    context="guard_expression"
                    placeholder="e.g. tw.player.has_item('DRAGON_SCALE') and tw.vars.get('boss_slain') == True"
                    min-height="90px"
                  />
                </div>
              </div>
            </div>

            <!-- Modal Action Buttons -->
            <div class="flex justify-end gap-3 pt-4 border-t border-white/5">
              <button class="px-5 py-2.5 text-xs font-bold border border-white/15 rounded-xl text-slate-300 hover:text-white transition-colors" @click="closeModal">Cancel</button>
              <button class="px-6 py-2.5 text-xs font-bold rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white shadow-lg transition-all disabled:opacity-50" :disabled="!(modalAward.title || '').trim() || !(modalAward.description || '').trim()" @click="saveAward">Save Award</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showDeleteConfirmModal" class="fixed inset-0 z-[210] flex items-center justify-center p-6 backdrop-blur-sm bg-black/60">
        <div class="w-full max-w-md bg-slate-900 border border-white/10 rounded-2xl p-6 space-y-4">
          <h4 class="text-sm font-black text-white">Delete this award?</h4>
          <p class="text-xs text-slate-400">This action removes the selected award from the adventure.</p>
          <div class="flex justify-end gap-3">
            <button class="px-3 py-2 text-xs font-bold border border-white/15 rounded text-slate-300" @click="cancelDeleteAward">Cancel</button>
            <button class="px-3 py-2 text-xs font-bold rounded bg-red-600 text-white" @click="confirmDeleteAward">Delete</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
