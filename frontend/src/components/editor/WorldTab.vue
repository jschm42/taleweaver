<script setup lang="ts">
import PlotTab from '@/components/editor/PlotTab.vue'
import { Save, X } from 'lucide-vue-next'

const props = defineProps<{
  form: any
  adventure: any
  debugData: any
  editingField: string | null
  tempValue: string
  isSaving: boolean
  isBatchGenerating: Record<string, boolean>
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  fixNewlines: (text: string) => string
}>()

const emit = defineEmits<{
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'open-text-edit', ...args: any[]): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'start-edit', field: string, value: string): void
  (e: 'save-field'): void
  (e: 'cancel-edit'): void
  (e: 'update:tempValue', val: string): void
  (e: 'update:mode', val: 'rpg' | 'story' | 'chat'): void
  (e: 'save-changes'): void
  (e: 'update:pacing', val: number): void
}>()

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return imagePath
}

function getCoverNarrativeContext() {
  if (!props.debugData) return ''
  return props.debugData.adventure?.plot || props.debugData.adventure?.original_prompt || ''
}

function handlePacingInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:pacing', parseInt(target.value))
}
</script>

<template>
  <div class="space-y-8 animate-page-in">
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Chronicle Title</label>
        <div v-if="editingField === 'title'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" class="flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all" />
          <button @click="emit('save-field')" :disabled="isSaving" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'title', form.title)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span class="text-sm font-bold text-white">{{ form.title }}</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>

      <div class="space-y-2">
        <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Version</label>
        <div v-if="editingField === 'version'" class="flex gap-2 animate-fade-in">
          <input :value="tempValue" @input="emit('update:tempValue', ($event.target as HTMLInputElement).value)" @keyup.enter="emit('save-field')" @keyup.esc="emit('cancel-edit')" type="text" maxlength="15" placeholder="e.g. 1.0.0" class="flex-grow bg-black/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all" />
          <button @click="emit('save-field')" :disabled="isSaving" class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg">
            <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
            <Save v-else class="w-4 h-4" />
          </button>
          <button @click="emit('cancel-edit')" class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-else @click="emit('start-edit', 'version', form.version)" class="group cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-2.5 transition-all duration-300 shadow-inner flex justify-between items-center">
          <span v-if="form.version" class="text-xs font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 uppercase tracking-widest">v{{ form.version }}</span>
          <span v-else class="text-xs italic text-slate-600 uppercase tracking-widest">No version set</span>
          <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity"></i>
        </div>
      </div>

      <div class="space-y-2">
        <div class="flex justify-between items-center">
          <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">In-Game Pacing ({{ form.time_per_turn }}m)</label>
          <div v-if="form.time_per_turn !== adventure?.time_per_turn" class="flex gap-2 animate-fade-in">
            <button @click="emit('update:pacing', adventure.time_per_turn)" class="text-xs font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
            <button @click="emit('save-changes')" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
          </div>
        </div>
        <input :value="form.time_per_turn" @input="handlePacingInput" type="range" min="1" max="60" class="w-full accent-emerald-500 h-2 bg-black/40 rounded-lg appearance-none cursor-pointer mt-3" />
      </div>
    </div>

    <section v-if="debugData?.adventure" class="space-y-4 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">World Essence</h3>
        <button @click="emit('quick-regen', 'cover', debugData.adventure.id)" :disabled="isBatchGenerating['cover']" class="px-4 py-2 rounded-xl bg-white/5 hover:bg-emerald-500/10 border border-white/5 text-xs font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-2 transition-all">
          <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['cover'] }"></i>
          Regenerate Cover
        </button>
      </div>
      <div class="relative group aspect-[3/2] bg-slate-900 border border-white/5 rounded-[2rem] overflow-hidden shadow-2xl max-w-2xl mx-auto">
        <img v-if="debugData.adventure.image_url" :src="buildVisualImageUrl(debugData.adventure.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-1000" />
        <div v-if="isQuickGenerating['cover_' + debugData.adventure.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
          <div class="flex flex-col items-center gap-2">
            <i class="ra ra-cycle animate-spin text-3xl text-emerald-500"></i>
            <span class="text-xs font-black text-emerald-500 uppercase tracking-widest">Reweaving Essence...</span>
          </div>
        </div>
        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent"></div>
        <div class="absolute inset-x-0 bottom-0 p-6">
          <div class="flex justify-between items-end gap-12">
            <div class="space-y-2 max-w-3xl">
              <h4 class="text-xl font-black text-white tracking-tight">{{ debugData.adventure.title }}</h4>
              <div class="flex items-center gap-3">
                <p v-if="debugData.adventure.teaser" class="text-xs font-bold text-emerald-500/80 uppercase tracking-widest">{{ debugData.adventure.teaser }}</p>
                <p v-else class="text-xs font-bold text-slate-500/40 uppercase tracking-widest italic">No teaser set...</p>
                <button @click="emit('open-text-edit', 'cover', debugData.adventure.id, debugData.adventure.title, getCoverNarrativeContext(), debugData.adventure.teaser)" class="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-emerald-400 transition-all" title="Edit Teaser & Metadata">
                  <i class="ra ra-quill-ink text-xs"></i>
                </button>
              </div>
              <p class="text-sm text-slate-400 leading-relaxed line-clamp-1">{{ getCoverNarrativeContext() }}</p>
            </div>
            <div class="relative shrink-0">
              <button @click="emit('toggle-menu', debugData.adventure.id, $event)" class="w-10 h-10 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                <div class="flex flex-col gap-0.5">
                  <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                  <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                  <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                </div>
              </button>
              <div v-if="activeMenuId === debugData.adventure.id" class="absolute right-0 bottom-full mb-3 w-56 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-2 z-50 animate-fade-in ring-1 ring-white/10">
                <button @click="emit('quick-regen', 'cover', debugData.adventure.id)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-emerald-600 hover:text-white transition-all uppercase tracking-widest">Quick Regenerate</button>
                <button @click="emit('open-regen-dialog', 'cover', debugData.adventure.id, debugData.adventure.title)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-cyan-600 hover:text-white transition-all uppercase tracking-widest">Regenerate (Prompt)</button>
                <button @click="emit('open-upload-picker', 'cover', debugData.adventure.id, debugData.adventure.title)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-amber-600 hover:text-white transition-all uppercase tracking-widest">Upload Custom Cover</button>
                <button v-if="debugData.adventure.image_url" @click="emit('download-asset', debugData.adventure.image_url, `${debugData.adventure.title || 'adventure'}_cover`)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-violet-600 hover:text-white transition-all uppercase tracking-widest">Download Cover</button>
                <button @click="emit('open-text-edit', 'cover', debugData.adventure.id, debugData.adventure.title, getCoverNarrativeContext(), debugData.adventure.teaser)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-blue-600 hover:text-white transition-all uppercase tracking-widest">Edit Essence Details</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <PlotTab
      :form="form"
      :adventure="adventure"
      :editing-field="editingField"
      :temp-value="tempValue"
      :is-saving="isSaving"
      :fix-newlines="fixNewlines"
      @update:temp-value="emit('update:tempValue', $event)"
      @update:mode="emit('update:mode', $event)"
      @start-edit="(field, value) => emit('start-edit', field, value)"
      @save-field="emit('save-field')"
      @cancel-edit="emit('cancel-edit')"
      @save-changes="emit('save-changes')"
    />
  </div>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
.animate-fade-in { animation: fadeIn 0.3s ease-out forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
