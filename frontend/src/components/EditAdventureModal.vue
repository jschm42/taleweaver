<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  open: boolean
  adventureId: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'updated'): void
}>()

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const showDebug = ref(false)
const activeTab = ref<'settings' | 'visuals' | 'advanced'>('settings')

const form = ref({
  title: '',
  context: '',
  strict_rules: true,
  time_per_turn: 5,
})

async function fetchAdventure() {
  if (!props.adventureId) {
    return
  }
  isLoading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}`)
    if (!res.ok) {
      throw new Error('Failed to load adventure configuration.')
    }
    const data = await res.json()
    adventure.value = data
    form.value.title = data.title
    form.value.context = data.context || ''
    form.value.strict_rules = data.strict_rules
    form.value.time_per_turn = data.time_per_turn || 5
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error loading adventure.'
  } finally {
    isLoading.value = false
  }
}

async function fetchDebugInfo() {
  if (!props.adventureId) {
    return
  }
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/debug`)
    if (res.ok) {
      debugData.value = await res.json()
    }
  } catch (error) {
    console.error('Failed to fetch debug info:', error)
  }
}

async function saveChanges() {
  if (!props.adventureId) {
    return
  }
  isSaving.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
    })

    if (!res.ok) {
      throw new Error('Failed to save changes.')
    }

    emit('updated')
    emit('close')
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error while saving.'
  } finally {
    isSaving.value = false
  }
}

