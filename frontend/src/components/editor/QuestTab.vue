<script setup lang="ts">
import { ref, computed } from 'vue'
import { entityService } from '@/services/entityService'


const props = defineProps<{
  adventure: any
}>()

const emit = defineEmits<{
  (e: 'update-quests', quests: any[]): void
  (e: 'notify', message: string, type?: 'error' | 'success' | 'info'): void
}>()

const quests = computed<any[]>(() => {
  const raw = props.adventure?.quests
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

const mainQuests = computed(() => quests.value.filter(q => q.is_main))
const sideQuests = computed(() => quests.value.filter(q => !q.is_main))

// Modal State
const showModal = ref(false)
const isNewQuest = ref(false)
const modalQuest = ref<any>({
  id: '',
  title: '',
  description: '',
  exp_reward: 50,
  is_main: true,
  status: 'open'
})

// Auto generation state
const isGeneratingDescription = ref(false)
const showDeleteConfirmModal = ref(false)
const pendingDeleteQuestId = ref<string | null>(null)

async function generateDescription() {
  if (!props.adventure?.id || !modalQuest.value.title) return
  isGeneratingDescription.value = true
  try {
    // Get other quests excluding the one currently editing to prevent self-reference
    const otherQuests = quests.value.filter(q => q.id !== modalQuest.value.id)
    const result = await entityService.generateQuestDescription(
      props.adventure.id,
      modalQuest.value.title,
      modalQuest.value.is_main,
      otherQuests
    )
    modalQuest.value.description = result.description
  } catch (error) {
    console.error('Failed to generate quest description:', error)
    emit('notify', error instanceof Error ? error.message : 'Failed to generate quest description', 'error')
  } finally {
    isGeneratingDescription.value = false
  }
}

const isGeneratingNewQuest = ref(false)

async function generateFullQuest() {
  if (!props.adventure?.id) return
  isGeneratingNewQuest.value = true
  try {
    const otherQuests = quests.value.filter(q => q.id !== modalQuest.value.id)
    const result = await entityService.generateNewQuest(
      props.adventure.id,
      modalQuest.value.is_main,
      otherQuests
    )
    modalQuest.value.title = result.title
    modalQuest.value.description = result.description
  } catch (error) {
    console.error('Failed to generate new quest:', error)
    emit('notify', error instanceof Error ? error.message : 'Failed to generate new quest', 'error')
  } finally {
    isGeneratingNewQuest.value = false
  }
}

async function autoGenerateNewQuest(isMain: boolean) {
  if (!props.adventure?.id) return
  isGeneratingNewQuest.value = true
  try {
    const result = await entityService.generateNewQuest(
      props.adventure.id,
      isMain,
      quests.value
    )
    isNewQuest.value = true
    modalQuest.value = {
      id: 'quest_' + Math.random().toString(36).substring(2, 11),
      title: result.title,
      description: result.description,
      exp_reward: 50,
      is_main: isMain,
      status: 'open'
    }
    showModal.value = true
  } catch (error) {
    console.error('Failed to generate quest:', error)
    emit('notify', error instanceof Error ? error.message : 'Failed to generate quest', 'error')
  } finally {
    isGeneratingNewQuest.value = false
  }
}


function openAddModal() {
  isNewQuest.value = true
  modalQuest.value = {
    id: 'quest_' + Math.random().toString(36).substring(2, 11),
    title: '',
    description: '',
    exp_reward: 50,
    is_main: true,
    status: 'open'
  }
  showModal.value = true
}

function openEditModal(quest: any) {
  isNewQuest.value = false
  modalQuest.value = { ...quest }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

function saveQuest() {
  if (!modalQuest.value.title) return
  let updatedList = [...quests.value]
  if (isNewQuest.value) {
    updatedList.push(modalQuest.value)
  } else {
    const idx = updatedList.findIndex(q => q.id === modalQuest.value.id)
    if (idx !== -1) {
      updatedList[idx] = modalQuest.value
    }
  }
  emit('update-quests', updatedList)
  closeModal()
}

function handleDelete(questId: string) {
  pendingDeleteQuestId.value = questId
  showDeleteConfirmModal.value = true
}

function cancelDeleteQuest() {
  showDeleteConfirmModal.value = false
  pendingDeleteQuestId.value = null
}

function confirmDeleteQuest() {
  if (!pendingDeleteQuestId.value) {
    cancelDeleteQuest()
    return
  }
  const updatedList = quests.value.filter(q => q.id !== pendingDeleteQuestId.value)
  emit('update-quests', updatedList)
  cancelDeleteQuest()
}
</script>

<template>
  <section class="space-y-8 animate-page-in">
    <!-- Header with Action -->
    <div class="flex items-center justify-between border-b border-white/5 pb-4">
      <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Quest Log ({{ quests.length }})</h3>
      <div class="flex items-center gap-3">
        <button 
          @click="autoGenerateNewQuest(true)" 
          :disabled="isGeneratingNewQuest"
          class="px-4 py-2 bg-slate-900 border border-white/5 hover:border-emerald-500/30 text-emerald-400 font-black uppercase text-[10px] tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2 group disabled:opacity-50"
        >
          <i class="ra ra-cycle" :class="{ 'animate-spin': isGeneratingNewQuest }"></i>
          <span>Auto-Generate Quest</span>
        </button>
        <button 
          @click="openAddModal" 
          class="px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-black uppercase text-[10px] tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2 group"
        >
          <span>+ Add Quest</span>
        </button>
      </div>
    </div>

    <!-- Main Quests Section -->
    <div v-if="mainQuests.length" class="space-y-4">
      <div class="flex items-center gap-3 border-b border-emerald-500/10 pb-2">
        <div class="w-7 h-7 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
          <i class="ra ra-trophy text-emerald-400 text-sm"></i>
        </div>
        <h3 class="text-xs font-black text-emerald-400 uppercase tracking-[0.2em]">Main Quests ({{ mainQuests.length }})</h3>
      </div>
      
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div 
          v-for="quest in mainQuests" 
          :key="'quest_' + quest.id" 
          class="bg-slate-900/40 border border-white/5 rounded-2xl p-5 hover:border-emerald-500/30 transition-all group relative overflow-hidden flex flex-col justify-between"
        >
          <div class="absolute inset-0 bg-gradient-to-br from-emerald-500/0 via-emerald-500/0 to-emerald-500/[0.02] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>
          
          <div>
            <div class="flex items-start justify-between gap-4 mb-3">
              <h4 class="text-sm font-bold text-white leading-snug group-hover:text-emerald-300 transition-colors">{{ quest.title }}</h4>
              <span class="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-[10px] font-black text-emerald-400 uppercase tracking-wider border border-emerald-500/20 shrink-0">
                {{ quest.exp_reward }} XP
              </span>
            </div>
            <p class="text-xs text-slate-400 leading-relaxed">{{ quest.description }}</p>
          </div>

          <!-- Actions Panel on Hover -->
          <div class="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-white/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <button @click="openEditModal(quest)" class="px-2.5 py-1 text-[10px] font-black text-slate-400 hover:text-emerald-400 flex items-center gap-1.5 uppercase tracking-wider transition-colors">
              <i class="ra ra-quill-ink"></i> Edit
            </button>
            <button @click="handleDelete(quest.id)" class="px-2.5 py-1 text-[10px] font-black text-slate-500 hover:text-rose-400 flex items-center gap-1.5 uppercase tracking-wider transition-colors">
              <i class="ra ra-trash"></i> Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Side Quests Section -->
    <div v-if="sideQuests.length" class="space-y-4">
      <div class="flex items-center gap-3 border-b border-blue-500/10 pb-2">
        <div class="w-7 h-7 rounded-lg bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
          <i class="ra ra-scroll-unfurled text-blue-400 text-sm"></i>
        </div>
        <h3 class="text-xs font-black text-blue-400 uppercase tracking-[0.2em]">Side Quests ({{ sideQuests.length }})</h3>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div 
          v-for="quest in sideQuests" 
          :key="'quest_' + quest.id" 
          class="bg-slate-900/40 border border-white/5 rounded-2xl p-5 hover:border-blue-500/30 transition-all group relative overflow-hidden flex flex-col justify-between"
        >
          <div class="absolute inset-0 bg-gradient-to-br from-blue-500/0 via-blue-500/0 to-blue-500/[0.02] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none"></div>

          <div>
            <div class="flex items-start justify-between gap-4 mb-3">
              <h4 class="text-sm font-bold text-white leading-snug group-hover:text-blue-300 transition-colors">{{ quest.title }}</h4>
              <span class="px-2.5 py-1 rounded-lg bg-blue-500/10 text-[10px] font-black text-blue-400 uppercase tracking-wider border border-blue-500/20 shrink-0">
                {{ quest.exp_reward }} XP
              </span>
            </div>
            <p class="text-xs text-slate-400 leading-relaxed">{{ quest.description }}</p>
          </div>

          <!-- Actions Panel on Hover -->
          <div class="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-white/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <button @click="openEditModal(quest)" class="px-2.5 py-1 text-[10px] font-black text-slate-400 hover:text-blue-400 flex items-center gap-1.5 uppercase tracking-wider transition-colors">
              <i class="ra ra-quill-ink"></i> Edit
            </button>
            <button @click="handleDelete(quest.id)" class="px-2.5 py-1 text-[10px] font-black text-slate-500 hover:text-rose-400 flex items-center gap-1.5 uppercase tracking-wider transition-colors">
              <i class="ra ra-trash"></i> Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="quests.length === 0" class="text-center py-16 bg-slate-900/20 border border-dashed border-white/5 rounded-3xl">
      <i class="ra ra-scroll text-4xl text-slate-600 block mb-4"></i>
      <p class="text-xs text-slate-500 uppercase tracking-widest mb-1">No quests generated for this adventure yet.</p>
      <p class="text-[10px] text-slate-600 uppercase tracking-wider">Click "+ Add Quest" above to start drafting your first chronicle entry.</p>
    </div>
  </section>

  <!-- Edit/Create Quest Modal -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showModal" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="modal-content w-full max-w-lg bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden animate-modal-in">
          <div class="p-10 space-y-8">
            <!-- Modal Header -->
            <div class="flex justify-between items-center">
              <div class="space-y-1">
                <h3 class="text-xs font-black text-emerald-400 uppercase tracking-widest">{{ isNewQuest ? 'Add Quest' : 'Edit Quest' }}</h3>
                <p class="text-slate-500 text-[10px] uppercase font-bold tracking-tighter" v-if="!isNewQuest">ID: {{ modalQuest.id }}</p>
              </div>
              <button @click="closeModal" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>

            <!-- Modal Form Fields -->
            <div class="space-y-5">
              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <label class="block text-[10px] font-black text-slate-500 uppercase tracking-widest">Quest Title</label>
                  <button 
                    v-if="isNewQuest"
                    type="button"
                    @click="generateFullQuest"
                    :disabled="isGeneratingNewQuest"
                    class="text-[10px] font-black text-emerald-400 hover:text-emerald-300 uppercase tracking-wider transition-colors flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <i class="ra ra-cycle" :class="{ 'animate-spin': isGeneratingNewQuest }"></i>
                    <span>{{ isGeneratingNewQuest ? 'Generating...' : 'Auto-Generate' }}</span>
                  </button>
                </div>
                <input 
                  v-model="modalQuest.title" 
                  placeholder="e.g. Find the Lost Key" 
                  class="w-full bg-black/40 border border-white/5 rounded-2xl px-5 py-3.5 text-base font-bold text-white focus:border-emerald-500 outline-none transition-all shadow-inner" 
                />
              </div>

              <div class="space-y-2">
                <label class="block text-[10px] font-black text-slate-500 uppercase tracking-widest">Quest Type</label>
                <div class="grid grid-cols-2 gap-3">
                  <button 
                    type="button"
                    @click="modalQuest.is_main = true"
                    :class="['py-3 rounded-xl text-xs font-black uppercase tracking-wider transition-all border', modalQuest.is_main ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 shadow-inner' : 'bg-black/20 border-white/5 text-slate-400 hover:text-white']"
                  >
                    Main Quest
                  </button>
                  <button 
                    type="button"
                    @click="modalQuest.is_main = false"
                    :class="['py-3 rounded-xl text-xs font-black uppercase tracking-wider transition-all border', !modalQuest.is_main ? 'bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-inner' : 'bg-black/20 border-white/5 text-slate-400 hover:text-white']"
                  >
                    Side Quest
                  </button>
                </div>
              </div>

              <div class="space-y-2">
                <label class="block text-[10px] font-black text-slate-500 uppercase tracking-widest">XP Reward</label>
                <input 
                  type="number" 
                  min="0" 
                  max="9999" 
                  v-model.number="modalQuest.exp_reward" 
                  class="w-full bg-black/40 border border-white/5 rounded-2xl px-5 py-3 text-sm font-bold text-white focus:border-emerald-500 outline-none transition-all shadow-inner" 
                />
              </div>

              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <label class="block text-[10px] font-black text-slate-500 uppercase tracking-widest">Description</label>
                  <button 
                    v-if="modalQuest.title"
                    type="button"
                    @click="generateDescription"
                    :disabled="isGeneratingDescription"
                    class="text-[10px] font-black text-emerald-400 hover:text-emerald-300 uppercase tracking-wider transition-colors flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <i class="ra ra-cycle" :class="{ 'animate-spin': isGeneratingDescription }"></i>
                    <span>{{ isGeneratingDescription ? 'Generating...' : 'Auto-Generate' }}</span>
                  </button>
                </div>
                <textarea 
                  v-model="modalQuest.description" 
                  rows="4" 
                  placeholder="Explain what the protagonist needs to do..." 
                  class="w-full bg-black/40 border border-white/5 rounded-2xl px-5 py-3 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"
                ></textarea>
              </div>
            </div>

            <!-- Modal Action Buttons -->
            <div class="flex justify-end gap-4 pt-4 border-t border-white/5">
              <button @click="closeModal" class="px-6 py-3 text-slate-400 hover:text-white font-black uppercase text-[10px] tracking-widest transition-colors">Cancel</button>
              <button 
                @click="saveQuest" 
                :disabled="!modalQuest.title" 
                class="px-8 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-black uppercase text-[10px] tracking-widest rounded-xl shadow-lg transition-all disabled:opacity-50"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>

  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showDeleteConfirmModal" class="fixed inset-0 z-[220] flex items-center justify-center p-6 backdrop-blur-sm bg-slate-950/70" @click="cancelDeleteQuest">
        <div class="modal-content w-full max-w-md bg-slate-900 border border-rose-500/20 rounded-3xl shadow-2xl overflow-hidden" @click.stop>
          <div class="px-6 py-5 border-b border-white/10 flex items-start gap-3">
            <div class="w-10 h-10 rounded-full border border-rose-400/40 bg-rose-500/15 flex items-center justify-center shrink-0">
              <i class="ra ra-warning text-rose-300"></i>
            </div>
            <div>
              <h3 class="text-sm font-black text-white uppercase tracking-wider">Delete Quest</h3>
              <p class="text-xs text-slate-400 mt-1">This action cannot be undone.</p>
            </div>
          </div>

          <div class="px-6 py-5">
            <p class="text-sm text-slate-200">Are you sure you want to remove this quest from the log?</p>
          </div>

          <div class="px-6 py-4 border-t border-white/10 flex items-center justify-end gap-3">
            <button class="px-4 py-2 rounded-lg border border-white/15 text-slate-300 text-sm font-bold hover:bg-white/5 transition-colors" @click="cancelDeleteQuest">
              Cancel
            </button>
            <button class="px-4 py-2 rounded-lg bg-rose-500 text-white text-sm font-black uppercase tracking-wider hover:bg-rose-400 transition-colors" @click="confirmDeleteQuest">
              Delete
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }

.modal-enter-active, .modal-leave-active { transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }

.modal-enter-active .modal-content { animation: modalScaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active .modal-content { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); transform: scale(0.95); }

@keyframes modalScaleIn {
  from { opacity: 0; transform: scale(0.9) translateY(40px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
</style>
