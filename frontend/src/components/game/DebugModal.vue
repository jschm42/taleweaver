<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'

const props = defineProps<{
  open: boolean
  data: any
}>()

const emit = defineEmits<{
  close: []
}>()

const fullWorld = computed(() => props.data?.fullWorld || null)
const blueprint = computed(() => fullWorld.value?.blueprint || null)
const runtime = computed(() => fullWorld.value?.runtime || null)

const scenes = computed<any[]>(() => blueprint.value?.scenes || [])
const npcs = computed<any[]>(() => blueprint.value?.npcs || [])
const objects = computed<any[]>(() => blueprint.value?.objects || [])
const exits = computed<any[]>(() => blueprint.value?.exits || [])

const searchQuery = ref('')
const currentSceneOnly = ref(false)
const lockedExitsOnly = ref(false)
const exitsFromCurrentOnly = ref(false)
const inventoryOnly = ref(false)
const entityVisibility = ref<'all' | 'visible' | 'hidden'>('all')

const currentSceneId = computed<string>(() => runtime.value?.current_scene_id || props.data?.sheet?.scene_id || '')
const normalizedQuery = computed<string>(() => searchQuery.value.trim().toLowerCase())

function matchesQuery(parts: Array<unknown>): boolean {
  if (!normalizedQuery.value) return true
  const haystack = parts
    .filter((part) => part !== null && part !== undefined)
    .map((part) => String(part).toLowerCase())
    .join(' ')
  return haystack.includes(normalizedQuery.value)
}

function matchesEntityState(entity: any): boolean {
  if (inventoryOnly.value && !entity?.is_in_inventory) {
    return false
  }
  if (entityVisibility.value === 'hidden' && !entity?.is_hidden) {
    return false
  }
  if (entityVisibility.value === 'visible' && entity?.is_hidden) {
    return false
  }
  return true
}

function resetFilters(): void {
  searchQuery.value = ''
  currentSceneOnly.value = false
  lockedExitsOnly.value = false
  exitsFromCurrentOnly.value = false
  inventoryOnly.value = false
  entityVisibility.value = 'all'
}

const filteredScenes = computed<any[]>(() => {
  return scenes.value.filter((scene) => matchesQuery([scene.id, scene.name, scene.description]))
})

const filteredNpcs = computed<any[]>(() => {
  return npcs.value.filter((npc) => {
    if (!matchesEntityState(npc)) {
      return false
    }
    if (currentSceneOnly.value && currentSceneId.value && npc.start_scene_id !== currentSceneId.value) {
      return false
    }
    return matchesQuery([npc.id, npc.name, npc.description, npc.start_scene_id])
  })
})

const filteredObjects = computed<any[]>(() => {
  return objects.value.filter((obj) => {
    if (!matchesEntityState(obj)) {
      return false
    }
    if (currentSceneOnly.value && currentSceneId.value && obj.start_scene_id !== currentSceneId.value) {
      return false
    }
    return matchesQuery([obj.id, obj.name, obj.description, obj.start_scene_id])
  })
})

const filteredExits = computed<any[]>(() => {
  return exits.value.filter((ex) => {
    if (lockedExitsOnly.value && !ex.is_locked) {
      return false
    }
    if (exitsFromCurrentOnly.value && currentSceneId.value && ex.from_scene_id !== currentSceneId.value) {
      return false
    }
    if (currentSceneOnly.value && currentSceneId.value) {
      const touchesCurrentScene = ex.from_scene_id === currentSceneId.value || ex.to_scene_id === currentSceneId.value
      if (!touchesCurrentScene) {
        return false
      }
    }
    return matchesQuery([ex.from_scene_id, ex.to_scene_id, ex.label, ex.lock_description])
  })
})

