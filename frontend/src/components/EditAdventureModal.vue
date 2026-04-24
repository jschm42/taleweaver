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

// Visuals state
const isQuickGenerating = ref<Record<string, boolean>>({})
const isBatchGenerating = ref<Record<string, boolean>>({})

// Editor State
const aiEditPrompt = ref('')
const isAIEditing = ref(false)

const editingEntityId = ref<string | null>(null)
const editForm = ref({ name: '', description: '' })
const isSavingText = ref(false)

function openTextEdit(type: string, id: string, currentName: string, currentDesc: string) {
  editingEntityId.value = `${type}_${id}`
  editForm.value = { name: currentName || '', description: currentDesc || '' }
}

async function saveEntityText(type: string, id: string) {
  isSavingText.value = true
  promptError.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/editor/entity`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_type: type,
        target_id: id,
        name: editForm.value.name,
        description: editForm.value.description
      })
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Failed to save entity text')
    }
    
    editingEntityId.value = null
    await fetchDebugInfo()
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
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/editor/ai-edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: aiEditPrompt.value })
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

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const showDebug = ref(false)
const activeTab = ref<'settings' | 'editor' | 'advanced'>('settings')
const uploadInput = ref<HTMLInputElement | null>(null)
const selectedVisual = ref<{ kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object'; id: string; label: string; description: string; hint: string } | null>(null)
const visualPrompt = ref('')
const visualsCacheVersion = ref(0)

const VISUAL_UPLOAD_LIMITS = {
  cover: { maxWidth: 2048, maxHeight: 1024, hint: 'Optimal: cinematic landscape 2:1, max 2048x1024. PNG, JPEG, or WEBP.' },
  protagonist: { maxWidth: 1024, maxHeight: 1280, hint: 'Optimal: portrait 4:5, max 1024x1280. PNG, JPEG, or WEBP.' },
  scene: { maxWidth: 1600, maxHeight: 900, hint: 'Optimal: landscape 16:9, max 1600x900. PNG, JPEG, or WEBP.' },
  npc: { maxWidth: 1024, maxHeight: 1280, hint: 'Optimal: portrait 4:5, max 1024x1280. PNG, JPEG, or WEBP.' },
  object: { maxWidth: 1024, maxHeight: 1024, hint: 'Optimal: square 1:1, max 1024x1024. PNG, JPEG, or WEBP.' },
} as const

const ALLOWED_UPLOAD_MIME_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])
const ALLOWED_UPLOAD_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'webp'])

const form = ref({
  title: '',
  context: '',
  strict_rules: true,
  time_per_turn: 5,
  min_scenes: 1,
  max_scenes: 5,
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
    form.value.min_scenes = data.min_scenes || 1
    form.value.max_scenes = data.max_scenes || 5
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
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/editor/assets`)
    if (res.ok) {
      debugData.value = await res.json()
      visualsCacheVersion.value += 1
    }
  } catch (error) {
    console.error('Failed to fetch debug info:', error)
  }
}

watch(() => props.adventureId, (newId) => {
  if (newId) {
    fetchAdventure()
    fetchDebugInfo()
  }
}, { immediate: true })

watch(() => props.open, (isOpen) => {
  if (isOpen && props.adventureId) {
    fetchAdventure()
    fetchDebugInfo()
  }
})

function buildVisualImageUrl(imagePath?: string | null) {
  if (!imagePath) {
    return ''
  }
  return `http://localhost:8000${imagePath}?v=${visualsCacheVersion.value}`
}

function bumpGlobalVisualCacheVersion() {
  localStorage.setItem('tw_visual_cache_version', String(Date.now()))
}

function getVisualKindLabel(kind?: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object' | null) {
  if (!kind) {
    return 'Visual'
  }

  if (kind === 'cover') {
    return 'Cover'
  }
  if (kind === 'protagonist') {
    return 'Protagonist'
  }
  if (kind === 'scene') {
    return 'Scene'
  }
  if (kind === 'npc') {
    return 'NPC'
  }
  return 'Object'
}

function openRegenerateDialog(kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object', id: string, label: string) {
  const description = getVisualDescription(kind, id)
  const hint = VISUAL_UPLOAD_LIMITS[kind].hint
  selectedVisual.value = { kind, id, label, description, hint }
  visualPrompt.value = ''
  promptError.value = ''
  showPromptDialog.value = true
}

