<script setup lang="ts">
import { onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  open: boolean
  data: any
}>()

const emit = defineEmits<{
  close: []
}>()

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) {
    emit('close')
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[100] bg-slate-950/95 backdrop-blur-xl flex items-center justify-center p-4 md:p-10"
        @click.self="emit('close')"
      >
        <div class="w-full max-w-5xl h-full flex flex-col bg-slate-900 border border-slate-800 rounded-3xl shadow-[0_0_100px_rgba(0,0,0,0.8)] overflow-hidden animate-modal-in">
          <div class="flex items-center justify-between px-8 py-6 border-b border-slate-800 shrink-0">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-500">
                <i class="ra ra-code"></i>
              </div>
              <h3 class="text-xl font-black text-white uppercase tracking-tighter">Debug Inspector</h3>
            </div>
            <button
              class="p-2.5 rounded-full bg-slate-800/80 hover:bg-red-600 text-slate-400 hover:text-white transition-all border border-slate-700/50"
              @click="emit('close')"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
              </svg>
            </button>
          </div>

          <div class="flex-grow overflow-auto p-8 custom-scrollbar bg-slate-950/30">
            <pre class="text-[11px] font-mono text-cyan-400/80 leading-relaxed">{{ JSON.stringify(data, null, 2) }}</pre>
          </div>
          
          <div class="px-8 py-4 bg-slate-900/50 border-t border-slate-800 text-[10px] font-bold text-slate-500 uppercase tracking-widest flex justify-between items-center shrink-0">
            <div class="flex items-center gap-4">
              <span>Game Session State</span>
              <span class="text-slate-700">|</span>
              <span class="text-cyan-600/60">{{ data?.sheet?.adventure_id || 'No Active Adventure' }}</span>
            </div>
            <span class="tabular-nums opacity-40">{{ new Date().toLocaleString() }}</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@keyframes modalIn {
  from { opacity: 0; transform: scale(0.98) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
.animate-modal-in { animation: modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1); }

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
.ra { font-family: 'rpgawesome' !important; }
</style>
