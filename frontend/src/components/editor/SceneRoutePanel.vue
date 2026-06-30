<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { entityService } from '@/services/entityService'
import { visualService } from '@/services/visualService'
import { notificationService } from '@/services/notificationService'
import { 
  isNpcEntity, 
  isObjectEntity, 
  mergeUniqueById, 
  formatObjectIds,
} from '@/utils/editor_utils'
import { Save, X, Trash2, ArrowLeft, Sparkles } from 'lucide-vue-next'
import InlineEditableField from '@/components/editor/InlineEditableField.vue'

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
  returnTabLabel?: string
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'open-text-edit', type: string, id: string, name: string, description: string, teaser?: string, hp?: number, stamina?: number, mana?: number, goal?: string, character?: string, isKillable?: boolean): void
  (e: 'open-create-item', itemType?: string): void
  (e: 'open-add-existing', kind: 'items' | 'switch' | 'container' | 'text-log' | 'npc'): void
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
  (e: 'clone-entity', entityType: 'npc' | 'object', entityId: string): void
  (e: 'quick-regen', kind: string, id: string): void
  (e: 'regen-all', kind: string, missingOnly?: boolean): void
  (e: 'refresh'): void
  (e: 'scene-id-changed', oldId: string, newId: string): void
}>()

// Local states for editing name and description
const sceneDescFieldRef = ref<any>(null)
const isGeneratingSceneDesc = ref(false)

// Decorative Background Details editing
const newDecorativeInput = ref('')

async function addDecorativeObject() {
  const scene = routeSceneDetails.value
  if (!scene) return
  const val = newDecorativeInput.value.trim()
  if (!val) return
  
  const currentDecor = [...(scene.decorative_objects || [])]
  if (currentDecor.length >= 7) {
    notificationService.add('Maximum of 7 decorative details allowed.', 'error')
    return
  }
  
  if (currentDecor.includes(val)) {
    notificationService.add('This detail already exists.', 'error')
    return
  }
  
  currentDecor.push(val)
  newDecorativeInput.value = ''
  
  localIsSavingText.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: String(scene.id),
      decorative_objects: currentDecor,
    })
    emit('refresh')
    notificationService.add('Decorative background details updated.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update decorative background details.', 'error')
  } finally {
    localIsSavingText.value = false
  }
}

async function removeDecorativeObject(index: number) {
  const scene = routeSceneDetails.value
  if (!scene) return
  
  const currentDecor = [...(scene.decorative_objects || [])]
  currentDecor.splice(index, 1)
  
  localIsSavingText.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: String(scene.id),
      decorative_objects: currentDecor,
    })
    emit('refresh')
    notificationService.add('Decorative background details updated.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update decorative background details.', 'error')
  } finally {
    localIsSavingText.value = false
  }
}

// Inline Scene ID editing
const isEditingSceneId = ref(false)
const editingSceneIdValue = ref('')
const isSavingSceneId = ref(false)

const sceneIdError = computed(() => {
  const val = editingSceneIdValue.value.trim().toUpperCase()
  if (!val) return 'ID is required.'
  if (!/^[A-Z0-9_]+$/.test(val)) return 'Only uppercase letters, digits and underscores allowed.'
  if (val.length > 50) return 'Max 50 characters.'
  const currentId = String(routeSceneDetails.value?.id || props.sceneId || '').toUpperCase()
  const taken = (props.referenceOptions || [])
    .map((e: any) => String(e.id || '').toUpperCase())
    .filter((id) => id !== currentId)
  if (taken.includes(val)) return `ID "${val}" already exists.`
  return ''
})

function startEditSceneId() {
  if (isSavingSceneId.value) return
  editingSceneIdValue.value = String(routeSceneDetails.value?.id || props.sceneId || '')
  isEditingSceneId.value = true
}

function cancelEditSceneId() {
  isEditingSceneId.value = false
  editingSceneIdValue.value = ''
}