function getVisualDescription(kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object', id: string) {
  if (!debugData.value) {
    return ''
  }

  if (kind === 'cover') {
    return debugData.value.adventure?.context || ''
  }

  if (kind === 'protagonist') {
    return debugData.value.protagonist?.description || ''
  }

  if (kind === 'scene') {
    return (debugData.value.scenes || []).find((scene: any) => scene.id === id)?.description || ''
  }

  if (kind === 'npc') {
    return (debugData.value.npcs || []).find((npc: any) => npc.id === id)?.description || ''
  }

  return (debugData.value.objects || []).find((obj: any) => obj.id === id)?.description || ''
}

function closeRegenerateDialog(force = false) {
  if ((isRegenerating.value || isUploading.value) && !force) {
    return
  }
  showPromptDialog.value = false
  selectedVisual.value = null
  visualPrompt.value = ''
  promptError.value = ''
}

async function regenerateVisual() {
  if (!props.adventureId || !selectedVisual.value) {
    return
  }

  isRegenerating.value = true
  promptError.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/visuals/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_type: selectedVisual.value.kind,
        target_id: selectedVisual.value.id,
        prompt: visualPrompt.value.trim() || null,
      }),
    })

    if (!res.ok) {
      const payload = await res.json().catch(() => null)
      throw new Error(payload?.detail || 'Failed to regenerate image.')
    }

    bumpGlobalVisualCacheVersion()
    isRegenerating.value = false
    closeRegenerateDialog(true)
    await fetchDebugInfo()
  } catch (error: any) {
    promptError.value = error?.message || 'Network error while regenerating.'
  } finally {
    isRegenerating.value = false
  }
}

async function quickRegenerateVisual(kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object', id: string) {
  if (!props.adventureId) return
  
  const key = `${kind}_${id}`
  isQuickGenerating.value[key] = true
  
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/visuals/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_type: kind,
        target_id: id,
        prompt: null,
      }),
    })

    if (res.ok) {
      bumpGlobalVisualCacheVersion()
      await fetchDebugInfo()
    } else {
      console.error('Failed to quick-regenerate image')
    }
  } catch (error) {
    console.error('Network error during quick regeneration', error)
  } finally {
    isQuickGenerating.value[key] = false
  }
}

async function regenerateAll(kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object') {
  isBatchGenerating.value[kind] = true
  
  let items: any[] = []
  if (kind === 'cover' && debugData.value?.adventure) items = [debugData.value.adventure]
  if (kind === 'protagonist' && debugData.value?.protagonist) items = [debugData.value.protagonist]
  if (kind === 'scene' && debugData.value?.scenes) items = debugData.value.scenes
  if (kind === 'npc' && debugData.value?.npcs) items = debugData.value.npcs
  if (kind === 'object' && debugData.value?.objects) items = debugData.value.objects

  for (const item of items) {
    if (!item.id) continue
    await quickRegenerateVisual(kind, item.id)
  }
  
  isBatchGenerating.value[kind] = false
}

function triggerUpload() {
  if (!selectedVisual.value || isUploading.value) {
    return
  }
  uploadInput.value?.click()
}

function getFileExtension(fileName: string) {
  return fileName.includes('.') ? fileName.split('.').pop()?.toLowerCase() || '' : ''
}

function readImageDimensions(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const preview = new window.Image()
    const objectUrl = URL.createObjectURL(file)

    preview.onload = () => {
      URL.revokeObjectURL(objectUrl)
      resolve({ width: preview.naturalWidth, height: preview.naturalHeight })
    }

    preview.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      reject(new Error('Invalid image file.'))
    }

    preview.src = objectUrl
  })
}

async function validateUploadFile(file: File, kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object'): Promise<string | null> {
  const ext = getFileExtension(file.name)
  if (!ALLOWED_UPLOAD_MIME_TYPES.has(file.type) && !ALLOWED_UPLOAD_EXTENSIONS.has(ext)) {
    return 'Unsupported image format. Use PNG, JPEG, or WEBP.'
  }

  const limits = VISUAL_UPLOAD_LIMITS[kind]
  const dimensions = await readImageDimensions(file)
  if (dimensions.width > limits.maxWidth || dimensions.height > limits.maxHeight) {
    return `Image too large. Max size for this asset is ${limits.maxWidth}x${limits.maxHeight}.`
  }

  return null
}

