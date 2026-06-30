<script setup lang="ts">
import { computed, ref } from 'vue'

interface SceneOption {
  id: string
  name: string
  imageUrl?: string | null
  type?: string
}

const props = defineProps<{
  editorObjects: any[]
  editorSwitches: any[]
  editorContainers: any[]
  editorTextLogs: any[]
  isBatchGenerating: Record<string, boolean>
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  ruleEnforcementMode: string
  visualsCacheVersion: number
  editorScenes?: SceneOption[]
  activeMapSceneId?: string | null
}>()

const emit = defineEmits<{
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'regen-all', kind: string, missingOnly?: boolean): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'open-text-edit', ...args: any[]): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'handle-hover', entity: any, event: MouseEvent): void
  (e: 'clear-hover'): void
  (e: 'request-change-item-type', itemId: string, name: string, currentItemType: string): void
  (e: 'request-move-item-to-scene', itemId: string, name: string, currentSceneId: string): void
  (e: 'request-delete-item', itemId: string, name: string): void
}>()

const isContainerLocked = (obj: any): boolean => {
  if (String(obj?.item_type || '').toUpperCase() !== 'CONTAINER') return false
  if (typeof obj?.locked === 'boolean') return obj.locked
  const metadata = (obj?.metadata_json && typeof obj.metadata_json === 'object') ? obj.metadata_json : {}
  return Boolean(metadata.code_to_unlock || metadata.item_to_unlock)
}

const hasMissingImage = (obj: any): boolean => {
  const raw = String(obj?.image_url || '').trim()
  if (!raw) return true
  const lowered = raw.toLowerCase()
  if (lowered.startsWith('assets/') || lowered.startsWith('/assets/')) return true
  if (lowered.includes('placeholder_') || lowered.includes('/placeholder-')) return true
  return false
}

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return `${imagePath}?v=${props.visualsCacheVersion}`
}

// ---------------------------------------------------------------------------
// Scene filter state
// ---------------------------------------------------------------------------
// '' (empty) means "All scenes". Any other value filters items to that scene.
const sceneFilter = ref<string>('')

const sceneOptions = computed<SceneOption[]>(() => {
  if (!props.activeMapSceneId) return props.editorScenes || []
  // If the user is currently viewing a scene, default the filter to that
  // scene so newly created items inside that scene show up immediately.
  const filtered = (props.editorScenes || []).filter((s) => String(s.id) === String(props.activeMapSceneId))
  return filtered.length ? filtered : props.editorScenes || []
})

const filteredTextLogs = computed(() => filterByScene(props.editorTextLogs))
const filteredContainers = computed(() => filterByScene(props.editorContainers))
const filteredSwitches = computed(() => filterByScene(props.editorSwitches))
const filteredObjects = computed(() => filterByScene(props.editorObjects))

const filteredTotal = computed(
  () =>
    filteredTextLogs.value.length +
    filteredContainers.value.length +
    filteredSwitches.value.length +
    filteredObjects.value.length,
)
const unfilteredTotal = computed(
  () =>
    props.editorTextLogs.length +
    props.editorContainers.length +
    props.editorSwitches.length +
    props.editorObjects.length,
)
const isFilterActive = computed(() => sceneFilter.value.trim().length > 0)

function filterByScene(items: any[]) {
  const activeFilter = sceneFilter.value.trim()
  if (!activeFilter) return items
  return items.filter((it) => String(it?.current_scene_id || '').toUpperCase() === activeFilter.toUpperCase())
}

function selectSceneFilter(value: string) {
  sceneFilter.value = value
}

function clearSceneFilter() {
  sceneFilter.value = ''
}

// Display helpers for the filter bar
const activeFilterLabel = computed(() => {
  if (!isFilterActive.value) return ''
  const match = sceneOptions.value.find((s) => String(s.id).toUpperCase() === sceneFilter.value.toUpperCase())
  if (match) return match.name
  const allScenes = props.editorScenes || []
  const fallback = allScenes.find((s) => String(s.id).toUpperCase() === sceneFilter.value.toUpperCase())
  return fallback?.name || sceneFilter.value
})
</script>

