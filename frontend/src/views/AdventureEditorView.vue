<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { adventureService } from '@/services/adventureService'
import { visualService } from '@/services/visualService'
import type { VisualKind } from '@/services/visualService'
import { entityService } from '@/services/entityService'
import { notificationService } from '@/services/notificationService'

// Icons & Assets

// Components
import EditorHeader from '@/components/editor/EditorHeader.vue'
import WorldTab from '@/components/editor/WorldTab.vue'
import ItemsTab from '@/components/editor/ItemsTab.vue'
import VisualsTab from '@/components/editor/VisualsTab.vue'
import ToneTab from '@/components/editor/ToneTab.vue'
import InhabitantsTab from '@/components/editor/InhabitantsTab.vue'
import ScenesTab from '@/components/editor/ScenesTab.vue'
import QuestTab from '@/components/editor/QuestTab.vue'
import AwardsTab from '@/components/editor/AwardsTab.vue'
import AdvancedTab from '@/components/editor/AdvancedTab.vue'
import EntityTooltip from '@/components/editor/EntityTooltip.vue'
import NotificationToast from '@/components/editor/NotificationToast.vue'
import EditEntityModal from '@/components/editor/EditEntityModal.vue'
import ManualVisionModal from '@/components/editor/ManualVisionModal.vue'
import DataDebugModal from '@/components/editor/DataDebugModal.vue'

// Utilities
import { 
  fixNewlines, 
  isNpcEntity, 
  isObjectEntity, 
  mergeUniqueById, 
  formatVoiceOption, 
  formatBytes,
  makeSafeFilename,
  getImageExtension,
} from '@/utils/editor_utils'

const props = defineProps<{
  adventureId: string
}>()

const router = useRouter()
const route = useRoute()
const ASSET_BASE = ''

// Visuals state
const isQuickGenerating = ref<Record<string, boolean>>({})
const isBatchGenerating = ref<Record<string, boolean>>({})

const isSavingText = ref(false)
const showEditModal = ref(false)
const editEntityContext = ref<{ type: string; id: string } | null>(null)
const editForm = ref({
  name: '',
  teaser: '',
  description: '',
  hp: 0,
  stamina: 0,
  mana: 0,
  goal: '',
  character: '',
  is_killable: true,
  item_type: 'PICKABLE',
  is_portable: true,
  locked: false,
  code_to_unlock: '',
  item_to_unlock: '',
  inventory_json: '[]',
  text_log_content: '',
})

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const promptError = ref('')
const showDebug = ref(false)
const activeTab = ref<'world' | 'items' | 'visuals' | 'inhabitants' | 'scenes' | 'quest' | 'awards' | 'tone' | 'advanced'>('world')

const selectedVisual = ref<{ kind: VisualKind; id: string; label: string; description: string; hint: string } | null>(null)
const selectedUploadTarget = ref<{ kind: VisualKind; id: string; label: string } | null>(null)
const visualPrompt = ref('')
const showPromptDialog = ref(false)
const isRegenerating = ref(false)
const isSuggestingPrompt = ref(false)
const useAdvancedModel = ref(false)
const isUploading = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
const visualsCacheVersion = ref(0)
const hoveredEntity = ref<any>(null)
const mousePos = ref({ x: 0, y: 0 })
const activeMenuId = ref<string | null>(null)
const tooltipAlignTop = ref(false)
const windowHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 1000)
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1000)

if (typeof window !== 'undefined') {
  window.addEventListener('resize', () => {
    windowHeight.value = window.innerHeight
    windowWidth.value = window.innerWidth
  })
}