function safePreview(value: unknown, max = 180): string {
  if (value === null || value === undefined) return ''
  const text = String(value)
  return text.length > max ? `${text.slice(0, max)}...` : text
}

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

          <div class="flex-grow overflow-auto p-8 custom-scrollbar bg-slate-950/30 space-y-6">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div class="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                <div class="text-[10px] uppercase tracking-widest text-slate-500">Scenes</div>
                <div class="text-lg font-black text-cyan-300">{{ filteredScenes.length }}<span class="text-slate-500">/{{ scenes.length }}</span></div>
              </div>
              <div class="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                <div class="text-[10px] uppercase tracking-widest text-slate-500">NPCs</div>
                <div class="text-lg font-black text-cyan-300">{{ filteredNpcs.length }}<span class="text-slate-500">/{{ npcs.length }}</span></div>
              </div>
              <div class="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                <div class="text-[10px] uppercase tracking-widest text-slate-500">Objects</div>
                <div class="text-lg font-black text-cyan-300">{{ filteredObjects.length }}<span class="text-slate-500">/{{ objects.length }}</span></div>
              </div>
              <div class="rounded-xl border border-slate-800 bg-slate-900/70 px-3 py-2">
                <div class="text-[10px] uppercase tracking-widest text-slate-500">Exits</div>
                <div class="text-lg font-black text-cyan-300">{{ filteredExits.length }}<span class="text-slate-500">/{{ exits.length }}</span></div>
              </div>
            </div>

            <section class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h4 class="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400 mb-3">Filters</h4>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div class="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-xs text-slate-300">
                  <input id="debug-current-scene-only" v-model="currentSceneOnly" type="checkbox" class="h-3.5 w-3.5 accent-cyan-500" />
                  <label for="debug-current-scene-only">Current scene only</label>
                </div>
                <div class="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-xs text-slate-300 md:col-span-3">
                  <input id="debug-locked-exits-only" v-model="lockedExitsOnly" type="checkbox" class="h-3.5 w-3.5 accent-cyan-500" />
                  <label for="debug-locked-exits-only">Locked exits only</label>
                </div>
              </div>
              <div class="mt-3 flex flex-wrap items-center gap-2">
                <button
                  class="px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-widest border transition-colors"
                  :class="entityVisibility === 'all' ? 'border-cyan-500/60 text-cyan-300 bg-cyan-500/10' : 'border-slate-700 text-slate-400 hover:text-slate-200'"
                  @click="entityVisibility = 'all'"
                >
                  All Entities
                </button>
                <button
                  class="px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-widest border transition-colors"
                  :class="entityVisibility === 'visible' ? 'border-cyan-500/60 text-cyan-300 bg-cyan-500/10' : 'border-slate-700 text-slate-400 hover:text-slate-200'"
                  @click="entityVisibility = 'visible'"
                >
                  Visible Only
                </button>
                <button
                  class="px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-widest border transition-colors"
                  :class="entityVisibility === 'hidden' ? 'border-cyan-500/60 text-cyan-300 bg-cyan-500/10' : 'border-slate-700 text-slate-400 hover:text-slate-200'"
                  @click="entityVisibility = 'hidden'"
                >
                  Hidden Only
                </button>
                <button
                  class="px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-widest border transition-colors"
                  :class="inventoryOnly ? 'border-cyan-500/60 text-cyan-300 bg-cyan-500/10' : 'border-slate-700 text-slate-400 hover:text-slate-200'"
                  @click="inventoryOnly = !inventoryOnly"
                >
                  Inventory Only
                </button>
                <button
                  class="px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-widest border transition-colors"
                  :class="exitsFromCurrentOnly ? 'border-cyan-500/60 text-cyan-300 bg-cyan-500/10' : 'border-slate-700 text-slate-400 hover:text-slate-200'"
                  @click="exitsFromCurrentOnly = !exitsFromCurrentOnly"
                >
                  Exits From Current
                </button>
                <button
                  class="px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-widest border border-red-700/60 text-red-300 hover:bg-red-500/10 transition-colors"
                  @click="resetFilters"
                >
                  Reset
                </button>
              </div>
            </section>

            <section class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h4 class="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400 mb-3">Session Snapshot</h4>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-slate-500 text-[10px] uppercase tracking-widest">Adventure</div>
                  <div class="text-slate-200">{{ data?.sheet?.adventure_title || 'Unknown' }}</div>
                </div>
                <div class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-slate-500 text-[10px] uppercase tracking-widest">Current Scene</div>
                  <div class="text-slate-200">{{ data?.sheet?.current_scene || data?.sheet?.scene_id || 'Unknown' }}</div>
                </div>
                <div class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-slate-500 text-[10px] uppercase tracking-widest">Runtime Time</div>
                  <div class="text-slate-200">{{ data?.sheet?.in_game_time ?? 0 }} min</div>
                </div>
                <div class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-slate-500 text-[10px] uppercase tracking-widest">Visible Entities</div>
                  <div class="text-slate-200">{{ data?.entities?.length || 0 }}</div>
                </div>
              </div>
            </section>

            <section v-if="runtime" class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h4 class="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400 mb-3">Full World Runtime</h4>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-slate-500 text-[10px] uppercase tracking-widest">Game ID</div>
                  <div class="text-slate-200 break-all">{{ runtime.game_id }}</div>
                </div>
                <div class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-slate-500 text-[10px] uppercase tracking-widest">Adventure ID</div>
                  <div class="text-slate-200 break-all">{{ runtime.adventure_id }}</div>
                </div>
                <div class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-slate-500 text-[10px] uppercase tracking-widest">Current Scene ID</div>
                  <div class="text-slate-200 break-all">{{ runtime.current_scene_id }}</div>
                </div>
                <div class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-slate-500 text-[10px] uppercase tracking-widest">Paused</div>
                  <div class="text-slate-200">{{ runtime.is_paused ? 'yes' : 'no' }}</div>
                </div>
              </div>
            </section>

            <section v-if="scenes.length" class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h4 class="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400 mb-3">Scenes</h4>
              <div class="space-y-2">
                <div v-for="scene in filteredScenes" :key="scene.id" class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-cyan-300 text-xs font-bold">{{ scene.name || scene.id }}</div>
                  <div class="text-slate-400 text-[11px] break-all">{{ scene.id }}</div>
                  <div v-if="scene.description" class="text-slate-300 text-xs mt-1">{{ safePreview(scene.description) }}</div>
                </div>
                <div v-if="!filteredScenes.length" class="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 px-3 py-2 text-xs text-slate-500">
                  No scenes match the active filters.
                </div>
              </div>
            </section>

            <section v-if="npcs.length" class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h4 class="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400 mb-3">NPCs</h4>
              <div class="space-y-2">
                <div v-for="npc in filteredNpcs" :key="npc.id" class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-cyan-300 text-xs font-bold">{{ npc.name || npc.id }}</div>
                  <div class="text-slate-400 text-[11px]">Start Scene: {{ npc.start_scene_id || '-' }}</div>
                  <div v-if="npc.description" class="text-slate-300 text-xs mt-1">{{ safePreview(npc.description) }}</div>
                </div>
                <div v-if="!filteredNpcs.length" class="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 px-3 py-2 text-xs text-slate-500">
                  No NPCs match the active filters.
                </div>
              </div>
            </section>

            <section v-if="objects.length" class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h4 class="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400 mb-3">Objects</h4>
              <div class="space-y-2">
                <div v-for="obj in filteredObjects" :key="obj.id" class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
                  <div class="text-cyan-300 text-xs font-bold">{{ obj.name || obj.id }}</div>
                  <div class="text-slate-400 text-[11px]">Start Scene: {{ obj.start_scene_id || '-' }}</div>
                  <div v-if="obj.description" class="text-slate-300 text-xs mt-1">{{ safePreview(obj.description) }}</div>
                </div>
                <div v-if="!filteredObjects.length" class="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 px-3 py-2 text-xs text-slate-500">
                  No objects match the active filters.
                </div>
              </div>
            </section>

            <section v-if="exits.length" class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h4 class="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400 mb-3">Exits</h4>
              <div class="space-y-2">
                <div v-for="(ex, idx) in filteredExits" :key="`${ex.from_scene_id || 'from'}-${ex.to_scene_id || 'to'}-${idx}`" class="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs">
                  <div class="text-cyan-300 font-bold">{{ ex.from_scene_id }} -> {{ ex.to_scene_id }}</div>
                  <div class="text-slate-300">{{ ex.label || 'Passage' }}</div>
                  <div class="text-slate-400">Locked: {{ ex.is_locked ? 'yes' : 'no' }}</div>
                </div>
                <div v-if="!filteredExits.length" class="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 px-3 py-2 text-xs text-slate-500">
                  No exits match the active filters.
                </div>
              </div>
            </section>

            <section class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
              <h4 class="text-[11px] font-bold uppercase tracking-[0.18em] text-slate-400 mb-3">Raw JSON</h4>
              <pre class="text-[11px] font-mono text-cyan-400/80 leading-relaxed">{{ JSON.stringify(data, null, 2) }}</pre>
            </section>
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
