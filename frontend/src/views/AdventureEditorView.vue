<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authState } from '@/store/auth'
import { ArrowLeft, Save, Trash2, Wand2, Sparkles, Image as ImageIcon, Plus, X, AlertTriangle } from 'lucide-vue-next'
import bronzeTrophy from '@/assets/svg/bronze-award-trophy.svg'
import silverTrophy from '@/assets/svg/silver-award-trophy.svg'
import goldTrophy from '@/assets/svg/gold-award-trophy.svg'

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
const editForm = ref({ name: '', teaser: '', description: '', hp: 0, stamina: 0, mana: 0 })

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const promptError = ref('')
const showDebug = ref(false)
const activeTab = ref<'physical' | 'plot' | 'rebuild' | 'advanced'>('physical')

type VisualKind = 'cover' | 'protagonist' | 'scene' | 'npc' | 'object'

const selectedVisual = ref<{ kind: VisualKind; id: string; label: string; description: string; hint: string } | null>(null)
const selectedUploadTarget = ref<{ kind: VisualKind; id: string; label: string } | null>(null)
const visualPrompt = ref('')
const showPromptDialog = ref(false)
const isRegenerating = ref(false)
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
    // Hide tooltip when opening menu
    hoveredEntity.value = null
  }
}

// Close menus on outside click
if (typeof window !== 'undefined') {
  window.addEventListener('click', () => {
    activeMenuId.value = null
  })
}

const imageStylesCatalog = ref<any[]>([])
const toneCatalog = ref<any[]>([])

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

function handleHover(entity: any, event: MouseEvent) {
  if (activeMenuId.value) return
  hoveredEntity.value = entity
  
  // Decide alignment based on mouse position relative to viewport
  tooltipAlignTop.value = event.clientY > windowHeight.value * 0.6
  
  let x = event.clientX + 20
  const tooltipWidth = 280
  
  // Flip horizontally if near right edge
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
  original_prompt: '',
  rule_enforcement_mode: 'rpg' as 'rpg' | 'story' | 'chat',
  time_per_turn: 5,
  min_scenes: 1,
  max_scenes: 5,
  awards: [] as any[],
  allow_dynamic_items: true,
  
  // New Concept Fields
  plot: '',
  rules: '',
  intro_text: '',
  walkthrough: '',
  completed_condition: '',
  gameover_condition: '',
  
  // Visual & Tone
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


function normalizeEntityType(entity: any): string {
  return String(entity?.entity_type || entity?.type || '').trim().toUpperCase()
}

function fixNewlines(text: string | null | undefined): string {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

function isNpcEntity(entity: any): boolean {
  const kind = normalizeEntityType(entity)
  return kind === 'NPC' || kind === 'CHARACTER'
}

function isObjectEntity(entity: any): boolean {
  const kind = normalizeEntityType(entity)
  return kind === 'OBJECT' || kind === 'ITEM'
}

function mergeUniqueById(primary: any[], extra: any[]): any[] {
  const seen = new Set<string>()
  const merged: any[] = []
  for (const item of [...primary, ...extra]) {
    if (!item || !item.id) continue
    if (seen.has(item.id)) continue
    seen.add(item.id)
    merged.push(item)
  }
  return merged
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
    }
  } catch (error) {
    console.error('Failed to fetch catalogs:', error)
  }
}

function normalizeDebugPayload(raw: any): any {
  if (!raw || typeof raw !== 'object') {
    return raw
  }

  const payload = { ...raw }
  const allEntities = Array.isArray(raw.entities_all) ? raw.entities_all : []
  if (allEntities.length === 0) {
    return payload
  }

  const inferredNpcs = allEntities.filter((entity: any) => isNpcEntity(entity))
  const inferredObjects = allEntities.filter((entity: any) => isObjectEntity(entity))

  payload.npcs = mergeUniqueById(Array.isArray(raw.npcs) ? raw.npcs : [], inferredNpcs)
  payload.objects = mergeUniqueById(Array.isArray(raw.objects) ? raw.objects : [], inferredObjects)
  return payload
}

function getAwardIcon(tier: string) {
  const t = (tier || '').toLowerCase()
  if (t === 'gold') return goldTrophy
  if (t === 'silver') return silverTrophy
  return bronzeTrophy
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

function nonZeroStatEntries(stats: Record<string, unknown> | null | undefined): Array<[string, number]> {
  if (!stats || typeof stats !== 'object') return []
  return Object.entries(stats)
    .map(([key, value]) => {
      if (typeof value === 'number' && Number.isFinite(value)) return [key, value] as [string, number]
      if (typeof value === 'string' && value.trim() !== '') {
        const parsed = Number(value)
        if (Number.isFinite(parsed)) return [key, parsed] as [string, number]
      }
      return null
    })
    .filter((entry): entry is [string, number] => !!entry && entry[1] !== 0)
}


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
    form.value.original_prompt = data.original_prompt || ''
    form.value.rule_enforcement_mode = (data.rule_enforcement_mode as 'rpg' | 'story' | 'chat') || 'rpg'
    form.value.time_per_turn = data.time_per_turn || 5
    form.value.min_scenes = data.min_scenes || 1
    form.value.max_scenes = data.max_scenes || 5
    form.value.awards = data.awards || []
    form.value.allow_dynamic_items = data.allow_dynamic_items ?? true
    
    // New Concept Fields
    form.value.plot = data.plot || ''
    form.value.rules = data.rules || ''
    form.value.intro_text = data.intro_text || ''
    form.value.walkthrough = data.walkthrough || ''
    form.value.completed_condition = data.completed_condition || ''
    form.value.gameover_condition = data.gameover_condition || ''

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

function openTextEdit(type: string, id: string, currentName: string, currentDesc: string, currentTeaser: string = '', hp?: number, stamina?: number, mana?: number) {
  editEntityContext.value = { type, id }
  editForm.value = { 
    name: currentName || '', 
    description: fixNewlines(currentDesc || ''),
    teaser: fixNewlines(currentTeaser || ''),
    hp: hp || 0,
    stamina: stamina || 0,
    mana: mana || 0
  }
  showEditModal.value = true
}

async function saveEntityText(type: string, id: string) {
  isSavingText.value = true
  promptError.value = ''
  try {
    const res = await fetch(`${BASE}/adventures/${props.adventureId}/editor/entity`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify({
        target_type: type,
        target_id: id,
        name: editForm.value.name,
        teaser: type === 'cover' ? editForm.value.teaser : undefined,
        description: editForm.value.description,
        hp: editForm.value.hp || undefined,
        stamina: editForm.value.stamina || undefined,
        mana: editForm.value.mana || undefined
      })
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to save entity text')
    }
    showEditModal.value = false
    editEntityContext.value = null
    await Promise.all([fetchAdventure(), fetchDebugInfo()])
  } catch (error: any) {
    promptError.value = error.message
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
  } catch (error: any) {
    promptError.value = error.message
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
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error while saving.'
  } finally {
    isSaving.value = false
  }
}

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) return ''
  return `${ASSET_BASE}${imagePath}?v=${visualsCacheVersion.value}`
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

function getCoverNarrativeContext() {
  if (!debugData.value) return ''
  return debugData.value.adventure?.plot || debugData.value.adventure?.original_prompt || ''
}

function getVisualDescription(kind: VisualKind, id: string) {
  if (!debugData.value) return ''
  if (kind === 'cover') return getCoverNarrativeContext()
  if (kind === 'protagonist') {
    const base = debugData.value.protagonist?.description || ''
    const plot = debugData.value.adventure?.plot || ''
    return plot ? `${base}\n\nNarrative context: ${plot}` : base
  }
  if (kind === 'scene') return (debugData.value.scenes || []).find((s: any) => s.id === id)?.description || ''
  if (kind === 'npc') return (debugData.value.npcs || []).find((n: any) => n.id === id)?.description || ''
  return (debugData.value.objects || []).find((o: any) => o.id === id)?.description || ''
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  return `${Math.ceil(bytes / 1024)} KB`
}

function getUploadHint(kind: VisualKind): string {
  const spec = VISUAL_UPLOAD_LIMITS[kind]
  return `${spec.hint} Max file size: ${formatBytes(spec.maxBytes)}.`
}