function toggleMenu(id: string, event: MouseEvent) {
  event.stopPropagation()
  if (activeMenuId.value === id) {
    activeMenuId.value = null
  } else {
    activeMenuId.value = id
    hoveredEntity.value = null
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('click', () => {
    activeMenuId.value = null
  })
}

const imageStylesCatalog = ref<any[]>([])
const toneCatalog = ref<any[]>([])
const availableVoices = ref<Array<{ name: string; gender?: string; description?: string }>>([])

const editorTabs = [
  { key: 'world', label: 'World' },
  { key: 'items', label: 'Items' },
  { key: 'visuals', label: 'Visuals' },
  { key: 'inhabitants', label: 'Inhabitants' },
  { key: 'scenes', label: 'Scenes' },
  { key: 'quest', label: 'Quest' },
  { key: 'awards', label: 'Awards' },
  { key: 'tone', label: 'Tone' },
  { key: 'advanced', label: 'Advanced' },
] as const

// Use notification service
const notifications = notificationService.all

function addNotification(message: string, type: 'error' | 'success' | 'info' = 'info') {
  notificationService.add(message, type)
}

async function clearCreationError() {
  if (!adventure.value) return
  try {
    await adventureService.clearCreationError(props.adventureId)
    adventure.value.creation_error = null
    addNotification('Generation notice dismissed.', 'success')
  } catch (error) {
    console.error('Failed to clear creation error:', error)
  }
}

function handleHover(entity: any, event: MouseEvent) {
  if (activeMenuId.value) return
  hoveredEntity.value = entity
  tooltipAlignTop.value = event.clientY > windowHeight.value * 0.6
  let x = event.clientX + 20
  const tooltipWidth = 280
  if (x + tooltipWidth > windowWidth.value) {
    x = event.clientX - tooltipWidth - 20
  }
  mousePos.value = { x, y: event.clientY }
}

function clearHover() {
  hoveredEntity.value = null
}

async function uploadSelectedVisual(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  const target = selectedUploadTarget.value
  if (!file || !target) return
  const spec = visualService.UPLOAD_LIMITS[target.kind]

  // Validate file
  const fileValidation = visualService.validateFile(file)
  if (!fileValidation.valid) {
    addNotification(fileValidation.error || 'Invalid file', 'error')
    input.value = ''
    return
  }

  // Validate file size
  if (file.size > spec.maxBytes) {
    addNotification(`File too large. Max is ${formatBytes(spec.maxBytes)}.`, 'error')
    input.value = ''
    return
  }

  // Validate dimensions
  try {
    const { width, height } = await visualService.getImageDimensions(file)
    const dimValidation = visualService.validateDimensions(width, height, spec)
    if (!dimValidation.valid) {
      addNotification(dimValidation.error || 'Invalid dimensions', 'error')
      input.value = ''
      return
    }
  } catch (error: any) {
    addNotification(error?.message || 'Unable to validate image dimensions.', 'error')
    input.value = ''
    return
  }

  isUploading.value = true
  try {
    await visualService.uploadVisual(props.adventureId, target.kind, target.id, file)
    await fetchDebugInfo()
    addNotification(`Image uploaded for ${target.label}.`, 'success')
  } catch (error: any) {
    addNotification(error?.message || 'Upload failed.', 'error')
  } finally {
    isUploading.value = false
    selectedUploadTarget.value = null
    input.value = ''
  }
}

const form = ref({
  title: '',
  teaser: '',
  version: '',
  original_prompt: '',
  rule_enforcement_mode: 'rpg' as 'rpg' | 'story' | 'chat',
  time_per_turn: 5,
  min_scenes: 1,
  max_scenes: 5,
  awards: [] as any[],
  allow_dynamic_items: true,
  can_damage_npcs: true,
  npcs_can_damage_protagonist: true,
  plot: '',
  rules: '',
  intro_text: '',
  walkthrough: '',
  completed_condition: '',
  gameover_condition: '',
  tts_director_notes: '',
  selected_style_id: '',
  selected_tone_id: '',
  is_adventure_generator: false
})

const editingField = ref<string | null>(null)
const tempValue = ref('')

function startEditing(field: string, value: string) {
  editingField.value = field
  tempValue.value = fixNewlines(value)
}

function cancelEditing() {
  editingField.value = null
  tempValue.value = ''
}

async function saveField() {
  if (!editingField.value) return
  // @ts-ignore
  form.value[editingField.value] = tempValue.value
  await saveChanges()
  editingField.value = null
}

async function fetchCatalogs() {
  try {
    const data = await adventureService.fetchCatalogs()
    imageStylesCatalog.value = data.image_styles_catalog || []
    toneCatalog.value = data.tone_catalog || []
    const voiceCatalog = Array.isArray(data.tts_settings?.voice_catalog)
      ? data.tts_settings.voice_catalog
      : []
    const voiceList = Array.isArray(data.tts_settings?.voice_list)
      ? data.tts_settings.voice_list
      : []
    availableVoices.value = voiceCatalog.length > 0
      ? voiceCatalog
      : voiceList.map((name: string) => ({ name }))
  } catch (error) {
    console.error('Failed to fetch catalogs:', error)
  }
}

const editorNpcs = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.npcs) ? debugData.value.npcs : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isNpcEntity(entity))
  return mergeUniqueById(source, inferred)
})

