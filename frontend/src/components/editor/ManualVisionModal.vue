<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  show: boolean
  selectedVisual: { kind: string; id: string; label: string; description: string; hint: string } | null
  visualPrompt: string
  isSuggestingPrompt: boolean
  isRegenerating: boolean
  useAdvancedModel: boolean
  uploadLimits: any
  formatBytes: (bytes: number) => string
  fixNewlines: (text: string) => string
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'suggest'): void
  (e: 'regenerate'): void
  (e: 'cancelRegen'): void
  (e: 'update:visualPrompt', val: string): void
  (e: 'update:useAdvancedModel', val: boolean): void
}>()

const localPrompt = ref(props.visualPrompt)

watch(() => props.visualPrompt, (newVal) => {
  localPrompt.value = newVal
})

watch(localPrompt, (newVal) => {
  emit('update:visualPrompt', newVal)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show && selectedVisual" class="fixed inset-0 z-[250] flex items-center justify-center p-6 backdrop-blur-2xl bg-slate-950/70">
        <div class="modal-content w-full max-w-xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden">
          <div class="p-10 space-y-8">
            <div class="flex justify-between items-center">
              <div class="space-y-1">
                <h3 class="text-xs font-black text-cyan-500 uppercase tracking-widest">Manual Vision Weaver</h3>
                <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">Target: {{ selectedVisual.label }}</p>
              </div>
              <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>

            <div class="space-y-6">
              <div class="p-6 bg-black/40 rounded-3xl border border-white/5 space-y-4">
                <div class="flex items-start gap-4">
                  <i class="ra ra-crystal-ball text-2xl text-cyan-500/50"></i>
                  <div class="space-y-1">
                    <h4 class="text-xs font-black text-slate-500 uppercase">Current description</h4>
                    <p class="text-xs text-slate-400 leading-relaxed italic line-clamp-3 whitespace-pre-wrap">"{{ fixNewlines(selectedVisual.description) }}"</p>
                  </div>
                </div>
              </div>

              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Override Prompt</label>
                  <button 
                    @click="emit('suggest')" 
                    :disabled="isSuggestingPrompt || isRegenerating"
                    class="flex items-center gap-2 px-3 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-[10px] font-black uppercase tracking-widest transition-all disabled:opacity-50"
                  >
                    <i :class="['ra ra-crystal-wand', isSuggestingPrompt ? 'animate-spin' : '']"></i>
                    <span>{{ isSuggestingPrompt ? 'Suggesting...' : 'Suggest Prompt' }}</span>
                  </button>
                </div>
                <p class="text-xs text-amber-300/80 leading-relaxed">Upload hint: {{ selectedVisual.hint }} Max file size: {{ formatBytes(uploadLimits[selectedVisual.kind].maxBytes) }}.</p>
                <textarea 
                  v-model="localPrompt" 
                  rows="5" 
                  :disabled="isRegenerating || isSuggestingPrompt"
                  placeholder="Describe exactly what you want to see. This will ignore the current asset description..." 
                  class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500 outline-none transition-all leading-relaxed shadow-inner disabled:opacity-50"
                ></textarea>
              </div>

              <div class="flex items-center justify-between p-4 bg-white/5 border border-white/5 rounded-2xl">
                <div class="space-y-1">
                  <span class="text-xs font-black uppercase tracking-widest text-slate-200">High-Quality Weaver</span>
                  <p class="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Use Advanced Model for superior detail</p>
                </div>
                <button 
                  @click="!isRegenerating && !isSuggestingPrompt && emit('update:useAdvancedModel', !useAdvancedModel)"
                  :disabled="isRegenerating || isSuggestingPrompt"
                  :class="['w-12 h-6 rounded-full transition-all relative flex items-center px-1 disabled:opacity-50', useAdvancedModel ? 'bg-cyan-600' : 'bg-slate-800']"
                >
                  <div :class="['w-4 h-4 bg-white rounded-full shadow-lg transition-transform duration-300', useAdvancedModel ? 'translate-x-6' : 'translate-x-0']"></div>
                </button>
              </div>
            </div>

            <div class="flex justify-end gap-6 pt-4">
              <button @click="isRegenerating ? emit('cancelRegen') : emit('close')" class="px-8 py-3 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors">
                {{ isRegenerating ? 'Abort' : 'Discard' }}
              </button>
              <button @click="emit('regenerate')" :disabled="isRegenerating" class="px-10 py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-black uppercase text-xs tracking-widest rounded-xl shadow-lg shadow-cyan-900/20 disabled:opacity-50 flex items-center gap-3">
                <i v-if="isRegenerating" class="ra ra-cycle animate-spin"></i>
                <span>{{ isRegenerating ? 'Weaving...' : 'Generate Vision' }}</span>
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
