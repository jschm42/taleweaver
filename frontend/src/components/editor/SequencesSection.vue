<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Plus,
  Trash2,
  Edit2,
  ChevronUp,
  ChevronDown,
  Check,
  X,
  BookOpen,
  Award,
  Package,
  MapPin,
  Swords,
  ShieldCheck,
} from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    adventure: any
    isSaving?: boolean
    editorScenes?: any[]
    editorObjects?: any[]
    editorNpcs?: any[]
  }>(),
  {
    isSaving: false,
    editorScenes: () => [],
    editorObjects: () => [],
    editorNpcs: () => [],
  }
)

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

const availableItems = computed(() => {
  const list = (props.editorObjects && props.editorObjects.length > 0)
    ? props.editorObjects
    : (props.adventure?.objects || [])
  return list.map((item: any) => ({
    id: String(item.id || item.entity_id || '').trim(),
    name: item.name || item.id || 'Unnamed Item',
  })).filter((i: any) => Boolean(i.id))
})

const availableScenes = computed(() => {
  const list = (props.editorScenes && props.editorScenes.length > 0)
    ? props.editorScenes
    : (props.adventure?.scenes || [])
  return list.map((scene: any) => ({
    id: String(scene.id || '').trim(),
    name: scene.label || scene.name || scene.id || 'Unnamed Scene',
  })).filter((s: any) => Boolean(s.id))
})