const editorScenes = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.scenes) ? debugData.value.scenes : []
  return source.filter((scene: any) => !!scene?.id)
})

const editorObjects = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred).filter((entity: any) => String(entity?.item_type || '').toUpperCase() !== 'READABLE')
})

const editorTextLogs = computed<any[]>(() => {
  const source = Array.isArray(debugData.value?.objects) ? debugData.value.objects : []
  const allEntities = Array.isArray(debugData.value?.entities_all) ? debugData.value.entities_all : []
  const inferred = allEntities.filter((entity: any) => isObjectEntity(entity))
  return mergeUniqueById(source, inferred).filter((entity: any) => String(entity?.item_type || '').toUpperCase() === 'READABLE')
})

async function fetchAdventure() {
  if (!props.adventureId) return
  isLoading.value = true
  errorMsg.value = ''
  try {
    const data = await adventureService.fetchAdventure(props.adventureId)
    adventure.value = data
    form.value.title = data.title
    form.value.teaser = data.teaser || ''
    form.value.version = data.version || ''
    form.value.original_prompt = data.original_prompt || ''
    form.value.rule_enforcement_mode = (data.rule_enforcement_mode as 'rpg' | 'story' | 'chat') || 'rpg'
    form.value.time_per_turn = data.time_per_turn || 5
    form.value.min_scenes = data.min_scenes || 1
    form.value.max_scenes = data.max_scenes || 5
    form.value.awards = data.awards || []
    form.value.allow_dynamic_items = data.allow_dynamic_items ?? true
    form.value.plot = data.plot || ''
    form.value.can_damage_npcs = data.can_damage_npcs ?? true
    form.value.npcs_can_damage_protagonist = data.npcs_can_damage_protagonist ?? true
    form.value.rules = data.rules || ''
    form.value.intro_text = data.intro_text || ''
    form.value.walkthrough = data.walkthrough || ''
    form.value.completed_condition = data.completed_condition || ''
    form.value.gameover_condition = data.gameover_condition || ''
    form.value.tts_director_notes = data.tts_director_notes || ''

    form.value.selected_style_id = Array.isArray(data.selected_image_styles) && data.selected_image_styles.length > 0 
      ? (typeof data.selected_image_styles[0] === 'string' ? data.selected_image_styles[0] : data.selected_image_styles[0].id)
      : ''
    let rawTone = data.selected_tone
    if (rawTone && typeof rawTone === 'object') {
      form.value.selected_tone_id = rawTone.id || rawTone.name || ''
    } else if (typeof rawTone === 'string' && rawTone.startsWith('{')) {
      try {
        const obj = JSON.parse(rawTone)
        form.value.selected_tone_id = obj.id || obj.name || rawTone
      } catch (e) {
        form.value.selected_tone_id = rawTone
      }
    } else {
      form.value.selected_tone_id = rawTone || ''
    }
    form.value.is_adventure_generator = !!data.is_adventure_generator
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error loading adventure.'
  } finally {
    isLoading.value = false
  }
}

async function fetchDebugInfo() {
  if (!props.adventureId) return
  try {
    const payload = await adventureService.fetchDebugInfo(props.adventureId)
    debugData.value = adventureService.normalizeDebugPayload(payload)
    visualsCacheVersion.value += 1
  } catch (error) {
    console.error('Failed to fetch debug info:', error)
    debugData.value = null
    errorMsg.value = 'Failed to load world assets/debug data.'
  }
}

