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
const debugData = ref<any>(null)

const form = ref({
  title: '',
  context: '',
  strict_rules: true,
  time_per_turn: 5
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
        time_per_turn: data.time_per_turn || 5
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

const fetchDebugInfo = async () => {
  if (!props.adventureId) return
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/debug`)
    if (res.ok) {
      debugData.value = await res.json()
    }
  } catch (err) {
    console.error("Failed to fetch debug info:", err)
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

const resetAdventure = async () => {
  if (!props.adventureId) return
  if (!confirm("Are you sure? This will wipe ALL current progress and restore the world to its original state.")) return
  
  isSaving.value = true
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/reset`, {
      method: 'POST'
    })
    if (res.ok) {
      await fetchAdventure()
      await fetchDebugInfo()
      emit('updated')
      alert("World has been reset to the golden manifest.")
    } else {
      errorMsg.value = "Failed to reset adventure."
    }
  } catch (err) {
    errorMsg.value = "Network error during reset."
  } finally {
    isSaving.value = false
  }
}

const exportBlueprint = async () => {
  if (!props.adventureId) return
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/export/manifest`)
    if (res.ok) {
      const data = await res.json()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `blueprint_${adventure.value.title.replace(/\s+/g, '_')}.json`
      a.click()
      URL.revokeObjectURL(url)
    }
  } catch (err) {
    console.error("Blueprint export failed", err)
  }
}

const exportSession = async () => {
  if (!props.adventureId) return
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/export/session`)
    if (res.ok) {
      const data = await res.json()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `session_${adventure.value.title.replace(/\s+/g, '_')}.json`
      a.click()
      URL.revokeObjectURL(url)
    }
  } catch (err) {
    console.error("Session backup failed", err)
  }
}