async function getImageDimensions(file: File): Promise<{ width: number; height: number }> {
  const objectUrl = URL.createObjectURL(file)
  try {
    const dimensions = await new Promise<{ width: number; height: number }>((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve({ width: image.width, height: image.height })
      image.onerror = () => reject(new Error('Could not read image dimensions.'))
      image.src = objectUrl
    })
    return dimensions
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

function openUploadPicker(kind: VisualKind, id: string, label: string) {
  selectedUploadTarget.value = { kind, id, label }
  promptError.value = ''
  addNotification(`Upload ${label}: ${getUploadHint(kind)}`, 'info')
  if (uploadInput.value) {
    uploadInput.value.value = ''
    uploadInput.value.click()
  }
}

async function uploadSelectedVisual(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  const target = selectedUploadTarget.value
  if (!file || !target) {
    return
  }

  const spec = VISUAL_UPLOAD_LIMITS[target.kind]
  const ext = file.name.includes('.') ? file.name.split('.').pop()?.toLowerCase() || '' : ''
  if (!ALLOWED_UPLOAD_MIME_TYPES.has(file.type)) {
    addNotification('Unsupported file type. Please use PNG, JPEG, or WEBP.', 'error')
    input.value = ''
    return
  }
  if (!ALLOWED_UPLOAD_EXTENSIONS.has(ext)) {
    addNotification('Unsupported file extension. Please use .png, .jpg, .jpeg, or .webp.', 'error')
    input.value = ''
    return
  }
  if (file.size > spec.maxBytes) {
    addNotification(`File too large. Max file size is ${formatBytes(spec.maxBytes)}.`, 'error')
    input.value = ''
    return
  }

  try {
    const { width, height } = await getImageDimensions(file)
    if (width > spec.maxWidth || height > spec.maxHeight) {
      addNotification(
        `Image too large: ${width}x${height}. Max is ${spec.maxWidth}x${spec.maxHeight}.`,
        'error'
      )
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

    if (!res.ok) {
      let detail = 'Upload failed.'
      try {
        const data = await res.json()
        detail = data?.detail || detail
      } catch {
        // Keep default error text if response is not JSON.
      }
      throw new Error(detail)
    }

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

  // Sequential execution to prevent SQLite locking issues and allow for cleaner tracking
  for (const item of items) {
    await quickRegenerateVisual(kind, item.id || props.adventureId, true)
  }
  
  await fetchDebugInfo()
  isBatchGenerating.value[kind] = false
}

async function regenerateVisual() {
  if (!selectedVisual.value) return
  isRegenerating.value = true
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
  } catch (error: any) {
    promptError.value = error.message
  } finally {
    isRegenerating.value = false
  }
}

watch(
  () => props.adventureId,
  async (newAdventureId) => {
    if (!newAdventureId) {
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

    <!-- Header -->
    <header class="bg-slate-900/40 border-b border-white/5 px-8 py-3 flex justify-between items-center backdrop-blur-2xl sticky top-0 z-40 shadow-2xl">
      <div class="flex items-center gap-6">
        <button 
          @click="goBack" 
          class="flex items-center gap-3 px-5 py-2.5 rounded-xl bg-slate-800/60 hover:bg-emerald-500/20 border border-white/10 hover:border-emerald-500/50 transition-all duration-300 shadow-xl group active:scale-95"
        >
          <ArrowLeft class="w-4 h-4 text-emerald-500 group-hover:text-emerald-400 transition-colors" />
          <span class="text-xs font-black uppercase tracking-[0.2em] text-white transition-colors">Back</span>
        </button>
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-xl font-black text-white tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
              {{ adventure?.title || 'Adventure Editor' }}
            </h1>
            <span class="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-xs font-bold text-emerald-400 uppercase tracking-widest">Editor</span>
          </div>
          <p class="text-xs text-slate-500 font-mono uppercase tracking-tighter">Instance: {{ adventureId }}</p>
        </div>
      </div>
      
      <div class="flex items-center gap-6">
        <nav class="flex bg-black/40 rounded-xl p-1 border border-white/5 backdrop-blur-md shadow-inner">
          <button 
            v-for="tab in (['physical', 'plot', 'rebuild', 'advanced'] as const)" 
            :key="tab"
            @click="activeTab = tab"
            :class="[
              'px-4 py-1.5 text-xs font-black uppercase tracking-[0.2em] rounded-lg transition-all duration-300',
              activeTab === tab ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
            ]"
          >
            {{ tab }}
          </button>
        </nav>
      </div>
    </header>

    <main class="flex-grow p-6 max-w-[1400px] mx-auto w-full relative z-10 pb-16">
      <div v-if="isLoading" class="flex flex-col justify-center items-center py-40 gap-6">
        <div class="relative w-20 h-20">
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500/20"></div>
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin"></div>
        </div>
        <p class="text-xs font-bold text-emerald-500 uppercase tracking-[0.3em] animate-pulse">Loading Chronicles...</p>
      </div>
      
      <div v-else class="space-y-10">
        <!-- Physical Tab (World Assets) -->
        <div v-if="activeTab === 'physical'" class="space-y-10 animate-page-in">
          <!-- Quick Settings Row -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
           <div class="space-y-2">
              <div class="flex justify-between items-center">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Chronicle Title</label>
                <div v-if="form.title !== adventure?.title" class="flex gap-2 animate-fade-in">
                  <button @click="form.title = adventure.title" class="text-xs font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
                  <button @click="saveChanges" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
                </div>
              </div>
              <input v-model="form.title" type="text" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:border-emerald-500/50 outline-none transition-all" />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between items-center">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">In-Game Pacing ({{ form.time_per_turn }}m)</label>
                <div v-if="form.time_per_turn !== adventure?.time_per_turn" class="flex gap-2 animate-fade-in">
                  <button @click="form.time_per_turn = adventure.time_per_turn" class="text-xs font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
                  <button @click="saveChanges" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
                </div>
              </div>
              <input v-model.number="form.time_per_turn" type="range" min="1" max="60" class="w-full accent-emerald-500 h-2 bg-black/40 rounded-lg appearance-none cursor-pointer mt-3" />
            </div>
            <div class="space-y-2 flex flex-col justify-center">
              <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Active Style</label>
              <div class="flex items-center gap-2">
                <div class="px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs font-bold text-emerald-400 uppercase tracking-widest">
                  {{ imageStylesCatalog.find(s => s.id === form.selected_style_id)?.name || 'Default' }}
                </div>
                <span class="text-[10px] text-slate-600 uppercase font-black">Scroll down to change</span>
              </div>
            </div>
          </div>

          <!-- Visual Style Gallery -->
          <section v-if="imageStylesCatalog.length" class="space-y-6 bg-slate-900/40 p-8 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
             <div class="flex items-center justify-between">
                <div class="flex items-center gap-4">
                   <div class="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                      <i class="ra ra-eye-shield text-emerald-500"></i>
                   </div>
                   <div>
                      <h3 class="text-sm font-black text-white uppercase tracking-[0.2em]">Visual Atmosphere</h3>
                      <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Select the aesthetic direction for generated images</p>
                   </div>
                </div>
                <div v-if="form.selected_style_id !== (adventure?.selected_image_styles?.[0] || '')" class="flex gap-4 animate-fade-in">
                   <button @click="form.selected_style_id = adventure?.selected_image_styles?.[0] || ''" class="px-4 py-2 rounded-xl bg-slate-800 text-xs font-black text-slate-400 uppercase tracking-widest hover:text-white transition-all">Discard</button>
                   <button @click="saveChanges" class="px-6 py-2 rounded-xl bg-emerald-600 text-xs font-black text-white uppercase tracking-widest hover:bg-emerald-500 transition-all shadow-lg shadow-emerald-900/40">Apply Style</button>
                </div>
             </div>
             <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
                <button 
                  v-for="style in imageStylesCatalog" 
                  :key="style.id" 
                  @click="form.selected_style_id = style.id"
                  class="relative aspect-[4/5] rounded-2xl overflow-hidden border-2 transition-all duration-500 group"
                  :class="form.selected_style_id === style.id ? 'border-emerald-500 ring-4 ring-emerald-500/20' : 'border-transparent hover:border-white/10'"
                >
                  <img :src="style.image_url" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
                  <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80 group-hover:opacity-40 transition-opacity"></div>
                  <div class="absolute bottom-3 left-3 right-3">
                    <p class="text-[10px] font-black text-white uppercase tracking-tighter truncate">{{ style.name }}</p>
                  </div>
                  <div v-if="form.selected_style_id === style.id" class="absolute top-2 right-2 w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center shadow-lg">
                    <i class="ra ra-checkmark text-[10px] text-white"></i>
                  </div>
                </button>
             </div>
          </section>

          <!-- Moved AI Weaver to Rebuild Tab -->

          <!-- Assets Section -->
          <div v-if="debugData" class="space-y-12">
            <!-- Cover -->
            <section v-if="debugData.adventure" class="space-y-4">
              <div class="flex items-center justify-between">
                <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">World Essence</h3>
                <button @click="regenerateAll('cover')" :disabled="isBatchGenerating['cover']" class="px-4 py-2 rounded-xl bg-white/5 hover:bg-emerald-500/10 border border-white/5 text-xs font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-2 transition-all">
                  <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['cover'] }"></i>
                  Regenerate Cover
                </button>
              </div>
              <div class="relative group aspect-[3/2] bg-slate-900 border border-white/5 rounded-[2rem] overflow-hidden shadow-2xl max-w-2xl mx-auto">
                <img v-if="debugData.adventure.image_url" :src="buildVisualImageUrl(debugData.adventure.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-1000" />
                <div v-if="isQuickGenerating['cover_' + debugData.adventure.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                  <div class="flex flex-col items-center gap-2">
                    <i class="ra ra-cycle animate-spin text-3xl text-emerald-500"></i>
                    <span class="text-xs font-black text-emerald-500 uppercase tracking-widest">Reweaving Essence...</span>
                  </div>
                </div>
                <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent"></div>
                <div class="absolute inset-x-0 bottom-0 p-6">
                  <div class="flex justify-between items-end gap-12">
                    <div class="space-y-2 max-w-3xl">
                      <h4 class="text-xl font-black text-white tracking-tight">{{ debugData.adventure.title }}</h4>
                      <div class="flex items-center gap-3">
                        <p v-if="debugData.adventure.teaser" class="text-xs font-bold text-emerald-500/80 uppercase tracking-widest">{{ debugData.adventure.teaser }}</p>
                        <p v-else class="text-xs font-bold text-slate-500/40 uppercase tracking-widest italic">No teaser set...</p>
                        <button @click="openTextEdit('cover', debugData.adventure.id, debugData.adventure.title, getCoverNarrativeContext(), debugData.adventure.teaser)" class="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-emerald-400 transition-all" title="Edit Teaser & Metadata">
                          <i class="ra ra-quill-ink text-xs"></i>
                        </button>
                      </div>
                      <p class="text-sm text-slate-400 leading-relaxed line-clamp-1">{{ getCoverNarrativeContext() }}</p>
                    </div>
                    <div class="relative shrink-0">
                       <button @click="toggleMenu(debugData.adventure.id, $event)" class="w-10 h-10 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                          <div class="flex flex-col gap-0.5">
                            <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                            <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                            <div class="w-1.5 h-1.5 bg-white rounded-full"></div>
                          </div>
                        </button>
                        
                        <div v-if="activeMenuId === debugData.adventure.id" class="absolute right-0 bottom-full mb-3 w-56 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-2 z-50 animate-fade-in ring-1 ring-white/10">
                           <button @click="quickRegenerateVisual('cover', debugData.adventure.id)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-emerald-600 hover:text-white transition-all uppercase tracking-widest">Quick Regenerate</button>
                           <button @click="openRegenerateDialog('cover', debugData.adventure.id, debugData.adventure.title)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-cyan-600 hover:text-white transition-all uppercase tracking-widest">Regenerate (Prompt)</button>
                           <button @click="openUploadPicker('cover', debugData.adventure.id, debugData.adventure.title)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-amber-600 hover:text-white transition-all uppercase tracking-widest">Upload Custom Cover</button>
                           <button @click="openTextEdit('cover', debugData.adventure.id, debugData.adventure.title, getCoverNarrativeContext(), debugData.adventure.teaser)" class="w-full px-4 py-2.5 text-left text-xs font-black text-slate-300 hover:bg-blue-600 hover:text-white transition-all uppercase tracking-widest">Edit Essence Details</button>
                        </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>


            <!-- Categorized Grid -->
            <div class="space-y-8">
               <!-- Protagonist (Compact) -->
               <section v-if="debugData.protagonist" class="space-y-3">
                 <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">The Protagonist</h3>
                 <div class="max-w-[200px]">
                      <div @mouseenter="handleHover({ name: debugData.protagonist.name, description: debugData.protagonist.description, image_url: debugData.protagonist.profile_image, type: 'PROTAGONIST', stats: { hp: debugData.protagonist.hp, stamina: debugData.protagonist.stamina, mana: debugData.protagonist.mana } }, $event)" @mouseleave="clearHover" class="relative group aspect-square bg-slate-900 border border-white/5 rounded-xl overflow-hidden shadow-lg">
                        <img v-if="debugData.protagonist.profile_image" :src="buildVisualImageUrl(debugData.protagonist.profile_image)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                        <div v-if="isQuickGenerating['protagonist_' + debugData.protagonist.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                           <i class="ra ra-cycle animate-spin text-2xl text-emerald-500"></i>
                        </div>
                        <div class="absolute inset-x-0 bottom-0 p-3">
                          <div class="font-black text-sm text-white tracking-tight truncate">{{ debugData.protagonist.name }}</div>
                        </div>
                        
                        <!-- Context Menu -->
                        <div class="absolute top-2 right-2 z-40">
                          <button @click="toggleMenu(debugData.protagonist.id, $event)" class="w-8 h-8 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                            <div class="flex flex-col gap-0.5">
                              <div class="w-1 h-1 bg-white rounded-full"></div>
                              <div class="w-1 h-1 bg-white rounded-full"></div>
                              <div class="w-1 h-1 bg-white rounded-full"></div>
                            </div>
                          </button>
                          
                          <div v-if="activeMenuId === debugData.protagonist.id" class="absolute right-0 mt-2 w-48 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                             <button @click="quickRegenerateVisual('protagonist', debugData.protagonist.id)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regenerate</button>
                             <button @click="openRegenerateDialog('protagonist', debugData.protagonist.id, debugData.protagonist.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regenerate (Prompt)</button>
                             <button @click="openUploadPicker('protagonist', debugData.protagonist.id, debugData.protagonist.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Portrait</button>
                             <button @click="openTextEdit('protagonist', debugData.protagonist.id, debugData.protagonist.name, debugData.protagonist.description, '', debugData.protagonist.hp, debugData.protagonist.stamina, debugData.protagonist.mana)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Character</button>
                          </div>
                        </div>
                      </div>
                 </div>
               </section>

               <!-- Scenes -->
               <section v-if="editorScenes.length" class="space-y-6">
                 <div class="flex items-center justify-between">
                   <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">World Locations ({{ editorScenes.length }})</h3>
                   <button @click="regenerateAll('scene')" :disabled="isBatchGenerating['scene']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
                     <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['scene'] }"></i> Regenerate All
                   </button>
                 </div>
                   <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                    <div v-for="scene in editorScenes" :key="'scene_' + scene.id" @mouseenter="handleHover({ id: scene.id, name: scene.label || scene.name, description: scene.description, image_url: scene.image_url, type: 'LOCATION' }, $event)" @mouseleave="clearHover" class="relative group aspect-[3/2] bg-slate-900 border border-white/5 rounded-2xl shadow-xl transition-all overflow-visible">
                      <div class="absolute inset-0 rounded-2xl overflow-hidden">
                        <img v-if="scene.image_url" :src="buildVisualImageUrl(scene.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                        <div v-if="isQuickGenerating['scene_' + scene.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                           <i class="ra ra-cycle animate-spin text-2xl text-emerald-500"></i>
                        </div>
                        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent opacity-80"></div>
                        <div class="absolute inset-x-0 bottom-0 p-4">
                          <div class="font-black text-sm text-white tracking-wide uppercase truncate drop-shadow-md">{{ scene.label || scene.name }}</div>
                        </div>
                      </div>
                      
                      <!-- Context Menu -->
                      <div class="absolute top-3 right-3 z-40">
                        <button @click="toggleMenu(scene.id, $event)" class="w-8 h-8 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                          <div class="flex flex-col gap-0.5">
                            <div class="w-1 h-1 bg-white rounded-full"></div>
                            <div class="w-1 h-1 bg-white rounded-full"></div>
                            <div class="w-1 h-1 bg-white rounded-full"></div>
                          </div>
                        </button>
                        
                        <div v-if="activeMenuId === scene.id" class="absolute right-0 mt-2 w-48 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                           <button @click="quickRegenerateVisual('scene', scene.id)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regenerate</button>
                           <button @click="openRegenerateDialog('scene', scene.id, scene.label || scene.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regenerate (Prompt)</button>
                           <button @click="openUploadPicker('scene', scene.id, scene.label || scene.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Illustration</button>
                           <button @click="openTextEdit('scene', scene.id, scene.label || scene.name, scene.description)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Description</button>
                        </div>
                      </div>
                    </div>
                  </div>
               </section>

               <!-- NPCs -->
               <section v-if="editorNpcs.length" class="space-y-6">
                 <div class="flex items-center justify-between">
                   <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Notable Inhabitants ({{ editorNpcs.length }})</h3>
                   <button @click="regenerateAll('npc')" :disabled="isBatchGenerating['npc']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
                     <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['npc'] }"></i> Regenerate All
                   </button>
                 </div>
                   <div class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
                    <div v-for="npc in editorNpcs" :key="'npc_' + npc.id" @mouseenter="handleHover({ id: npc.id, name: npc.name, description: npc.description, image_url: npc.image_url, type: 'NPC', stats: npc.stats }, $event)" @mouseleave="clearHover" class="relative group aspect-[3/4] bg-slate-900 border border-white/5 rounded-2xl shadow-lg transition-all overflow-visible">
                      <div class="absolute inset-0 rounded-2xl overflow-hidden">
                        <img v-if="npc.image_url" :src="buildVisualImageUrl(npc.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                        <div v-if="isQuickGenerating['npc_' + npc.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                          <i class="ra ra-cycle animate-spin text-xl text-emerald-500"></i>
                        </div>
                        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
                        <div class="absolute bottom-0 left-0 right-0 p-3">
                          <div class="text-xs font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ npc.name }}</div>
                          <div v-if="npc.role" class="text-[9px] text-slate-300 font-bold uppercase tracking-tighter truncate opacity-70">{{ npc.role }}</div>
                          
                          <div v-if="form.rule_enforcement_mode !== 'chat' && npc.stats" class="flex gap-1.5 mt-1.5">
                            <template v-if="npc.stats.hp !== undefined">
                              <div class="flex items-center gap-1 text-[8px] font-black text-red-500 bg-red-500/10 px-1 py-0.5 rounded border border-red-500/20"><i class="ra ra-heart"></i> {{ npc.stats.hp }}</div>
                            </template>
                          </div>
                        </div>
                      </div>

                      <!-- Context Menu -->
                      <div class="absolute top-2 right-2 z-40">
                        <button @click="toggleMenu(npc.id, $event)" class="w-8 h-8 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                          <div class="flex flex-col gap-0.5">
                            <div class="w-1 h-1 bg-white rounded-full group-hover/dots:bg-white"></div>
                            <div class="w-1 h-1 bg-white rounded-full group-hover/dots:bg-white"></div>
                            <div class="w-1 h-1 bg-white rounded-full group-hover/dots:bg-white"></div>
                          </div>
                        </button>
                        
                        <div v-if="activeMenuId === npc.id" class="absolute right-0 mt-2 w-48 bg-slate-900 border border-white/20 rounded-xl shadow-2xl overflow-hidden py-1.5 z-[100] animate-fade-in ring-1 ring-white/5">
                           <button @click="quickRegenerateVisual('npc', npc.id)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regenerate</button>
                           <button @click="openRegenerateDialog('npc', npc.id, npc.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regenerate (Prompt)</button>
                           <button @click="openUploadPicker('npc', npc.id, npc.name)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                           <button @click="openTextEdit('npc', npc.id, npc.name, npc.description, '', npc.stats?.hp, npc.stats?.stamina, npc.stats?.mana)" class="w-full px-4 py-2 text-left text-xs font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
                        </div>
                      </div>
                    </div>
                  </div>
               </section>

               <!-- Items -->
               <section v-if="editorObjects.length" class="space-y-6">
                 <div class="flex items-center justify-between">
                   <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Mystical Objects ({{ editorObjects.length }})</h3>
                   <button @click="regenerateAll('object')" :disabled="isBatchGenerating['object']" class="text-xs font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
                     <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Regenerate All
                   </button>
                 </div>
                   <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
                    <div v-for="obj in editorObjects" :key="'obj_' + obj.id" @mouseenter="handleHover({ id: obj.id, name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM', stats: obj.stats }, $event)" @mouseleave="clearHover" class="relative group aspect-square bg-slate-900 border border-white/5 rounded-xl shadow-lg transition-all overflow-visible">
                      <div class="absolute inset-0 rounded-xl overflow-hidden">
                        <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                        <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                          <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
                        </div>
                        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent opacity-80"></div>
                        <div class="absolute bottom-0 left-0 right-0 p-2">
                          <div class="text-[10px] font-black text-white uppercase tracking-wider truncate drop-shadow-md">{{ obj.name }}</div>
                          
                          <div v-if="form.rule_enforcement_mode !== 'chat' && obj.stats && Object.keys(obj.stats).length > 0" class="flex gap-1 mt-1">
                            <div class="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_5px_rgba(16,185,129,0.5)]"></div>
                          </div>
                        </div>
                      </div>

                      <!-- Context Menu -->
                      <div class="absolute top-1.5 right-1.5 z-40">
                        <button @click="toggleMenu(obj.id, $event)" class="w-6 h-6 rounded-full bg-black/60 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:bg-emerald-500 transition-all shadow-lg group/dots">
                          <div class="flex flex-col gap-0.5">
                            <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                            <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                            <div class="w-0.5 h-0.5 bg-white rounded-full"></div>
                          </div>
                        </button>
                        
                        <div v-if="activeMenuId === obj.id" class="absolute right-0 mt-1 w-40 bg-slate-900 border border-white/20 rounded-lg shadow-2xl overflow-hidden py-1 z-[100] animate-fade-in ring-1 ring-white/5">
                           <button @click="quickRegenerateVisual('object', obj.id)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-emerald-500 hover:text-white transition-all">Quick Regen</button>
                           <button @click="openRegenerateDialog('object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-cyan-500 hover:text-white transition-all">Regen (Prompt)</button>
                           <button @click="openUploadPicker('object', obj.id, obj.name)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-amber-500 hover:text-white transition-all">Upload Image</button>
                           <button @click="openTextEdit('object', obj.id, obj.name, obj.description)" class="w-full px-3 py-1.5 text-left text-[10px] font-bold text-slate-300 hover:bg-blue-500 hover:text-white transition-all">Edit Details</button>
                        </div>
                      </div>
                    </div>
                  </div>
               </section>

 
               <!-- Quests -->
               <section v-if="adventure?.quests?.length" class="space-y-6">
                 <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Quest Log ({{ adventure.quests.length }})</h3>
                 <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                   <div v-for="quest in adventure.quests" :key="'quest_' + quest.id" class="bg-slate-900/40 border border-white/5 rounded-2xl p-4 hover:border-emerald-500/20 transition-all group">
                     <div class="flex items-start justify-between mb-2">
                       <div class="flex items-center gap-3">
                         <div class="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                           <i :class="[quest.is_main ? 'ra ra-trophy text-emerald-400' : 'ra ra-scroll-unfurled text-slate-400']"></i>
                         </div>
                         <div>
                           <h4 class="text-sm font-bold text-white">{{ quest.title }}</h4>
                           <span class="text-xs text-slate-500 uppercase tracking-widest">{{ quest.is_main ? 'Main Quest' : 'Side Quest' }}</span>
                         </div>
                       </div>
                       <span class="px-2 py-0.5 rounded bg-black/40 text-xs font-black text-emerald-500 uppercase border border-emerald-500/20">{{ quest.exp_reward }} XP</span>
                     </div>
                     <p class="text-xs text-slate-400 leading-relaxed line-clamp-2 mb-3">{{ quest.description }}</p>
                     <div class="flex items-center gap-2">
                        <div class="flex-grow h-1 bg-black/40 rounded-full overflow-hidden">
                           <div class="h-full bg-emerald-500/40" :style="{ width: quest.status === 'completed' ? '100%' : '0%' }"></div>
                        </div>
                        <span class="text-xs font-black uppercase tracking-tighter" :class="quest.status === 'completed' ? 'text-emerald-500' : 'text-slate-600'">{{ quest.status }}</span>
                     </div>
                   </div>
                 </div>
               </section>
 
               <!-- Awards (Read-only) -->
               <section v-if="adventure?.awards?.length" class="space-y-6">
                 <h3 class="text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Achievements & Awards ({{ adventure.awards.length }})</h3>
                 <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                   <div v-for="award in adventure.awards" :key="'award_' + award.key" class="bg-slate-900/40 border border-white/5 rounded-2xl p-5 hover:border-emerald-500/20 transition-all group flex items-start gap-4">
                     <div :class="[
                       'w-12 h-12 rounded-xl flex items-center justify-center border shrink-0',
                       award.tier === 'gold' ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' :
                       award.tier === 'silver' ? 'bg-slate-300/10 border-slate-300/20 text-slate-300' :
                       'bg-orange-700/10 border-orange-700/20 text-orange-700'
                     ]">
                       <img :src="getAwardIcon(award.tier)" class="w-8 h-8 object-contain" alt="Trophy" />
                     </div>
                     <div class="space-y-1">
                       <div class="flex items-center gap-2">
                         <h4 class="text-sm font-black text-white uppercase tracking-tight">{{ award.title }}</h4>
                         <span :class="[
                           'text-xs font-black uppercase px-1.5 py-0.5 rounded border',
                           award.tier === 'gold' ? 'bg-amber-500/20 border-amber-500/30 text-amber-500' :
                           award.tier === 'silver' ? 'bg-slate-300/20 border-slate-300/30 text-slate-300' :
                           'bg-orange-700/20 border-orange-700/30 text-orange-700'
                         ]">{{ award.tier }}</span>
                       </div>
                       <p class="text-xs text-slate-400 leading-relaxed">{{ award.description }}</p>
                       <p class="text-xs text-slate-500 italic mt-1">Requirement: {{ award.requirement }}</p>
                     </div>
                   </div>
                 </div>
               </section>

            </div>
          </div>
        </div>


        <div v-if="activeTab === 'plot'" class="space-y-10 animate-page-in">
          <div class="bg-slate-900/40 p-10 rounded-[3rem] border border-white/5 backdrop-blur-md shadow-2xl space-y-12">
            <div class="flex justify-between items-center">
              <div>
                <h2 class="text-2xl font-black text-white tracking-tight uppercase tracking-[0.2em]">Narrative Blueprint</h2>
                <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Adjust the soul and mechanics of your chronicles</p>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-10 border-b border-white/5 pb-10">
               <!-- Rule Enforcement (Moved from Physical) -->
               <div class="space-y-4">
                 <div class="flex justify-between items-center">
                   <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Game Mechanics</label>
                   <button v-if="form.rule_enforcement_mode !== adventure?.rule_enforcement_mode" @click="saveChanges" class="text-xs font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 transition-colors">Save Mode</button>
                 </div>
                 <div class="flex bg-black/40 p-1 rounded-2xl border border-white/5 shadow-inner">
                   <button 
                     v-for="mode in ['rpg', 'story', 'chat']" 
                     :key="mode" 
                     @click="form.rule_enforcement_mode = mode"
                     :class="[
                       'flex-1 py-3 rounded-xl text-xs font-black uppercase tracking-widest transition-all',
                       form.rule_enforcement_mode === mode ? 'bg-emerald-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
                     ]"
                   >
                     {{ mode === 'rpg' ? 'RPG (Exp)' : mode }}
                   </button>
                 </div>
                 <div v-if="form.rule_enforcement_mode === 'rpg'" class="p-4 rounded-2xl border border-amber-500/30 bg-amber-500/5 flex items-start gap-4">
                    <AlertTriangle class="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    <p class="text-slate-400 text-[10px] leading-relaxed uppercase font-bold tracking-tight">
                      <span class="text-amber-500 font-black">Warning:</span> Experimental mode. Combat and attribute checks may behave unexpectedly.
                    </p>
                 </div>
               </div>

               <!-- Narrative Tone -->
               <div class="space-y-4">
                 <div class="flex justify-between items-center">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Narrative Tone</label>
                    <button v-if="form.selected_tone_id !== (adventure?.selected_tone || '')" @click="saveChanges" class="text-xs font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 transition-colors">Apply Tone</button>
                 </div>
                 <div class="grid grid-cols-2 gap-3">
                    <button 
                      v-for="tone in toneCatalog" 
                      :key="tone.id" 
                      @click="form.selected_tone_id = tone.id"
                      class="relative h-14 rounded-xl overflow-hidden border-2 transition-all group"
                      :class="form.selected_tone_id === tone.id ? 'border-emerald-500 ring-4 ring-emerald-500/20' : 'border-transparent hover:border-white/10'"
                    >
                       <img :src="tone.image_url" class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
                       <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-[1px] flex items-center justify-center group-hover:bg-slate-900/40 transition-colors">
                         <span class="text-[10px] font-black text-white uppercase tracking-[0.2em]">{{ tone.name }}</span>
                       </div>
                    </button>
                 </div>
               </div>
            </div>

            <div class="flex flex-col gap-10">
              <!-- Adventure Plot Section -->
              <div class="space-y-4">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Adventure Plot (Secret)</label>
                <div v-if="editingField === 'plot'" class="space-y-4 animate-fade-in">
                  <textarea v-model="tempValue" rows="10" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[200px]" placeholder="The main plotline, hidden goals, and core narrative..."></textarea>
                  <div class="flex gap-4">
                    <button @click="saveField" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                      <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                      <span>Save Plot</span>
                    </button>
                    <button @click="cancelEditing" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
                  </div>
                </div>
                <div v-else @click="startEditing('plot', form.plot)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
                  <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
                    <i class="ra ra-quill-pen"></i> Edit Plot
                  </div>
                  <p v-if="form.plot" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.plot) }}</p>
                  <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No plot defined. Click to weave the story.</p>
                </div>
              </div>

              <!-- Rules Section -->
              <div class="space-y-4">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Adventure Rules / Mechanics</label>
                <div v-if="editingField === 'rules'" class="space-y-4 animate-fade-in">
                  <textarea v-model="tempValue" rows="6" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[150px]" placeholder="Special rules for this world..."></textarea>
                  <div class="flex gap-4">
                    <button @click="saveField" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                      <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                      <span>Save Rules</span>
                    </button>
                    <button @click="cancelEditing" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
                  </div>
                </div>
                <div v-else @click="startEditing('rules', form.rules)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
                  <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
                    <i class="ra ra-quill-pen"></i> Edit Rules
                  </div>
                  <p v-if="form.rules" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.rules) }}</p>
                  <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No specific rules. Click to define world logic.</p>
                </div>
              </div>

              <!-- Session Intro Section -->
              <div class="space-y-4">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">Session Intro Text (Shown Once)</label>
                <div v-if="editingField === 'intro_text'" class="space-y-4 animate-fade-in">
                  <textarea v-model="tempValue" rows="6" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[150px]" placeholder="Optional opening system text for a newly started session..."></textarea>
                  <div class="flex gap-4">
                    <button @click="saveField" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                      <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                      <span>Save Intro</span>
                    </button>
                    <button @click="cancelEditing" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
                  </div>
                </div>
                <div v-else @click="startEditing('intro_text', form.intro_text)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
                  <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
                    <i class="ra ra-quill-pen"></i> Edit Intro
                  </div>
                  <p v-if="form.intro_text" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.intro_text) }}</p>
                  <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No intro text set. Click to add a one-time session opener.</p>
                </div>
              </div>

              <!-- Walkthrough Section -->
              <div class="space-y-4">
                <label class="block text-xs font-black text-slate-500 uppercase tracking-[0.3em]">GM Walkthrough (Solution Path)</label>
                <div v-if="editingField === 'walkthrough'" class="space-y-4 animate-fade-in">
                  <textarea v-model="tempValue" rows="10" class="w-full bg-black/60 border border-emerald-500/50 rounded-3xl px-8 py-6 text-lg text-slate-200 focus:ring-2 ring-emerald-500/20 outline-none transition-all leading-relaxed shadow-2xl resize-y min-h-[200px]" placeholder="Step-by-step secret solution for the GM..."></textarea>
                  <div class="flex gap-4">
                    <button @click="saveField" :disabled="isSaving" class="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg flex items-center gap-2">
                      <i v-if="isSaving" class="ra ra-cycle animate-spin"></i>
                      <span>Save Walkthrough</span>
                    </button>
                    <button @click="cancelEditing" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all">Cancel</button>
                  </div>
                </div>
                <div v-else @click="startEditing('walkthrough', form.walkthrough)" class="group relative cursor-pointer bg-black/20 hover:bg-black/40 border border-white/5 hover:border-emerald-500/30 rounded-[2rem] p-8 transition-all duration-300 shadow-inner">
                  <div class="absolute top-6 right-8 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-2 text-emerald-500 text-xs font-black uppercase">
                    <i class="ra ra-quill-pen"></i> Edit Walkthrough
                  </div>
                  <p v-if="form.walkthrough" class="text-lg text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.walkthrough) }}</p>
                  <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center py-6">No solution path recorded. Click to document the intended flow.</p>
                </div>
              </div>

              <!-- Conditions -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-10">
                <div class="space-y-4">
                  <label class="block text-xs font-black text-emerald-500/80 uppercase tracking-[0.3em]">Win Conditions</label>
                  <div v-if="editingField === 'completed_condition'" class="space-y-4 animate-fade-in">
                    <textarea v-model="tempValue" rows="4" class="w-full bg-black/60 border border-emerald-500/50 rounded-2xl px-6 py-5 text-base text-slate-200 outline-none transition-all resize-y" placeholder="What must the player achieve?"></textarea>
                    <div class="flex gap-4">
                      <button @click="saveField" :disabled="isSaving" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all">Save</button>
                      <button @click="cancelEditing" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all">Cancel</button>
                    </div>
                  </div>
                  <div v-else @click="startEditing('completed_condition', form.completed_condition)" class="group relative cursor-pointer bg-emerald-500/5 hover:bg-emerald-500/10 border border-emerald-500/10 hover:border-emerald-500/30 rounded-2xl p-6 transition-all duration-300">
                    <p v-if="form.completed_condition" class="text-base text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.completed_condition) }}</p>
                    <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center">Define Victory Conditions</p>
                  </div>
                </div>

                <div class="space-y-4">
                  <label class="block text-xs font-black text-red-500/80 uppercase tracking-[0.3em]">Loss Conditions</label>
                  <div v-if="editingField === 'gameover_condition'" class="space-y-4 animate-fade-in">
                    <textarea v-model="tempValue" rows="4" class="w-full bg-black/60 border border-red-500/50 rounded-2xl px-6 py-5 text-base text-slate-200 outline-none transition-all resize-y" placeholder="How can the adventure fail?"></textarea>
                    <div class="flex gap-4">
                      <button @click="saveField" :disabled="isSaving" class="px-6 py-2 bg-red-600 hover:bg-red-500 text-white text-xs font-black uppercase tracking-widest rounded-lg transition-all">Save</button>
                      <button @click="cancelEditing" class="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 text-xs font-black uppercase tracking-widest rounded-lg transition-all">Cancel</button>
                    </div>
                  </div>
                  <div v-else @click="startEditing('gameover_condition', form.gameover_condition)" class="group relative cursor-pointer bg-red-500/5 hover:bg-red-500/10 border border-red-500/10 hover:border-red-500/30 rounded-2xl p-6 transition-all duration-300">
                    <p v-if="form.gameover_condition" class="text-base text-slate-300 leading-relaxed whitespace-pre-wrap">{{ fixNewlines(form.gameover_condition) }}</p>
                    <p v-else class="text-xs italic text-slate-600 uppercase tracking-widest text-center">Define Failure Conditions</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Rebuild Tab (AI Weaver) -->
        <div v-if="activeTab === 'rebuild'" class="space-y-10 animate-page-in">
          <div class="bg-slate-900/40 p-10 rounded-[3rem] border border-white/5 backdrop-blur-md shadow-2xl space-y-8">
            <div class="flex items-center gap-6">
              <div class="w-16 h-16 bg-emerald-500/10 rounded-2xl flex items-center justify-center border border-emerald-500/20 shadow-lg">
                <i class="ra ra-player-teleport text-emerald-500 text-3xl"></i>
              </div>
              <div>
                <h2 class="text-2xl font-black text-white tracking-tight uppercase">AI Reality Weaver</h2>
                <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Rebuild or expand your world using natural language</p>
              </div>
            </div>

            <div class="space-y-6">
               <div class="relative">
                  <textarea 
                    v-model="aiEditPrompt" 
                    @keyup.enter.ctrl="runAIEdit" 
                    :disabled="isAIEditing"
                    rows="4"
                    class="w-full bg-black/40 border border-white/5 rounded-3xl px-8 py-6 text-lg text-white focus:border-emerald-500 outline-none transition-all disabled:opacity-50 shadow-inner" 
                    placeholder="Tell the Weaver to change reality... (e.g. 'Add a hidden basement to the tavern with a smuggler NPC')" 
                  ></textarea>
                  <div class="absolute bottom-6 right-8 text-xs font-bold text-slate-600 uppercase tracking-widest">Ctrl + Enter to Execute</div>
               </div>

               <div class="flex flex-wrap items-center justify-between gap-6">
                  <div class="flex bg-black/60 p-1 rounded-2xl border border-white/5 shadow-inner">
                    <button 
                      @click="aiAutoVisualize = false" 
                      :class="['px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all', !aiAutoVisualize ? 'bg-slate-800 text-white shadow-lg' : 'text-slate-500 hover:text-slate-400']"
                    >
                      Text Only
                    </button>
                    <button 
                      @click="aiAutoVisualize = true" 
                      :class="['px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all flex items-center gap-2', aiAutoVisualize ? 'bg-emerald-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-400']"
                    >
                      <i class="ra ra-eye-shield"></i>
                      Visuals
                    </button>
                  </div>

                  <button @click="runAIEdit" :disabled="isAIEditing || !aiEditPrompt" class="px-12 py-4 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-black uppercase tracking-widest rounded-2xl disabled:opacity-50 transition-all shadow-xl shadow-emerald-900/40 flex items-center gap-4">
                    <i v-if="isAIEditing" class="ra ra-cycle animate-spin"></i>
                    <span>{{ isAIEditing ? 'Weaving Reality...' : 'Execute Command' }}</span>
                  </button>
               </div>
            </div>

            <!-- Helpful Hints -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 pt-8 border-t border-white/5">
              <div v-for="hint in [
                { icon: 'ra-quill-ink', title: 'Content', desc: 'Add new scenes, NPCs, or items' },
                { icon: 'ra-cycle', title: 'Refine', desc: 'Modify existing descriptions or connections' },
                { icon: 'ra-crystal-ball', title: 'Logic', desc: 'Establish new rules or hidden secrets' }
              ]" :key="hint.title" class="flex gap-4">
                <i :class="['ra', hint.icon, 'text-emerald-500/50 mt-1']"></i>
                <div>
                  <h4 class="text-xs font-black text-slate-400 uppercase tracking-widest mb-1">{{ hint.title }}</h4>
                  <p class="text-xs text-slate-500 leading-relaxed">{{ hint.desc }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Advanced Tab -->
        <div v-else-if="activeTab === 'advanced'" class="space-y-10 animate-page-in">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <!-- Meta-Adventure Features -->
            <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6">
              <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
                <i class="ra ra-gear text-amber-500"></i> Special Features
              </h4>
              <p class="text-xs text-slate-400 leading-relaxed">Enable specialized behaviors for this adventure.</p>
              
              <div class="space-y-4">
                <div class="flex items-center justify-between p-4 bg-white/5 border border-white/5 rounded-2xl group hover:border-emerald-500/30 transition-all">
                  <div class="space-y-1">
                    <span class="text-xs font-black uppercase tracking-widest text-slate-200">Adventure Generator</span>
                    <p class="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Enable Game-Designer NPC & Tools</p>
                  </div>
                  <button 
                    @click="form.is_adventure_generator = !form.is_adventure_generator; saveChanges()"
                    :class="['w-14 h-8 rounded-full transition-all relative flex items-center px-1', form.is_adventure_generator ? 'bg-emerald-600' : 'bg-slate-800']"
                  >
                    <div :class="['w-6 h-6 bg-white rounded-full shadow-lg transition-transform duration-300', form.is_adventure_generator ? 'translate-x-6' : 'translate-x-0']"></div>
                  </button>
                </div>
              </div>
            </div>

            <!-- Data Debug -->

            <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6">
              <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
                <i class="ra ra-crystal-ball text-cyan-500"></i> Adventure Data Debug
              </h4>
              <p class="text-xs text-slate-400 leading-relaxed">View raw JSON data structures of this adventure template. Useful for deep analysis.</p>
              <div class="grid grid-cols-1 gap-3">
                <button @click="showDebug = true" class="flex items-center justify-between px-6 py-4 bg-white/5 hover:bg-cyan-500/10 border border-white/5 hover:border-cyan-500/30 rounded-2xl transition-all group">
                  <span class="text-xs font-black uppercase tracking-widest text-slate-300 group-hover:text-cyan-400">Open JSON Debug Inspector</span>
                  <i class="ra ra-search text-cyan-500"></i>
                </button>
              </div>
            </div>

            <!-- GM Capabilities -->
            <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6">
              <h4 class="text-xs font-black text-white uppercase tracking-widest flex items-center gap-2">
                <i class="ra ra-crystal-wand text-violet-400"></i> Game Master Capabilities
              </h4>
              <p class="text-xs text-slate-400 leading-relaxed">Control what the GM is allowed to do during live sessions of this adventure.</p>

              <!-- allow_dynamic_items toggle -->
              <div class="flex items-center justify-between p-5 bg-black/30 rounded-2xl border border-white/5">
                <div class="space-y-1 pr-6">
                  <p class="text-sm font-bold text-white">GM may create new items in-game</p>
                  <p class="text-xs text-slate-500 leading-relaxed">Allows the GM to invent and drop new items (e.g. potions, loot) that were not in the original world manifest.</p>
                </div>
                <button
                  id="toggle-allow-dynamic-items"
                  type="button"
                  @click="form.allow_dynamic_items = !form.allow_dynamic_items; saveChanges()"
                  :class="[
                    'relative inline-flex h-7 w-13 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500',
                    form.allow_dynamic_items ? 'bg-violet-600' : 'bg-slate-700'
                  ]"
                  :aria-pressed="form.allow_dynamic_items"
                >
                  <span
                    :class="[
                      'inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition-transform duration-200',
                      form.allow_dynamic_items ? 'translate-x-7' : 'translate-x-1'
                    ]"
                  />
                </button>
              </div>
            </div>

          </div>
        </div>
      </div>
    </main>

    <!-- HOVER TOOLTIP (Teleport to Body) -->
    <Teleport to="body">
      <Transition name="tooltip">
        <div 
          v-if="hoveredEntity && !activeMenuId" 
          class="fixed z-[100] pointer-events-none transition-all duration-75 flex flex-col"
          :style="{ 
            left: mousePos.x + 'px', 
            top: tooltipAlignTop ? 'auto' : (mousePos.y + 15) + 'px',
            bottom: tooltipAlignTop ? (windowHeight - mousePos.y + 15) + 'px' : 'auto'
          }"
        >
          <div class="w-64 max-h-[85vh] bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl backdrop-blur-xl overflow-y-auto flex flex-col animate-tooltip-in scrollbar-hide">
            <!-- Image Area -->
            <div v-if="hoveredEntity.image_url" class="h-32 w-full relative">
              <img :src="buildVisualImageUrl(hoveredEntity.image_url)" class="absolute inset-0 w-full h-full object-cover object-top" />
              <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
            </div>

            <!-- Content -->
            <div class="p-4 bg-slate-900 space-y-3">
              <div class="flex items-start justify-between mb-1">
                <div class="flex flex-col">
                  <span class="text-sm font-bold text-white uppercase tracking-wider leading-tight">{{ hoveredEntity.name }}</span>
                  <span class="text-[10px] text-slate-500 font-mono uppercase tracking-tighter">{{ hoveredEntity.id }}</span>
                </div>
                <span 
                  class="text-[9px] px-1.5 py-0.5 rounded border font-mono uppercase border-emerald-500/50 text-emerald-400 bg-emerald-500/5 shrink-0"
                >
                  {{ hoveredEntity.type }}
                </span>
              </div>
              
              <!-- Stats Display (Mode Aware) -->
              <div v-if="form.rule_enforcement_mode !== 'chat' && hoveredEntity.stats" class="flex flex-wrap gap-2 pt-2 border-t border-white/5">
                <template v-if="hoveredEntity.type === 'NPC' || hoveredEntity.type === 'PROTAGONIST'">
                  <div class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-red-500/10 border border-red-500/20 text-xs font-black text-red-500">
                    <i class="ra ra-heart"></i> {{ hoveredEntity.stats.hp || 10 }}
                  </div>
                  <template v-if="form.rule_enforcement_mode === 'rpg' || form.rule_enforcement_mode === 'story'">
                    <div class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-xs font-black text-emerald-500">
                      <i class="ra ra-muscle-up"></i> {{ hoveredEntity.stats.stamina || 10 }}
                    </div>
                    <div v-if="form.rule_enforcement_mode === 'rpg'" class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-xs font-black text-blue-500">
                      <i class="ra ra-crystal-ball"></i> {{ hoveredEntity.stats.mana || 0 }}
                    </div>
                  </template>
                </template>
                <template v-else-if="hoveredEntity.type === 'ITEM'">
                  <div v-for="(val, stat) in hoveredEntity.stats" :key="stat" class="flex items-center gap-1.5 px-2 py-0.5 rounded bg-slate-800 border border-white/10 text-xs font-bold text-slate-300 uppercase">
                    {{ String(stat).replace('_', ' ') }}: +{{ val }}
                  </div>
                </template>
              </div>

              <p class="text-xs text-slate-400 leading-relaxed italic whitespace-pre-wrap">{{ fixNewlines(hoveredEntity.description) }}</p>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  
      <!-- MANUAL PROMPT DIALOG -->
      <Teleport to="body">
        <Transition name="modal">
        <div v-if="showPromptDialog && selectedVisual" class="fixed inset-0 z-[250] flex items-center justify-center p-6 backdrop-blur-2xl bg-slate-950/70">
          <div class="modal-content w-full max-w-xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden">
            <div class="p-10 space-y-8">
              <div class="flex justify-between items-center">
                <div class="space-y-1">
                  <h3 class="text-xs font-black text-cyan-500 uppercase tracking-widest">Manual Vision Weaver</h3>
                  <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">Target: {{ selectedVisual.label }}</p>
                </div>
                <button @click="showPromptDialog = false" class="text-slate-500 hover:text-white transition-colors">
                  <i class="ra ra-cancel text-xl"></i>
                </button>
              </div>

              <div class="space-y-6">
                <div class="p-6 bg-black/40 rounded-3xl border border-white/5 space-y-4">
                  <div class="flex items-start gap-4">
                    <i class="ra ra-crystal-ball text-2xl text-cyan-500/50"></i>
                    <div class="space-y-1">
                      <h4 class="text-xs font-black text-slate-500 uppercase">Current description</h4>
                      <p class="text-xs text-slate-400 leading-relaxed italic line-clamp-3 whitespace-pre-wrap">"{{ fixNewlines(selectedVisual.description) }}"</p>
                    </div>
                  </div>
                </div>

                <div class="space-y-3">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Override Prompt</label>
                  <p class="text-xs text-amber-300/80 leading-relaxed">Upload hint: {{ selectedVisual.hint }} Max file size: {{ formatBytes(VISUAL_UPLOAD_LIMITS[selectedVisual.kind].maxBytes) }}.</p>
                  <textarea 
                    v-model="visualPrompt" 
                    rows="5" 
                    placeholder="Describe exactly what you want to see. This will ignore the current asset description..." 
                    class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500 outline-none transition-all leading-relaxed shadow-inner"
                  ></textarea>
                </div>

                <div class="flex items-center justify-between p-4 bg-white/5 border border-white/5 rounded-2xl">
                  <div class="space-y-1">
                    <span class="text-xs font-black uppercase tracking-widest text-slate-200">High-Quality Weaver</span>
                    <p class="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Use Advanced Model for superior detail</p>
                  </div>
                  <button 
                    @click="useAdvancedModel = !useAdvancedModel"
                    :class="['w-12 h-6 rounded-full transition-all relative flex items-center px-1', useAdvancedModel ? 'bg-cyan-600' : 'bg-slate-800']"
                  >
                    <div :class="['w-4 h-4 bg-white rounded-full shadow-lg transition-transform duration-300', useAdvancedModel ? 'translate-x-6' : 'translate-x-0']"></div>
                  </button>
                </div>
              </div>

              <div class="flex justify-end gap-6 pt-4">
                <button @click="showPromptDialog = false" class="px-8 py-3 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors">Discard</button>
                <button @click="regenerateVisual" :disabled="isRegenerating" class="px-10 py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-black uppercase text-xs tracking-widest rounded-xl shadow-lg shadow-cyan-900/20 disabled:opacity-50 flex items-center gap-3">
                  <i v-if="isRegenerating" class="ra ra-cycle animate-spin"></i>
                  <span>{{ isRegenerating ? 'Weaving...' : 'Generate Vision' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showEditModal && editEntityContext" class="fixed inset-0 z-[200] flex items-center justify-center p-6 backdrop-blur-xl bg-slate-950/60">
          <div class="modal-content w-full max-w-2xl bg-slate-900 border border-white/10 rounded-[2.5rem] shadow-2xl overflow-hidden">
            <div class="p-10 space-y-8">
              <div class="flex justify-between items-center">
                <div class="space-y-1">
                  <h3 class="text-xs font-black text-emerald-500 uppercase tracking-widest">Editing {{ editEntityContext.type }}</h3>
                  <p class="text-slate-500 text-xs uppercase font-bold tracking-tighter">ID: {{ editEntityContext.id }}</p>
                </div>
                <button @click="showEditModal = false" class="text-slate-500 hover:text-white transition-colors">
                  <i class="ra ra-cancel text-xl"></i>
                </button>
              </div>

              <div class="space-y-6">
                <div class="space-y-3">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Entity Name</label>
                  <input v-model="editForm.name" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-2xl font-bold text-white focus:border-emerald-500 outline-none transition-all shadow-inner" />
                
                <!-- Stats Inputs -->
                <div v-if="['protagonist', 'npc'].includes(editEntityContext.type) && form.rule_enforcement_mode !== 'chat'" class="grid grid-cols-3 gap-4">
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Health (HP)</label>
                    <input v-model.number="editForm.hp" type="number" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-red-500/50 outline-none transition-all" />
                  </div>
                  <div class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Stamina (STM)</label>
                    <input v-model.number="editForm.stamina" type="number" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-emerald-500/50 outline-none transition-all" />
                  </div>
                  <div v-if="form.rule_enforcement_mode === 'rpg'" class="space-y-2">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Mana (MAN)</label>
                    <input v-model.number="editForm.mana" type="number" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2 text-white font-bold focus:border-blue-500/50 outline-none transition-all" />
                  </div>
                </div>
                </div>
                
                <div v-if="editEntityContext.type === 'cover'" class="space-y-3">
                  <div class="flex justify-between items-center">
                    <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">Teaser (Max 300 Characters)</label>
                    <span :class="['text-xs font-bold tracking-widest', editForm.teaser.length > 300 ? 'text-red-500' : 'text-emerald-500/50']">
                      {{ editForm.teaser.length }} / 300
                    </span>
                  </div>
                  <textarea v-model="editForm.teaser" rows="3" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner" placeholder="A short, catchy teaser for your adventure..."></textarea>
                </div>

                <div class="space-y-3">
                  <label class="block text-xs font-black text-slate-500 uppercase tracking-widest">{{ editEntityContext.type === 'cover' ? 'Global Context / Premise' : 'Description / Biography' }}</label>
                  <textarea v-model="editForm.description" rows="8" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-lg text-slate-300 resize-none focus:border-emerald-500 outline-none transition-all leading-relaxed shadow-inner"></textarea>
                </div>
              </div>

              <div class="flex justify-end gap-6 pt-4">
                <button @click="showEditModal = false" class="px-8 py-3 text-slate-400 hover:text-white font-black uppercase text-xs tracking-widest transition-colors">Discard</button>
                <button @click="saveEntityText(editEntityContext.type, editEntityContext.id)" :disabled="isSavingText" class="px-10 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-black uppercase text-xs tracking-widest rounded-xl shadow-lg shadow-emerald-900/20 disabled:opacity-50 flex items-center gap-3">
                  <i v-if="isSavingText" class="ra ra-cycle animate-spin"></i>
                  <span>{{ isSavingText ? 'Saving...' : 'Apply Changes' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <input
      ref="uploadInput"
      type="file"
      accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
      class="hidden"
      @change="uploadSelectedVisual"
    />

    <!-- TOAST NOTIFICATIONS -->
    <Teleport to="body">
      <div class="fixed bottom-8 right-8 z-[300] flex flex-col gap-3 pointer-events-none">
        <TransitionGroup name="notif">
          <div 
            v-for="n in notifications" 
            :key="n.id"
            :class="[
              'pointer-events-auto px-6 py-4 rounded-2xl border backdrop-blur-2xl shadow-2xl flex items-center gap-4 min-w-[320px] max-w-md animate-notif-in',
              n.type === 'error' ? 'bg-red-500/10 border-red-500/20 text-red-400' : 
              n.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
              'bg-blue-500/10 border-blue-500/20 text-blue-400'
            ]"
          >
            <i :class="[
              'text-lg',
              n.type === 'error' ? 'ra ra-cancel' : 
              n.type === 'success' ? 'ra ra-circle' : 'ra ra-light-bulb'
            ]"></i>
            <div class="flex-grow">
              <p class="text-xs font-black uppercase tracking-widest opacity-50">{{ n.type }}</p>
              <p class="text-xs font-bold leading-relaxed">{{ n.message }}</p>
            </div>
            <button @click="notifications = notifications.filter(x => x.id !== n.id)" class="opacity-50 hover:opacity-100 transition-opacity">
              <i class="ra ra-cancel text-xs"></i>
            </button>
          </div>
        </TransitionGroup>
      </div>
    </Teleport>
 
    <!-- DATA DEBUG MODAL -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showDebug" class="fixed inset-0 z-[600] flex items-center justify-center p-12 backdrop-blur-3xl bg-slate-950/90">
          <div class="modal-content w-full max-w-6xl h-[80vh] bg-slate-900 border border-white/10 rounded-[3rem] shadow-2xl overflow-hidden flex flex-col">
            <div class="p-8 border-b border-white/5 flex justify-between items-center bg-slate-900/50">
              <div class="flex items-center gap-4">
                <div class="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center border border-cyan-500/20">
                  <i class="ra ra-crystal-ball text-cyan-400"></i>
                </div>
                <div>
                  <h3 class="text-lg font-black text-white uppercase tracking-widest">Chronicle Debug Inspector</h3>
                  <p class="text-xs text-slate-500 font-bold uppercase tracking-tighter">Raw Adventure Manifest & Entities</p>
                </div>
              </div>
              <button @click="showDebug = false" class="p-3 rounded-full hover:bg-white/5 text-slate-500 hover:text-white transition-all">
                <i class="ra ra-cancel text-xl"></i>
              </button>
            </div>
            
            <div class="flex-grow overflow-hidden flex">
              <div class="flex-grow p-8 overflow-auto font-mono text-xs leading-relaxed">
                <div class="space-y-8">
                  <section v-if="adventure" class="space-y-4">
                    <h4 class="text-xs font-black text-emerald-500 uppercase tracking-widest border-l-2 border-emerald-500 pl-4">Adventure Core</h4>
                    <pre class="bg-black/40 p-6 rounded-2xl border border-white/5 text-emerald-300/80 whitespace-pre-wrap break-all">{{ JSON.stringify(adventure, null, 2) }}</pre>
                  </section>
                  <section v-if="debugData" class="space-y-4">
                    <h4 class="text-xs font-black text-cyan-500 uppercase tracking-widest border-l-2 border-cyan-500 pl-4">Asset Matrix (DebugData)</h4>
                    <pre class="bg-black/40 p-6 rounded-2xl border border-white/5 text-cyan-300/80 whitespace-pre-wrap break-all">{{ JSON.stringify(debugData, null, 2) }}</pre>
                  </section>
                </div>
              </div>
            </div>

            <div class="p-6 bg-black/20 border-t border-white/5 flex justify-end gap-4">
              <button @click="showDebug = false" class="px-10 py-3 bg-slate-800 hover:bg-slate-700 text-white font-black uppercase text-xs tracking-widest rounded-xl transition-all">Close Inspector</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.animate-page-in {
  animation: pageIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

.animate-fade-in {
  animation: fadeIn 0.3s ease-out forwards;
}

@keyframes pageIn {
  from { opacity: 0; transform: translateY(20px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

input, textarea {
  transition: all 0.3s ease;
}

.shadow-inner {
  box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.4);
}

/* Tooltip Animations */
.tooltip-enter-active, .tooltip-leave-active { transition: opacity 0.2s, transform 0.2s; }
.tooltip-enter-from, .tooltip-leave-to { opacity: 0; transform: scale(0.95) translateY(5px); }

.animate-tooltip-in {
  animation: toolTipIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

/* Modal Animations */
.modal-enter-active, .modal-leave-active { transition: opacity 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-enter-from, .modal-leave-to { opacity: 0; }

.modal-enter-active .modal-content { animation: modalScaleIn 0.5s cubic-bezier(0.16, 1, 0.3, 1); }
.modal-leave-active .modal-content { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); transform: scale(0.95); }

@keyframes modalScaleIn {
  from { opacity: 0; transform: scale(0.9) translateY(40px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes toolTipIn {
  from { opacity: 0; transform: translateY(10px) scale(0.9); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* Notification Animations */
.notif-enter-active, .notif-leave-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.notif-enter-from { opacity: 0; transform: translateX(50px) scale(0.9); }
.notif-leave-to { opacity: 0; transform: translateX(50px) scale(0.9); }

@keyframes notifIn {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>