function openTextEdit(type: string, id: string, currentName: string, currentDesc: string, currentTeaser: string = '', hp?: number, stamina?: number, mana?: number, goal?: string, character?: string, isKillable?: boolean) {
  const selectedObject = type === 'object'
    ? ([...(editorObjects.value || []), ...(editorTextLogs.value || [])]).find((entry: any) => String(entry.id) === String(id))
    : null

  editEntityContext.value = { type, id }
  editForm.value = { 
    name: currentName || '', 
    description: fixNewlines(currentDesc || ''),
    teaser: fixNewlines(currentTeaser || ''),
    hp: hp ?? 0,
    stamina: stamina ?? 0,
    mana: mana ?? 0,
    goal: goal || '',
    character: character || '',
    is_killable: isKillable ?? true,
    item_type: selectedObject?.item_type || 'PICKABLE',
    is_portable: selectedObject?.is_portable !== false,
    locked: selectedObject?.locked === true,
    code_to_unlock: selectedObject?.code_to_unlock || '',
    item_to_unlock: selectedObject?.item_to_unlock || '',
    inventory_json: JSON.stringify(selectedObject?.inventory || [], null, 2),
    text_log_content: fixNewlines(selectedObject?.metadata_json?.text_log_content || ''),
  }
  showEditModal.value = true
}

async function saveEntityText(data: any) {
  if (!editEntityContext.value) return
  
  // Basic validation for stats
  if (data.hp < 0 || data.hp > 999 || data.stamina < 0 || data.stamina > 999 || data.mana < 0 || data.mana > 999) {
    addNotification('Stats must be between 0 and 999.', 'error')
    return
  }

  // Persona validation (NPC and Protagonist)
  if (['npc', 'protagonist'].includes(editEntityContext.value.type)) {
    if ((data.goal || '').length > 200 || (data.character || '').length > 200) {
      addNotification('Motivation and traits must be under 200 characters.', 'error')
      return
    }
  }

  if (editEntityContext.value.type === 'object' && (data.text_log_content || '').length > 500) {
    addNotification('Text logs must be 500 characters or less.', 'error')
    return
  }

  isSavingText.value = true
  promptError.value = ''
  try {
    await entityService.saveEntityText(props.adventureId, {
      target_type: editEntityContext.value.type,
      target_id: editEntityContext.value.id,
      name: data.name,
      teaser: editEntityContext.value.type === 'cover' ? data.teaser : undefined,
      description: data.description,
      hp: data.hp || undefined,
      stamina: data.stamina || undefined,
      mana: data.mana || undefined,
      goal: ['npc', 'protagonist'].includes(editEntityContext.value.type) ? data.goal : undefined,
      character: ['npc', 'protagonist'].includes(editEntityContext.value.type) ? data.character : undefined,
      is_killable: editEntityContext.value.type === 'npc' ? data.is_killable : undefined,
      item_type: editEntityContext.value.type === 'object' ? data.item_type : undefined,
      is_portable: editEntityContext.value.type === 'object' ? data.is_portable : undefined,
      locked: editEntityContext.value.type === 'object' ? data.locked : undefined,
      code_to_unlock: editEntityContext.value.type === 'object' ? data.code_to_unlock : undefined,
      item_to_unlock: editEntityContext.value.type === 'object' ? data.item_to_unlock : undefined,
      inventory: editEntityContext.value.type === 'object' ? data.inventory : undefined,
      text_log_content: editEntityContext.value.type === 'object' ? data.text_log_content : undefined,
    })
    showEditModal.value = false
    editEntityContext.value = null
    await Promise.all([fetchAdventure(), fetchDebugInfo()])
    addNotification('Changes applied successfully.', 'success')
  } catch (error: any) {
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isSavingText.value = false
  }
}

async function saveChanges() {
  isSaving.value = true
  errorMsg.value = ''
  try {
    const fullStyleObj = imageStylesCatalog.value.find(s => s.id === form.value.selected_style_id) || { id: form.value.selected_style_id, name: form.value.selected_style_id }
    const fullToneObj = toneCatalog.value.find(t => t.id === form.value.selected_tone_id) || { id: form.value.selected_tone_id, name: form.value.selected_tone_id }
    const payload = {
      ...form.value,
      selected_image_styles: form.value.selected_style_id ? [fullStyleObj] : [],
      selected_tone: form.value.selected_tone_id ? fullToneObj : null
    }
    await adventureService.updateAdventure(props.adventureId, payload as any)
    await fetchAdventure()
    addNotification('Adventure configuration updated.', 'success')
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error while saving.'
    addNotification(errorMsg.value, 'error')
  } finally {
    isSaving.value = false
  }
}

function buildVisualImageUrl(imagePath?: string | null) {
  return visualService.buildImageUrl(imagePath, visualsCacheVersion.value)
}

