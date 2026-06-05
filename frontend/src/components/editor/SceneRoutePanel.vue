<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { entityService } from '@/services/entityService'
import { visualService } from '@/services/visualService'
import { notificationService } from '@/services/notificationService'
import { 
  fixNewlines, 
  isNpcEntity, 
  isObjectEntity, 
  mergeUniqueById, 
  formatObjectIds,
} from '@/utils/editor_utils'
import { Save, X, Trash2, ArrowLeft } from 'lucide-vue-next'

const props = defineProps<{
  adventureId: string
  sceneId: string
  debugData: any
  referenceOptions: any[]
  isSavingText: boolean
  isDeletingRouteAsset: boolean
  isBatchGenerating: Record<string, boolean>
  isQuickGenerating: Record<string, boolean>
  activeMenuId: string | null
  visualsCacheVersion: number
  ruleEnforcementMode: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'open-text-edit', type: string, id: string, name: string, description: string, teaser?: string, hp?: number, stamina?: number, mana?: number, goal?: string, character?: string, isKillable?: boolean): void
  (e: 'open-create-item', itemType?: string): void
  (e: 'open-regen-dialog', kind: string, id: string, label: string): void
  (e: 'open-upload-picker', kind: string, id: string, label: string): void
  (e: 'download-asset', path: string, label: string): void
  (e: 'toggle-menu', id: string, event: MouseEvent): void
  (e: 'handle-hover', entity: any, event: MouseEvent): void
  (e: 'clear-hover'): void
  (e: 'open-exit', exitId: string): void
  (e: 'open-create-exit'): void
  (e: 'open-edit-exit', exitId: string): void
  (e: 'request-delete-scene'): void
  (e: 'request-delete-exit', exitId: string): void
  (e: 'request-delete-entity', entityId: string): void
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'regen-all', kind: string, missingOnly?: boolean): void
  (e: 'refresh'): void
}>()

// Local states for editing name and description
const isEditingSceneName = ref(false)
const isEditingSceneDesc = ref(false)
const isGeneratingSceneDesc = ref(false)
const sceneNameEdit = ref('')
const sceneDescEdit = ref('')
const sceneNameInputRef = ref<HTMLInputElement | null>(null)
const sceneDescInputRef = ref<HTMLTextAreaElement | null>(null)

// Filtering
const routeSceneSearch = ref('')
const hideEmptyFilteredGroups = ref(false)

// Local saving flag to override or supplement prop
const localIsSavingText = ref(false)

// Computeds based on debugData
const editorNpcs = computed<any[]>(() => {
  const source = Array.isArray(props.debugData?.npcs) ? props.debugData.npcs : []
  const allEntities = Array.isArray(props.debugData?.entities_all) ? props.debugData.entities_all : []
  const inferred = allEntities.filter((entity: any) => isNpcEntity(entity))
  return mergeUniqueById(source, inferred)
})

const editorScenes = computed<any[]>(() => {
  const source = Array.isArray(props.debugData?.scenes) ? props.debugData.scenes : []
  return source.filter((scene: any) => !!scene?.id)
})

const editorAllObjects = computed<any[]>(() => {
  const source = Array.isArray(props.debugData?.objects) ? props.debugData.objects : []
  const allEntities = Array.isArray(props.debugData?.entities_all) ? props.debugData.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred)
})

const routeSceneDetails = computed<any | null>(() => {
  const sId = String(props.sceneId || '').trim()
  if (!sId) return null
  return editorScenes.value.find((scene: any) => String(scene.id) === sId) || null
})

const routeSceneNpcs = computed<any[]>(() => {
  const sId = String(props.sceneId || '').trim()
  if (!sId) return []
  return editorNpcs.value.filter((npc: any) => String(npc.current_scene_id || '') === sId)
})

const routeSceneObjects = computed<any[]>(() => {
  const sId = String(props.sceneId || '').trim()
  if (!sId) return []
  return editorAllObjects.value.filter((obj: any) => String(obj.current_scene_id || '') === sId)
})

const routeSceneSwitches = computed<any[]>(() => {
  return routeSceneObjects.value.filter((obj: any) => String(obj.item_type || '').toUpperCase() === 'SWITCH')
})