const importAdventure = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  
  const file = target.files[0]
  try {
    const text = await file.text()
    const payload = JSON.parse(text)
    
    isSaving.value = true
    const res = await fetch('http://localhost:8000/api/adventures/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    
    if (res.ok) {
      alert("Adventure imported successfully!")
      emit('updated')
      emit('close')
    } else {
      alert("Failed to import adventure.")
    }
  } catch (err) {
    alert("Error reading file.")
  } finally {
    isSaving.value = false
    target.value = ''
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
            <div class="flex items-center gap-3">
              <button 
                @click="$refs.advImportInput.click()"
                class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[10px] font-bold uppercase tracking-widest transition-all border border-slate-700 flex items-center gap-2"
              >
                <i class="ra ra-save"></i>
                Import
              </button>
              <input type="file" ref="advImportInput" class="hidden" accept=".json" @change="importAdventure" />
              
              <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors p-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
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
              <div class="grid grid-cols-1 gap-4">
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
              </div>

              <!-- Time Pacing -->
              <div class="p-6 bg-slate-950 border border-slate-800 rounded-2xl">
                <div class="flex items-center gap-3 mb-4">
                  <div class="p-2 bg-emerald-500/10 rounded-lg text-emerald-500">
                    <i class="ra ra-hourglass text-xl"></i>
                  </div>
                  <div>
                    <h3 class="text-sm font-bold text-white uppercase tracking-wider">Time Pacing</h3>
                    <p class="text-[10px] text-slate-500">How many minutes pass per action?</p>
                  </div>
                </div>
                
                <div class="flex items-center gap-6">
                  <input 
                    type="range" 
                    v-model.number="form.time_per_turn" 
                    min="1" 
                    max="60" 
                    step="1"
                    class="flex-grow accent-emerald-500 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
                  />
                  <div class="w-20 text-center">
                    <span class="text-xl font-bold text-emerald-500">{{ form.time_per_turn }}</span>
                    <span class="text-[10px] text-slate-500 block uppercase pt-0.5">Minutes</span>
                  </div>
                </div>
              </div>

              <!-- Export Options -->
              <div class="grid grid-cols-2 gap-4 border-t border-slate-800 pt-6">
                <div 
                  @click="exportBlueprint"
                  class="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-emerald-500/50 cursor-pointer transition-all group"
                >
                  <div class="flex items-center gap-2 mb-1 text-emerald-400">
                    <i class="ra ra-scroll-unfurled"></i>
                    <span class="text-xs font-bold uppercase tracking-widest">Blueprint</span>
                  </div>
                  <p class="text-[9px] text-slate-500">Export world manifest for fresh starts.</p>
                </div>
                
                <div 
                  @click="exportSession"
                  class="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-cyan-500/50 cursor-pointer transition-all group"
                >
                  <div class="flex items-center gap-2 mb-1 text-cyan-400">
                    <i class="ra ra-save"></i>
                    <span class="text-xs font-bold uppercase tracking-widest">Session</span>
                  </div>
                  <p class="text-[9px] text-slate-500">Backup full world state & chat history.</p>
                </div>
              </div>

              <!-- Debug Panel -->
              <div class="mt-8 border-t border-slate-800 pt-6">
                <button 
                  @click="() => { showDebug = !showDebug; if(showDebug) fetchDebugInfo(); }"
                  class="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-emerald-400 transition-colors uppercase tracking-widest"
                >
                  <i class="ra ra-search"></i>
                  {{ showDebug ? 'Hide Debug Context' : 'Show Debug Context' }}
                </button>
                
                <div v-if="showDebug" class="mt-4 space-y-4">
                  <div v-if="!debugData" class="flex items-center gap-2 text-slate-400 text-xs py-4">
                    <span class="w-4 h-4 border-2 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin"></span>
                    Fetching detailed manifest...
                  </div>
                  
                  <div v-else class="space-y-4">
                    <!-- Basic Config -->
                    <div class="bg-black/50 border border-slate-800 rounded-xl p-4">
                      <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Adventure Configuration</h4>
                      <pre class="text-[10px] font-mono text-emerald-500/80 leading-relaxed">{{ JSON.stringify(debugData.adventure, null, 2) }}</pre>
                    </div>

                    <!-- World Scenes -->
                    <div class="bg-black/50 border border-slate-800 rounded-xl p-4">
                      <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Pre-generated Scenes ({{ debugData.scenes.length }})</h4>
                      <div class="grid grid-cols-1 gap-2">
                        <div v-for="scene in debugData.scenes" :key="scene.id" class="p-2 border border-slate-800 rounded bg-slate-900/50">
                          <div class="text-[10px] font-bold text-emerald-400">{{ scene.label }}</div>
                          <div class="text-[9px] text-slate-500 font-mono">{{ scene.id }}</div>
                        </div>
                      </div>
                    </div>

                    <!-- NPCs & Items -->
                    <div class="grid grid-cols-2 gap-4">
                      <div class="bg-black/50 border border-slate-800 rounded-xl p-4">
                          <div v-for="npc in debugData.npcs" :key="npc.id" class="text-[9px] text-slate-400 flex flex-col gap-2 p-2 bg-slate-900 border border-slate-700/50 rounded-lg">
                            <div class="flex items-center gap-2">
                              <span class="w-1.5 h-1.5 rounded-full bg-cyan-500"></span>
                              <span class="font-bold underline">{{ npc.name }}</span> ({{ npc.current_scene_id }})
                            </div>
                            <img v-if="npc.image_url" :src="npc.image_url" class="w-full h-24 object-cover rounded-md border border-slate-700 shadow-inner" />
                            <div v-if="npc.spatial_position" class="pl-1 text-slate-500 italic">{{ npc.spatial_position }}</div>
                          </div>
                        </div>
                      </div>
                      <div class="bg-black/50 border border-slate-800 rounded-xl p-4">
                        <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Objects ({{ debugData.objects.length }})</h4>
                        <div class="space-y-2">
                          <div v-for="obj in debugData.objects" :key="obj.id" class="text-[9px] text-slate-400 flex flex-col gap-2 p-2 bg-slate-900 border border-slate-700/50 rounded-lg">
                            <div class="flex items-center gap-2">
                              <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                              <span class="font-bold underline">{{ obj.name }}</span> ({{ obj.current_scene_id }})
                            </div>
                            <img v-if="obj.image_url" :src="obj.image_url" class="w-full h-24 object-cover rounded-md border border-slate-700 shadow-inner" />
                            <div v-if="obj.spatial_position" class="pl-1 text-slate-500 italic">{{ obj.spatial_position }}</div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- Exits -->
                    <div class="bg-black/50 border border-slate-800 rounded-xl p-4">
                      <h4 class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">World Map Exits ({{ debugData.exits.length }})</h4>
                      <div class="space-y-1">
                        <div v-for="ex in debugData.exits" :key="ex.id" class="text-[9px] text-slate-400 flex justify-between">
                          <span>{{ ex.from_scene_id }} → {{ ex.to_scene_id }}</span>
                          <span :class="ex.is_locked ? 'text-red-500' : 'text-emerald-500'">{{ ex.is_locked ? '[LOCKED]' : '[OPEN]' }}</span>
                        </div>
                      </div>
                    </div>

                    <!-- Reset Area -->
                    <div class="mt-8 pt-6 border-t border-red-500/20">
                       <h4 class="text-[10px] font-bold text-red-500 uppercase tracking-widest mb-3">Danger Zone</h4>
                       <button 
                        @click="resetAdventure"
                        :disabled="isSaving"
                        class="px-4 py-2 border border-red-500 text-red-500 hover:bg-red-500 hover:text-white transition-all rounded-lg text-xs font-bold uppercase tracking-widest flex items-center gap-2"
                       >
                        <i class="ra ra-recycle"></i>
                        Reset Adventure to Golden Manifest
                       </button>
                    </div>
                  </div>
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
