<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authState } from '@/store/auth'

// Icons & Assets

// Components
import EditorHeader from '@/components/editor/EditorHeader.vue'
import PhysicalTab from '@/components/editor/PhysicalTab.vue'
import PlotTab from '@/components/editor/PlotTab.vue'
import RebuildTab from '@/components/editor/RebuildTab.vue'
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
  type VisualKind
} from '@/utils/editor_utils'

const props = defineProps<{
  adventureId: string
}>()

const router = useRouter()
const route = useRoute()
const BASE = '/api'
const ASSET_BASE = ''

function authHeaders(includeJson = false): Record<string, string> {
  const headers: Record<string, string> = {}
  if (includeJson) {
    headers['Content-Type'] = 'application/json'
  }
  if (authState.token) {
    headers.Authorization = `Bearer ${authState.token}`
  }
  return headers
}

// Visuals state
const isQuickGenerating = ref<Record<string, boolean>>({})
const isBatchGenerating = ref<Record<string, boolean>>({})

// Editor State
const aiEditPrompt = ref('')
const aiAutoVisualize = ref(true)
const isAIEditing = ref(false)

const isSavingText = ref(false)
const showEditModal = ref(false)
const editEntityContext = ref<{ type: string; id: string } | null>(null)
const editForm = ref({ name: '', teaser: '', description: '', hp: 0, stamina: 0, mana: 0, voice: '' })

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const promptError = ref('')
const showDebug = ref(false)
const activeTab = ref<'physical' | 'plot' | 'rebuild' | 'advanced'>('physical')

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

// Notifications state
const notifications = ref<{ id: number; message: string; type: 'error' | 'success' | 'info' }[]>([])
let nextNotifId = 0

function addNotification(message: string, type: 'error' | 'success' | 'info' = 'info') {
  const id = nextNotifId++
  notifications.value.push({ id, message, type })
  setTimeout(() => {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }, 5000)
}

async function clearCreationError() {
  if (!adventure.value) return
  try {
    const res = await fetch(`${BASE}/adventures/${props.adventureId}`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify({ creation_error: null })
    })
    if (res.ok) {
      adventure.value.creation_error = null
      addNotification('Generation notice dismissed.', 'success')
    }
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

const VISUAL_UPLOAD_LIMITS = {
  cover: { maxWidth: 2048, maxHeight: 1024, maxBytes: 4 * 1024 * 1024, hint: 'Optimal: cinematic landscape 2:1, max 2048x1024. PNG, JPEG, or WEBP.' },
  protagonist: { maxWidth: 1024, maxHeight: 1280, maxBytes: 2 * 1024 * 1024, hint: 'Optimal: portrait 4:5, max 1024x1280. PNG, JPEG, or WEBP.' },
  scene: { maxWidth: 1600, maxHeight: 900, maxBytes: 3 * 1024 * 1024, hint: 'Optimal: landscape 16:9, max 1600x900. PNG, JPEG, or WEBP.' },
  npc: { maxWidth: 1024, maxHeight: 1280, maxBytes: 2 * 1024 * 1024, hint: 'Optimal: portrait 4:5, max 1024x1280. PNG, JPEG, or WEBP.' },
  object: { maxWidth: 1024, maxHeight: 1024, maxBytes: 2 * 1024 * 1024, hint: 'Optimal: square 1:1, max 1024x1024. PNG, JPEG, or WEBP.' },
} as const

const ALLOWED_UPLOAD_MIME_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])
const ALLOWED_UPLOAD_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'webp'])

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
    const res = await fetch(`${BASE}/settings`, {
      headers: authHeaders(false)
    })
    if (res.ok) {
      const data = await res.json()
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
    }
  } catch (error) {
    console.error('Failed to fetch catalogs:', error)
  }
}

function normalizeDebugPayload(raw: any): any {
  if (!raw || typeof raw !== 'object') return raw
  const payload = { ...raw }
  const allEntities = Array.isArray(raw.entities_all) ? raw.entities_all : []
  if (allEntities.length === 0) return payload
  const inferredNpcs = allEntities.filter((entity: any) => isNpcEntity(entity))
  const inferredObjects = allEntities.filter((entity: any) => isObjectEntity(entity))
  payload.npcs = mergeUniqueById(Array.isArray(raw.npcs) ? raw.npcs : [], inferredNpcs)
  payload.objects = mergeUniqueById(Array.isArray(raw.objects) ? raw.objects : [], inferredObjects)
  return payload
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
  return mergeUniqueById(source, inferred)
})