const routeSceneContainers = computed<any[]>(() => {
  return routeSceneObjects.value.filter((obj: any) => String(obj.item_type || '').toUpperCase() === 'CONTAINER')
})

const routeSceneTextLogs = computed<any[]>(() => {
  return routeSceneObjects.value.filter((obj: any) => String(obj.item_type || '').toUpperCase() === 'READABLE')
})

const routeSceneItems = computed<any[]>(() => {
  return routeSceneObjects.value.filter((obj: any) => {
    const itemType = String(obj.item_type || '').toUpperCase()
    return itemType !== 'SWITCH' && itemType !== 'CONTAINER' && itemType !== 'READABLE'
  })
})

const routeSceneExits = computed<any[]>(() => {
  const sId = String(props.sceneId || '').trim()
  const exits = Array.isArray(props.debugData?.exits) ? props.debugData.exits : []
  if (!sId) return []
  return exits.filter((worldExit: any) => {
    return String(worldExit.from_scene_id || '') === sId || String(worldExit.to_scene_id || '') === sId
  })
})

const normalizedRouteSceneSearch = computed(() => String(routeSceneSearch.value || '').trim().toLowerCase())

function matchesRouteSceneSearch(entry: any): boolean {
  const query = normalizedRouteSceneSearch.value
  if (!query) return true
  const haystack = [
    entry?.id,
    entry?.name,
    entry?.label,
    entry?.description,
    entry?.item_type,
    entry?.from_scene_id,
    entry?.to_scene_id,
  ]
    .map((value: any) => String(value || '').toLowerCase())
    .join(' ')
  return haystack.includes(query)
}

const filteredRouteSceneNpcs = computed(() => routeSceneNpcs.value.filter((entry) => matchesRouteSceneSearch(entry)))
const filteredRouteSceneItems = computed(() => routeSceneItems.value.filter((entry) => matchesRouteSceneSearch(entry)))
const filteredRouteSceneSwitches = computed(() => routeSceneSwitches.value.filter((entry) => matchesRouteSceneSearch(entry)))
const filteredRouteSceneContainers = computed(() => routeSceneContainers.value.filter((entry) => matchesRouteSceneSearch(entry)))
const filteredRouteSceneTextLogs = computed(() => routeSceneTextLogs.value.filter((entry) => matchesRouteSceneSearch(entry)))
const filteredRouteSceneExits = computed(() => routeSceneExits.value.filter((entry) => matchesRouteSceneSearch(entry)))

// Actions
function startEditingSceneName() {
  const scene = routeSceneDetails.value
  if (!scene) return
  sceneNameEdit.value = String(scene.label || scene.name || scene.id || '')
  isEditingSceneName.value = true
  nextTick(() => {
    sceneNameInputRef.value?.focus()
    sceneNameInputRef.value?.select()
  })
}

function startEditingSceneDesc() {
  const scene = routeSceneDetails.value
  if (!scene) return
  sceneDescEdit.value = String(scene.description || '')
  isEditingSceneDesc.value = true
  nextTick(() => {
    sceneDescInputRef.value?.focus()
  })
}

async function saveSceneNameEdit() {
  const scene = routeSceneDetails.value
  if (!scene) return
  const newName = sceneNameEdit.value.trim()
  if (!newName) {
    notificationService.add('Scene name is required.', 'error')
    return
  }
  if (newName.length > 100) {
    notificationService.add('Scene name must be 100 characters or less.', 'error')
    return
  }
  if (newName === String(scene.label || scene.name || '')) {
    isEditingSceneName.value = false
    return
  }
  localIsSavingText.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: String(scene.id),
      name: newName,
      description: scene.description,
    })
    emit('refresh')
    notificationService.add('Scene name updated.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update scene name.', 'error')
  } finally {
    localIsSavingText.value = false
    isEditingSceneName.value = false
  }
}

async function saveSceneDescEdit() {
  const scene = routeSceneDetails.value
  if (!scene) return
  const newDesc = sceneDescEdit.value.trim()
  if (!newDesc) {
    notificationService.add('Scene description is required.', 'error')
    return
  }
  if (newDesc.length > 1000) {
    notificationService.add('Scene description must be 1000 characters or less.', 'error')
    return
  }
  if (newDesc === String(scene.description || '')) {
    isEditingSceneDesc.value = false
    return
  }
  localIsSavingText.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: String(scene.id),
      name: scene.label || scene.name,
      description: newDesc,
    })
    emit('refresh')
    notificationService.add('Scene description updated.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update scene description.', 'error')
  } finally {
    localIsSavingText.value = false
    isEditingSceneDesc.value = false
  }
}