async function saveSceneId() {
  const scene = routeSceneDetails.value
  if (!scene) return
  const newId = editingSceneIdValue.value.trim().toUpperCase()
  if (sceneIdError.value || !newId) return
  const oldId = String(scene.id)
  if (newId === oldId) {
    cancelEditSceneId()
    return
  }
  isSavingSceneId.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: oldId,
      new_id: newId,
      name: scene.label || scene.name,
      description: scene.description,
    })
    isEditingSceneId.value = false
    editingSceneIdValue.value = ''
    notificationService.add('Scene ID updated.', 'success')
    emit('scene-id-changed', oldId, newId)
    emit('refresh')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update Scene ID.', 'error')
  } finally {
    isSavingSceneId.value = false
  }
}

watch(() => editingSceneIdValue.value, (val) => {
  editingSceneIdValue.value = val.toUpperCase().replace(/[^A-Z0-9_]/g, '')
})

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

function isSpecialItemType(itemType: string): boolean {
  const t = String(itemType || '').toUpperCase()
  return t === 'SWITCH' || t === 'CONTAINER' || t === 'READABLE'
}

const availableItemsForType = computed<any[]>(() => {
  const sId = String(props.sceneId || '').trim()
  return editorAllObjects.value.filter((obj: any) => {
    if (String(obj.current_scene_id || '') === sId) return false
    const t = String(obj.item_type || '').toUpperCase()
    return !isSpecialItemType(t)
  })
})

const availableSwitchesForType = computed<any[]>(() => {
  const sId = String(props.sceneId || '').trim()
  return editorAllObjects.value.filter((obj: any) => {
    if (String(obj.current_scene_id || '') === sId) return false
    return String(obj.item_type || '').toUpperCase() === 'SWITCH'
  })
})

const availableContainersForType = computed<any[]>(() => {
  const sId = String(props.sceneId || '').trim()
  return editorAllObjects.value.filter((obj: any) => {
    if (String(obj.current_scene_id || '') === sId) return false
    return String(obj.item_type || '').toUpperCase() === 'CONTAINER'
  })
})

const availableTextLogsForType = computed<any[]>(() => {
  const sId = String(props.sceneId || '').trim()
  return editorAllObjects.value.filter((obj: any) => {
    if (String(obj.current_scene_id || '') === sId) return false
    return String(obj.item_type || '').toUpperCase() === 'READABLE'
  })
})

const availableNpcsForType = computed<any[]>(() => {
  const sId = String(props.sceneId || '').trim()
  return editorNpcs.value.filter((npc: any) => String(npc.current_scene_id || '') !== sId)
})
const filteredRouteSceneExits = computed(() => routeSceneExits.value.filter((entry) => matchesRouteSceneSearch(entry)))

// Actions
async function saveSceneName(newName: any) {
  const scene = routeSceneDetails.value
  if (!scene) return
  const nameStr = String(newName).trim()
  if (!nameStr) {
    notificationService.add('Scene name is required.', 'error')
    return
  }
  localIsSavingText.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: String(scene.id),
      name: nameStr,
      description: scene.description,
    })
    emit('refresh')
    notificationService.add('Scene name updated.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update scene name.', 'error')
  } finally {
    localIsSavingText.value = false
  }
}

async function saveSceneDesc(newDesc: any) {
  const scene = routeSceneDetails.value
  if (!scene) return
  const descStr = String(newDesc).trim()
  if (!descStr) {
    notificationService.add('Scene description is required.', 'error')
    return
  }
  localIsSavingText.value = true
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: 'scene',
      target_id: String(scene.id),
      name: scene.label || scene.name,
      description: descStr,
    })
    emit('refresh')
    notificationService.add('Scene description updated.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to update scene description.', 'error')
  } finally {
    localIsSavingText.value = false
  }
}

async function handleGenerateSceneDesc() {
  const sceneName = routeSceneDetails.value?.label || routeSceneDetails.value?.name
  if (!props.adventureId || !sceneName) return
  isGeneratingSceneDesc.value = true
  try {
    const result = await entityService.generateSceneDescription(props.adventureId, sceneName)
    sceneDescFieldRef.value?.setEditValue(result.description)
    notificationService.add('AI generated scene description.', 'success')
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to generate scene description.', 'error')
  } finally {
    isGeneratingSceneDesc.value = false
  }
}

const isGeneratingDecorativeItems = ref(false)