async function fetchAdventure() {
  if (!props.adventureId) return
  isLoading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`${BASE}/adventures/${props.adventureId}`, {
      headers: authHeaders(false),
    })
    if (!res.ok) throw new Error('Failed to load adventure configuration.')
    const data = await res.json()
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
    const res = await fetch(`${BASE}/adventures/${props.adventureId}/editor/assets`, {
      headers: authHeaders(false),
    })
    if (res.ok) {
      const payload = await res.json()
      debugData.value = normalizeDebugPayload(payload)
      visualsCacheVersion.value += 1
    } else {
      debugData.value = null
      errorMsg.value = 'Failed to load world assets/debug data.'
    }
  } catch (error) {
    console.error('Failed to fetch debug info:', error)
    debugData.value = null
    errorMsg.value = 'Network error while loading world assets/debug data.'
  }
}

function openTextEdit(type: string, id: string, currentName: string, currentDesc: string, currentTeaser: string = '', hp?: number, stamina?: number, mana?: number, voice?: string) {
  editEntityContext.value = { type, id }
  editForm.value = { 
    name: currentName || '', 
    description: fixNewlines(currentDesc || ''),
    teaser: fixNewlines(currentTeaser || ''),
    hp: hp || 0,
    stamina: stamina || 0,
    mana: mana || 0,
    voice: voice || ''
  }
  showEditModal.value = true
}