function cancelSceneNameEdit() {
  isEditingSceneName.value = false
  sceneNameEdit.value = ''
}

function cancelSceneDescEdit() {
  isEditingSceneDesc.value = false
  sceneDescEdit.value = ''
}

async function handleGenerateSceneDesc() {
  const sceneName = routeSceneDetails.value?.label || routeSceneDetails.value?.name
  if (!props.adventureId || !sceneName) return
  isGeneratingSceneDesc.value = true
  try {
    const result = await entityService.generateSceneDescription(props.adventureId, sceneName)
    sceneDescEdit.value = result.description
    notificationService.add('AI generated scene description.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to generate scene description.', 'error')
  } finally {
    isGeneratingSceneDesc.value = false
  }
}

function shouldShowSceneGroup(filteredCount: number): boolean {
  return !hideEmptyFilteredGroups.value || filteredCount > 0
}

function buildVisualImageUrl(imagePath?: string | null) {
  return visualService.buildImageUrl(imagePath, props.visualsCacheVersion)
}

function hasMissingImage(entity: any): boolean {
  const raw = String(entity?.image_url || '').trim()
  if (!raw) return true
  const lowered = raw.toLowerCase()
  if (lowered.startsWith('assets/') || lowered.startsWith('/assets/')) return true
  if (lowered.includes('placeholder_') || lowered.includes('/placeholder-')) return true
  return false
}

function editRouteEntity(type: 'npc' | 'object', entity: any) {
  if (!entity) return
  emit(
    'open-text-edit',
    type,
    String(entity.id || ''),
    String(entity.name || entity.id || ''),
    String(entity.description || ''),
    '',
    entity.hp,
    entity.stamina,
    entity.mana,
    entity.goal,
    entity.character,
    entity.is_killable,
  )
}
</script>

