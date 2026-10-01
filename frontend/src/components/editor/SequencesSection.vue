<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, Trash2, Edit2, ChevronUp, ChevronDown, Check, X, BookOpen, Award } from 'lucide-vue-next'

const props = defineProps<{
  adventure: any
  isSaving?: boolean
}>()

const emit = defineEmits<{
  (e: 'update-sequences', sequences: any[]): void
  (e: 'notify', message: string, type?: 'error' | 'success' | 'info'): void
}>()

const sequences = computed<any[]>(() => {
  const raw = props.adventure?.sequences
  if (Array.isArray(raw)) {
    return [...raw].sort((a, b) => (Number(a.order) || 0) - (Number(b.order) || 0))
  }
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        return [...parsed].sort((a, b) => (Number(a.order) || 0) - (Number(b.order) || 0))
      }
    } catch {
      return []
    }
  }
  return []
})

const showModal = ref(false)
const isNewSequence = ref(false)
const modalSequence = ref<any>({
  id: '',
  order: 1,
  title: '',
  description: '',
  walkthrough: '',
  end_condition: '',
  exp_reward: 50,
})

const showDeleteConfirm = ref(false)
const pendingDeleteId = ref<string | null>(null)

function openAddModal() {
  if (sequences.value.length >= 15) {
    emit('notify', 'Maximum limit of 15 sequences reached.', 'info')
    return
  }
  isNewSequence.value = true
  const nextOrder = sequences.value.length + 1
  const randSlug = Math.random().toString(36).substring(2, 8).toUpperCase()
  modalSequence.value = {
    id: `SEQ_${nextOrder}_${randSlug}`,
    order: nextOrder,
    title: '',
    description: '',
    walkthrough: '',
    end_condition: '',
    exp_reward: 50,
  }
  showModal.value = true
}