async function saveEntityText(data: any) {
  if (!editEntityContext.value) return
  isSavingText.value = true
  promptError.value = ''
  try {
    const res = await fetch(`${BASE}/adventures/${props.adventureId}/editor/entity`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify({
        target_type: editEntityContext.value.type,
        target_id: editEntityContext.value.id,
        name: data.name,
        teaser: editEntityContext.value.type === 'cover' ? data.teaser : undefined,
        description: data.description,
        voice: editEntityContext.value.type === 'npc' ? data.voice || '' : undefined,
        hp: data.hp || undefined,
        stamina: data.stamina || undefined,
        mana: data.mana || undefined
      })
    })
    if (!res.ok) {
      const respData = await res.json()
      throw new Error(respData.detail || 'Failed to save entity text')
    }
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

async function runAIEdit() {
  if (!aiEditPrompt.value) return
  isAIEditing.value = true
  promptError.value = ''
  try {
    const res = await fetch(`${BASE}/adventures/${props.adventureId}/editor/ai-edit`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({ 
        prompt: aiEditPrompt.value,
        auto_visualize: aiAutoVisualize.value 
      })
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to apply AI changes')
    }
    aiEditPrompt.value = ''
    await fetchDebugInfo()
    addNotification('AI weaver has reshaped reality.', 'success')
  } catch (error: any) {
    promptError.value = error.message
    addNotification(error.message, 'error')
  } finally {
    isAIEditing.value = false
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
    const res = await fetch(`${BASE}/adventures/${props.adventureId}`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify(payload),
    })
    if (!res.ok) throw new Error('Failed to save changes.')
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
  if (!imagePath) return ''
  return `${ASSET_BASE}${imagePath}?v=${visualsCacheVersion.value}`
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
  const hint = VISUAL_UPLOAD_LIMITS[kind].hint
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

async function getImageDimensions(file: File): Promise<{ width: number; height: number }> {
  const objectUrl = URL.createObjectURL(file)
  try {
    return await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve({ width: image.width, height: image.height })
      image.onerror = () => reject(new Error('Could not read image dimensions.'))
      image.src = objectUrl
    })
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

function openUploadPicker(kind: VisualKind, id: string, label: string) {
  selectedUploadTarget.value = { kind, id, label }
  promptError.value = ''
  addNotification(`Upload ${label}: ${VISUAL_UPLOAD_LIMITS[kind].hint}`, 'info')
  if (uploadInput.value) {
    uploadInput.value.value = ''
    uploadInput.value.click()
  }
}

async function uploadSelectedVisual(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  const target = selectedUploadTarget.value
  if (!file || !target) return
  const spec = VISUAL_UPLOAD_LIMITS[target.kind]
  const ext = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() || '' : ''
  if (!ALLOWED_UPLOAD_MIME_TYPES.has(file.type)) {
    addNotification('Unsupported file type. Please use PNG, JPEG, or WEBP.', 'error')
    input.value = ''
    return
  }
  if (!ALLOWED_UPLOAD_EXTENSIONS.has(ext)) {
    addNotification('Unsupported file extension.', 'error')
    input.value = ''
    return
  }
  if (file.size > spec.maxBytes) {
    addNotification(`File too large. Max is ${formatBytes(spec.maxBytes)}.`, 'error')
    input.value = ''
    return
  }
  try {
    const { width, height } = await getImageDimensions(file)
    if (width > spec.maxWidth || height > spec.maxHeight) {
      addNotification(`Image too large: ${width}x${height}. Max is ${spec.maxWidth}x${spec.maxHeight}.`, 'error')
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
    const payload = new FormData()
    payload.append('target_type', target.kind)
    payload.append('target_id', target.id)
    payload.append('file', file)
    const res = await fetch(`${BASE}/adventures/${props.adventureId}/visuals/upload`, {
      method: 'POST',
      headers: authHeaders(false),
      body: payload,
    })
    if (!res.ok) throw new Error('Upload failed.')
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

async function quickRegenerateVisual(kind: VisualKind, id: string, skipFetch: boolean = false) {
  const key = `${kind}_${id}`
  isQuickGenerating.value[key] = true
  try {
    const res = await fetch(`${BASE}/adventures/${props.adventureId}/visuals/regenerate`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({ target_type: kind, target_id: id, prompt: null }),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Generation failed')
    }
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
    const res = await fetch(`${BASE}/adventures/${props.adventureId}/visuals/regenerate`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        target_type: selectedVisual.value.kind,
        target_id: selectedVisual.value.id,
        prompt: visualPrompt.value.trim() || null,
        use_advanced_model: useAdvancedModel.value
      }),
    })
    if (!res.ok) throw new Error('Failed to regenerate.')
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
    const res = await fetch(`${BASE}/adventures/${props.adventureId}/visuals/suggest-prompt`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({
        target_type: selectedVisual.value.kind,
        target_id: selectedVisual.value.id
      })
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to suggest prompt')
    }
    const data = await res.json()
    if (data && data.suggested_prompt) {
      visualPrompt.value = data.suggested_prompt
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
      :active-tab="activeTab"
      @go-back="goBack"
      @update:active-tab="activeTab = $event"
    />

    <main class="flex-grow p-6 max-w-[1400px] mx-auto w-full relative z-10 pb-16">
      <div v-if="isLoading" class="flex flex-col justify-center items-center py-40 gap-6">
        <div class="relative w-20 h-20">
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500/20"></div>
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin"></div>
        </div>
        <p class="text-xs font-bold text-emerald-500 uppercase tracking-[0.3em]">Loading Chronicles...</p>
      </div>
      
      <div v-else class="space-y-10">
        <PhysicalTab 
          v-if="activeTab === 'physical'"
          :form="form"
          :adventure="adventure"
          :debug-data="debugData"
          :image-styles-catalog="imageStylesCatalog"
          :editing-field="editingField"
          :temp-value="tempValue"
          :is-saving="isSaving"
          :is-batch-generating="isBatchGenerating"
          :is-quick-generating="isQuickGenerating"
          :active-menu-id="activeMenuId"
          :editor-npcs="editorNpcs"
          :editor-scenes="editorScenes"
          :editor-objects="editorObjects"
          :rule-enforcement-mode="form.rule_enforcement_mode"
          @update:temp-value="tempValue = $event"
          @update:pacing="form.time_per_turn = $event"
          @update:style="form.selected_style_id = $event"
          @start-edit="startEditing"
          @save-field="saveField"
          @cancel-edit="cancelEditing"
          @save-changes="saveChanges"
          @quick-regen="quickRegenerateVisual"
          @regen-all="regenerateAll"
          @open-regen-dialog="openRegenerateDialog"
          @open-upload-picker="openUploadPicker"
          @download-asset="downloadVisualAsset"
          @open-text-edit="openTextEdit"
          @toggle-menu="toggleMenu"
          @handle-hover="handleHover"
          @clear-hover="clearHover"
          @clear-creation-error="clearCreationError"
        />

        <PlotTab 
          v-if="activeTab === 'plot'"
          :form="form"
          :adventure="adventure"
          :tone-catalog="toneCatalog"
          :editing-field="editingField"
          :temp-value="tempValue"
          :is-saving="isSaving"
          :fix-newlines="fixNewlines"
          @update:temp-value="tempValue = $event"
          @update:tone="form.selected_tone_id = $event"
          @update:mode="form.rule_enforcement_mode = $event as any"
          @start-edit="startEditing"
          @save-field="saveField"
          @cancel-edit="cancelEditing"
          @save-changes="saveChanges"
        />

        <RebuildTab 
          v-if="activeTab === 'rebuild'"
          v-model:ai-edit-prompt="aiEditPrompt"
          v-model:ai-auto-visualize="aiAutoVisualize"
          :is-ai-editing="isAIEditing"
          @run-ai-edit="runAIEdit"
        />

        <AdvancedTab 
          v-if="activeTab === 'advanced'"
          :form="form"
          @update:generator="form.is_adventure_generator = $event; saveChanges()"
          @update:dynamic-items="form.allow_dynamic_items = $event; saveChanges()"
          @show-debug="showDebug = true"
          @save-changes="saveChanges"
        />
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
      :upload-limits="VISUAL_UPLOAD_LIMITS"
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
      :available-voices="availableVoices"
      :rule-enforcement-mode="form.rule_enforcement_mode"
      :is-saving="isSavingText"
      :format-voice-option="formatVoiceOption"
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
      @close="notifications = notifications.filter(x => x.id !== $event)"
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