<template>
  <section class="space-y-4 animate-page-in">
    <div class="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
      <button
        class="flex items-center gap-2 px-3 py-1.5 text-xs font-black uppercase tracking-[0.15em] rounded-lg border border-white/10 bg-slate-900/40 text-slate-300 hover:text-white hover:bg-white/5 transition-all"
        @click="emit('back')"
      >
        <ArrowLeft class="w-4 h-4" />
        Back to Scenes
      </button>
    </div>

    <!-- Scene Details Card -->
    <div class="bg-slate-900/40 border border-white/5 rounded-2xl p-6 backdrop-blur-md space-y-6 shadow-xl text-slate-200">
      <!-- Card Header -->
      <div class="flex items-center justify-between gap-4 border-b border-white/5 pb-4">
        <div class="flex items-center gap-3">
          <span class="px-2.5 py-1 rounded-md bg-slate-950/80 border border-white/10 text-xs font-mono text-emerald-400 tracking-wider">
            {{ routeSceneDetails?.id || sceneId }}
          </span>
          <h4 class="text-xs font-black text-slate-400 uppercase tracking-[0.25em]">Scene Editor</h4>
        </div>
        <button
          class="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all duration-200 border border-white/5 hover:border-red-500/20 bg-slate-950/40"
          :disabled="isDeletingRouteAsset"
          @click="emit('request-delete-scene')"
          title="Delete Scene"
        >
          <Trash2 class="w-4.5 h-4.5" />
        </button>
      </div>

      <!-- Card Body -->
      <div class="space-y-6">
        <!-- Scene Name Column -->
        <div class="space-y-2">
          <div class="flex justify-between items-center">
            <label class="block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Scene Name <span class="text-red-400">*</span></label>
            <span v-if="isEditingSceneName" :class="['text-[9px] font-bold tracking-widest', (sceneNameEdit || '').length > 100 ? 'text-red-500' : 'text-emerald-500/50']">
              {{ (sceneNameEdit || '').length }} / 100
            </span>
          </div>
          <div v-if="isEditingSceneName" class="flex gap-2 animate-fade-in">
            <input
              ref="sceneNameInputRef"
              v-model="sceneNameEdit"
              maxlength="100"
              class="flex-grow bg-slate-950/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all"
              @keydown.enter="saveSceneNameEdit"
              @keydown.esc="cancelSceneNameEdit"
            />
            <button
              :disabled="localIsSavingText || isSavingText || !(sceneNameEdit || '').trim()"
              class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg shrink-0"
              title="Save"
              @click="saveSceneNameEdit"
            >
              <i v-if="localIsSavingText || isSavingText" class="ra ra-cycle animate-spin"></i>
              <Save v-else class="w-4 h-4" />
            </button>
            <button
              class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all shrink-0"
              title="Discard"
              @click="cancelSceneNameEdit"
            >
              <X class="w-4 h-4" />
            </button>
          </div>
          <div
            v-else
            class="group cursor-pointer bg-slate-950/30 hover:bg-slate-950/50 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-3 transition-all duration-300 shadow-inner flex justify-between items-center h-[46px]"
            @click="startEditingSceneName"
          >
            <span class="text-sm font-bold text-white truncate mr-2">{{ routeSceneDetails?.label || routeSceneDetails?.name || routeSceneDetails?.id || sceneId }}</span>
            <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"></i>
          </div>
        </div>

        <!-- Scene Description Column -->
        <div class="space-y-2">
          <div class="flex justify-between items-center">
            <label class="block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Description <span class="text-red-400">*</span></label>
            <span v-if="isEditingSceneDesc" :class="['text-[9px] font-bold tracking-widest', (sceneDescEdit || '').length > 1000 ? 'text-red-500' : 'text-emerald-500/50']">
              {{ (sceneDescEdit || '').length }} / 1000
            </span>
          </div>
          <div v-if="isEditingSceneDesc" class="flex gap-2 animate-fade-in">
            <textarea
              ref="sceneDescInputRef"
              v-model="sceneDescEdit"
              maxlength="1000"
              rows="3"
              class="flex-grow bg-slate-950/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm focus:ring-2 ring-emerald-500/20 outline-none transition-all resize-none"
              @keydown.esc="cancelSceneDescEdit"
            ></textarea>
            <div class="flex flex-col gap-1.5 shrink-0">
              <button
                :disabled="localIsSavingText || isSavingText || !(sceneDescEdit || '').trim()"
                class="p-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg"
                title="Save"
                @click="saveSceneDescEdit"
              >
                <i v-if="localIsSavingText || isSavingText" class="ra ra-cycle animate-spin"></i>
                <Save v-else class="w-4 h-4" />
              </button>
              <button
                type="button"
                :disabled="localIsSavingText || isSavingText || isGeneratingSceneDesc || !(routeSceneDetails?.label || routeSceneDetails?.name)"
                class="p-2.5 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-400 rounded-xl transition-all"
                title="AI Generate Description"
                @click="handleGenerateSceneDesc"
              >
                <i class="ra ra-crystals" :class="{ 'animate-spin': isGeneratingSceneDesc }"></i>
              </button>
              <button
                class="p-2.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-xl transition-all"
                title="Discard"
                @click="cancelSceneDescEdit"
              >
                <X class="w-4 h-4" />
              </button>
            </div>
          </div>
          <div
            v-else
            class="group cursor-pointer bg-slate-950/30 hover:bg-slate-950/50 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-3 transition-all duration-300 shadow-inner flex justify-between items-start min-h-[46px]"
            @click="startEditingSceneDesc"
          >
            <span class="text-sm text-slate-300 break-words flex-grow mr-2" v-html="formatObjectIds(routeSceneDetails?.description || 'No description.')"></span>
            <i class="ra ra-quill-pen text-xs text-emerald-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 mt-0.5"></i>
          </div>
        </div>
      </div>
    </div>

    <div class="grid md:grid-cols-2 gap-3 text-slate-200">
      <label class="text-xs text-slate-300 space-y-1">
        <span>Filter Scene Content</span>
        <input
          v-model="routeSceneSearch"
          class="w-full bg-slate-950 border border-white/10 rounded px-2 py-1 text-sm text-white"
          placeholder="Search by id, name, label, description..."
        />
      </label>
      <div class="flex items-end justify-end gap-2">
        <label class="px-3 py-2 text-xs font-bold rounded border border-white/15 text-slate-300 hover:text-white hover:bg-white/5 flex items-center gap-2 cursor-pointer">
          <input v-model="hideEmptyFilteredGroups" type="checkbox" class="accent-emerald-500" />
          Hide Empty Groups
        </label>
        <button class="px-3 py-2 text-xs font-bold rounded border border-white/15 text-slate-300 hover:text-white hover:bg-white/5" @click="routeSceneSearch = ''">
          Clear Filter
        </button>
      </div>
    </div>

    <div class="space-y-4">
      <div v-if="shouldShowSceneGroup(filteredRouteSceneNpcs.length)" class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">NPCs ({{ filteredRouteSceneNpcs.length }}/{{ routeSceneNpcs.length }})</p>
          <div class="flex items-center gap-4">
            <button @click="emit('regen-all', 'npc', true)" :disabled="isBatchGenerating['npc']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['npc'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'npc', false)" :disabled="isBatchGenerating['npc']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['npc'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-text-edit', 'npc', 'NEW_NPC', 'New NPC', 'A mysterious inhabitant of this scene.', '', 20, 20, 20, '', '', true)">+ Add</button>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
          <article
            v-for="npc in filteredRouteSceneNpcs"
            :key="npc.id"
            :class="[
              'relative group aspect-square bg-slate-900 border border-white/10 rounded-xl shadow-lg overflow-visible',
              activeMenuId === `scene-npc-${npc.id}` ? 'z-[180]' : 'z-0 hover:z-30',
            ]"
          >
            <img v-if="npc.image_url" :src="buildVisualImageUrl(npc.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-else class="absolute inset-0 bg-slate-900 flex items-center justify-center text-slate-600">
              <i class="ra ra-player text-3xl"></i>
            </div>
            <div v-if="isQuickGenerating['npc_' + npc.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(npc)" class="absolute top-2 right-10 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-20">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/25 to-transparent opacity-80"></div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-sky-400/50 bg-sky-500/20 text-sky-100">NPC</div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ npc.name || npc.id }}</div>
              <div class="text-[9px] text-sky-200/80 uppercase tracking-widest truncate mt-1">{{ npc.id }}</div>
            </div>
            <div class="absolute top-2 right-2 z-40">
              <button
                @click="emit('toggle-menu', `scene-npc-${npc.id}`, $event)"
                class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg"
              >
                <div class="flex flex-col gap-0.5">
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                </div>
              </button>
              <div v-if="activeMenuId === `scene-npc-${npc.id}`" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'npc', npc.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'npc', npc.id, npc.name || npc.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'npc', npc.id, npc.name || npc.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="npc.image_url" @click="emit('download-asset', npc.image_url, `${npc.name || 'npc'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="editRouteEntity('npc', npc)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', npc.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-red-500 hover:text-white transition-all">Delete</button>
              </div>
            </div>
          </article>
          <div v-if="filteredRouteSceneNpcs.length === 0" class="text-xs text-slate-500">No NPCs match the current filter.</div>
        </div>
      </div>

      <div v-if="shouldShowSceneGroup(filteredRouteSceneItems.length)" class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Items ({{ filteredRouteSceneItems.length }}/{{ routeSceneItems.length }})</p>
          <div class="flex items-center gap-4">
            <button @click="emit('regen-all', 'object', true)" :disabled="isBatchGenerating['object']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'object', false)" :disabled="isBatchGenerating['object']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-item')">+ Add</button>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
          <article
            v-for="obj in filteredRouteSceneItems"
            :key="obj.id"
            :class="[
              'relative group aspect-square bg-slate-900 border border-white/10 rounded-xl shadow-lg overflow-visible',
              activeMenuId === `scene-item-${obj.id}` ? 'z-[180]' : 'z-0 hover:z-30',
            ]"
          >
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-else class="absolute inset-0 bg-slate-900 flex items-center justify-center text-slate-600">
              <i class="ra ra-key text-3xl"></i>
            </div>
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-10 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-20">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/25 to-transparent opacity-80"></div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-white/20 bg-white/10 text-slate-200">{{ obj.item_type || 'ITEM' }}</div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name || obj.id }}</div>
            </div>
            <div class="absolute top-2 right-2 z-40">
              <button
                @click="emit('toggle-menu', `scene-item-${obj.id}`, $event)"
                class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg"
              >
                <div class="flex flex-col gap-0.5">
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                </div>
              </button>
              <div v-if="activeMenuId === `scene-item-${obj.id}`" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name || obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'object', obj.id, obj.name || obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'object'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="editRouteEntity('object', obj)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-red-500 hover:text-white transition-all">Delete</button>
              </div>
            </div>
          </article>
          <div v-if="filteredRouteSceneItems.length === 0" class="text-xs text-slate-500">No items match the current filter.</div>
        </div>
      </div>

      <div v-if="shouldShowSceneGroup(filteredRouteSceneSwitches.length)" class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Switches ({{ filteredRouteSceneSwitches.length }}/{{ routeSceneSwitches.length }})</p>
          <div class="flex items-center gap-4">
            <button @click="emit('regen-all', 'switch', true)" :disabled="isBatchGenerating['switch']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['switch'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'switch', false)" :disabled="isBatchGenerating['switch']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['switch'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-item', 'SWITCH')">+ Add</button>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
          <article
            v-for="obj in filteredRouteSceneSwitches"
            :key="obj.id"
            :class="[
              'relative group aspect-square bg-slate-900 border border-lime-500/20 rounded-xl shadow-lg overflow-visible',
              activeMenuId === `scene-switch-${obj.id}` ? 'z-[180]' : 'z-0 hover:z-30',
            ]"
          >
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-else class="absolute inset-0 bg-slate-900 flex items-center justify-center text-slate-600">
              <i class="ra ra-lightning-bolt text-3xl"></i>
            </div>
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-10 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-20">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/25 to-transparent opacity-80"></div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-lime-400/50 bg-lime-500/20 text-lime-100">SWITCH</div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name || obj.id }}</div>
            </div>
            <div class="absolute top-2 right-2 z-40">
              <button
                @click="emit('toggle-menu', `scene-switch-${obj.id}`, $event)"
                class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg"
              >
                <div class="flex flex-col gap-0.5">
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                </div>
              </button>
              <div v-if="activeMenuId === `scene-switch-${obj.id}`" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name || obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'object', obj.id, obj.name || obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'switch'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="editRouteEntity('object', obj)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-red-500 hover:text-white transition-all">Delete</button>
              </div>
            </div>
          </article>
          <div v-if="filteredRouteSceneSwitches.length === 0" class="text-xs text-slate-500">No switches match the current filter.</div>
        </div>
      </div>

      <div v-if="shouldShowSceneGroup(filteredRouteSceneContainers.length)" class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Containers ({{ filteredRouteSceneContainers.length }}/{{ routeSceneContainers.length }})</p>
          <div class="flex items-center gap-4">
            <button @click="emit('regen-all', 'container', true)" :disabled="isBatchGenerating['container']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['container'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'container', false)" :disabled="isBatchGenerating['container']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['container'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-item', 'CONTAINER')">+ Add</button>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
          <article
            v-for="obj in filteredRouteSceneContainers"
            :key="obj.id"
            :class="[
              'relative group aspect-square bg-slate-900 border border-amber-500/20 rounded-xl shadow-lg overflow-visible',
              activeMenuId === `scene-container-${obj.id}` ? 'z-[180]' : 'z-0 hover:z-30',
            ]"
          >
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-else class="absolute inset-0 bg-slate-900 flex items-center justify-center text-slate-600">
              <i class="ra ra-chest text-3xl"></i>
            </div>
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-10 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-20">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/25 to-transparent opacity-80"></div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-amber-400/50 bg-amber-500/25 text-amber-100">CONTAINER</div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name || obj.id }}</div>
            </div>
            <div class="absolute top-2 right-2 z-40">
              <button
                @click="emit('toggle-menu', `scene-container-${obj.id}`, $event)"
                class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg"
              >
                <div class="flex flex-col gap-0.5">
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                </div>
              </button>
              <div v-if="activeMenuId === `scene-container-${obj.id}`" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name || obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'object', obj.id, obj.name || obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'container'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="editRouteEntity('object', obj)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-red-500 hover:text-white transition-all">Delete</button>
              </div>
            </div>
          </article>
          <div v-if="filteredRouteSceneContainers.length === 0" class="text-xs text-slate-500">No containers match the current filter.</div>
        </div>
      </div>

      <div v-if="shouldShowSceneGroup(filteredRouteSceneTextLogs.length)" class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Text Logs ({{ filteredRouteSceneTextLogs.length }}/{{ routeSceneTextLogs.length }})</p>
          <div class="flex items-center gap-4">
            <button @click="emit('regen-all', 'text-log', true)" :disabled="isBatchGenerating['text-log']" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['text-log'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'text-log', false)" :disabled="isBatchGenerating['text-log']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['text-log'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-item', 'READABLE')">+ Add</button>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
          <article
            v-for="obj in filteredRouteSceneTextLogs"
            :key="obj.id"
            :class="[
              'relative group aspect-square bg-slate-900 border border-cyan-500/20 rounded-xl shadow-lg overflow-visible',
              activeMenuId === `scene-log-${obj.id}` ? 'z-[180]' : 'z-0 hover:z-30',
            ]"
          >
            <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
            <div v-else class="absolute inset-0 bg-slate-900 flex items-center justify-center text-slate-600">
              <i class="ra ra-scroll-unfurled text-3xl"></i>
            </div>
            <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
              <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
            </div>
            <div v-if="hasMissingImage(obj)" class="absolute top-2 right-10 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-rose-400/50 bg-rose-500/25 text-rose-100 z-20">MISSING</div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/25 to-transparent opacity-80"></div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-cyan-500/40 bg-cyan-500/20 text-cyan-200">LOG</div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name || obj.id }}</div>
            </div>
            <div class="absolute top-2 right-2 z-40">
              <button
                @click="emit('toggle-menu', `scene-log-${obj.id}`, $event)"
                class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg"
              >
                <div class="flex flex-col gap-0.5">
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                </div>
              </button>
              <div v-if="activeMenuId === `scene-log-${obj.id}`" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name || obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'object', obj.id, obj.name || obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'text-log'}_image`)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="editRouteEntity('object', obj)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-red-500 hover:text-white transition-all">Delete</button>
              </div>
            </div>
          </article>
          <div v-if="filteredRouteSceneTextLogs.length === 0" class="text-xs text-slate-500">No text logs match the current filter.</div>
        </div>
      </div>

      <div v-if="shouldShowSceneGroup(filteredRouteSceneExits.length)" class="bg-slate-950/70 border border-white/5 rounded-xl p-3">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Exits ({{ filteredRouteSceneExits.length }}/{{ routeSceneExits.length }})</p>
          <div class="flex items-center gap-4">
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-exit')">+ Add</button>
          </div>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-3">
          <article
            v-for="worldExit in filteredRouteSceneExits"
            :key="worldExit.id"
            :class="[
              'relative group aspect-square bg-slate-900 border border-emerald-500/20 rounded-xl shadow-lg overflow-visible',
              activeMenuId === `scene-exit-${worldExit.id}` ? 'z-[180]' : 'z-0 hover:z-30',
            ]"
          >
            <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.22),transparent_55%)]"></div>
            <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-85"></div>
            <div class="absolute top-2 left-2 px-1.5 py-0.5 rounded-full text-[9px] font-black tracking-wide border border-emerald-400/50 bg-emerald-500/20 text-emerald-100">EXIT</div>
            <div class="absolute bottom-0 left-0 right-0 p-2">
              <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ worldExit.label || worldExit.id }}</div>
              <div class="text-[9px] text-emerald-200/80 uppercase tracking-widest truncate mt-1">{{ worldExit.exit_type || 'one_way' }}</div>
            </div>
            <div class="absolute top-2 right-2 z-40">
              <button
                @click="emit('toggle-menu', `scene-exit-${worldExit.id}`, $event)"
                class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg"
              >
                <div class="flex flex-col gap-0.5">
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                  <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                </div>
              </button>
              <div v-if="activeMenuId === `scene-exit-${worldExit.id}`" class="absolute right-0 mt-1 w-44 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('open-exit', worldExit.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Open Route</button>
                <button @click="emit('open-edit-exit', worldExit.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-exit', worldExit.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-red-500 hover:text-white transition-all">Delete</button>
              </div>
            </div>
          </article>
          <div v-if="filteredRouteSceneExits.length === 0" class="text-xs text-slate-500">No exits match the current filter.</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

input, textarea {
  transition: all 0.3s ease;
}

.shadow-inner {
  box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.4);
}
</style>