async function handleUploadChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''

  if (!file || !props.adventureId || !selectedVisual.value) {
    return
  }

  promptError.value = ''
  try {
    const validationError = await validateUploadFile(file, selectedVisual.value.kind)
    if (validationError) {
      promptError.value = validationError
      return
    }

    isUploading.value = true
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_type', selectedVisual.value.kind)
    formData.append('target_id', selectedVisual.value.id)

    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/visuals/upload`, {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      const payload = await res.json().catch(() => null)
      throw new Error(payload?.detail || 'Failed to upload image.')
    }

    bumpGlobalVisualCacheVersion()
    isUploading.value = false
    closeRegenerateDialog(true)
    await fetchDebugInfo()
  } catch (error: any) {
    promptError.value = error?.message || 'Network error while uploading.'
  } finally {
    isUploading.value = false
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

async function exportADZ() {
  if (!props.adventureId) return
  const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/export/adz`)
  if (!res.ok) return

  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${(adventure.value?.title || 'adventure').replace(/\s+/g, '_')}.adz`
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
    showPromptDialog.value = false
    selectedVisual.value = null
    promptError.value = ''
    await fetchAdventure()
    await fetchDebugInfo()
  }
)
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-[60] flex items-start md:items-center justify-center p-4 md:p-6 overflow-y-auto">
        <div class="absolute inset-0 bg-black/80 backdrop-blur-md" @click="emit('close')" />

        <div class="relative z-10 my-4 md:my-0 w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-3xl shadow-2xl flex flex-col min-h-0 max-h-[calc(100dvh-2rem)] overflow-hidden">
          <div class="px-8 py-6 border-b border-slate-800 flex justify-between items-center shrink-0">
            <div>
              <h2 class="text-2xl font-bold text-white flex items-center gap-3">
                <i class="ra ra-gear-hammer text-emerald-500"></i>
                Adventure Settings
              </h2>
              <p class="text-xs text-slate-400 mt-1">Configure mechanics and inspect runtime/debug state.</p>
            </div>
            <button @click="emit('close')" class="text-slate-500 hover:text-white transition-colors p-2">X</button>
          </div>

          <div class="flex px-8 border-b border-slate-800 bg-slate-950/30 shrink-0">
            <button
              v-for="tab in ['settings', 'editor', 'advanced']"
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

          <div class="flex-grow min-h-0 overflow-y-auto p-8 custom-scrollbar">
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

              <div class="p-6 bg-slate-950 border border-slate-800 rounded-2xl space-y-4">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-emerald-500/10 rounded-lg text-emerald-500">
                    <i class="ra ra-scroll-unfurled text-xl"></i>
                  </div>
                  <div>
                    <h3 class="text-sm font-bold text-white uppercase tracking-wider">World Size</h3>
                    <p class="text-[10px] text-slate-500">Min/Max scenes for regeneration</p>
                  </div>
                </div>

                <div class="grid grid-cols-2 gap-6">
                  <div>
                    <div class="flex items-center justify-between text-[10px] mb-2 uppercase tracking-widest text-slate-500">
                      <span>Min Scenes</span>
                      <strong class="text-emerald-400">{{ form.min_scenes }}</strong>
                    </div>
                    <input type="range" v-model.number="form.min_scenes" min="1" max="10" step="1" class="w-full accent-emerald-500" />
                  </div>
                  <div>
                    <div class="flex items-center justify-between text-[10px] mb-2 uppercase tracking-widest text-slate-500">
                      <span>Max Scenes</span>
                      <strong class="text-emerald-400">{{ form.max_scenes }}</strong>
                    </div>
                    <input type="range" v-model.number="form.max_scenes" min="1" max="20" step="1" class="w-full accent-emerald-500" />
                  </div>
                </div>
              </div>
            </div>

            <div v-else-if="activeTab === 'editor'" class="space-y-8">
              <div v-if="!debugData" class="text-xs text-slate-500">No debug data available yet.</div>
              <div v-else class="space-y-8">
                
                <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl">
                  <h3 class="text-sm font-bold text-white mb-2 flex items-center gap-2">
                    <i class="ra ra-player-teleport text-emerald-500"></i> AI World Editor
                  </h3>
                  <p class="text-[11px] text-slate-400 mb-3">Describe what you want to change in the adventure (e.g. "Add a hacker NPC", "Change the sword to a laser rifle"). The AI will adjust the texts. Images are not re-generated automatically.</p>
                  <textarea v-model="aiEditPrompt" rows="2" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white mb-3 placeholder-slate-600 focus:outline-none focus:border-emerald-500 transition-colors" placeholder="Your instructions..."></textarea>
                  <div class="flex justify-end">
                    <button @click="runAIEdit" :disabled="isAIEditing || !aiEditPrompt" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-widest rounded-lg disabled:opacity-50 flex items-center gap-2 transition-colors">
                      <i v-if="isAIEditing" class="ra ra-cycle animate-spin"></i>
                      <i v-else class="ra ra-light-bulb"></i>
                      Apply AI Changes
                    </button>
                  </div>
                </div>

                <section v-if="debugData.adventure">
                  <div class="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                    <h3 class="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em]">Adventure Cover</h3>
                    <button @click="regenerateAll('cover')" :disabled="isBatchGenerating['cover']" class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 disabled:opacity-50 transition-colors flex items-center gap-1">
                      <i v-if="isBatchGenerating['cover']" class="ra ra-cycle animate-spin"></i>
                      <i v-else class="ra ra-cycle"></i>
                      Generate
                    </button>
                  </div>
                  <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    <div class="relative group aspect-[3/2] bg-slate-950 border border-slate-800 rounded-xl overflow-hidden col-span-2 lg:col-span-3">
                      <img v-if="debugData.adventure.image_url" :src="buildVisualImageUrl(debugData.adventure.image_url)" class="absolute inset-0 w-full h-full object-cover" />
                      <div class="absolute inset-x-0 bottom-0 p-2 bg-black/55 text-[10px] text-white leading-tight">
                        <div class="font-bold text-[11px]">{{ debugData.adventure.title || 'Adventure Cover' }}</div>
                        <div class="text-white/70">Cinematic title artwork</div>
                      </div>
                      
                      <!-- Loading Overlay -->
                      <div v-if="isQuickGenerating['cover_' + debugData.adventure.id]" class="absolute inset-0 bg-slate-900/80 backdrop-blur-sm flex flex-col items-center justify-center z-10">
                        <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500 mb-2"></div>
                        <span class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest animate-pulse">Generating...</span>
                      </div>

                      <div v-if="!isQuickGenerating['cover_' + debugData.adventure.id]" class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          @click="quickRegenerateVisual('cover', debugData.adventure.id)"
                          :disabled="isQuickGenerating['cover_' + debugData.adventure.id]"
                          class="px-2 py-1 rounded-md bg-emerald-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-emerald-500/50 hover:bg-emerald-500 transition-colors disabled:opacity-50 flex items-center gap-1"
                        >
                          <i v-if="isQuickGenerating['cover_' + debugData.adventure.id]" class="ra ra-cycle animate-spin"></i>
                          <span>Fast Gen</span>
                        </button>
                        <button
                          @click="openRegenerateDialog('cover', debugData.adventure.id, debugData.adventure.title || 'Adventure Cover')"
                          class="px-2 py-1 rounded-md bg-black/70 text-[10px] font-bold uppercase tracking-widest text-white/90 border border-white/10 hover:bg-black/90 transition-colors"
                        >
                          Custom
                        </button>
                        <button
                          @click="openTextEdit('cover', debugData.adventure.id, debugData.adventure.title, debugData.adventure.context)"
                          class="px-2 py-1 rounded-md bg-blue-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-blue-500/50 hover:bg-blue-500 transition-colors flex items-center gap-1"
                        >
                          <i class="ra ra-quill-ink"></i>
                          <span>Edit Text</span>
                        </button>
                      </div>

                      <!-- Text Edit Overlay -->
                      <div v-if="editingEntityId === 'cover_' + debugData.adventure.id" class="absolute inset-0 bg-slate-900 z-30 p-4 flex flex-col gap-3">
                        <div class="flex justify-between items-center mb-1">
                          <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Edit Cover Text</span>
                          <button @click="editingEntityId = null" class="text-slate-500 hover:text-white">X</button>
                        </div>
                        <input v-model="editForm.name" placeholder="Title" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-emerald-500 outline-none" />
                        <textarea v-model="editForm.description" placeholder="Context / Description" class="w-full flex-grow bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white resize-none focus:border-emerald-500 outline-none"></textarea>
                        <div class="flex justify-end gap-2 mt-1">
                          <button @click="editingEntityId = null" class="px-3 py-1.5 text-[10px] font-bold uppercase text-slate-400 hover:text-white transition-colors">Cancel</button>
                          <button @click="saveEntityText('cover', debugData.adventure.id)" :disabled="isSavingText" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-widest rounded-md disabled:opacity-50 transition-colors flex items-center gap-2">
                            <i v-if="isSavingText" class="ra ra-cycle animate-spin"></i>
                            <span>Save</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                <section v-if="debugData.protagonist">
                  <div class="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                    <h3 class="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em]">Protagonist Portrait</h3>
                    <button @click="regenerateAll('protagonist')" :disabled="isBatchGenerating['protagonist']" class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 disabled:opacity-50 transition-colors flex items-center gap-1">
                      <i v-if="isBatchGenerating['protagonist']" class="ra ra-cycle animate-spin"></i>
                      <i v-else class="ra ra-cycle"></i>
                      Generate
                    </button>
                  </div>
                  <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    <div class="relative group aspect-[4/5] bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                      <img v-if="debugData.protagonist.profile_image" :src="buildVisualImageUrl(debugData.protagonist.profile_image)" class="absolute inset-0 w-full h-full object-cover" />
                      <div class="absolute inset-x-0 bottom-0 p-2 bg-black/55 text-[10px] text-white leading-tight">
                        <div class="font-bold text-[11px]">{{ debugData.protagonist.name || 'Protagonist' }}</div>
                        <div class="text-white/70">{{ debugData.protagonist.role || 'Player character' }}</div>
                      </div>

                      <!-- Loading Overlay -->
                      <div v-if="isQuickGenerating['protagonist_' + debugData.protagonist.id]" class="absolute inset-0 bg-slate-900/80 backdrop-blur-sm flex flex-col items-center justify-center z-10">
                        <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500 mb-2"></div>
                        <span class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest animate-pulse">Generating...</span>
                      </div>

                      <div v-if="!isQuickGenerating['protagonist_' + debugData.protagonist.id]" class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          @click="quickRegenerateVisual('protagonist', debugData.protagonist.id)"
                          :disabled="isQuickGenerating['protagonist_' + debugData.protagonist.id]"
                          class="px-2 py-1 rounded-md bg-emerald-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-emerald-500/50 hover:bg-emerald-500 transition-colors disabled:opacity-50 flex items-center gap-1"
                        >
                          <i v-if="isQuickGenerating['protagonist_' + debugData.protagonist.id]" class="ra ra-cycle animate-spin"></i>
                          <span>Fast Gen</span>
                        </button>
                        <button
                          @click="openRegenerateDialog('protagonist', debugData.protagonist.id, debugData.protagonist.name || 'Protagonist')"
                          class="px-2 py-1 rounded-md bg-black/70 text-[10px] font-bold uppercase tracking-widest text-white/90 border border-white/10 hover:bg-black/90 transition-colors"
                        >
                          Custom
                        </button>
                        <button
                          @click="openTextEdit('protagonist', debugData.protagonist.id, debugData.protagonist.name, debugData.protagonist.description)"
                          class="px-2 py-1 rounded-md bg-blue-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-blue-500/50 hover:bg-blue-500 transition-colors flex items-center gap-1"
                        >
                          <i class="ra ra-quill-ink"></i>
                          <span>Edit Text</span>
                        </button>
                      </div>

                      <!-- Text Edit Overlay -->
                      <div v-if="editingEntityId === 'protagonist_' + debugData.protagonist.id" class="absolute inset-0 bg-slate-900 z-30 p-4 flex flex-col gap-3">
                        <div class="flex justify-between items-center mb-1">
                          <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Edit Protagonist</span>
                          <button @click="editingEntityId = null" class="text-slate-500 hover:text-white">X</button>
                        </div>
                        <input v-model="editForm.name" placeholder="Name" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-emerald-500 outline-none" />
                        <textarea v-model="editForm.description" placeholder="Description" class="w-full flex-grow bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white resize-none focus:border-emerald-500 outline-none"></textarea>
                        <div class="flex justify-end gap-2 mt-1">
                          <button @click="editingEntityId = null" class="px-3 py-1.5 text-[10px] font-bold uppercase text-slate-400 hover:text-white transition-colors">Cancel</button>
                          <button @click="saveEntityText('protagonist', debugData.protagonist.id)" :disabled="isSavingText" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-widest rounded-md disabled:opacity-50 transition-colors flex items-center gap-2">
                            <i v-if="isSavingText" class="ra ra-cycle animate-spin"></i>
                            <span>Save</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                <section>
                  <div class="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                    <h3 class="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em]">Scene Visuals</h3>
                    <button @click="regenerateAll('scene')" :disabled="isBatchGenerating['scene']" class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 disabled:opacity-50 transition-colors flex items-center gap-1">
                      <i v-if="isBatchGenerating['scene']" class="ra ra-cycle animate-spin"></i>
                      <i v-else class="ra ra-cycle"></i>
                      Generate All
                    </button>
                  </div>
                  <div v-if="(debugData.scenes ? debugData.scenes.length : 0) === 0" class="text-xs text-slate-600 italic">No scene visuals generated.</div>
                  <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    <div v-for="scene in (debugData.scenes || [])" :key="scene.id" class="relative group aspect-[4/5] bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                      <img v-if="scene.image_url" :src="buildVisualImageUrl(scene.image_url)" class="absolute inset-0 w-full h-full object-cover" />
                      <div class="absolute inset-x-0 bottom-0 p-2 bg-black/55 text-[10px] text-white leading-tight">
                        <div class="font-bold text-[11px]">{{ scene.label || scene.name || scene.id }}</div>
                      </div>

                      <!-- Loading Overlay -->
                      <div v-if="isQuickGenerating['scene_' + scene.id]" class="absolute inset-0 bg-slate-900/80 backdrop-blur-sm flex flex-col items-center justify-center z-10">
                        <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500 mb-2"></div>
                        <span class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest animate-pulse">Generating...</span>
                      </div>

                      <div v-if="!isQuickGenerating['scene_' + scene.id]" class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          @click="quickRegenerateVisual('scene', scene.id)"
                          :disabled="isQuickGenerating['scene_' + scene.id]"
                          class="px-2 py-1 rounded-md bg-emerald-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-emerald-500/50 hover:bg-emerald-500 transition-colors disabled:opacity-50 flex items-center gap-1"
                        >
                          <i v-if="isQuickGenerating['scene_' + scene.id]" class="ra ra-cycle animate-spin"></i>
                          <span>Fast Gen</span>
                        </button>
                        <button
                          @click="openRegenerateDialog('scene', scene.id, scene.label || scene.name || scene.id)"
                          class="px-2 py-1 rounded-md bg-black/70 text-[10px] font-bold uppercase tracking-widest text-white/90 border border-white/10 hover:bg-black/90 transition-colors"
                        >
                          Custom
                        </button>
                        <button
                          @click="openTextEdit('scene', scene.id, scene.label || scene.name, scene.description)"
                          class="px-2 py-1 rounded-md bg-blue-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-blue-500/50 hover:bg-blue-500 transition-colors flex items-center gap-1"
                        >
                          <i class="ra ra-quill-ink"></i>
                          <span>Edit Text</span>
                        </button>
                      </div>

                      <!-- Text Edit Overlay -->
                      <div v-if="editingEntityId === 'scene_' + scene.id" class="absolute inset-0 bg-slate-900 z-30 p-4 flex flex-col gap-3">
                        <div class="flex justify-between items-center mb-1">
                          <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Edit Scene</span>
                          <button @click="editingEntityId = null" class="text-slate-500 hover:text-white">X</button>
                        </div>
                        <input v-model="editForm.name" placeholder="Name" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-emerald-500 outline-none" />
                        <textarea v-model="editForm.description" placeholder="Description" class="w-full flex-grow bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white resize-none focus:border-emerald-500 outline-none"></textarea>
                        <div class="flex justify-end gap-2 mt-1">
                          <button @click="editingEntityId = null" class="px-3 py-1.5 text-[10px] font-bold uppercase text-slate-400 hover:text-white transition-colors">Cancel</button>
                          <button @click="saveEntityText('scene', scene.id)" :disabled="isSavingText" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-widest rounded-md disabled:opacity-50 transition-colors flex items-center gap-2">
                            <i v-if="isSavingText" class="ra ra-cycle animate-spin"></i>
                            <span>Save</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                <section>
                  <div class="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                    <h3 class="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em]">Population Portraits</h3>
                    <button @click="regenerateAll('npc')" :disabled="isBatchGenerating['npc']" class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 disabled:opacity-50 transition-colors flex items-center gap-1">
                      <i v-if="isBatchGenerating['npc']" class="ra ra-cycle animate-spin"></i>
                      <i v-else class="ra ra-cycle"></i>
                      Generate All
                    </button>
                  </div>
                  <div v-if="(debugData.npcs ? debugData.npcs.length : 0) === 0" class="text-xs text-slate-600 italic">No inhabitant visuals generated.</div>
                  <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    <div v-for="npc in (debugData.npcs || [])" :key="npc.id" class="relative group aspect-[4/5] bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                      <img v-if="npc.image_url" :src="buildVisualImageUrl(npc.image_url)" class="absolute inset-0 w-full h-full object-cover" />
                      <div class="absolute inset-x-0 bottom-0 p-2 bg-black/55 text-[10px] text-white leading-tight">
                        <div class="font-bold text-[11px]">{{ npc.name }}</div>
                      </div>

                      <!-- Loading Overlay -->
                      <div v-if="isQuickGenerating['npc_' + npc.id]" class="absolute inset-0 bg-slate-900/80 backdrop-blur-sm flex flex-col items-center justify-center z-10">
                        <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500 mb-2"></div>
                        <span class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest animate-pulse">Generating...</span>
                      </div>

                      <div v-if="!isQuickGenerating['npc_' + npc.id]" class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          @click="quickRegenerateVisual('npc', npc.id)"
                          :disabled="isQuickGenerating['npc_' + npc.id]"
                          class="px-2 py-1 rounded-md bg-emerald-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-emerald-500/50 hover:bg-emerald-500 transition-colors disabled:opacity-50 flex items-center gap-1"
                        >
                          <i v-if="isQuickGenerating['npc_' + npc.id]" class="ra ra-cycle animate-spin"></i>
                          <span>Fast Gen</span>
                        </button>
                        <button
                          @click="openRegenerateDialog('npc', npc.id, npc.name || npc.id)"
                          class="px-2 py-1 rounded-md bg-black/70 text-[10px] font-bold uppercase tracking-widest text-white/90 border border-white/10 hover:bg-black/90 transition-colors"
                        >
                          Custom
                        </button>
                        <button
                          @click="openTextEdit('npc', npc.id, npc.name, npc.description)"
                          class="px-2 py-1 rounded-md bg-blue-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-blue-500/50 hover:bg-blue-500 transition-colors flex items-center gap-1"
                        >
                          <i class="ra ra-quill-ink"></i>
                          <span>Edit Text</span>
                        </button>
                      </div>

                      <!-- Text Edit Overlay -->
                      <div v-if="editingEntityId === 'npc_' + npc.id" class="absolute inset-0 bg-slate-900 z-30 p-4 flex flex-col gap-3">
                        <div class="flex justify-between items-center mb-1">
                          <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Edit NPC</span>
                          <button @click="editingEntityId = null" class="text-slate-500 hover:text-white">X</button>
                        </div>
                        <input v-model="editForm.name" placeholder="Name" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-emerald-500 outline-none" />
                        <textarea v-model="editForm.description" placeholder="Description" class="w-full flex-grow bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white resize-none focus:border-emerald-500 outline-none"></textarea>
                        <div class="flex justify-end gap-2 mt-1">
                          <button @click="editingEntityId = null" class="px-3 py-1.5 text-[10px] font-bold uppercase text-slate-400 hover:text-white transition-colors">Cancel</button>
                          <button @click="saveEntityText('npc', npc.id)" :disabled="isSavingText" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-widest rounded-md disabled:opacity-50 transition-colors flex items-center gap-2">
                            <i v-if="isSavingText" class="ra ra-cycle animate-spin"></i>
                            <span>Save</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                <section>
                  <div class="flex items-center justify-between mb-4 border-b border-slate-800 pb-2">
                    <h3 class="text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em]">Artifact Illustrations</h3>
                    <button @click="regenerateAll('object')" :disabled="isBatchGenerating['object']" class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest hover:text-emerald-400 disabled:opacity-50 transition-colors flex items-center gap-1">
                      <i v-if="isBatchGenerating['object']" class="ra ra-cycle animate-spin"></i>
                      <i v-else class="ra ra-cycle"></i>
                      Generate All
                    </button>
                  </div>
                  <div v-if="(debugData.objects ? debugData.objects.length : 0) === 0" class="text-xs text-slate-600 italic">No object visuals generated.</div>
                  <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    <div v-for="obj in (debugData.objects || [])" :key="obj.id" class="relative group aspect-[4/5] bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                      <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover" />
                      <div class="absolute inset-x-0 bottom-0 p-2 bg-black/55 text-[10px] text-white leading-tight">
                        <div class="font-bold text-[11px]">{{ obj.name }}</div>
                      </div>

                      <!-- Loading Overlay -->
                      <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-900/80 backdrop-blur-sm flex flex-col items-center justify-center z-10">
                        <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500 mb-2"></div>
                        <span class="text-[10px] font-bold text-emerald-500 uppercase tracking-widest animate-pulse">Generating...</span>
                      </div>

                      <div v-if="!isQuickGenerating['object_' + obj.id]" class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          @click="quickRegenerateVisual('object', obj.id)"
                          :disabled="isQuickGenerating['object_' + obj.id]"
                          class="px-2 py-1 rounded-md bg-emerald-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-emerald-500/50 hover:bg-emerald-500 transition-colors disabled:opacity-50 flex items-center gap-1"
                        >
                          <i v-if="isQuickGenerating['object_' + obj.id]" class="ra ra-cycle animate-spin"></i>
                          <span>Fast Gen</span>
                        </button>
                        <button
                          @click="openRegenerateDialog('object', obj.id, obj.name || obj.id)"
                          class="px-2 py-1 rounded-md bg-black/70 text-[10px] font-bold uppercase tracking-widest text-white/90 border border-white/10 hover:bg-black/90 transition-colors"
                        >
                          Custom
                        </button>
                        <button
                          @click="openTextEdit('object', obj.id, obj.name, obj.description)"
                          class="px-2 py-1 rounded-md bg-blue-600/90 text-[10px] font-bold uppercase tracking-widest text-white border border-blue-500/50 hover:bg-blue-500 transition-colors flex items-center gap-1"
                        >
                          <i class="ra ra-quill-ink"></i>
                          <span>Edit Text</span>
                        </button>
                      </div>

                      <!-- Text Edit Overlay -->
                      <div v-if="editingEntityId === 'object_' + obj.id" class="absolute inset-0 bg-slate-900 z-30 p-4 flex flex-col gap-3">
                        <div class="flex justify-between items-center mb-1">
                          <span class="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Edit Object</span>
                          <button @click="editingEntityId = null" class="text-slate-500 hover:text-white">X</button>
                        </div>
                        <input v-model="editForm.name" placeholder="Name" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:border-emerald-500 outline-none" />
                        <textarea v-model="editForm.description" placeholder="Description" class="w-full flex-grow bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white resize-none focus:border-emerald-500 outline-none"></textarea>
                        <div class="flex justify-end gap-2 mt-1">
                          <button @click="editingEntityId = null" class="px-3 py-1.5 text-[10px] font-bold uppercase text-slate-400 hover:text-white transition-colors">Cancel</button>
                          <button @click="saveEntityText('object', obj.id)" :disabled="isSavingText" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-bold uppercase tracking-widest rounded-md disabled:opacity-50 transition-colors flex items-center gap-2">
                            <i v-if="isSavingText" class="ra ra-cycle animate-spin"></i>
                            <span>Save</span>
                          </button>
                        </div>
                      </div>
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

              <div class="grid grid-cols-3 gap-4">
                <button @click="exportADZ" class="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-emerald-500/50 text-left col-span-3">
                  <div class="text-xs font-bold text-emerald-400 uppercase tracking-widest">ADZ Package</div>
                  <div class="text-[10px] text-slate-500 mt-1">Single versioned exchange format.</div>
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

          <div class="p-8 border-t border-slate-800 bg-slate-900/50 flex justify-between items-center shrink-0">
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

    <Transition name="fade">
      <div v-if="showPromptDialog" class="fixed inset-0 z-[70] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/75 backdrop-blur-sm" @click="() => closeRegenerateDialog()" />
        <div class="relative z-10 w-full max-w-lg bg-slate-900 border border-slate-700 rounded-3xl shadow-2xl overflow-hidden">
          <div class="px-6 py-5 border-b border-slate-800">
            <div class="flex items-center justify-between gap-3">
              <h3 class="text-lg font-bold text-white">Replace Visual</h3>
              <span class="inline-flex items-center rounded-full border border-emerald-400/40 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.15em] text-emerald-300">
                {{ getVisualKindLabel(selectedVisual?.kind) }}
              </span>
            </div>
            <p class="text-xs text-slate-400 mt-1">{{ selectedVisual?.label || 'Selected visual' }}. Leave the prompt empty to use the default description.</p>
            <p v-if="selectedVisual?.kind !== 'cover'" class="text-xs text-slate-300 mt-3 whitespace-pre-line">{{ selectedVisual?.description || 'No description available.' }}</p>
            <p class="text-[10px] text-slate-500 mt-2">{{ selectedVisual?.hint || '' }}</p>
          </div>
          <div class="p-6 space-y-4">
            <div>
              <label class="block text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] mb-2">Optional Prompt</label>
              <textarea v-model="visualPrompt" rows="5" class="w-full bg-slate-950 border border-slate-800 rounded-2xl px-4 py-3 text-white resize-none" placeholder="Leave empty to use the entity's own description..."></textarea>
            </div>
            <div v-if="promptError" class="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
              {{ promptError }}
            </div>
          </div>
          <div class="px-6 pb-2 flex items-center justify-between gap-3 text-[10px] text-slate-500 uppercase tracking-[0.2em]">
            <span>Upload PNG, JPEG, or WEBP</span>
            <button @click="triggerUpload" :disabled="isRegenerating || isUploading" class="px-3 py-1.5 rounded-lg bg-cyan-500/20 border border-cyan-400/40 text-cyan-200 hover:bg-cyan-500/30 hover:border-cyan-300/70 font-bold text-[10px] tracking-wider disabled:opacity-40">Upload Image</button>
          </div>
          <input ref="uploadInput" type="file" accept="image/png,image/jpeg,image/webp" class="hidden" @change="handleUploadChange" />
          <div class="px-6 py-4 border-t border-slate-800 flex justify-end gap-3 bg-slate-950/40">
            <button @click="closeRegenerateDialog()" :disabled="isRegenerating || isUploading" class="px-4 py-2 rounded-xl text-slate-400 hover:bg-white/5 transition-colors text-xs font-bold uppercase tracking-widest disabled:opacity-40">Cancel</button>
            <button @click="regenerateVisual" :disabled="isRegenerating || isUploading" class="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold uppercase tracking-widest disabled:opacity-50">
              {{ isRegenerating ? 'Replacing...' : 'Replace Image' }}
            </button>
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
