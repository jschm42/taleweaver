<script setup lang="ts">
import { computed } from 'vue'
import { hasAnyScript } from '@/utils/editor_utils'
import type { WorldSection } from '@/services/sectionService'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import PlaceFilterBar from '@/components/editor/filters/PlaceFilterBar.vue'
import { groupsByScene, placeKey, sectionMapOf, usePlaceFilter } from '@/components/editor/filters/placeFilter'
import ItemTile from './ItemTile.vue'

interface SceneOption {
  id: string
  name: string
  label?: string
  section_id?: string | null
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
  adventureId?: string
  worldSections?: WorldSection[]
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
  (e: 'duplicate-entity', kind: 'item', id: string): void
  (e: 'import-entity', kind: 'item'): void
}>()

const isContainerLocked = (obj: any): boolean => {
  if (!['CONTAINER', 'CONTAINER_SWITCH'].includes(String(obj?.item_type || '').toUpperCase())) return false
  if (typeof obj?.locked === 'boolean') return obj.locked
  const metadata = (obj?.metadata_json && typeof obj.metadata_json === 'object') ? obj.metadata_json : {}
  return Boolean(metadata.code_to_unlock || metadata.item_to_unlock)
}

const isItemLocked = (obj: any): boolean => {
  if (['CONTAINER', 'CONTAINER_SWITCH', 'SWITCH', 'CONSTRUCTABLE'].includes(String(obj?.item_type || '').toUpperCase())) {
    return false
  }
  return Boolean(obj?.locked === true || obj?.metadata_json?.locked === true)
}

const containerBadges = (obj: any) => {
  const badges: Array<{ label: string; class: string }> = []
  if (String(obj?.item_type || '').toUpperCase() === 'CONTAINER_SWITCH') {
    badges.push(...SWITCH_BADGE)
  }
  if (isContainerLocked(obj)) {
    badges.push(...LOCKED_BADGE)
  }
  return badges
}

const objectBadges = (obj: any) => {
  const badges: Array<{ label: string; class: string }> = []
  if (obj.is_hidden) badges.push(...HIDDEN_BADGE)
  if (isItemLocked(obj)) badges.push(...LOCKED_BADGE)
  return badges
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
  'duplicate-entity': (kind: 'item', id: string) => emit('duplicate-entity', kind, id),
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

// Region and scene filter of the four item sections (constructables are never in a scene).
const worldItems = computed(() => [...props.editorTextLogs, ...props.editorContainers, ...props.editorSwitches, ...props.editorObjects])
const placeFilter = usePlaceFilter({
  memoryKey: () => `items:${props.adventureId || ''}`,
  sections: () => props.worldSections || [],
  sectionOfScene: () => sectionMapOf(props.editorScenes),
  groups: () => groupsByScene(worldItems.value, props.editorScenes),
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
const isFilterActive = computed(() => placeFilter.isActive.value)
const knownSceneKeys = computed(() => new Set((props.editorScenes || []).map((s) => placeKey(s.id))))

function filterByScene(items: any[]): any[] {
  if (!isFilterActive.value) return items
  return items.filter((it) => {
    const sceneId = knownSceneKeys.value.has(placeKey(it?.current_scene_id)) ? it.current_scene_id : null
    return placeFilter.matches(sceneId)
  })
}
</script>

<template>
  <div class="space-y-6">
  <div class="flex items-center justify-end">
    <button @click="emit('import-entity', 'item')" class="text-xs font-bold text-sky-500 hover:text-sky-400 flex items-center gap-1.5 uppercase tracking-widest transition-colors" title="Import an item from a .twe file">
      <i class="ra ra-load"></i> Import Item
    </button>
  </div>
  <section v-if="unfilteredTotal > 0" class="space-y-8 animate-page-in">
    <PlaceFilterBar :filter="placeFilter" :shown="filteredTotal" :total="unfilteredTotal" noun="items" />

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
            :badges="containerBadges(obj)"
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
            :badges="objectBadges(obj)"
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
    <UiEmptyState
      v-if="isFilterActive && filteredTotal === 0"
      title="No items here"
      description="No item lies in a scene of this region. Pick another region or scene."
    />
  </section>
  </div>
</template>

<style scoped>
.animate-page-in { animation: pageIn 0.6s cubic-bezier(0.16,1,0.3,1) forwards; }
@keyframes pageIn { from { opacity: 0; transform: translateY(20px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
</style>