function downloadVisualAsset(imagePath: string | null | undefined, filenameLabel: string) {
  if (!imagePath) {
    addNotification('No image available for download.', 'error')
    activeMenuId.value = null
    return
  }
  const url = buildVisualImageUrl(imagePath)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = makeSafeFilename(filenameLabel, getImageExtension(imagePath))
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  activeMenuId.value = null
}

function openRegenerateDialog(kind: VisualKind, id: string, label: string) {
  const description = getVisualDescription(kind, id)
  const hint = visualService.UPLOAD_LIMITS[kind].hint
  selectedVisual.value = { kind, id, label, description, hint }
  visualPrompt.value = ''
  useAdvancedModel.value = kind === 'scene' || kind === 'cover'
  promptError.value = ''
  showPromptDialog.value = true
}

function getVisualDescription(kind: VisualKind, id: string) {
  if (!debugData.value) return ''
  if (kind === 'cover') return debugData.value.adventure?.plot || debugData.value.adventure?.original_prompt || ''
  if (kind === 'protagonist') {
    const base = debugData.value.protagonist?.description || ''
    const plot = debugData.value.adventure?.plot || ''
    return plot ? `${base}\n\nNarrative context: ${plot}` : base
  }
  if (kind === 'scene') return (debugData.value.scenes || []).find((s: any) => s.id === id)?.description || ''
  if (kind === 'npc') return (debugData.value.npcs || []).find((n: any) => n.id === id)?.description || ''
  return (debugData.value.objects || []).find((o: any) => o.id === id)?.description || ''
}

function openUploadPicker(kind: VisualKind, id: string, label: string) {
  selectedUploadTarget.value = { kind, id, label }
  promptError.value = ''
  addNotification(`Upload ${label}: ${visualService.UPLOAD_LIMITS[kind].hint}`, 'info')
  if (uploadInput.value) {
    uploadInput.value.value = ''
    uploadInput.value.click()
  }
}

async function quickRegenerateVisual(kind: VisualKind, id: string, skipFetch: boolean = false) {
  const key = `${kind}_${id}`
  isQuickGenerating.value[key] = true
  try {
     await visualService.quickRegenerateVisual(props.adventureId, kind, id)
    if (!skipFetch) await fetchDebugInfo()
  } catch (error: any) {
    console.error('Quick regen error:', error)
    addNotification(error.message, 'error')
  } finally {
    isQuickGenerating.value[key] = false
  }
}

async function regenerateAll(kind: VisualKind) {
  isBatchGenerating.value[kind] = true
  let items: any[] = []
  if (kind === 'cover' && debugData.value?.adventure) items = [debugData.value.adventure]
  if (kind === 'protagonist' && debugData.value?.protagonist) items = [debugData.value.protagonist]
  if (kind === 'scene') items = editorScenes.value
  if (kind === 'npc') items = editorNpcs.value
  if (kind === 'object') items = editorObjects.value
  for (const item of items) {
    await quickRegenerateVisual(kind, item.id || props.adventureId, true)
  }
  await fetchDebugInfo()
  isBatchGenerating.value[kind] = false
}

async function regenerateVisual() {
  if (!selectedVisual.value || isRegenerating.value) return
  isRegenerating.value = true
  promptError.value = ''
  try {
     await visualService.regenerateVisual(
       props.adventureId,
       selectedVisual.value.kind,
       selectedVisual.value.id,
       visualPrompt.value,
       useAdvancedModel.value
     )
    showPromptDialog.value = false
    await fetchDebugInfo()
    addNotification(`Visual for ${selectedVisual.value.label} re-woven.`, 'success')
  } catch (error: any) {
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isRegenerating.value = false
  }
}

async function suggestPrompt() {
  if (!selectedVisual.value || isSuggestingPrompt.value) return
  isSuggestingPrompt.value = true
  promptError.value = ''
  try {
     const suggested = await visualService.suggestPrompt(
       props.adventureId,
       selectedVisual.value.kind,
       selectedVisual.value.id
     )
     if (suggested) {
       visualPrompt.value = suggested
       addNotification('AI suggested a prompt based on the description.', 'success')
     } else {
       addNotification('AI returned an empty suggestion.', 'info')
     }
  } catch (error: any) {
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isSuggestingPrompt.value = false
  }
}