function openEditModal(seq: any) {
  isNewSequence.value = false
  modalSequence.value = {
    id: seq.id || `SEQ_${seq.order || 1}`,
    order: seq.order || 1,
    title: seq.title || '',
    description: seq.description || '',
    walkthrough: seq.walkthrough || '',
    end_condition: seq.end_condition || '',
    exp_reward: seq.exp_reward ?? 50,
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

function saveSequence() {
  if (!modalSequence.value.title.trim()) {
    emit('notify', 'Sequence title is required.', 'error')
    return
  }

  const currentList = [...sequences.value]
  if (isNewSequence.value) {
    modalSequence.value.order = currentList.length + 1
    currentList.push({ ...modalSequence.value })
  } else {
    const idx = currentList.findIndex((s) => s.id === modalSequence.value.id)
    if (idx !== -1) {
      currentList[idx] = { ...modalSequence.value }
    }
  }

  // Re-normalize order
  const normalized = currentList.map((item, i) => ({
    ...item,
    order: i + 1,
  }))

  emit('update-sequences', normalized)
  closeModal()
}

function moveUp(index: number) {
  if (index <= 0) return
  const currentList = [...sequences.value]
  const temp = currentList[index]
  currentList[index] = currentList[index - 1]
  currentList[index - 1] = temp
  const reordered = currentList.map((item, i) => ({ ...item, order: i + 1 }))
  emit('update-sequences', reordered)
}

function moveDown(index: number) {
  if (index >= sequences.value.length - 1) return
  const currentList = [...sequences.value]
  const temp = currentList[index]
  currentList[index] = currentList[index + 1]
  currentList[index + 1] = temp
  const reordered = currentList.map((item, i) => ({ ...item, order: i + 1 }))
  emit('update-sequences', reordered)
}

function requestDelete(id: string) {
  pendingDeleteId.value = id
  showDeleteConfirm.value = true
}

function cancelDelete() {
  pendingDeleteId.value = null
  showDeleteConfirm.value = false
}

function confirmDelete() {
  if (!pendingDeleteId.value) return
  const updated = sequences.value
    .filter((s) => s.id !== pendingDeleteId.value)
    .map((item, i) => ({ ...item, order: i + 1 }))
  emit('update-sequences', updated)
  cancelDelete()
}
</script>

<template>
  <div class="space-y-6 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/5 pb-4">
      <div>
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <BookOpen class="w-4 h-4 text-amber-400" />
          </div>
          <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Story Sequences (Linear Chapters)</h3>
          <span class="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-500/10 border border-amber-500/20 text-amber-300">
            {{ sequences.length }} / 15
          </span>
        </div>
        <p class="text-xs text-slate-400 mt-1">
          Chronological chapters forming the main storyline backbone. The protagonist advances through each sequence sequentially.
        </p>
      </div>

      <button
        @click="openAddModal"
        :disabled="sequences.length >= 15 || isSaving"
        class="px-4 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black uppercase text-[10px] tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
      >
        <Plus class="w-3.5 h-3.5" />
        <span>Add Sequence</span>
      </button>
    </div>

    <!-- Empty State -->
    <div v-if="sequences.length === 0" class="p-8 border border-dashed border-white/10 rounded-2xl text-center space-y-3">
      <div class="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mx-auto text-amber-400">
        <BookOpen class="w-6 h-6" />
      </div>
      <p class="text-xs uppercase font-bold tracking-widest text-slate-400">No story sequences defined</p>
      <p class="text-xs text-slate-500 max-w-md mx-auto">
        Define linear sequence chapters to structure the core adventure progression.
      </p>
      <button
        @click="openAddModal"
        class="mt-2 px-4 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 rounded-xl text-xs font-bold uppercase tracking-wider transition-all"
      >
        + Add First Sequence
      </button>
    </div>

    <!-- Sequence Cards List -->
    <div v-else class="space-y-4">
      <div
        v-for="(seq, idx) in sequences"
        :key="seq.id || idx"
        class="bg-black/30 border border-white/5 hover:border-amber-500/30 rounded-2xl p-5 transition-all group relative overflow-hidden"
      >
        <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div class="flex items-start gap-3 flex-1 min-w-0">
            <!-- Order Number Badge -->
            <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500/20 to-amber-900/30 border border-amber-500/30 flex items-center justify-center shrink-0">
              <span class="text-xs font-black text-amber-400 font-mono">{{ idx + 1 }}</span>
            </div>

            <!-- Sequence Content -->
            <div class="space-y-2 flex-1 min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <h4 class="text-sm font-black text-white group-hover:text-amber-300 transition-colors">
                  {{ seq.title }}
                </h4>
                <span class="px-2 py-0.5 rounded-lg bg-emerald-500/10 text-[10px] font-black text-emerald-400 uppercase tracking-wider border border-emerald-500/20 flex items-center gap-1">
                  <Award class="w-3 h-3" />
                  {{ seq.exp_reward ?? 50 }} XP
                </span>
                <span v-if="seq.id" class="text-[10px] font-mono text-slate-500">
                  {{ seq.id }}
                </span>
              </div>

              <!-- Description -->
              <p v-if="seq.description" class="text-xs text-slate-300 leading-relaxed">
                {{ seq.description }}
              </p>

              <!-- Extra Meta: End Condition & Walkthrough -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                <div v-if="seq.end_condition" class="p-2.5 rounded-xl bg-slate-900/60 border border-white/5 text-[11px]">
                  <span class="text-amber-400/80 font-bold uppercase tracking-widest text-[9px] block mb-0.5">End Condition</span>
                  <span class="text-slate-300">{{ seq.end_condition }}</span>
                </div>
                <div v-if="seq.walkthrough" class="p-2.5 rounded-xl bg-slate-900/60 border border-white/5 text-[11px]">
                  <span class="text-cyan-400/80 font-bold uppercase tracking-widest text-[9px] block mb-0.5">GM Walkthrough</span>
                  <span class="text-slate-400">{{ seq.walkthrough }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 shrink-0 self-end sm:self-start">
            <button
              @click="moveUp(idx)"
              :disabled="idx === 0 || isSaving"
              class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30 disabled:hover:bg-transparent"
              title="Move Up"
            >
              <ChevronUp class="w-4 h-4" />
            </button>
            <button
              @click="moveDown(idx)"
              :disabled="idx === sequences.length - 1 || isSaving"
              class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 disabled:opacity-30 disabled:hover:bg-transparent"
              title="Move Down"
            >
              <ChevronDown class="w-4 h-4" />
            </button>
            <button
              @click="openEditModal(seq)"
              :disabled="isSaving"
              class="p-1.5 rounded-lg text-slate-400 hover:text-amber-400 hover:bg-amber-500/10 transition-colors"
              title="Edit Sequence"
            >
              <Edit2 class="w-4 h-4" />
            </button>
            <button
              @click="requestDelete(seq.id)"
              :disabled="isSaving"
              class="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
              title="Delete Sequence"
            >
              <Trash2 class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit/Add Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in" @click.self="closeModal">
      <div class="bg-slate-900 border border-white/10 rounded-3xl p-6 sm:p-8 max-w-xl w-full shadow-2xl space-y-6">
        <div class="flex items-center justify-between border-b border-white/5 pb-4">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
              <BookOpen class="w-4 h-4 text-amber-400" />
            </div>
            <h3 class="text-base font-black text-white uppercase tracking-wider">
              {{ isNewSequence ? 'Add New Sequence' : 'Edit Sequence' }}
            </h3>
          </div>
          <button @click="closeModal" class="p-1 rounded-lg text-slate-400 hover:text-white">
            <X class="w-5 h-5" />
          </button>
        </div>

        <div class="space-y-4">
          <!-- Title & XP -->
          <div class="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div class="sm:col-span-3 space-y-1">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Sequence Title *</label>
              <input
                v-model="modalSequence.title"
                type="text"
                maxlength="80"
                placeholder="e.g. The Escape From Cell Block C"
                class="w-full bg-black/60 border border-white/10 focus:border-amber-500/60 rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all"
              />
            </div>
            <div class="space-y-1">
              <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">EXP Reward</label>
              <input
                v-model.number="modalSequence.exp_reward"
                type="number"
                min="0"
                max="10000"
                class="w-full bg-black/60 border border-white/10 focus:border-amber-500/60 rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all"
              />
            </div>
          </div>

          <!-- Description -->
          <div class="space-y-1">
            <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">Narrative Description</label>
            <textarea
              v-model="modalSequence.description"
              rows="3"
              placeholder="What occurs in this chapter? Key story events and narrative backdrop for the GM."
              class="w-full bg-black/60 border border-white/10 focus:border-amber-500/60 rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all resize-y"
            ></textarea>
          </div>

          <!-- End Condition -->
          <div class="space-y-1">
            <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">End Condition / Completion Trigger</label>
            <input
              v-model="modalSequence.end_condition"
              type="text"
              placeholder="e.g. Player unlocks the iron door and reaches the courtyard."
              class="w-full bg-black/60 border border-white/10 focus:border-amber-500/60 rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all"
            />
          </div>

          <!-- Walkthrough -->
          <div class="space-y-1">
            <label class="block text-xs font-black text-slate-400 uppercase tracking-widest">GM Solution Path (Walkthrough)</label>
            <textarea
              v-model="modalSequence.walkthrough"
              rows="2"
              placeholder="Solution steps for this specific sequence..."
              class="w-full bg-black/60 border border-white/10 focus:border-amber-500/60 rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all resize-y"
            ></textarea>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 pt-4 border-t border-white/5">
          <button
            @click="closeModal"
            class="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold uppercase tracking-wider transition-all"
          >
            Cancel
          </button>
          <button
            @click="saveSequence"
            :disabled="!modalSequence.title.trim() || isSaving"
            class="px-6 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black uppercase text-xs tracking-widest transition-all shadow-lg flex items-center gap-2 disabled:opacity-50"
          >
            <Check class="w-4 h-4" />
            <span>Save Sequence</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in" @click.self="cancelDelete">
      <div class="bg-slate-900 border border-rose-500/20 rounded-2xl p-6 max-w-sm w-full space-y-4 shadow-2xl">
        <h4 class="text-sm font-black text-white uppercase tracking-wider">Delete Sequence?</h4>
        <p class="text-xs text-slate-400">
          Are you sure you want to remove this sequence chapter? Remaining sequences will be re-ordered.
        </p>
        <div class="flex items-center justify-end gap-3 pt-2">
          <button @click="cancelDelete" class="px-3 py-1.5 rounded-lg bg-slate-800 text-xs font-bold text-slate-300">
            Cancel
          </button>
          <button @click="confirmDelete" class="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-xs font-bold text-white uppercase tracking-wider">
            Delete
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