async function handleGenerateDecorativeItems() {
  const scene = routeSceneDetails.value
  if (!scene || !props.adventureId) return
  const sceneName = scene.label || scene.name || scene.id
  const currentDecor: string[] = Array.isArray(scene.decorative_objects) ? scene.decorative_objects : []
  if (currentDecor.length >= 7) {
    notificationService.add('Maximum of 7 decorative details allowed.', 'error')
    return
  }

  const adventureTheme = props.debugData?.adventure?.plot || props.debugData?.adventure?.original_prompt || undefined
  const sceneDescription = scene.description || ''

  isGeneratingDecorativeItems.value = true
  try {
    const result = await entityService.generateDecorativeItems(
      props.adventureId,
      sceneName,
      currentDecor,
      { description: sceneDescription, adventureTheme }
    )
    const fresh = (result.items || []).filter((item) => item && !currentDecor.includes(item))
    if (fresh.length === 0) {
      notificationService.add('AI had no new suggestions for this scene.', 'info')
      return
    }
    const merged = [...currentDecor, ...fresh].slice(0, 7)
    localIsSavingText.value = true
    try {
      await entityService.saveEntityText(props.adventureId, {
        target_type: 'scene',
        target_id: String(scene.id),
        decorative_objects: merged,
      })
      emit('refresh')
      notificationService.add(`Added ${fresh.length} decorative ${fresh.length === 1 ? 'detail' : 'details'}.`, 'success')
    } catch (error: any) {
      notificationService.add(error?.message || 'Failed to save decorative background details.', 'error')
    } finally {
      localIsSavingText.value = false
    }
  } catch (error: any) {
    notificationService.add(error?.message || 'Failed to generate decorative background details.', 'error')
  } finally {
    isGeneratingDecorativeItems.value = false
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
        Back to {{ props.returnTabLabel || 'Scenes' }}
      </button>
    </div>

    <!-- Scene Details Card -->
    <div class="bg-slate-900/40 border border-white/5 rounded-2xl p-6 backdrop-blur-md space-y-6 shadow-xl text-slate-200">
      <!-- Card Header -->
      <div class="flex items-center justify-between gap-4 border-b border-white/5 pb-4">
        <div class="flex items-center gap-3 flex-1 min-w-0">
          <!-- Inline Scene ID Editor -->
          <div class="flex items-center gap-2 flex-1 min-w-0">
            <template v-if="isEditingSceneId">
              <div class="flex-1 min-w-0 space-y-1">
                <div class="flex items-center gap-2">
                  <input
                    v-model="editingSceneIdValue"
                    maxlength="50"
                    class="flex-1 min-w-0 bg-slate-950/80 border rounded-lg px-3 py-1.5 text-xs font-mono font-bold text-amber-300 focus:outline-none uppercase tracking-wider transition-all"
                    :class="sceneIdError ? 'border-red-500/70 focus:border-red-500' : 'border-emerald-500/50 focus:border-emerald-400'"
                    placeholder="SCENE_ID"
                    @keydown.enter="saveSceneId"
                    @keydown.esc="cancelEditSceneId"
                    autofocus
                  />
                  <button
                    @click="saveSceneId"
                    :disabled="!!sceneIdError || isSavingSceneId"
                    class="shrink-0 p-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white rounded-lg transition-all"
                    title="Save ID"
                  >
                    <i v-if="isSavingSceneId" class="ra ra-cycle animate-spin text-xs"></i>
                    <Save v-else class="w-3.5 h-3.5" />
                  </button>
                  <button
                    @click="cancelEditSceneId"
                    :disabled="isSavingSceneId"
                    class="shrink-0 p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-lg transition-all"
                    title="Cancel"
                  >
                    <X class="w-3.5 h-3.5" />
                  </button>
                </div>
                <p v-if="sceneIdError" class="text-[10px] text-red-400 font-bold pl-1">{{ sceneIdError }}</p>
              </div>
            </template>
            <template v-else>
              <button
                class="px-2.5 py-1 rounded-md bg-slate-950/80 border border-white/10 text-xs font-mono text-emerald-400 tracking-wider hover:border-emerald-500/50 hover:bg-emerald-500/10 transition-all cursor-pointer shrink-0"
                title="Click to edit Scene ID"
                @click="startEditSceneId"
              >
                {{ routeSceneDetails?.id || sceneId }}
              </button>
              <h4 class="text-xs font-black text-slate-400 uppercase tracking-[0.25em]">Scene Editor</h4>
            </template>
          </div>
        </div>
        <button
          class="shrink-0 p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all duration-200 border border-white/5 hover:border-red-500/20 bg-slate-950/40"
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
          </div>
          <InlineEditableField
            :value="routeSceneDetails?.label || routeSceneDetails?.name || routeSceneDetails?.id || sceneId"
            type="text"
            :maxlength="100"
            required
            :is-saving="localIsSavingText || isSavingText"
            display-class="group cursor-pointer bg-slate-950/30 hover:bg-slate-950/50 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-3 transition-all duration-300 shadow-inner flex justify-between items-center w-full min-h-[46px]"
            input-class="flex-grow min-w-0 w-full bg-slate-950/60 border border-emerald-500/50 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:ring-2 ring-emerald-500/20 outline-none transition-all"
            @save="saveSceneName"
          />
        </div>

        <!-- Scene Description Column -->
        <div class="space-y-2">
          <div class="flex justify-between items-center">
            <label class="block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Description <span class="text-red-400">*</span></label>
          </div>
          <InlineEditableField
            ref="sceneDescFieldRef"
            :value="routeSceneDetails?.description || ''"
            type="textarea"
            :maxlength="1000"
            required
            :use-references="true"
            :reference-options="referenceOptions"
            :is-saving="localIsSavingText || isSavingText"
            :show-ai-generate="true"
            :is-generating-ai="isGeneratingSceneDesc"
            display-class="group cursor-pointer bg-slate-950/30 hover:bg-slate-950/50 border border-white/5 hover:border-emerald-500/30 rounded-xl px-4 py-3 transition-all duration-300 shadow-inner flex justify-between items-start w-full min-h-[46px]"
            @save="saveSceneDesc"
            @ai-generate="handleGenerateSceneDesc"
          >
            <template #default="{ value }">
              <span class="text-sm text-slate-300 break-words flex-grow mr-2" v-html="formatObjectIds(String(value || 'No description.'))"></span>
            </template>
          </InlineEditableField>
        </div>

        <!-- Decorative Background Details Column -->
        <div class="space-y-2">
          <div class="flex flex-wrap justify-between items-center gap-2">
            <label class="block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Decorative Background Details <span class="text-slate-400">({{ (routeSceneDetails?.decorative_objects || []).length }}/7)</span></label>
            <div class="flex items-center gap-2">
              <span class="text-[9px] text-slate-400 font-medium hidden sm:inline">Simple, static background details (max 7)</span>
              <button
                v-if="(routeSceneDetails?.decorative_objects || []).length < 7"
                type="button"
                @click="handleGenerateDecorativeItems"
                :disabled="isGeneratingDecorativeItems || localIsSavingText"
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-cyan-400/20 bg-cyan-500/10 text-cyan-300 text-[9px] font-black uppercase tracking-widest transition-all hover:bg-cyan-500/20 disabled:opacity-40 disabled:cursor-not-allowed shrink-0"
                title="Use the Simple LLM to suggest decorative background details that fit this scene"
              >
                <Sparkles :class="['w-3 h-3', isGeneratingDecorativeItems ? 'animate-spin' : '']" />
                {{ isGeneratingDecorativeItems ? 'Generating...' : 'AI Generate' }}
              </button>
            </div>
          </div>
          <div class="bg-slate-950/30 border border-white/5 rounded-xl p-4 space-y-3 shadow-inner">
            <!-- Existing Tags -->
            <div class="flex flex-wrap gap-2">
              <div 
                v-for="(item, idx) in (routeSceneDetails?.decorative_objects || [])" 
                :key="idx"
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 bg-slate-900/60 text-xs text-slate-300 hover:text-white hover:border-white/20 transition-all shadow-sm"
              >
                <span>{{ item }}</span>
                <button
                  type="button"
                  @click="removeDecorativeObject(idx)"
                  class="text-slate-500 hover:text-red-400 transition-colors cursor-pointer"
                  title="Remove detail"
                >
                  <X class="w-3.5 h-3.5" />
                </button>
              </div>
              <div v-if="!(routeSceneDetails?.decorative_objects || []).length" class="text-xs text-slate-500 italic py-1">
                No decorative details added yet. These fill the room with static items (e.g. "metal table", "bookshelf").
              </div>
            </div>

            <!-- Add Input -->
            <div v-if="(routeSceneDetails?.decorative_objects || []).length < 7" class="flex gap-2 items-center">
              <input
                v-model="newDecorativeInput"
                type="text"
                maxlength="100"
                placeholder="e.g. metal table, light fixture, sterile kacheln..."
                class="flex-1 bg-slate-950/80 border border-white/10 rounded-xl px-4 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50 focus:ring-2 ring-emerald-500/10 placeholder-slate-600 transition-all font-medium"
                @keydown.enter="addDecorativeObject"
              />
              <button
                type="button"
                @click="addDecorativeObject"
                :disabled="!newDecorativeInput.trim() || localIsSavingText"
                class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white font-black text-[10px] uppercase tracking-wider rounded-xl transition-all shadow-md flex items-center gap-1 shrink-0 cursor-pointer"
              >
                Add Detail
              </button>
            </div>
            <div v-else class="text-[10px] text-amber-400 font-bold uppercase tracking-wider pl-1">
              Maximum limit of 7 decorative details reached.
            </div>
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
            <button @click="emit('regen-all', 'npc', true)" :disabled="isBatchGenerating['npc']" title="Generate portrait images for NPCs that are still missing one (does not create new NPCs)" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['npc'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'npc', false)" :disabled="isBatchGenerating['npc']" title="Re-render portrait images for every NPC in this scene (does not create new NPCs)" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['npc'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-text-edit', 'npc', 'NEW_NPC', 'New NPC', 'A mysterious inhabitant of this scene.', '', 20, 20, 20, '', '', true)">+ Create</button>
            <button
              class="text-xs font-bold text-amber-400 hover:text-amber-300 uppercase tracking-widest transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="availableNpcsForType.length === 0"
              :title="availableNpcsForType.length === 0 ? 'No other NPCs exist in the adventure' : 'Place an existing NPC from another scene into this scene'"
              @click="emit('open-add-existing', 'npc')"
            >+ Add Existing</button>
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
              <div v-if="activeMenuId === `scene-npc-${npc.id}`" class="absolute right-0 mt-1 w-48 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'npc', npc.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'npc', npc.id, npc.name || npc.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'npc', npc.id, npc.name || npc.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="npc.image_url" @click="emit('download-asset', npc.image_url, `${npc.name || 'npc'}_image`)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="emit('clone-entity', 'npc', npc.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Clone</button>
                <button @click="editRouteEntity('npc', npc)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', npc.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
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
            <button @click="emit('regen-all', 'object', true)" :disabled="isBatchGenerating['object']" title="Generate item images for items in this list that are still missing one (does not create new items)" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'object', false)" :disabled="isBatchGenerating['object']" title="Re-render item images for every item in this list (does not create new items)" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-item')">+ Create</button>
            <button
              class="text-xs font-bold text-amber-400 hover:text-amber-300 uppercase tracking-widest transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="availableItemsForType.length === 0"
              :title="availableItemsForType.length === 0 ? 'No other items of this type exist in the adventure' : 'Place an existing item from another scene or inventory into this scene'"
              @click="emit('open-add-existing', 'items')"
            >+ Add Existing</button>
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
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
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
              <div v-if="activeMenuId === `scene-item-${obj.id}`" class="absolute right-0 mt-1 w-48 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name || obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'object', obj.id, obj.name || obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'object'}_image`)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="emit('clone-entity', 'object', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Clone</button>
                <button @click="editRouteEntity('object', obj)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
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
            <button @click="emit('regen-all', 'switch', true)" :disabled="isBatchGenerating['switch']" title="Generate switch images for switches in this list that are still missing one (does not create new switches)" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['switch'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'switch', false)" :disabled="isBatchGenerating['switch']" title="Re-render switch images for every switch in this list (does not create new switches)" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['switch'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-item', 'SWITCH')">+ Create</button>
            <button
              class="text-xs font-bold text-amber-400 hover:text-amber-300 uppercase tracking-widest transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="availableSwitchesForType.length === 0"
              :title="availableSwitchesForType.length === 0 ? 'No other switches exist in the adventure' : 'Place an existing switch from another scene or inventory into this scene'"
              @click="emit('open-add-existing', 'switch')"
            >+ Add Existing</button>
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
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
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
              <div v-if="activeMenuId === `scene-switch-${obj.id}`" class="absolute right-0 mt-1 w-48 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name || obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'object', obj.id, obj.name || obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'switch'}_image`)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="emit('clone-entity', 'object', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Clone</button>
                <button @click="editRouteEntity('object', obj)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
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
            <button @click="emit('regen-all', 'container', true)" :disabled="isBatchGenerating['container']" title="Generate container images for containers in this list that are still missing one (does not create new containers)" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['container'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'container', false)" :disabled="isBatchGenerating['container']" title="Re-render container images for every container in this list (does not create new containers)" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['container'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-item', 'CONTAINER')">+ Create</button>
            <button
              class="text-xs font-bold text-amber-400 hover:text-amber-300 uppercase tracking-widest transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="availableContainersForType.length === 0"
              :title="availableContainersForType.length === 0 ? 'No other containers exist in the adventure' : 'Place an existing container from another scene or inventory into this scene'"
              @click="emit('open-add-existing', 'container')"
            >+ Add Existing</button>
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
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
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
              <div v-if="activeMenuId === `scene-container-${obj.id}`" class="absolute right-0 mt-1 w-48 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name || obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'object', obj.id, obj.name || obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'container'}_image`)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="emit('clone-entity', 'object', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Clone</button>
                <button @click="editRouteEntity('object', obj)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
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
            <button @click="emit('regen-all', 'text-log', true)" :disabled="isBatchGenerating['text-log']" title="Generate text-log images for text logs in this list that are still missing one (does not create new text logs)" class="text-xs font-bold text-cyan-500 hover:text-cyan-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-wand" :class="{ 'animate-spin': isBatchGenerating['text-log'] }"></i> Generate Missing
            </button>
            <button @click="emit('regen-all', 'text-log', false)" :disabled="isBatchGenerating['text-log']" title="Re-render text-log images for every text log in this list (does not create new text logs)" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
              <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['text-log'] }"></i> Regenerate All
            </button>
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-item', 'READABLE')">+ Create</button>
            <button
              class="text-xs font-bold text-amber-400 hover:text-amber-300 uppercase tracking-widest transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="availableTextLogsForType.length === 0"
              :title="availableTextLogsForType.length === 0 ? 'No other text logs exist in the adventure' : 'Place an existing text log from another scene or inventory into this scene'"
              @click="emit('open-add-existing', 'text-log')"
            >+ Add Existing</button>
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
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="obj.id">ID: {{ obj.id }}</div>
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
              <div v-if="activeMenuId === `scene-log-${obj.id}`" class="absolute right-0 mt-1 w-48 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('quick-regen', 'object', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                <button @click="emit('open-regen-dialog', 'object', obj.id, obj.name || obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                <button @click="emit('open-upload-picker', 'object', obj.id, obj.name || obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                <button v-if="obj.image_url" @click="emit('download-asset', obj.image_url, `${obj.name || 'text-log'}_image`)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-violet-500 hover:text-white transition-all">Download Image</button>
                <button @click="emit('clone-entity', 'object', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-sky-500 hover:text-white transition-all">Clone</button>
                <button @click="editRouteEntity('object', obj)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-blue-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-entity', obj.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
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
            <button class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase tracking-widest transition-colors" @click="emit('open-create-exit')">+ Create</button>
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
              <div class="text-[9px] font-mono text-slate-200/80 tracking-widest mt-1 truncate" :title="worldExit.id">ID: {{ worldExit.id }}</div>
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
              <div v-if="activeMenuId === `scene-exit-${worldExit.id}`" class="absolute right-0 mt-1 w-48 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                <button @click="emit('open-exit', worldExit.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-cyan-500 hover:text-white transition-all">Open Route</button>
                <button @click="emit('open-edit-exit', worldExit.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-emerald-500 hover:text-white transition-all">Edit</button>
                <button @click="emit('request-delete-exit', worldExit.id)" class="w-full px-3.5 py-2 text-left text-xs font-bold text-slate-200 hover:bg-red-500 hover:text-white transition-all">Delete</button>
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
