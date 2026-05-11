<script setup lang="ts">
defineProps<{
  show: boolean
  adventure: any
  debugData: any
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="fixed inset-0 z-[600] flex items-center justify-center p-12 backdrop-blur-3xl bg-slate-950/90">
        <div class="modal-content w-full max-w-6xl h-[80vh] bg-slate-900 border border-white/10 rounded-[3rem] shadow-2xl overflow-hidden flex flex-col">
          <div class="p-8 border-b border-white/5 flex justify-between items-center bg-slate-900/50">
            <div class="flex items-center gap-4">
              <div class="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20">
                <i class="ra ra-crystal-ball text-cyan-400"></i>
              </div>
              <div>
                <h3 class="text-lg font-black text-white uppercase tracking-widest">Chronicle Debug Inspector</h3>
                <p class="text-xs text-slate-500 font-bold uppercase tracking-tighter">Raw Adventure Manifest & Entities</p>
              </div>
            </div>
            <button @click="emit('close')" class="p-3 rounded-full hover:bg-white/5 text-slate-500 hover:text-white transition-all">
              <i class="ra ra-cancel text-xl"></i>
            </button>
          </div>
          
          <div class="flex-grow overflow-hidden flex">
            <div class="flex-grow p-8 overflow-auto font-mono text-xs leading-relaxed">
              <div class="space-y-8">
                <section v-if="adventure" class="space-y-4">
                  <h4 class="text-xs font-black text-emerald-500 uppercase tracking-widest border-l-2 border-emerald-500 pl-4">Adventure Core</h4>
                  <pre class="bg-black/40 p-6 rounded-2xl border border-white/5 text-emerald-300/80 whitespace-pre-wrap break-all">{{ JSON.stringify(adventure, null, 2) }}</pre>
                </section>
                <section v-if="debugData" class="space-y-4">
                  <h4 class="text-xs font-black text-cyan-500 uppercase tracking-widest border-l-2 border-cyan-500 pl-4">Asset Matrix (DebugData)</h4>
                  <pre class="bg-black/40 p-6 rounded-2xl border border-white/5 text-cyan-300/80 whitespace-pre-wrap break-all">{{ JSON.stringify(debugData, null, 2) }}</pre>
                </section>
              </div>
            </div>
          </div>

          <div class="p-6 bg-black/20 border-t border-white/5 flex justify-end gap-4">
            <button @click="emit('close')" class="px-10 py-3 bg-slate-800 hover:bg-slate-700 text-white font-black uppercase text-xs tracking-widest rounded-xl transition-all">Close Inspector</button>
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
