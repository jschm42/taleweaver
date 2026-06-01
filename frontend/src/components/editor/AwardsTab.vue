<script setup lang="ts">
import { computed, ref } from 'vue'
import ReferenceTextarea from '@/components/editor/ReferenceTextarea.vue'
import bronzeTrophy from '@/assets/svg/bronze-award-trophy.svg'
import silverTrophy from '@/assets/svg/silver-award-trophy.svg'
import goldTrophy from '@/assets/svg/gold-award-trophy.svg'

const props = defineProps<{
  adventure: any
  referenceOptions?: Array<{ id: string; name?: string; imageUrl?: string | null }>
}>()

const emit = defineEmits<{
  (e: 'update-awards', awards: any[]): void
  (e: 'notify', message: string, type?: 'error' | 'success' | 'info'): void
}>()

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
  }
  showModal.value = true
}

function openEditModal(award: any) {
  isNewAward.value = false
  modalAward.value = { ...award }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

function saveAward() {
  if (!modalAward.value.title) {
    emit('notify', 'Award title is required.', 'error')
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
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <h4 class="text-sm font-black text-white uppercase tracking-tight">{{ award.title }}</h4>
            <span :class="[
              'text-xs font-black uppercase px-1.5 py-0.5 rounded border',
              award.tier === 'gold' ? 'bg-amber-500/20 border-amber-500/30 text-amber-500' :
              award.tier === 'silver' ? 'bg-slate-300/20 border-slate-300/30 text-slate-300' :
              'bg-orange-700/20 border-orange-700/30 text-orange-700'
            ]">{{ award.tier }}</span>
          </div>
          <p class="text-xs text-slate-400 leading-relaxed">{{ award.description }}</p>
          <p class="text-xs text-slate-500 italic mt-1">Requirement: {{ award.requirement }}</p>
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
      <div v-if="showModal" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
        <div class="w-full max-w-lg bg-slate-900 border border-white/10 rounded-[2rem] shadow-2xl overflow-hidden">
          <div class="p-8 space-y-5">
            <div class="flex items-center justify-between">
              <h3 class="text-xs font-black text-emerald-400 uppercase tracking-widest">{{ isNewAward ? 'Add Award' : 'Edit Award' }}</h3>
              <button @click="closeModal" class="text-slate-500 hover:text-white"><i class="ra ra-cancel"></i></button>
            </div>

            <div class="space-y-2">
              <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Key</label>
              <input v-model="modalAward.key" :disabled="!isNewAward" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-white disabled:opacity-60" />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Title</label>
              <input v-model="modalAward.title" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-white" />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Tier</label>
              <select v-model="modalAward.tier" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-white">
                <option value="bronze">bronze</option>
                <option value="silver">silver</option>
                <option value="gold">gold</option>
              </select>
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Description</label>
              <ReferenceTextarea
                v-model="modalAward.description"
                :rows="3"
                :options="props.referenceOptions || []"
                class-name="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-white"
              />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-black text-slate-500 uppercase tracking-widest">Requirement</label>
              <ReferenceTextarea
                v-model="modalAward.requirement"
                :rows="2"
                :options="props.referenceOptions || []"
                class-name="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-sm text-white"
              />
            </div>

            <div class="flex justify-end gap-3 pt-2">
              <button class="px-4 py-2 text-xs font-bold border border-white/15 rounded-lg text-slate-300" @click="closeModal">Cancel</button>
              <button class="px-4 py-2 text-xs font-bold rounded-lg bg-emerald-600 text-white" @click="saveAward">Save Award</button>
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
