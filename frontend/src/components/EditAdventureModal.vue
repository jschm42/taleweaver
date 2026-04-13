<script setup lang="ts">
/**
 * EditAdventureModal — Dedicated modal for editing adventure settings.
 * Includes a "Debug Panel" showing the raw JSON configuration.
 */
import { ref, watch, onMounted } from 'vue'

const props = defineProps<{
  open: boolean
  adventureId: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'updated'): void
}>()

const adventure = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const showDebug = ref(false)

const form = ref({
  title: '',
  context: '',
  strict_rules: true,
  heartbeat_enabled: false,
  heartbeat_interval: 60
})

const fetchAdventure = async () => {
  if (!props.adventureId) return
  isLoading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}`)
    if (res.ok) {
      const data = await res.json()
      adventure.value = data
      form.value = {
        title: data.title,
        context: data.context || '',
        strict_rules: data.strict_rules,
        heartbeat_enabled: data.heartbeat_enabled,
        heartbeat_interval: data.heartbeat_interval
      }
    } else {
      errorMsg.value = "Failed to load adventure configuration."
    }
  } catch (err) {
    errorMsg.value = "Network error loading adventure."
  } finally {
    isLoading.value = false
  }
}

const saveChanges = async () => {
  if (!props.adventureId) return
  isSaving.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    })
    if (res.ok) {
      emit('updated')
      emit('close')
    } else {
      errorMsg.value = "Failed to save changes."
    }
  } catch (err) {
    errorMsg.value = "Network error while saving."
  } finally {
    isSaving.value = false
  }
}

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    fetchAdventure()
    showDebug.value = false
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-md" @click="emit('close')" />

        <!-- Modal Content -->
        <div class="relative z-10 w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden animate-modal-in">
          
          <!-- Header -->
          <div class="px-8 py-6 border-b border-slate-800 flex justify-between items-center">
            <div>
              <h2 class="text-2xl font-bold text-white flex items-center gap-3">
                <i class="ra ra-gear-hammer text-emerald-500"></i>
                Adventure Settings
              </h2>
              <p class="text-xs text-slate-400 mt-1">Configure your chronicle and mechanical rules.</p>
            </div>
            <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="flex-grow overflow-y-auto p-8 custom-scrollbar">
            <div v-if="isLoading" class="flex justify-center py-12">
              <div class="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-emerald-500"></div>
            </div>

            <div v-else-if="errorMsg" class="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl">
              {{ errorMsg }}
            </div>

            <div v-else-if="adventure" class="space-y-6">
              <!-- Title -->
              <div>
                <label class="block text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">Chronicle Title</label>
                <input 
                  v-model="form.title"
                  type="text"
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none transition-all"
                />
              </div>

              <!-- Context -->
              <div>
                <label class="block text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">World Context / Idea</label>
                <textarea 
                  v-model="form.context"
                  rows="4"
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white focus:ring-2 focus:ring-emerald-500/50 outline-none transition-all resize-none"
                ></textarea>
              </div>

              <!-- Rules Toggle -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div 
                  class="p-4 rounded-xl border-2 cursor-pointer transition-all"
                  :class="form.strict_rules ? 'bg-emerald-500/5 border-emerald-500 text-white' : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'"
                  @click="form.strict_rules = !form.strict_rules"
                >
                  <div class="flex items-center gap-3 mb-1">
                    <i class="ra ra-scales text-lg"></i>
                    <span class="font-bold">Strict Rules</span>
                  </div>
                  <p class="text-[10px] leading-tight opacity-70">Enforces structured mechanics and character sheet impact via complexe LLM routing.</p>
                </div>

                <div 
                  class="p-4 rounded-xl border-2 cursor-pointer transition-all"
                  :class="form.heartbeat_enabled ? 'bg-cyan-500/5 border-cyan-500 text-white' : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'"
                  @click="form.heartbeat_enabled = !form.heartbeat_enabled"
                >
                  <div class="flex items-center gap-3 mb-1">
                    <i class="ra ra-heartbeat text-lg"></i>
                    <span class="font-bold">Heartbeat</span>
                  </div>
                  <p class="text-[10px] leading-tight opacity-70">Enables background time-based checks (damage/healing/status effects over time).</p>
                </div>
              </div>

              <!-- Debug Panel -->
              <div class="mt-8 border-t border-slate-800 pt-6">
                <button 
                  @click="showDebug = !showDebug"
                  class="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-emerald-400 transition-colors uppercase tracking-widest"
                >
                  <i class="ra ra-search"></i>
                  {{ showDebug ? 'Hide Debug Context' : 'Show Debug Context' }}
                </button>
                
                <div v-if="showDebug" class="mt-4 bg-black/50 border border-slate-800 rounded-xl p-4 overflow-x-auto">
                  <pre class="text-[10px] font-mono text-emerald-500/80 leading-relaxed">{{ JSON.stringify(adventure, null, 2) }}</pre>
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="p-8 border-t border-slate-800 bg-slate-900/50 flex justify-end gap-3">
            <button 
              @click="emit('close')"
              class="px-6 py-2 rounded-xl text-slate-400 hover:bg-white/5 transition-colors font-medium border border-transparent hover:border-slate-700"
            >
              Cancel
            </button>
            <button 
              @click="saveChanges"
              :disabled="isSaving || isLoading"
              class="px-8 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl shadow-lg transition-all flex items-center gap-2 disabled:opacity-50"
            >
              <span v-if="isSaving" class="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin"></span>
              {{ isSaving ? 'Saving...' : 'Save Settings' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.animate-modal-in {
  animation: modalIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes modalIn {
  from { opacity: 0; transform: translateY(10px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
.custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(16, 185, 129, 0.2); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(16, 185, 129, 0.4); }
</style>