<template>
  <section v-if="unfilteredTotal > 0" class="space-y-8 animate-page-in">
    <!-- ==================================================================
         Filter bar — filter the four item sections by scene.
         Two-column layout: scene <select> on the left, clear/visibility on the right.
         ================================================================== -->
    <div class="bg-slate-950/60 border border-white/5 rounded-xl p-4 grid md:grid-cols-3 gap-4 items-end">
      <label class="text-xs text-slate-300 space-y-1 md:col-span-2">
        <span class="block font-black uppercase tracking-[0.2em] text-slate-500">Filter by Scene</span>
        <div class="relative">
          <i class="ra ra-tower absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm"></i>
          <select
            :value="sceneFilter"
            @change="selectSceneFilter(($event.target as HTMLSelectElement).value)"
            class="w-full bg-black/40 border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-sm text-white focus:border-emerald-500/50 outline-none transition-all appearance-none cursor-pointer"
          >
            <option value="">All scenes ({{ unfilteredTotal }})</option>
            <option
              v-for="scene in sceneOptions"
              :key="scene.id"
              :value="scene.id"
            >
              {{ scene.name || scene.id }} — {{ scene.id }}
            </option>
          </select>
        </div>
      </label>
      <div class="flex items-center justify-end gap-3">
        <div v-if="isFilterActive" class="text-[10px] text-slate-400 uppercase tracking-widest font-black">
          <span class="text-emerald-400">{{ filteredTotal }}</span>
          <span class="text-slate-500">/</span>
          <span>{{ unfilteredTotal }}</span>
          <span class="text-slate-500 ml-1">in <span class="text-slate-200">{{ activeFilterLabel }}</span></span>
        </div>
        <button
          v-if="isFilterActive"
          @click="clearSceneFilter"
          class="px-3 py-2 text-xs font-bold rounded border border-white/15 text-slate-300 hover:text-white hover:bg-white/5 uppercase tracking-widest transition-all"
        >
          Clear Filter
        </button>
      </div>
    </div>

    <!-- ==================================================================
         Text Logs Section
         ================================================================== -->
    <div v-if="filteredTextLogs.length" class="space-y-6">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Text Logs ({{ filteredTextLogs.length }}<span v-if="isFilterActive"> / {{ editorTextLogs.length }}</span>)</h3>
        <div class="flex items-center gap-4">
          <button @click="emit('regen-all', 'text-log', true)" :disabled="isBatchGenerating['text-log']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['text-log'] }"></i> Generate Missing
          </button>
          <button @click="emit('regen-all', 'text-log', false)" :disabled="isBatchGenerating['text-log']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['text-log'] }"></i> Regenerate All
          </button>
        </div>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
        <div
          v-for="obj in filteredTextLogs"
          :key="'txt_' + obj.id"
          @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: (obj.metadata_json?.text_log_content || obj.description), image_url: obj.image_url, type: 'TEXT_LOG', stats: {} }, $event)"
          @mouseleave="emit('clear-hover')"
          :class="[
            'relative group aspect-square bg-slate-900 border border-cyan-500/20 rounded-xl shadow-lg transition-all overflow-visible',
            activeMenuId === obj.id ? 'z-[180]' : 'z-0',
          ]"
        >
          <div class="absolute inset-0 rounded-xl overflow-hidden">
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-10">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-cyan-500/40 bg-cyan-500/20 text-cyan-200">LOG</div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
            </div>
          </div>
          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-cyan-500 transition-all shadow-lg group/dots">
              <div class="flex flex-col gap-0.5">
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-56 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
              <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
              <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
              <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'object'}_image`)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
              <button @click="emit('open-text-edit', 'object', obj.id, obj.name, (obj.description || ''))" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
              <div class="my-1 border-t border-white/5"></div>
              <button @click="emit('request-change-item-type', obj.id, obj.name, obj.item_type || 'DEFAULT')" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Change Type…</button>
              <button @click="emit('request-move-item-to-scene', obj.id, obj.name, obj.current_scene_id || '')" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Move to Scene…</button>
              <button @click="emit('request-delete-item', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================================================================
         Containers Section
         ================================================================== -->
    <div v-if="filteredContainers.length" class="space-y-6">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Containers ({{ filteredContainers.length }}<span v-if="isFilterActive"> / {{ editorContainers.length }}</span>)</h3>
        <div class="flex items-center gap-4">
          <button @click="emit('regen-all', 'container', true)" :disabled="isBatchGenerating['container']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['container'] }"></i> Generate Missing
          </button>
          <button @click="emit('regen-all', 'container', false)" :disabled="isBatchGenerating['container']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['container'] }"></i> Regenerate All
          </button>
        </div>
      </div>
      <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
        <div
          v-for="obj in filteredContainers"
          :key="'con_' + obj.id"
          @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM', stats: obj.stats }, $event)"
          @mouseleave="emit('clear-hover')"
          :class="[
            'relative group aspect-square bg-slate-900 border border-amber-500/20 rounded-xl shadow-lg transition-all overflow-visible',
            activeMenuId === obj.id ? 'z-[180]' : 'z-0',
          ]"
        >
          <div class="absolute inset-0 rounded-xl overflow-hidden">
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-10">MISSING</div>
            <div v-if="isContainerLocked(obj)" class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-amber-400/50 bg-amber-500/25 text-amber-100 z-10">LOCKED</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
            </div>
          </div>
          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
              <div class="flex flex-col gap-0.5">
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-56 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
              <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
              <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
              <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'container'}_image`)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
              <button @click="emit('open-text-edit', 'object', obj.id, obj.name, obj.description)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
              <div class="my-1 border-t border-white/5"></div>
              <button @click="emit('request-change-item-type', obj.id, obj.name, obj.item_type || 'DEFAULT')" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Change Type…</button>
              <button @click="emit('request-move-item-to-scene', obj.id, obj.name, obj.current_scene_id || '')" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Move to Scene…</button>
              <button @click="emit('request-delete-item', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================================================================
         Switches Section
         ================================================================== -->
    <div v-if="filteredSwitches.length" class="space-y-6">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Switches ({{ filteredSwitches.length }}<span v-if="isFilterActive"> / {{ editorSwitches.length }}</span>)</h3>
        <div class="flex items-center gap-4">
          <button @click="emit('regen-all', 'switch', true)" :disabled="isBatchGenerating['switch']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['switch'] }"></i> Generate Missing
          </button>
          <button @click="emit('regen-all', 'switch', false)" :disabled="isBatchGenerating['switch']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['switch'] }"></i> Regenerate All
          </button>
        </div>
      </div>
      <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
        <div
          v-for="obj in filteredSwitches"
          :key="'sw_' + obj.id"
          @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM', stats: obj.stats }, $event)"
          @mouseleave="emit('clear-hover')"
          :class="[
            'relative group aspect-square bg-slate-900 border border-lime-500/20 rounded-xl shadow-lg transition-all overflow-visible',
            activeMenuId === obj.id ? 'z-[180]' : 'z-0',
          ]"
        >
          <div class="absolute inset-0 rounded-xl overflow-hidden">
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-10">MISSING</div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-lime-400/50 bg-lime-500/25 text-lime-100 z-10">SWITCH</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
            </div>
          </div>

          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
              <div class="flex flex-col gap-0.5">
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-56 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
              <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
              <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
              <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'switch'}_image`)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
              <button @click="emit('open-text-edit', 'object', obj.id, obj.name, obj.description)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
              <div class="my-1 border-t border-white/5"></div>
              <button @click="emit('request-change-item-type', obj.id, obj.name, obj.item_type || 'DEFAULT')" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Change Type…</button>
              <button @click="emit('request-move-item-to-scene', obj.id, obj.name, obj.current_scene_id || '')" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Move to Scene…</button>
              <button @click="emit('request-delete-item', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================================================================
         Mystical Objects Section
         ================================================================== -->
    <div v-if="filteredObjects.length" class="space-y-6">
      <div class="flex items-center justify-between">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Mystical Objects ({{ filteredObjects.length }}<span v-if="isFilterActive"> / {{ editorObjects.length }}</span>)</h3>
        <div class="flex items-center gap-4">
          <button @click="emit('regen-all', 'object', true)" :disabled="isBatchGenerating['object']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Generate Missing
          </button>
          <button @click="emit('regen-all', 'object', false)" :disabled="isBatchGenerating['object']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
            <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Regenerate All
          </button>
        </div>
      </div>
      <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
        <div
          v-for="obj in filteredObjects"
          :key="'obj_' + obj.id"
          @mouseenter="emit('handle-hover', { id: obj.id, name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM', stats: obj.stats }, $event)"
          @mouseleave="emit('clear-hover')"
          :class="[
            'relative group aspect-square bg-slate-900 border border-white/5 rounded-xl shadow-lg transition-all overflow-visible',
            activeMenuId === obj.id ? 'z-[180]' : 'z-0',
          ]"
        >
          <div class="absolute inset-0 rounded-xl overflow-hidden">
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-10">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
              <div v-if="ruleEnforcementMode !== 'chat' && obj.stats && Object.keys(obj.stats).length > 0" class="flex gap-1 mt-1">
                <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.5)]"></div>
              </div>
            </div>
          </div>

          <div class="absolute top-1.5 right-1.5 z-40">
            <button @click="emit('toggle-menu', obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
              <div class="flex flex-col gap-0.5">
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
              </div>
            </button>
            <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-56 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[200] animate-fade-in ring-1 ring-white/5">
              <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
              <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
              <button @click="emit('open-upload-picker', 'object', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
              <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'object'}_image`)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
              <button @click="emit('open-text-edit', 'object', obj.id, obj.name, obj.description)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
              <div class="my-1 border-t border-white/5"></div>
              <button @click="emit('request-change-item-type', obj.id, obj.name, obj.item_type || 'DEFAULT')" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Change Type…</button>
              <button @click="emit('request-move-item-to-scene', obj.id, obj.name, obj.current_scene_id || '')" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Move to Scene…</button>
              <button @click="emit('request-delete-item', obj.id, obj.name)" class="w-full px-3 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty-state messaging for filter hits that hide everything -->
    <div
      v-if="isFilterActive && filteredTotal === 0"
      class="text-center py-10 px-6 border border-dashed border-slate-700 rounded-xl"
    >
      <i class="ra ra-tower text-2xl text-slate-600"></i>
      <p class="text-sm text-slate-400 mt-3">No items in <span class="text-slate-200 font-bold">{{ activeFilterLabel }}</span>.</p>
      <button
        @click="clearSceneFilter"
        class="mt-3 px-3 py-2 text-xs font-bold rounded border border-white/15 text-slate-300 hover:text-white hover:bg-white/5 uppercase tracking-widest transition-all"
      >
        Show All Items
      </button>
    </div>
  </section>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