const availableNpcs = computed(() => {
  const list = (props.editorNpcs && props.editorNpcs.length > 0)
    ? props.editorNpcs
    : (props.adventure?.npcs || [])
  return list.map((npc: any) => ({
    id: String(npc.id || npc.entity_id || '').trim(),
    name: npc.name || npc.id || 'Unnamed NPC',
  })).filter((n: any) => Boolean(n.id))
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
  required_item_id: '',
  required_scene_id: '',
  required_defeated_npc_id: '',
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
    required_item_id: '',
    required_scene_id: '',
    required_defeated_npc_id: '',
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
    required_item_id: seq.required_item_id || '',
    required_scene_id: seq.required_scene_id || '',
    required_defeated_npc_id: seq.required_defeated_npc_id || '',
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
  <div class="space-y-6">
    <!-- Header / Info Bar -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-black/40 border border-white/5 backdrop-blur-md">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <BookOpen class="w-5 h-5 text-amber-400" />
          <h3 class="text-sm font-black text-white uppercase tracking-widest">
            Story Sequences (Linear Chapters)
          </h3>
          <span class="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[10px] font-mono font-bold">
            {{ sequences.length }} / 15
          </span>
        </div>
        <p class="text-xs text-slate-400 max-w-2xl">
          Chronological chapters forming the main story arc. Each sequence has its own dedicated walkthrough, narrative backdrop, and completion trigger.
        </p>
      </div>

      <button
        @click="openAddModal"
        :disabled="sequences.length >= 15 || isSaving"
        class="px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black uppercase text-xs tracking-wider transition-all shadow-lg flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
      >
        <Plus class="w-4 h-4" />
        <span>Add Sequence</span>
      </button>
    </div>

    <!-- Empty State -->
    <div
      v-if="sequences.length === 0"
      class="text-center py-16 px-4 rounded-3xl border border-dashed border-white/10 bg-black/20 space-y-3"
    >
      <div class="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mx-auto text-amber-400">
        <BookOpen class="w-6 h-6" />
      </div>
      <h4 class="text-sm font-bold text-slate-300">No story sequences defined yet</h4>
      <p class="text-xs text-slate-500 max-w-md mx-auto">
        Break down your adventure into ordered chapters with dedicated GM walkthroughs and completion conditions.
      </p>
      <button
        @click="openAddModal"
        class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-400 border border-amber-500/30 text-xs font-bold transition-all mt-2"
      >
        <Plus class="w-4 h-4" />
        <span>Create First Sequence</span>
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
                  <span class="text-amber-400/80 font-bold uppercase tracking-widest text-[9px] block mb-0.5">Narrative End Condition (Soft Rule)</span>
                  <span class="text-slate-300">{{ seq.end_condition }}</span>
                </div>
                <div v-if="seq.walkthrough" class="p-2.5 rounded-xl bg-slate-900/60 border border-white/5 text-[11px]">
                  <span class="text-cyan-400/80 font-bold uppercase tracking-widest text-[9px] block mb-0.5">GM Walkthrough</span>
                  <span class="text-slate-400">{{ seq.walkthrough }}</span>
                </div>
              </div>

              <!-- Hard Rules Tags (if any) -->
              <div v-if="seq.required_item_id || seq.required_scene_id || seq.required_defeated_npc_id" class="flex flex-wrap items-center gap-2 pt-1.5">
                <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Hard Rules:</span>
                <span v-if="seq.required_item_id" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-[11px] font-medium">
                  <Package class="w-3.5 h-3.5 text-emerald-400" />
                  <span>Item: <strong class="font-mono text-white">{{ seq.required_item_id }}</strong></span>
                </span>
                <span v-if="seq.required_scene_id" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-300 text-[11px] font-medium">
                  <MapPin class="w-3.5 h-3.5 text-sky-400" />
                  <span>Scene: <strong class="font-mono text-white">{{ seq.required_scene_id }}</strong></span>
                </span>
                <span v-if="seq.required_defeated_npc_id" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px] font-medium">
                  <Swords class="w-3.5 h-3.5 text-rose-400" />
                  <span>Defeat: <strong class="font-mono text-white">{{ seq.required_defeated_npc_id }}</strong></span>
                </span>
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

    <!-- Edit/Add Modal (Larger, Non-clipping Scrollable Container) -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 overflow-y-auto p-4 sm:p-6 md:p-8 bg-black/85 backdrop-blur-md flex items-center justify-center animate-fade-in"
      @click.self="closeModal"
    >
      <div class="relative bg-slate-900 border border-white/10 rounded-3xl p-6 sm:p-8 max-w-3xl w-full shadow-2xl flex flex-col max-h-[92vh] my-auto">
        <!-- Fixed Header -->
        <div class="shrink-0 flex items-center justify-between border-b border-white/5 pb-4">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
              <BookOpen class="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <h3 class="text-base font-black text-white uppercase tracking-wider">
                {{ isNewSequence ? 'Add New Sequence' : 'Edit Sequence' }}
              </h3>
              <p class="text-[11px] text-slate-400">
                Configure narrative goals and completion triggers for this chapter.
              </p>
            </div>
          </div>
          <button @click="closeModal" class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors">
            <X class="w-5 h-5" />
          </button>
        </div>

        <!-- Scrollable Content Body -->
        <div class="flex-1 overflow-y-auto space-y-5 pr-1.5 -mr-1.5 my-4">
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

          <!-- Soft Rule: Narrative End Condition -->
          <div class="space-y-1.5 p-4 rounded-2xl bg-black/40 border border-white/5">
            <div class="flex items-center justify-between">
              <label class="block text-xs font-black text-amber-400 uppercase tracking-widest">
                Narrative End Condition (Soft Rule)
              </label>
              <span class="text-[10px] text-slate-500 font-mono">Evaluated by GM LLM</span>
            </div>
            <p class="text-[11px] text-slate-400">
              Narrative or contextual condition evaluated by the GM LLM to determine chapter completion.
            </p>
            <input
              v-model="modalSequence.end_condition"
              type="text"
              placeholder="e.g. Player convinces the gatekeeper or solves the courtyard riddle."
              class="w-full bg-slate-900/90 border border-white/10 focus:border-amber-500/60 rounded-xl px-4 py-2.5 text-sm text-white outline-none transition-all placeholder:text-slate-600"
            />
          </div>

          <!-- Hard Rules: Deterministic Triggers -->
          <div class="space-y-3.5 p-4 rounded-2xl bg-black/40 border border-white/5">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <ShieldCheck class="w-4 h-4 text-emerald-400" />
                <label class="block text-xs font-black text-emerald-400 uppercase tracking-widest">
                  Deterministic Completion Triggers (Hard Rules)
                </label>
              </div>
              <span class="text-[10px] text-slate-500 font-mono">Engine Enforced</span>
            </div>
            <p class="text-[11px] text-slate-400">
              Optional hard conditions enforced deterministically by the game engine. When configured, the sequence automatically advances when these conditions are fulfilled.
            </p>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
              <!-- Item Hard Rule (prot erhält item X) -->
              <div class="space-y-1.5 p-3 rounded-xl bg-slate-900/80 border border-white/5">
                <div class="flex items-center justify-between">
                  <span class="flex items-center gap-1.5 text-[11px] font-bold text-slate-300">
                    <Package class="w-3.5 h-3.5 text-emerald-400" />
                    Obtain Item
                  </span>
                  <button
                    v-if="modalSequence.required_item_id"
                    type="button"
                    @click="modalSequence.required_item_id = ''"
                    class="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                    title="Clear item requirement"
                  >
                    Clear
                  </button>
                </div>
                <select
                  v-model="modalSequence.required_item_id"
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
                    v-if="modalSequence.required_item_id && !availableItems.some(i => i.id === modalSequence.required_item_id)"
                    :value="modalSequence.required_item_id"
                    class="bg-slate-900 text-amber-300"
                  >
                    {{ modalSequence.required_item_id }} (Custom ID)
                  </option>
                </select>
                <span class="block text-[10px] text-slate-500">Protagonist acquires item X</span>
              </div>

              <!-- Scene Hard Rule (prot betritt Scene X) -->
              <div class="space-y-1.5 p-3 rounded-xl bg-slate-900/80 border border-white/5">
                <div class="flex items-center justify-between">
                  <span class="flex items-center gap-1.5 text-[11px] font-bold text-slate-300">
                    <MapPin class="w-3.5 h-3.5 text-sky-400" />
                    Enter Scene
                  </span>
                  <button
                    v-if="modalSequence.required_scene_id"
                    type="button"
                    @click="modalSequence.required_scene_id = ''"
                    class="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                    title="Clear scene requirement"
                  >
                    Clear
                  </button>
                </div>
                <select
                  v-model="modalSequence.required_scene_id"
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
                    v-if="modalSequence.required_scene_id && !availableScenes.some(s => s.id === modalSequence.required_scene_id)"
                    :value="modalSequence.required_scene_id"
                    class="bg-slate-900 text-amber-300"
                  >
                    {{ modalSequence.required_scene_id }} (Custom ID)
                  </option>
                </select>
                <span class="block text-[10px] text-slate-500">Protagonist enters Scene X</span>
              </div>

              <!-- NPC Defeat Hard Rule (prot besiegt NPC X) -->
              <div class="space-y-1.5 p-3 rounded-xl bg-slate-900/80 border border-white/5">
                <div class="flex items-center justify-between">
                  <span class="flex items-center gap-1.5 text-[11px] font-bold text-slate-300">
                    <Swords class="w-3.5 h-3.5 text-rose-400" />
                    Defeat NPC
                  </span>
                  <button
                    v-if="modalSequence.required_defeated_npc_id"
                    type="button"
                    @click="modalSequence.required_defeated_npc_id = ''"
                    class="text-[10px] text-slate-500 hover:text-rose-400 transition-colors"
                    title="Clear NPC requirement"
                  >
                    Clear
                  </button>
                </div>
                <select
                  v-model="modalSequence.required_defeated_npc_id"
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
                    v-if="modalSequence.required_defeated_npc_id && !availableNpcs.some(n => n.id === modalSequence.required_defeated_npc_id)"
                    :value="modalSequence.required_defeated_npc_id"
                    class="bg-slate-900 text-amber-300"
                  >
                    {{ modalSequence.required_defeated_npc_id }} (Custom ID)
                  </option>
                </select>
                <span class="block text-[10px] text-slate-500">Protagonist defeats NPC X</span>
              </div>
            </div>
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

        <!-- Fixed Footer -->
        <div class="shrink-0 flex items-center justify-end gap-3 pt-4 border-t border-white/5">
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
