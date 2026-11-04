<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  show: boolean
  selectedVisual: { kind: string; id: string; label: string; description: string; hint: string; appearance?: string } | null
  visualPrompt: string
  isSuggestingPrompt: boolean
  isEnhancingPrompt?: boolean
  isRegenerating: boolean
  useAdvancedModel: boolean
  applyStyle?: boolean
  applyAppearance?: boolean
  configuredStyleName?: string
  uploadLimits: any
  formatBytes: (bytes: number) => string
  fixNewlines: (text: string) => string
}>(), {
  isEnhancingPrompt: false,
  applyStyle: true,
  applyAppearance: true,
  configuredStyleName: '',
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'suggest'): void
  (e: 'enhance'): void
  (e: 'regenerate'): void
  (e: 'cancelRegen'): void
  (e: 'update:visualPrompt', val: string): void
  (e: 'update:useAdvancedModel', val: boolean): void
  (e: 'update:applyStyle', val: boolean): void
  (e: 'update:applyAppearance', val: boolean): void
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
      <div v-if="show && selectedVisual" class="fixed inset-0 z-[250] flex items-center justify-center p-3 sm:p-5 backdrop-blur-2xl bg-slate-950/75">
        <div class="modal-content w-full max-w-lg max-h-[90vh] flex flex-col bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
          
          <!-- Header (pinned) -->
          <div class="px-5 py-3.5 border-b border-white/5 flex justify-between items-center flex-shrink-0 bg-slate-950/30">
            <div class="space-y-0.5">
              <h3 class="text-xs font-black text-cyan-400 uppercase tracking-widest">Manual Vision Weaver</h3>
              <p class="text-slate-400 text-[11px] uppercase font-bold tracking-tight">Target: <span class="text-slate-200">{{ selectedVisual.label }}</span></p>
            </div>
            <button 
              type="button"
              @click="emit('close')" 
              class="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
              aria-label="Close dialog"
            >
              <i class="ra ra-cancel text-lg"></i>
            </button>
          </div>

          <!-- Body (scrollable) -->
          <div class="p-5 space-y-3.5 overflow-y-auto flex-1 custom-scrollbar">
            <!-- Current Description & Appearance Keywords Card -->
            <div class="p-3.5 bg-black/40 rounded-xl border border-white/5 space-y-2.5">
              <div class="flex items-start gap-2.5">
                <i class="ra ra-crystal-ball text-base text-cyan-400/70 mt-0.5 flex-shrink-0"></i>
                <div class="space-y-0.5 flex-1 min-w-0">
                  <h4 class="text-[10px] font-black text-slate-500 uppercase tracking-wider">Current description</h4>
                  <p class="text-xs text-slate-300 leading-relaxed italic line-clamp-3 hover:line-clamp-none transition-all cursor-pointer whitespace-pre-wrap" title="Click to view full text">"{{ fixNewlines(selectedVisual.description) }}"</p>
                </div>
              </div>

              <div v-if="selectedVisual.kind === 'npc' || selectedVisual.kind === 'protagonist'" class="pt-2 border-t border-white/5 flex items-start gap-2.5">
                <i class="ra ra-eye text-sm text-purple-400/70 mt-0.5 flex-shrink-0"></i>
                <div class="space-y-1 flex-1 min-w-0">
                  <div class="flex items-center justify-between gap-2">
                    <h4 class="text-[10px] font-black text-slate-500 uppercase tracking-wider">Appearance Keywords</h4>
                    <span v-if="selectedVisual.appearance" class="text-[9px] font-mono text-purple-300 font-bold uppercase tracking-wider px-1.5 py-0.2 bg-purple-500/10 rounded border border-purple-500/20">Configured</span>
                    <span v-else class="text-[9px] font-mono text-slate-500 uppercase tracking-wider">Not set</span>
                  </div>
                  <p v-if="selectedVisual.appearance" class="text-xs text-purple-200 font-mono leading-relaxed bg-black/50 px-3 py-1.5 rounded-lg border border-purple-500/20 break-words">
                    {{ selectedVisual.appearance }}
                  </p>
                  <p v-else class="text-[11px] text-slate-500 italic">
                    No appearance keywords defined for this {{ selectedVisual.kind === 'protagonist' ? 'protagonist' : 'NPC' }}.
                  </p>
                </div>
              </div>
            </div>

            <!-- Override Prompt -->
            <div class="space-y-1.5">
              <div class="flex justify-between items-center gap-2">
                <label class="block text-[10px] font-black text-slate-400 uppercase tracking-widest">Override Prompt</label>
                <div class="flex items-center gap-1.5">
                  <button 
                    v-if="localPrompt.trim().length > 0"
                    type="button"
                    @click="emit('enhance')" 
                    :disabled="isEnhancingPrompt || isSuggestingPrompt || isRegenerating"
                    class="flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20 hover:bg-cyan-500/20 text-cyan-400 text-[10px] font-bold uppercase tracking-wider transition-all disabled:opacity-50"
                    title="Optimize prompt with AI"
                  >
                    <i :class="['ra ra-lightning-bolt', isEnhancingPrompt ? 'animate-spin' : '']"></i>
                    <span>{{ isEnhancingPrompt ? 'Enhancing...' : 'Enhance Prompt' }}</span>
                  </button>
                  <button 
                    type="button"
                    @click="emit('suggest')" 
                    :disabled="isSuggestingPrompt || isEnhancingPrompt || isRegenerating"
                    class="flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 text-[10px] font-bold uppercase tracking-wider transition-all disabled:opacity-50"
                    title="Generate suggestion from description"
                  >
                    <i :class="['ra ra-crystal-wand', isSuggestingPrompt ? 'animate-spin' : '']"></i>
                    <span>{{ isSuggestingPrompt ? 'Suggesting...' : 'Suggest Prompt' }}</span>
                  </button>
                </div>
              </div>
              <p class="text-[11px] text-amber-300/80 leading-tight">Upload hint: {{ selectedVisual.hint }} Max file size: {{ formatBytes(uploadLimits[selectedVisual.kind].maxBytes) }}.</p>
              <textarea 
                v-model="localPrompt" 
                rows="3" 
                :disabled="isRegenerating || isSuggestingPrompt || isEnhancingPrompt"
                placeholder="Describe exactly what you want to see. This will ignore the current asset description..." 
                class="w-full bg-black/40 border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder:text-slate-500 focus:border-cyan-500 outline-none transition-all leading-relaxed shadow-inner disabled:opacity-50 resize-y min-h-[64px]"
              ></textarea>
            </div>

            <!-- Toggles List (compact grouped card) -->
            <div class="bg-black/30 border border-white/5 rounded-xl divide-y divide-white/5 overflow-hidden">
              <!-- Apply Appearance Keywords (NPC & Protagonist only) -->
              <div 
                v-if="selectedVisual.kind === 'npc' || selectedVisual.kind === 'protagonist'"
                class="flex items-center justify-between px-3.5 py-2 hover:bg-white/[0.02] transition-colors"
                :class="{ 'opacity-50': !selectedVisual.appearance }"
              >
                <div class="space-y-0.5 pr-2 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-slate-200">Apply Appearance Keywords</span>
                    <span v-if="!selectedVisual.appearance" class="text-[9px] font-mono text-slate-500 uppercase px-1 py-0.2 rounded bg-slate-800">Unset</span>
                  </div>
                  <p class="text-[10px] text-slate-400 truncate">
                    <template v-if="!selectedVisual.appearance">No appearance keywords defined</template>
                    <template v-else-if="applyAppearance">Automatically include visual keywords in generation</template>
                    <template v-else>Generate vision without appearance keywords</template>
                  </p>
                </div>
                <button 
                  type="button"
                  @click="!isRegenerating && !isSuggestingPrompt && !isEnhancingPrompt && Boolean(selectedVisual.appearance) && emit('update:applyAppearance', !applyAppearance)"
                  :disabled="isRegenerating || isSuggestingPrompt || isEnhancingPrompt || !selectedVisual.appearance"
                  :class="['w-9 h-5 rounded-full transition-all relative flex items-center px-0.5 disabled:opacity-50 flex-shrink-0', applyAppearance && selectedVisual.appearance ? 'bg-purple-600' : 'bg-slate-800']"
                  :aria-label="applyAppearance ? 'Disable appearance keywords' : 'Enable appearance keywords'"
                >
                  <div :class="['w-4 h-4 bg-white rounded-full shadow transition-transform duration-200', applyAppearance && selectedVisual.appearance ? 'translate-x-4' : 'translate-x-0']"></div>
                </button>
              </div>

              <!-- Apply Adventure Style -->
              <div class="flex items-center justify-between px-3.5 py-2 hover:bg-white/[0.02] transition-colors">
                <div class="space-y-0.5 pr-2 min-w-0">
                  <span class="text-xs font-bold text-slate-200">Apply Adventure Style</span>
                  <p class="text-[10px] text-slate-400 truncate">
                    {{ applyStyle
                        ? (configuredStyleName ? `Apply '${configuredStyleName}' style to prompt` : 'Apply adventure visual style to prompt')
                        : 'Send prompt without adventure style to T2I model' }}
                  </p>
                </div>
                <button 
                  type="button"
                  @click="!isRegenerating && !isSuggestingPrompt && emit('update:applyStyle', !applyStyle)"
                  :disabled="isRegenerating || isSuggestingPrompt || isEnhancingPrompt"
                  :class="['w-9 h-5 rounded-full transition-all relative flex items-center px-0.5 disabled:opacity-50 flex-shrink-0', applyStyle ? 'bg-cyan-600' : 'bg-slate-800']"
                  :aria-label="applyStyle ? 'Disable adventure style' : 'Enable adventure style'"
                >
                  <div :class="['w-4 h-4 bg-white rounded-full shadow transition-transform duration-200', applyStyle ? 'translate-x-4' : 'translate-x-0']"></div>
                </button>
              </div>

              <!-- High-Quality Weaver -->
              <div class="flex items-center justify-between px-3.5 py-2 hover:bg-white/[0.02] transition-colors">
                <div class="space-y-0.5 pr-2 min-w-0">
                  <span class="text-xs font-bold text-slate-200">High-Quality Weaver</span>
                  <p class="text-[10px] text-slate-400 truncate">Use advanced model for superior detail</p>
                </div>
                <button 
                  type="button"
                  @click="!isRegenerating && !isSuggestingPrompt && emit('update:useAdvancedModel', !useAdvancedModel)"
                  :disabled="isRegenerating || isSuggestingPrompt || isEnhancingPrompt"
                  :class="['w-9 h-5 rounded-full transition-all relative flex items-center px-0.5 disabled:opacity-50 flex-shrink-0', useAdvancedModel ? 'bg-cyan-600' : 'bg-slate-800']"
                  :aria-label="useAdvancedModel ? 'Disable advanced model' : 'Enable advanced model'"
                >
                  <div :class="['w-4 h-4 bg-white rounded-full shadow transition-transform duration-200', useAdvancedModel ? 'translate-x-4' : 'translate-x-0']"></div>
                </button>
              </div>
            </div>
          </div>

          <!-- Footer (pinned) -->
          <div class="px-5 py-3 bg-slate-950/40 border-t border-white/5 flex justify-end items-center gap-3 flex-shrink-0">
            <button 
              type="button"
              @click="isRegenerating ? emit('cancelRegen') : emit('close')" 
              class="px-4 py-2 text-slate-400 hover:text-white font-bold uppercase text-xs tracking-wider transition-colors"
            >
              {{ isRegenerating ? 'Abort' : 'Discard' }}
            </button>
            <button 
              type="button"
              @click="emit('regenerate')" 
              :disabled="isRegenerating" 
              class="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold uppercase text-xs tracking-wider rounded-xl shadow-lg shadow-cyan-900/30 disabled:opacity-50 flex items-center gap-2 transition-all"
            >
              <i v-if="isRegenerating" class="ra ra-cycle animate-spin"></i>
              <span>{{ isRegenerating ? 'Weaving...' : 'Generate Vision' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }

.modal-enter-active .modal-content { animation: modalScaleIn 0.35s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active .modal-content { transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1); transform: scale(0.97); }

@keyframes modalScaleIn {
  from { opacity: 0; transform: scale(0.95) translateY(20px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 9999px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 9999px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}
</style>
