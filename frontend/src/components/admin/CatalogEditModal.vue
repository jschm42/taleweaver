<script setup lang="ts">
import { ref, watch } from 'vue'
import type { CatalogTile } from '@/types'

const props = withDefaults(defineProps<{
  isOpen: boolean
  isEditingExisting: boolean
  item: CatalogTile
  index: number | null
  type: 'styles' | 'tones'
  isGenerating?: boolean
  isSubmitting?: boolean
}>(), {
  isGenerating: false,
  isSubmitting: false,
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', item: CatalogTile): void
  (e: 'generate', payload: { type: 'styles' | 'tones', item: CatalogTile, index: number | null }): void
  (e: 'upload', payload: { event: Event, type: 'styles' | 'tones', item: CatalogTile, index: number | null }): void
}>()

const editingItem = ref<CatalogTile>({ ...props.item })

watch(() => props.item, (newItem) => {
  editingItem.value = JSON.parse(JSON.stringify(newItem))
}, { deep: true })

const triggerFileUpload = () => {
  const input = document.getElementById('modal-upload') as HTMLInputElement
  input?.click()
}

const handleSave = () => {
  emit('save', editingItem.value)
}

const handleGenerate = () => {
  emit('generate', { type: props.type, item: editingItem.value, index: props.index })
}

const handleUpload = (event: Event) => {
  emit('upload', { event, type: props.type, item: editingItem.value, index: props.index })
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="emit('close')"></div>
      <div class="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl p-8 animate-fade-in">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-2xl font-bold text-white flex items-center gap-3 capitalize">
            <i :class="type === 'styles' ? 'ra ra-paint-brush text-amber-500' : 'ra ra-scroll text-indigo-500'"></i>
            {{ isEditingExisting ? 'Edit' : 'Add' }} {{ type.replace('s', '') }}
          </h2>
          <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
            <i class="ra ra-cancel"></i>
          </button>
        </div>

        <!-- Image Preview & Actions in Modal -->
        <div class="mb-8 flex items-center gap-6 bg-slate-950/50 p-4 rounded-2xl border border-slate-800">
          <div class="w-24 h-24 rounded-xl overflow-hidden bg-slate-900 border border-slate-800 flex-shrink-0 relative group">
            <img v-if="editingItem.image_url" :src="editingItem.image_url" class="w-full h-full object-cover" />
            <div v-else class="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-900 to-slate-950 text-slate-800">
              <svg v-if="type === 'styles'" class="w-10 h-10 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z" /><path d="M12 8v4l3 3" /><path d="M9 3v2" /><path d="M5 5L6.5 6.5" /><path d="M3 9h2" /><path d="M3 15h2" /><path d="M5 19l1.5-1.5" /><path d="M9 21v-2" /><path d="M15 21v-2" /><path d="M19 19l-1.5-1.5" /><path d="M21 15h-2" /><path d="M21 9h-2" /><path d="M19 5L17.5 6.5" /><path d="M15 3v2" /></svg>
              <svg v-else class="w-10 h-10 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
            </div>
            <div v-if="isGenerating" class="absolute inset-0 bg-black/60 flex items-center justify-center">
              <div class="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-emerald-500"></div>
            </div>
          </div>
          <div class="flex flex-col gap-2 flex-grow">
            <button 
              @click="handleGenerate" 
              :disabled="!editingItem.name || isGenerating"
              class="flex items-center justify-center gap-2 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition-all disabled:opacity-50"
            >
              <i class="ra ra-cycle" :class="{'animate-spin': isGenerating}"></i>
              AI Generate Image
            </button>
            <button 
              @click="triggerFileUpload"
              class="flex items-center justify-center gap-2 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold rounded-lg transition-all"
            >
              <i class="ra ra-camera"></i>
              Upload Manually
            </button>
            <input id="modal-upload" type="file" class="hidden" accept="image/*" @change="handleUpload" />
          </div>
        </div>

        <div class="space-y-6">
          <div>
            <div class="flex justify-between items-center mb-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-widest">Display Name</label>
              <span class="text-xxs font-mono text-slate-600">{{ (editingItem.name || '').length }} / 30</span>
            </div>
            <input v-model="editingItem.name" type="text" maxlength="30" placeholder="e.g. Dark Fantasy" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none" />
          </div>
          <div>
            <div class="flex justify-between items-center mb-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-widest">Description</label>
              <span class="text-xxs font-mono text-slate-600">{{ (editingItem.description || '').length }} / 200</span>
            </div>
            <textarea v-model="editingItem.description" rows="2" maxlength="200" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none resize-y"></textarea>
          </div>
          <div>
            <div class="flex justify-between items-center mb-2">
              <label class="block text-xs font-bold text-slate-500 uppercase tracking-widest">System Instruction / Prompt Prefix</label>
              <span class="text-xxs font-mono text-slate-600">{{ (editingItem.instruction || '').length }} / 500</span>
            </div>
            <textarea v-model="editingItem.instruction" rows="3" maxlength="500" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none resize-y font-mono text-xs"></textarea>
          </div>
          
          <button @click="handleSave" class="w-full py-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all shadow-lg">
            Save Entry
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.animate-fade-in {
  animation: fadeIn 0.4s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
