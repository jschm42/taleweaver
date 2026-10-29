<script setup lang="ts">
import { computed, ref } from 'vue'
import { hasAnyScript } from '@/utils/editor_utils'
import ItemTile from './ItemTile.vue'

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
  /** CONSTRUCTABLE meta items: never in the world, no image, not filtered by scene. */
  editorConstructables?: any[]
  isBatchGenerating: Record<string, boolean>
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  ruleEnforcementMode: string
  visualsCacheVersion: number
  editorScenes?: SceneOption[]
  activeMapSceneId?: string | null
  adventureScripts?: any[]
}>()

const hasScript = (obj: any): boolean => hasAnyScript(obj, props.adventureScripts)

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
  (e: 'export-entity', kind: 'item', id: string, label: string): void
  (e: 'import-entity', kind: 'item'): void
}>()

const isContainerLocked = (obj: any): boolean => {
  if (String(obj?.item_type || '').toUpperCase() !== 'CONTAINER') return false
  if (typeof obj?.locked === 'boolean') return obj.locked
  const metadata = (obj?.metadata_json && typeof obj.metadata_json === 'object') ? obj.metadata_json : {}
  return Boolean(metadata.code_to_unlock || metadata.item_to_unlock)
}

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return `${imagePath}?v=${props.visualsCacheVersion}`
}

/** Props every tile gets, whatever its section. */
const tileProps = (obj: any) => ({
  obj,
  hasScript: hasScript(obj),
  imageUrl: buildVisualImageUrl(obj.image_url),
  isGenerating: !!props.isQuickGenerating['object_' + obj.id],
  menuOpen: props.activeMenuId === obj.id,
})

/** Forwards every tile menu action unchanged to the editor view. */
const tileListeners = {
  'quick-regen': (kind: string, id: string) => emit('quick-regen', kind, id),
  'open-regen-dialog': (kind: string, id: string, label: string) => emit('open-regen-dialog', kind, id, label),
  'open-upload-picker': (kind: string, id: string, label: string) => emit('open-upload-picker', kind, id, label),
  'download-asset': (path: string, label: string) => emit('download-asset', path, label),
  'open-text-edit': (...args: any[]) => emit('open-text-edit', ...args),
  'toggle-menu': (id: string, event: MouseEvent) => emit('toggle-menu', id, event),
  'handle-hover': (entity: any, event: MouseEvent) => emit('handle-hover', entity, event),
  'clear-hover': () => emit('clear-hover'),
  'request-change-item-type': (id: string, name: string, type: string) => emit('request-change-item-type', id, name, type),
  'request-move-item-to-scene': (id: string, name: string, scene: string) => emit('request-move-item-to-scene', id, name, scene),
  'request-delete-item': (id: string, name: string) => emit('request-delete-item', id, name),
  'export-entity': (kind: 'item', id: string, label: string) => emit('export-entity', kind, id, label),
}

const LOG_BADGE = [{ label: 'LOG', class: 'border-cyan-500/40 bg-cyan-500/20 text-cyan-200' }]
const LOCKED_BADGE = [{ label: 'LOCKED', class: 'border-amber-400/50 bg-amber-500/25 text-amber-100' }]
const SWITCH_BADGE = [{ label: 'SWITCH', class: 'border-lime-400/50 bg-lime-500/25 text-lime-100' }]
const HIDDEN_BADGE = [{ label: 'HIDDEN', class: 'border-violet-500/50 bg-violet-500/30 text-violet-200' }]
const CONSTRUCTABLE_BADGE = [{ label: 'CONSTRUCTABLE', class: 'border-orange-400/50 bg-orange-500/25 text-orange-100' }]

const textLogHover = (obj: any) => ({
  id: obj.id,
  name: obj.name,
  description: obj.metadata_json?.text_log_content || obj.description,
  image_url: obj.image_url,
  type: 'TEXT_LOG',
  stats: {},
})

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
const constructables = computed(() => props.editorConstructables || [])

const filteredTotal = computed(
  () =>
    filteredTextLogs.value.length +
    filteredContainers.value.length +
    filteredSwitches.value.length +
    filteredObjects.value.length +
    constructables.value.length,
)
const unfilteredTotal = computed(
  () =>
    props.editorTextLogs.length +
    props.editorContainers.length +
    props.editorSwitches.length +
    props.editorObjects.length +
    constructables.value.length,
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
  <div class="space-y-6">
  <div class="flex items-center justify-end">
    <button @click="emit('import-entity', 'item')" class="text-xs font-bold text-sky-500 hover:text-sky-400 flex items-center gap-1.5 uppercase tracking-widest transition-colors" title="Import an item from a .twe file">
      <i class="ra ra-load"></i> Import Item
    </button>
  </div>
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
        <ItemTile
            v-for="obj in filteredTextLogs"
            :key="'txt_' + obj.id"
            v-bind="tileProps(obj)"
            accent-class="border-cyan-500/20"
            menu-hover-class="hover:bg-cyan-500"
            :badges="LOG_BADGE"
            :hover-entity="textLogHover(obj)"
            image-actions
            movable
            v-on="tileListeners"
          />
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
        <ItemTile
            v-for="obj in filteredContainers"
            :key="'con_' + obj.id"
            v-bind="tileProps(obj)"
            accent-class="border-amber-500/20"
            :badges="isContainerLocked(obj) ? LOCKED_BADGE : []"
            image-actions
            movable
            v-on="tileListeners"
          />
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
        <ItemTile
            v-for="obj in filteredSwitches"
            :key="'sw_' + obj.id"
            v-bind="tileProps(obj)"
            accent-class="border-lime-500/20"
            :badges="SWITCH_BADGE"
            image-actions
            movable
            v-on="tileListeners"
          />
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
        <ItemTile
            v-for="obj in filteredObjects"
            :key="'obj_' + obj.id"
            v-bind="tileProps(obj)"
            accent-class="border-white/5"
            :badges="obj.is_hidden ? HIDDEN_BADGE : []"
            :show-stats-dot="ruleEnforcementMode !== 'chat' && obj.stats && Object.keys(obj.stats).length > 0"
            image-actions
            movable
            v-on="tileListeners"
          />
      </div>
    </div>

    <!-- ==================================================================
         Constructables Section — CONSTRUCTABLE meta items: never in the world, no image
         ================================================================== -->
    <div v-if="constructables.length" class="space-y-6">
      <div class="flex items-center justify-between gap-4">
        <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Constructables ({{ constructables.length }})</h3>
        <p class="text-[10px] text-slate-500 uppercase tracking-widest">Never appear in the world · no image</p>
      </div>
      <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
        <ItemTile
            v-for="obj in constructables"
            :key="'cst_' + obj.id"
            v-bind="tileProps(obj)"
            accent-class="border-orange-500/20"
            :badges="CONSTRUCTABLE_BADGE"
            v-on="tileListeners"
          />
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
  </div>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