async function resetAdventure() {
  if (!props.adventureId) {
    return
  }
  if (!confirm('Are you sure? This will wipe all progress and restore the original world.')) {
    return
  }

  isSaving.value = true
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/reset`, {
      method: 'POST',
    })
    if (!res.ok) {
      throw new Error('Failed to reset adventure.')
    }

    await fetchAdventure()
    await fetchDebugInfo()
    emit('updated')
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error during reset.'
  } finally {
    isSaving.value = false
  }
}

async function removeAdventure() {
  if (!props.adventureId) {
    return
  }
  if (!confirm('Are you sure? This deletes the entire adventure permanently.')) {
    return
  }

  isSaving.value = true
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      throw new Error('Failed to delete adventure.')
    }

    emit('updated')
    emit('close')
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error during deletion.'
  } finally {
    isSaving.value = false
  }
}

async function exportBlueprint() {
  if (!props.adventureId) {
    return
  }
  const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/export/manifest`)
  if (!res.ok) {
    return
  }
  const data = await res.json()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `blueprint_${(adventure.value?.title || 'adventure').replace(/\s+/g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function exportSession() {
  if (!props.adventureId) {
    return
  }
  const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/export/session`)
  if (!res.ok) {
    return
  }
  const data = await res.json()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `session_${(adventure.value?.title || 'adventure').replace(/\s+/g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

watch(
  () => props.open,
  async (isOpen) => {
    if (!isOpen) {
      return
    }
    activeTab.value = 'settings'
    showDebug.value = false
    await fetchAdventure()
    await fetchDebugInfo()
  }
)
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-md" @click="emit('close')" />

        <div class="relative z-10 w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
          <div class="px-8 py-6 border-b border-slate-800 flex justify-between items-center">
            <div>
              <h2 class="text-2xl font-bold text-white flex items-center gap-3">
                <i class="ra ra-gear-hammer text-emerald-500"></i>
                Adventure Settings
              </h2>
              <p class="text-xs text-slate-400 mt-1">Configure mechanics and inspect runtime/debug state.</p>
            </div>
            <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors p-2">X</button>
          </div>

          <div class="flex px-8 border-b border-slate-800 bg-slate-950/30">
            <button
              v-for="tab in ['settings', 'visuals', 'advanced']"
              :key="tab"
              @click="activeTab = tab as any"
              :class="[
                'px-6 py-4 text-[10px] font-bold uppercase tracking-widest transition-all border-b-2',
                activeTab === tab ? 'border-emerald-500 text-emerald-400 bg-emerald-500/5' : 'border-transparent text-slate-500 hover:text-slate-300'
              ]"
            >
              {{ tab }}
            </button>
          </div>

          <div class="flex-grow overflow-y-auto p-8 custom-scrollbar">
            <div v-if="isLoading" class="flex justify-center py-12">
              <div class="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-emerald-500"></div>
            </div>

            <div v-else-if="errorMsg" class="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl">
              {{ errorMsg }}
            </div>

            <div v-else-if="activeTab === 'settings' && adventure" class="space-y-6">
              <div>
                <label class="block text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">Chronicle Title</label>
                <input v-model="form.title" type="text" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
              </div>

              <div>
                <label class="block text-sm font-semibold text-slate-400 mb-2 uppercase tracking-wider">World Context / Idea</label>
                <textarea v-model="form.context" rows="4" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
              </div>

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
                  <input type="range" v-model.number="form.time_per_turn" min="1" max="60" step="1" class="flex-grow accent-emerald-500" />
                  <div class="w-20 text-center">
                    <span class="text-xl font-bold text-emerald-500">{{ form.time_per_turn }}</span>
                    <span class="text-[10px] text-slate-500 block uppercase pt-0.5">Minutes</span>
                  </div>
                </div>
              </div>
            </div>

            <div v-else-if="activeTab === 'visuals'" class="space-y-8">
              <div v-if="!debugData" class="text-xs text-slate-500">No debug data available yet.</div>
              <div v-else class="space-y-8">
                <section>
                  <h3 class="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] mb-4 border-b border-slate-800 pb-2">Population Portraits</h3>
                  <div v-if="(debugData.npcs ? debugData.npcs.length : 0) === 0" class="text-xs text-slate-600 italic">No inhabitant visuals generated.</div>
                  <div class="grid grid-cols-2 gap-4">
                    <div v-for="npc in (debugData.npcs || [])" :key="npc.id" class="relative group aspect-square bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden">
                      <img v-if="npc.image_url" :src="'http://localhost:8000' + npc.image_url" class="absolute inset-0 w-full h-full object-cover" />
                      <div class="absolute bottom-0 left-0 right-0 p-2 bg-black/50 text-[10px] text-white">{{ npc.name }}</div>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 class="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] mb-4 border-b border-slate-800 pb-2">Artifact Illustrations</h3>
                  <div v-if="(debugData.objects ? debugData.objects.length : 0) === 0" class="text-xs text-slate-600 italic">No object visuals generated.</div>
                  <div class="grid grid-cols-2 gap-4">
                    <div v-for="obj in (debugData.objects || [])" :key="obj.id" class="relative group aspect-square bg-slate-950 border border-slate-800 rounded-2xl overflow-hidden">
                      <img v-if="obj.image_url" :src="'http://localhost:8000' + obj.image_url" class="absolute inset-0 w-full h-full object-cover" />
                      <div class="absolute bottom-0 left-0 right-0 p-2 bg-black/50 text-[10px] text-white">{{ obj.name }}</div>
                    </div>
                  </div>
                </section>
              </div>
            </div>

            <div v-else-if="activeTab === 'advanced'" class="space-y-6">
              <div class="p-4 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 grid grid-cols-2 gap-3">
                <div>
                  <span class="text-slate-500">Scenes:</span>
                  <span class="ml-2 font-bold">{{ debugData?.scenes?.length || 0 }}</span>
                </div>
                <div>
                  <span class="text-slate-500">NPCs:</span>
                  <span class="ml-2 font-bold">{{ debugData?.npcs?.length || 0 }}</span>
                </div>
                <div>
                  <span class="text-slate-500">Objects:</span>
                  <span class="ml-2 font-bold">{{ debugData?.objects?.length || 0 }}</span>
                </div>
                <div>
                  <span class="text-slate-500">Exits:</span>
                  <span class="ml-2 font-bold">{{ debugData?.exits?.length || 0 }}</span>
                </div>
              </div>

              <div class="grid grid-cols-2 gap-4">
                <button @click="exportBlueprint" class="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-emerald-500/50 text-left">
                  <div class="text-xs font-bold text-emerald-400 uppercase tracking-widest">Blueprint</div>
                  <div class="text-[10px] text-slate-500 mt-1">Export world manifest.</div>
                </button>
                <button @click="exportSession" class="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-cyan-500/50 text-left">
                  <div class="text-xs font-bold text-cyan-400 uppercase tracking-widest">Session</div>
                  <div class="text-[10px] text-slate-500 mt-1">Export complete runtime session.</div>
                </button>
              </div>

              <div class="p-6 bg-red-500/5 border border-red-500/20 rounded-2xl">
                <h3 class="text-sm font-bold text-red-500 uppercase tracking-wider mb-2">Danger Zone</h3>
                <p class="text-[10px] text-slate-500 mb-4">Reset restores the original manifest and clears progress.</p>
                <button
                  @click="resetAdventure"
                  :disabled="isSaving"
                  class="w-full px-4 py-3 border border-red-500 text-red-500 hover:bg-red-500 hover:text-white transition-all rounded-xl text-xs font-bold uppercase tracking-widest"
                >
                  Reset Adventure
                </button>
              </div>

              <div class="border-t border-slate-800 pt-4">
                <button @click="showDebug = !showDebug" class="text-xs font-bold text-slate-500 hover:text-emerald-400 uppercase tracking-widest">
                  {{ showDebug ? 'Hide Debug Context' : 'Show Debug Context' }}
                </button>
                <div v-if="showDebug" class="mt-4 bg-black/50 border border-slate-800 rounded-xl p-4">
                  <pre class="text-[10px] font-mono text-emerald-500/80 leading-relaxed overflow-auto max-h-72 custom-scrollbar">{{ JSON.stringify(debugData, null, 2) }}</pre>
                </div>
              </div>
            </div>
          </div>

          <div class="p-8 border-t border-slate-800 bg-slate-900/50 flex justify-between items-center">
            <button
              @click="removeAdventure"
              :disabled="isSaving || isLoading"
              class="px-4 py-2 border border-red-500/30 hover:border-red-500 text-red-500 hover:bg-red-500/10 rounded-xl text-xs font-bold uppercase tracking-widest transition-all disabled:opacity-30"
            >
              Delete
            </button>
            <div class="flex gap-3">
              <button @click="emit('close')" class="px-6 py-2 rounded-xl text-slate-400 hover:bg-white/5 transition-colors font-medium">Cancel</button>
              <button
                @click="saveChanges"
                :disabled="isSaving || isLoading"
                class="px-8 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold rounded-xl transition-all disabled:opacity-50"
              >
                {{ isSaving ? 'Saving...' : 'Save Settings' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(16, 185, 129, 0.2);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(16, 185, 129, 0.4);
}
</style>