function cancelRegeneration() {
  isRegenerating.value = false
  showPromptDialog.value = false
  addNotification('Generation request abandoned.', 'info')
}

watch(
  () => props.adventureId,
  async (newId) => {
    if (!newId) {
      adventure.value = null
      debugData.value = null
      return
    }
    await Promise.all([fetchAdventure(), fetchDebugInfo(), fetchCatalogs()])
  },
  { immediate: true }
)

const goBack = () => {
  const from = route.query.from as string
  if (from) {
    router.push({ name: 'portal', query: { section: from } })
  } else {
    router.push({ name: 'portal' })
  }
}
</script>

<template>
  <div class="h-screen bg-slate-950 text-slate-200 font-sans flex flex-col relative overflow-x-hidden overflow-y-auto">
    <!-- Ambient Background -->
    <div v-if="debugData?.adventure?.image_url" class="absolute inset-0 pointer-events-none z-0 opacity-20">
      <img :src="ASSET_BASE + debugData.adventure.image_url" class="w-full h-full object-cover blur-3xl scale-110" />
      <div class="absolute inset-0 bg-slate-950/60"></div>
    </div>

    <EditorHeader 
      :adventure="adventure" 
      :adventure-id="adventureId" 
      :cover-source-name="adventure?.cover_source_adventure_name || ''"
      @go-back="goBack"
    />

    <main class="flex-grow p-6 max-w-[1400px] mx-auto w-full relative z-10 pb-16">
      <div v-if="isLoading" class="flex flex-col justify-center items-center py-40 gap-6">
        <div class="relative w-20 h-20">
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500/20"></div>
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin"></div>
        </div>
        <p class="text-xs font-bold text-emerald-500 uppercase tracking-[0.3em]">Loading Chronicles...</p>
      </div>
      
      <div v-else class="space-y-6">
        <nav class="lg:hidden flex gap-2 overflow-x-auto pb-2">
          <button
            v-for="tab in editorTabs"
            :key="tab.key"
            @click="activeTab = tab.key"
            :class="[
              'shrink-0 px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-[0.15em] transition-all border',
              activeTab === tab.key
                ? 'bg-emerald-600/80 border-emerald-500 text-white'
                : 'bg-slate-900/50 border-white/10 text-slate-400 hover:text-slate-200'
            ]"
          >
            {{ tab.label }}
          </button>
        </nav>

        <div class="lg:grid lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-6">
          <aside class="hidden lg:block">
            <div class="sticky top-24 bg-slate-900/40 border border-white/5 rounded-2xl p-3 backdrop-blur-md">
              <div class="space-y-1">
                <button
                  v-for="tab in editorTabs"
                  :key="tab.key"
                  @click="activeTab = tab.key"
                  :class="[
                    'w-full text-left px-3 py-2 rounded-xl text-xs font-black uppercase tracking-[0.18em] transition-all',
                    activeTab === tab.key
                      ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-lg'
                      : 'text-slate-400 hover:text-white hover:bg-white/5'
                  ]"
                >
                  {{ tab.label }}
                </button>
              </div>
            </div>
          </aside>

          <div class="space-y-10 min-w-0">
            <WorldTab
              v-if="activeTab === 'world'"
              :form="form"
              :adventure="adventure"
              :debug-data="debugData"
              :editing-field="editingField"
              :temp-value="tempValue"
              :is-saving="isSaving"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :fix-newlines="fixNewlines"
              @quick-regen="quickRegenerateVisual"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @open-text-edit="openTextEdit"
              @toggle-menu="toggleMenu"
              @start-edit="startEditing"
              @save-field="saveField"
              @cancel-edit="cancelEditing"
              @update:temp-value="tempValue = $event"
              @update:pacing="form.time_per_turn = $event"
              @update:mode="form.rule_enforcement_mode = $event as any"
              @save-changes="saveChanges"
            />

            <ItemsTab 
              v-if="activeTab === 'items'"
              :editor-objects="editorObjects"
              :editor-text-logs="editorTextLogs"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :rule-enforcement-mode="form.rule_enforcement_mode"
              @quick-regen="quickRegenerateVisual"
              @regen-all="regenerateAll"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @open-text-edit="openTextEdit"
              @toggle-menu="toggleMenu"
              @handle-hover="handleHover"
              @clear-hover="clearHover"
            />

            <InhabitantsTab
              v-if="activeTab === 'inhabitants'"
              :form="form"
              :adventure="adventure"
              :debug-data="debugData"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              :editor-npcs="editorNpcs"
              :rule-enforcement-mode="form.rule_enforcement_mode"
              @quick-regen="quickRegenerateVisual"
              @regen-all="regenerateAll"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @open-text-edit="openTextEdit"
              @toggle-menu="toggleMenu"
              @handle-hover="handleHover"
              @clear-hover="clearHover"
            />

            <ScenesTab
              v-if="activeTab === 'scenes'"
              :editor-scenes="editorScenes"
              :debug-data="debugData"
              :is-batch-generating="isBatchGenerating"
              :is-quick-generating="isQuickGenerating"
              :active-menu-id="activeMenuId"
              @quick-regen="quickRegenerateVisual"
              @regen-all="regenerateAll"
              @open-regen-dialog="openRegenerateDialog"
              @open-upload-picker="openUploadPicker"
              @download-asset="downloadVisualAsset"
              @open-text-edit="openTextEdit"
              @toggle-menu="toggleMenu"
              @handle-hover="handleHover"
              @clear-hover="clearHover"
            />

            <QuestTab
              v-if="activeTab === 'quest'"
              :adventure="adventure"
            />

            <AwardsTab
              v-if="activeTab === 'awards'"
              :adventure="adventure"
            />

            <VisualsTab
              v-if="activeTab === 'visuals'"
              :form="form"
              :adventure="adventure"
              :image-styles-catalog="imageStylesCatalog"
              @update:style="form.selected_style_id = $event"
              @save-changes="saveChanges"
            />

            <ToneTab
              v-if="activeTab === 'tone'"
              :form="form"
              :adventure="adventure"
              :debug-data="debugData"
              :tone-catalog="toneCatalog"
              :is-saving="isSaving"
              @update:tone="form.selected_tone_id = $event"
              @save-changes="saveChanges"
            />

            <AdvancedTab 
              v-if="activeTab === 'advanced'"
              :form="form"
              @update:generator="form.is_adventure_generator = $event; saveChanges()"
              @update:dynamic-items="form.allow_dynamic_items = $event; saveChanges()"
              @update:can-damage-npcs="form.can_damage_npcs = $event; saveChanges()"
              @update:npcs-can-damage-protagonist="form.npcs_can_damage_protagonist = $event; saveChanges()"
              @show-debug="showDebug = true"
              @save-changes="saveChanges"
            />
          </div>
        </div>
      </div>
    </main>

    <EntityTooltip 
      :hovered-entity="hoveredEntity"
      :active-menu-id="activeMenuId"
      :mouse-pos="mousePos"
      :tooltip-align-top="tooltipAlignTop"
      :window-height="windowHeight"
      :rule-enforcement-mode="form.rule_enforcement_mode"
      :build-visual-image-url="buildVisualImageUrl"
      :fix-newlines="fixNewlines"
    />

    <ManualVisionModal 
      :show="showPromptDialog"
      :selected-visual="selectedVisual"
      v-model:visual-prompt="visualPrompt"
      v-model:use-advanced-model="useAdvancedModel"
      :is-suggesting-prompt="isSuggestingPrompt"
      :is-regenerating="isRegenerating"
      :upload-limits="visualService.UPLOAD_LIMITS"
      :format-bytes="formatBytes"
      :fix-newlines="fixNewlines"
      @close="showPromptDialog = false"
      @suggest="suggestPrompt"
      @regenerate="regenerateVisual"
      @cancel-regen="cancelRegeneration"
    />

    <EditEntityModal 
      :show="showEditModal"
      :context="editEntityContext"
      :initial-form="editForm"
      :rule-enforcement-mode="form.rule_enforcement_mode"
      :is-saving="isSavingText"
      :adventure-id="adventureId"
      @close="showEditModal = false"
      @save="saveEntityText"
    />

    <DataDebugModal 
      :show="showDebug"
      :adventure="adventure"
      :debug-data="debugData"
      @close="showDebug = false"
    />

    <NotificationToast 
      :notifications="notifications"
      @close="notificationService.remove($event)"
    />

    <input
      ref="uploadInput"
      type="file"
      accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
      class="hidden"
      @change="uploadSelectedVisual"
    />
  </div>
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
