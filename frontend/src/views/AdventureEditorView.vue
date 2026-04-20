<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps<{
  adventureId: string
}>()

const router = useRouter()

// Visuals state
const isQuickGenerating = ref<Record<string, boolean>>({})
const isBatchGenerating = ref<Record<string, boolean>>({})

// Editor State
const aiEditPrompt = ref('')
const isAIEditing = ref(false)

const isSavingText = ref(false)
const showEditModal = ref(false)
const editEntityContext = ref<{ type: string; id: string } | null>(null)
const editForm = ref({ name: '', description: '' })

const adventure = ref<any>(null)
const debugData = ref<any>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const errorMsg = ref('')
const promptError = ref('')
const showDebug = ref(false)
const activeTab = ref<'world' | 'advanced'>('world')

const selectedVisual = ref<{ kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object'; id: string; label: string; description: string; hint: string } | null>(null)
const visualPrompt = ref('')
const showPromptDialog = ref(false)
const isRegenerating = ref(false)
const isUploading = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
const visualsCacheVersion = ref(0)
const hoveredEntity = ref<any>(null)
const mousePos = ref({ x: 0, y: 0 })

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
  hoveredEntity.value = entity
  mousePos.value = { x: event.clientX, y: event.clientY }
}

function clearHover() {
  hoveredEntity.value = null
}

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
  rule_enforcement_mode: 'rpg' as 'rpg' | 'story' | 'chat',
  time_per_turn: 5,
  min_scenes: 1,
  max_scenes: 5,
})

async function fetchAdventure() {
  if (!props.adventureId) return
  isLoading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}`)
    if (!res.ok) throw new Error('Failed to load adventure configuration.')
    const data = await res.json()
    adventure.value = data
    form.value.title = data.title
    form.value.context = data.context || ''
    form.value.rule_enforcement_mode = data.rule_enforcement_mode || 'rpg'
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
  if (!props.adventureId) return
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/debug`)
    if (res.ok) {
      debugData.value = await res.json()
      visualsCacheVersion.value += 1
    }
  } catch (error) {
    console.error('Failed to fetch debug info:', error)
  }
}

function openTextEdit(type: string, id: string, currentName: string, currentDesc: string) {
  editEntityContext.value = { type, id }
  editForm.value = { name: currentName || '', description: currentDesc || '' }
  showEditModal.value = true
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
    showEditModal.value = false
    editEntityContext.value = null
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

async function saveChanges() {
  isSaving.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
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
  return `http://localhost:8000${imagePath}?v=${visualsCacheVersion.value}`
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
  if (!debugData.value) return ''
  if (kind === 'cover') return debugData.value.adventure?.context || ''
  if (kind === 'protagonist') return debugData.value.protagonist?.description || ''
  if (kind === 'scene') return (debugData.value.scenes || []).find((s: any) => s.id === id)?.description || ''
  if (kind === 'npc') return (debugData.value.npcs || []).find((n: any) => n.id === id)?.description || ''
  return (debugData.value.objects || []).find((o: any) => o.id === id)?.description || ''
}

async function quickRegenerateVisual(kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object', id: string) {
  const key = `${kind}_${id}`
  isQuickGenerating.value[key] = true
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/visuals/regenerate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_type: kind, target_id: id, prompt: null }),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail || 'Generation failed')
    }
    await fetchDebugInfo()
  } catch (error: any) {
    console.error('Quick regen error:', error)
    addNotification(error.message, 'error')
  } finally {
    isQuickGenerating.value[key] = false
  }
}

async function regenerateAll(kind: 'cover' | 'protagonist' | 'scene' | 'npc' | 'object') {
  isBatchGenerating.value[kind] = true
  let items: any[] = []
  if (kind === 'cover' && debugData.value?.adventure) items = [debugData.value.adventure]
  if (kind === 'protagonist' && debugData.value?.protagonist) items = [debugData.value.protagonist]
  if (kind === 'scene') items = debugData.value?.scenes || []
  if (kind === 'npc') items = debugData.value?.npcs || []
  if (kind === 'object') items = debugData.value?.objects || []

  for (const item of items) {
    await quickRegenerateVisual(kind, item.id || props.adventureId)
  }
  isBatchGenerating.value[kind] = false
}

async function regenerateVisual() {
  if (!selectedVisual.value) return
  isRegenerating.value = true
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
    if (!res.ok) throw new Error('Failed to regenerate.')
    showPromptDialog.value = false
    await fetchDebugInfo()
  } catch (error: any) {
    promptError.value = error.message
  } finally {
    isRegenerating.value = false
  }
}

onMounted(() => {
  fetchAdventure()
  fetchDebugInfo()
})

async function resetAdventure() {
  if (!confirm('Are you sure? This will reset all story progress and character stats.')) return
  isSaving.value = true
  try {
    const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/reset`, {
      method: 'POST'
    })
    if (!res.ok) throw new Error('Reset failed')
    await fetchDebugInfo()
    alert('Adventure has been reset to its original state.')
  } catch (error: any) {
    errorMsg.value = error.message
  } finally {
    isSaving.value = false
  }
}

async function exportBlueprint() {
  const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/export/manifest`)
  if (!res.ok) return
  const data = await res.json()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `blueprint_${(adventure.value?.title || 'adventure').replace(/\s+/g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function exportSession() {
  const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/export/session`)
  if (!res.ok) return
  const data = await res.json()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `session_${(adventure.value?.title || 'adventure').replace(/\s+/g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function exportADV() {
  const res = await fetch(`http://localhost:8000/api/adventures/${props.adventureId}/export/manifest`)
  if (!res.ok) return
  const data = await res.json()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `adv_${(adventure.value?.title || 'adventure').replace(/\s+/g, '_')}.adv`
  a.click()
  URL.revokeObjectURL(url)
}

const goBack = () => router.push({ name: 'portal' })
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans flex flex-col relative overflow-hidden">
    <!-- Ambient Background -->
    <div v-if="debugData?.adventure?.image_url" class="absolute inset-0 pointer-events-none z-0 opacity-20">
      <img :src="'http://localhost:8000' + debugData.adventure.image_url" class="w-full h-full object-cover blur-3xl scale-110" />
      <div class="absolute inset-0 bg-slate-950/60"></div>
    </div>

    <!-- Header -->
    <header class="bg-slate-900/40 border-b border-white/5 px-8 py-3 flex justify-between items-center backdrop-blur-2xl sticky top-0 z-40 shadow-2xl">
      <div class="flex items-center gap-6">
        <button @click="goBack" class="group p-2 rounded-xl bg-white/5 hover:bg-emerald-500/10 border border-white/10 hover:border-emerald-500/50 transition-all duration-300 shadow-xl">
          <i class="ra ra-back-arrow text-lg text-slate-400 group-hover:text-emerald-400"></i>
        </button>
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-xl font-black text-white tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
              {{ adventure?.title || 'Adventure Editor' }}
            </h1>
            <span class="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[9px] font-bold text-emerald-400 uppercase tracking-widest">Editor</span>
          </div>
          <p class="text-[9px] text-slate-500 font-mono uppercase tracking-tighter">Instance: {{ adventureId }}</p>
        </div>
      </div>
      
      <div class="flex items-center gap-6">
        <nav class="flex bg-black/40 rounded-xl p-1 border border-white/5 backdrop-blur-md shadow-inner">
          <button 
            v-for="tab in (['world', 'advanced'] as const)" 
            :key="tab"
            @click="activeTab = tab"
            :class="[
              'px-4 py-1.5 text-[9px] font-black uppercase tracking-[0.2em] rounded-lg transition-all duration-300',
              activeTab === tab ? 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
            ]"
          >
            {{ tab }}
          </button>
        </nav>
      </div>
    </header>

    <main class="flex-grow p-6 max-w-[1400px] mx-auto w-full relative z-10">
      <div v-if="isLoading" class="flex flex-col justify-center items-center py-40 gap-6">
        <div class="relative w-20 h-20">
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500/20"></div>
          <div class="absolute inset-0 rounded-full border-4 border-emerald-500 border-t-transparent animate-spin"></div>
        </div>
        <p class="text-xs font-bold text-emerald-500 uppercase tracking-[0.3em] animate-pulse">Loading Chronicles...</p>
      </div>
      
      <div v-else class="space-y-10">
        <!-- World Tab (Merged Settings & Assets) -->
        <div v-if="activeTab === 'world'" class="space-y-10 animate-page-in">
          <!-- Quick Settings Row -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 bg-slate-900/40 p-6 rounded-[2rem] border border-white/5 backdrop-blur-md shadow-xl">
           <div class="space-y-2">
              <div class="flex justify-between items-center">
                <label class="block text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Chronicle Title</label>
                <div v-if="form.title !== adventure?.title" class="flex gap-2 animate-fade-in">
                  <button @click="form.title = adventure.title" class="text-[8px] font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
                  <button @click="saveChanges" class="text-[8px] font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
                </div>
              </div>
              <input v-model="form.title" type="text" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:border-emerald-500/50 outline-none transition-all" />
            </div>
            <div class="space-y-2">
              <div class="flex justify-between items-center">
                <label class="block text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Game Mode</label>
                <div v-if="form.rule_enforcement_mode !== adventure?.rule_enforcement_mode" class="flex gap-2 animate-fade-in">
                  <button @click="form.rule_enforcement_mode = adventure.rule_enforcement_mode" class="text-[8px] font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
                  <button @click="saveChanges" class="text-[8px] font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
                </div>
              </div>
              <select v-model="form.rule_enforcement_mode" class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-white text-sm font-bold focus:border-emerald-500/50 outline-none transition-all appearance-none">
                <option value="rpg">RPG (Strict)</option>
                <option value="story">Story (Balanced)</option>
                <option value="chat">Chat (Creative)</option>
              </select>
            </div>
            <div class="space-y-2">
              <div class="flex justify-between items-center">
                <label class="block text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Pacing ({{ form.time_per_turn }}m)</label>
                <div v-if="form.time_per_turn !== adventure?.time_per_turn" class="flex gap-2 animate-fade-in">
                  <button @click="form.time_per_turn = adventure.time_per_turn" class="text-[8px] font-bold text-slate-500 hover:text-white uppercase transition-colors">Discard</button>
                  <button @click="saveChanges" class="text-[8px] font-bold text-emerald-500 hover:text-emerald-400 uppercase transition-colors">Save</button>
                </div>
              </div>
              <input v-model.number="form.time_per_turn" type="range" min="1" max="60" class="w-full accent-emerald-500 h-2 bg-black/40 rounded-lg appearance-none cursor-pointer mt-3" />
            </div>
          </div>

          <!-- AI Weaver Command (More Compact) -->
          <div class="p-4 bg-gradient-to-r from-slate-900 to-slate-950 border border-white/5 rounded-2xl shadow-xl relative overflow-hidden group">
            <div class="flex items-center gap-4">
              <div class="bg-emerald-500/10 p-2 rounded-lg border border-emerald-500/20">
                <i class="ra ra-player-teleport text-emerald-500 text-lg"></i>
              </div>
              <div class="flex-grow relative">
                <input 
                  v-model="aiEditPrompt" 
                  @keyup.enter="runAIEdit" 
                  :disabled="isAIEditing"
                  class="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:border-emerald-500/50 outline-none transition-all disabled:opacity-50" 
                  placeholder="Tell the Weaver to change reality... (e.g. 'Add a dragon to the ruins')" 
                />
                <button @click="runAIEdit" :disabled="isAIEditing || !aiEditPrompt" class="absolute right-2 top-1.5 px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-[9px] font-black uppercase rounded-lg disabled:opacity-50 transition-all">
                  {{ isAIEditing ? 'Weaving...' : 'Execute' }}
                </button>
              </div>
            </div>
          </div>

          <!-- Assets Section -->
          <div v-if="debugData" class="space-y-12">
            <!-- Cover -->
            <section v-if="debugData.adventure" class="space-y-4">
              <div class="flex items-center justify-between">
                <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">World Essence</h3>
                <button @click="regenerateAll('cover')" :disabled="isBatchGenerating['cover']" class="px-4 py-2 rounded-xl bg-white/5 hover:bg-emerald-500/10 border border-white/5 text-[10px] font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-2 transition-all">
                  <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['cover'] }"></i>
                  Regenerate Cover
                </button>
              </div>
              <div class="relative group aspect-[3/1] bg-slate-900 border border-white/5 rounded-[2rem] overflow-hidden shadow-2xl">
                <img v-if="debugData.adventure.image_url" :src="buildVisualImageUrl(debugData.adventure.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-1000" />
                <div v-if="isQuickGenerating['cover_' + debugData.adventure.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                  <div class="flex flex-col items-center gap-2">
                    <i class="ra ra-cycle animate-spin text-3xl text-emerald-500"></i>
                    <span class="text-[10px] font-black text-emerald-500 uppercase tracking-widest">Reweaving Essence...</span>
                  </div>
                </div>
                <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent"></div>
                <div class="absolute inset-x-0 bottom-0 p-8">
                  <div class="flex justify-between items-end gap-12">
                    <div class="space-y-2 max-w-3xl">
                      <h4 class="text-3xl font-black text-white tracking-tight">{{ debugData.adventure.title }}</h4>
                      <p class="text-sm text-slate-400 leading-relaxed line-clamp-1">{{ debugData.adventure.context }}</p>
                    </div>
                    <div class="flex gap-3 shrink-0">
                       <button @click="quickRegenerateVisual('cover', debugData.adventure.id)" class="px-4 py-2 bg-white/10 backdrop-blur-md text-emerald-400 text-[9px] font-black uppercase tracking-widest rounded-lg border border-white/10 hover:bg-emerald-500 hover:text-white transition-all">Fast Gen</button>
                       <button @click="openRegenerateDialog('cover', debugData.adventure.id, debugData.adventure.title, debugData.adventure.context)" class="px-4 py-2 bg-white/10 backdrop-blur-md text-cyan-400 text-[9px] font-black uppercase tracking-widest rounded-lg border border-white/10 hover:bg-cyan-500 hover:text-white transition-all">Gen</button>
                       <button @click="openTextEdit('cover', debugData.adventure.id, debugData.adventure.title, debugData.adventure.context)" class="px-4 py-2 bg-white/10 backdrop-blur-md text-white text-[9px] font-black uppercase tracking-widest rounded-lg border border-white/10 hover:bg-blue-500 transition-all">Edit</button>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <!-- Categorized Grid -->
            <div class="space-y-8">
               <!-- Protagonist (Compact) -->
               <section v-if="debugData.protagonist" class="space-y-3">
                 <h3 class="text-[9px] font-black text-slate-500 uppercase tracking-[0.3em]">The Protagonist</h3>
                 <div class="max-w-[200px]">
                      <div @mouseenter="handleHover({ name: debugData.protagonist.name, description: debugData.protagonist.description, image_url: debugData.protagonist.profile_image, type: 'PROTAGONIST' }, $event)" @mouseleave="clearHover" class="relative group aspect-square bg-slate-900 border border-white/5 rounded-xl overflow-hidden shadow-lg">
                        <img v-if="debugData.protagonist.profile_image" :src="buildVisualImageUrl(debugData.protagonist.profile_image)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                        <div v-if="isQuickGenerating['protagonist_' + debugData.protagonist.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                           <i class="ra ra-cycle animate-spin text-2xl text-emerald-500"></i>
                        </div>
                        <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent"></div>
                        <div class="absolute inset-x-0 bottom-0 p-3">
                          <div class="font-black text-sm text-white tracking-tight truncate">{{ debugData.protagonist.name }}</div>
                        </div>
                        <div class="absolute top-2 right-2 flex gap-1.5 opacity-0 group-hover:opacity-100 transition-all scale-75 origin-top-right">
                          <button @click="quickRegenerateVisual('protagonist', debugData.protagonist.id)" class="p-2 bg-black/60 backdrop-blur-md text-emerald-400 rounded-lg border border-white/10 hover:bg-emerald-500 hover:text-white transition-all"><i class="ra ra-cycle"></i></button>
                          <button @click="openRegenerateDialog('protagonist', debugData.protagonist.id, debugData.protagonist.name, debugData.protagonist.description)" class="p-2 bg-black/60 backdrop-blur-md text-cyan-400 rounded-lg border border-white/10 hover:bg-cyan-500 hover:text-white transition-all"><i class="ra ra-eye-shield"></i></button>
                          <button @click="openTextEdit('protagonist', debugData.protagonist.id, debugData.protagonist.name, debugData.protagonist.description)" class="p-2 bg-black/60 backdrop-blur-md text-blue-400 rounded-lg border border-white/10 hover:bg-blue-500 hover:text-white transition-all"><i class="ra ra-quill-ink"></i></button>
                        </div>
                      </div>
                 </div>
               </section>

               <!-- Scenes -->
               <section v-if="debugData.scenes?.length" class="space-y-6">
                 <div class="flex items-center justify-between">
                   <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">World Locations ({{ debugData.scenes.length }})</h3>
                   <button @click="regenerateAll('scene')" :disabled="isBatchGenerating['scene']" class="text-[10px] font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
                     <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['scene'] }"></i> Regenerate All
                   </button>
                 </div>
                  <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                    <div v-for="scene in debugData.scenes" :key="'scene_' + scene.id" @mouseenter="handleHover({ name: scene.label || scene.name, description: scene.description, image_url: scene.image_url, type: 'LOCATION' }, $event)" @mouseleave="clearHover" class="relative group aspect-[1.8/1] bg-slate-900 border border-white/5 rounded-2xl overflow-hidden shadow-xl">
                      <img v-if="scene.image_url" :src="buildVisualImageUrl(scene.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                      <div v-if="isQuickGenerating['scene_' + scene.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                         <i class="ra ra-cycle animate-spin text-2xl text-emerald-500"></i>
                      </div>
                      <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-transparent to-transparent"></div>
                      <div class="absolute inset-x-0 bottom-0 p-4">
                        <div class="font-black text-sm text-white tracking-wide uppercase truncate">{{ scene.label || scene.name }}</div>
                      </div>
                      <div class="absolute top-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-all translate-y-1 group-hover:translate-y-0">
                        <button @click="quickRegenerateVisual('scene', scene.id)" class="p-2 bg-black/60 backdrop-blur-md text-emerald-400 rounded-lg border border-white/10 hover:bg-emerald-500 hover:text-white transition-all"><i class="ra ra-cycle"></i></button>
                        <button @click="openRegenerateDialog('scene', scene.id, scene.label || scene.name, scene.description)" class="p-2 bg-black/60 backdrop-blur-md text-cyan-400 rounded-lg border border-white/10 hover:bg-cyan-500 hover:text-white transition-all"><i class="ra ra-eye-shield"></i></button>
                        <button @click="openTextEdit('scene', scene.id, scene.label || scene.name, scene.description)" class="p-2 bg-black/60 backdrop-blur-md text-blue-400 rounded-lg border border-white/10 hover:bg-blue-500 hover:text-white transition-all"><i class="ra ra-quill-ink"></i></button>
                      </div>
                    </div>
                  </div>
               </section>

               <!-- NPCs -->
               <section v-if="debugData.npcs?.length" class="space-y-6">
                 <div class="flex items-center justify-between">
                   <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">Notable Inhabitants ({{ debugData.npcs.length }})</h3>
                   <button @click="regenerateAll('npc')" :disabled="isBatchGenerating['npc']" class="text-[10px] font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
                     <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['npc'] }"></i> Regenerate All
                   </button>
                 </div>
                  <div class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 gap-4">
                    <div v-for="npc in debugData.npcs" :key="'npc_' + npc.id" @mouseenter="handleHover({ name: npc.name, description: npc.description, image_url: npc.image_url, type: 'NPC' }, $event)" @mouseleave="clearHover" class="relative group aspect-[3/4] bg-slate-900 border border-white/5 rounded-2xl overflow-hidden shadow-lg">
                      <img v-if="npc.image_url" :src="buildVisualImageUrl(npc.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                      <div v-if="isQuickGenerating['npc_' + npc.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                         <i class="ra ra-cycle animate-spin text-xl text-emerald-500"></i>
                      </div>
                      <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent"></div>
                      <div class="absolute inset-x-0 bottom-0 p-3">
                        <div class="font-bold text-sm text-white truncate">{{ npc.name }}</div>
                      </div>
                      <div class="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-all translate-y-1 group-hover:translate-y-0 scale-75 origin-top-right">
                        <button @click="quickRegenerateVisual('npc', npc.id)" class="p-2 bg-black/60 backdrop-blur-md text-emerald-400 rounded-lg border border-white/10 hover:bg-emerald-500 hover:text-white transition-all"><i class="ra ra-cycle"></i></button>
                        <button @click="openRegenerateDialog('npc', npc.id, npc.name, npc.description)" class="p-2 bg-black/60 backdrop-blur-md text-cyan-400 rounded-lg border border-white/10 hover:bg-cyan-500 hover:text-white transition-all"><i class="ra ra-eye-shield"></i></button>
                        <button @click="openTextEdit('npc', npc.id, npc.name, npc.description)" class="p-2 bg-black/60 backdrop-blur-md text-blue-400 rounded-lg border border-white/10 hover:bg-blue-500 hover:text-white transition-all"><i class="ra ra-quill-ink"></i></button>
                      </div>
                    </div>
                  </div>
               </section>

               <!-- Items -->
               <section v-if="debugData.objects?.length" class="space-y-6">
                 <div class="flex items-center justify-between">
                   <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">Mystical Objects ({{ debugData.objects.length }})</h3>
                   <button @click="regenerateAll('object')" :disabled="isBatchGenerating['object']" class="text-[10px] font-bold text-emerald-500 hover:text-emerald-400 flex items-center gap-2 uppercase tracking-widest transition-colors">
                     <i class="ra ra-cycle" :class="{ 'animate-spin': isBatchGenerating['object'] }"></i> Regenerate All
                   </button>
                 </div>
                  <div class="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-3">
                    <div v-for="obj in debugData.objects" :key="'obj_' + obj.id" @mouseenter="handleHover({ name: obj.name, description: obj.description, image_url: obj.image_url, type: 'ITEM' }, $event)" @mouseleave="clearHover" class="relative group aspect-square bg-slate-900 border border-white/5 rounded-xl overflow-hidden shadow-lg">
                      <img v-if="obj.image_url" :src="buildVisualImageUrl(obj.image_url)" class="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                      <div v-if="isQuickGenerating['object_' + obj.id]" class="absolute inset-0 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center z-20">
                         <i class="ra ra-cycle animate-spin text-lg text-emerald-500"></i>
                      </div>
                      <div class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent"></div>
                      <div class="absolute inset-x-0 bottom-0 p-2">
                        <div class="font-bold text-[10px] text-white truncate text-center">{{ obj.name }}</div>
                      </div>
                      <div class="absolute top-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-all scale-75 origin-top-right">
                        <button @click="quickRegenerateVisual('object', obj.id)" class="p-1.5 bg-black/60 backdrop-blur-md text-emerald-400 rounded border border-white/10 hover:bg-emerald-500 hover:text-white transition-all"><i class="ra ra-cycle text-xs"></i></button>
                        <button @click="openRegenerateDialog('object', obj.id, obj.name, obj.description)" class="p-1.5 bg-black/60 backdrop-blur-md text-cyan-400 rounded border border-white/10 hover:bg-cyan-500 hover:text-white transition-all"><i class="ra ra-eye-shield text-xs"></i></button>
                        <button @click="openTextEdit('object', obj.id, obj.name, obj.description)" class="p-1.5 bg-black/60 backdrop-blur-md text-blue-400 rounded border border-white/10 hover:bg-blue-500 hover:text-white transition-all"><i class="ra ra-quill-ink text-xs"></i></button>
                      </div>
                    </div>
                  </div>
               </section>

               <!-- Quests -->
               <section v-if="adventure?.quests?.length" class="space-y-6">
                 <h3 class="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">Quest Log ({{ adventure.quests.length }})</h3>
                 <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                   <div v-for="quest in adventure.quests" :key="'quest_' + quest.id" class="bg-slate-900/40 border border-white/5 rounded-2xl p-4 hover:border-emerald-500/20 transition-all group">
                     <div class="flex items-start justify-between mb-2">
                       <div class="flex items-center gap-3">
                         <div class="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                           <i :class="[quest.is_main ? 'ra ra-trophy text-emerald-400' : 'ra ra-scroll-unfurled text-slate-400']"></i>
                         </div>
                         <div>
                           <h4 class="text-sm font-bold text-white">{{ quest.title }}</h4>
                           <span class="text-[8px] text-slate-500 uppercase tracking-widest">{{ quest.is_main ? 'Main Quest' : 'Side Quest' }}</span>
                         </div>
                       </div>
                       <span class="px-2 py-0.5 rounded bg-black/40 text-[8px] font-black text-emerald-500 uppercase border border-emerald-500/20">{{ quest.exp_reward }} XP</span>
                     </div>
                     <p class="text-[11px] text-slate-400 leading-relaxed line-clamp-2 mb-3">{{ quest.description }}</p>
                     <div class="flex items-center gap-2">
                        <div class="flex-grow h-1 bg-black/40 rounded-full overflow-hidden">
                           <div class="h-full bg-emerald-500/40" :style="{ width: quest.status === 'completed' ? '100%' : '0%' }"></div>
                        </div>
                        <span class="text-[8px] font-black uppercase tracking-tighter" :class="quest.status === 'completed' ? 'text-emerald-500' : 'text-slate-600'">{{ quest.status }}</span>
                     </div>
                   </div>
                 </div>
               </section>
            </div>
          </div>
        </div>

        <!-- Advanced Tab -->
        <div v-else-if="activeTab === 'advanced'" class="space-y-10 animate-page-in">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
            <!-- Exports -->
            <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6">
              <h4 class="text-[10px] font-black text-white uppercase tracking-widest flex items-center gap-2">
                <i class="ra ra-save text-emerald-500"></i> Archival & Export
              </h4>
              <p class="text-xs text-slate-400 leading-relaxed">Download this adventure for external use, backup, or sharing with others.</p>
              <div class="grid grid-cols-1 gap-3">
                <button @click="exportADV" class="flex items-center justify-between px-6 py-4 bg-white/5 hover:bg-emerald-500/10 border border-white/5 hover:border-emerald-500/30 rounded-2xl transition-all group">
                  <span class="text-[10px] font-black uppercase tracking-widest text-slate-300 group-hover:text-emerald-400">Export as .ADV Manifest</span>
                  <i class="ra ra-save text-emerald-500"></i>
                </button>
                <button @click="exportBlueprint" class="flex items-center justify-between px-6 py-4 bg-white/5 hover:bg-blue-500/10 border border-white/5 hover:border-blue-500/30 rounded-2xl transition-all group">
                  <span class="text-[10px] font-black uppercase tracking-widest text-slate-300 group-hover:text-blue-400">Download Blueprint (JSON)</span>
                  <i class="ra ra-quill-ink text-blue-500"></i>
                </button>
                <button @click="exportSession" class="flex items-center justify-between px-6 py-4 bg-white/5 hover:bg-amber-500/10 border border-white/5 hover:border-amber-500/30 rounded-2xl transition-all group">
                  <span class="text-[10px] font-black uppercase tracking-widest text-slate-300 group-hover:text-amber-400">Full Session Snapshot</span>
                  <i class="ra ra-scroll-unfurled text-amber-500"></i>
                </button>
              </div>
            </div>

            <!-- Maintenance -->
            <div class="p-8 bg-slate-900/50 border border-white/5 rounded-3xl space-y-6">
              <h4 class="text-[10px] font-black text-white uppercase tracking-widest flex items-center gap-2">
                <i class="ra ra-cycle text-emerald-500"></i> Batch Operations
              </h4>
              <p class="text-xs text-slate-400 leading-relaxed">Perform mass updates on all world assets. Warning: This consumes AI resources.</p>
              <div class="flex flex-wrap gap-2">
                <button v-for="kind in (['cover', 'protagonist', 'scene', 'npc', 'object'] as const)" :key="kind" @click="regenerateAll(kind)" class="px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all">
                  Regen {{ kind }}
                </button>
              </div>
              
              <div class="pt-6 border-t border-white/5">
                <h4 class="text-[10px] font-black text-red-500 uppercase tracking-widest flex items-center gap-2 mb-4">
                  <i class="ra ra-tombstone"></i> Danger Zone
                </h4>
                <button @click="resetAdventure" class="w-full py-4 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500 hover:text-white rounded-2xl text-[10px] font-black uppercase tracking-[0.2em] transition-all">
                  Reset Adventure Progress
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
          v-if="hoveredEntity" 
          class="fixed z-[100] pointer-events-none transition-all duration-75"
          :style="{ left: (mousePos.x + 20) + 'px', top: (mousePos.y + 20) + 'px' }"
        >
          <div class="w-64 bg-slate-900/95 border border-slate-700 rounded-2xl shadow-2xl backdrop-blur-xl overflow-hidden flex flex-col animate-tooltip-in">
            <!-- Image Area -->
            <div v-if="hoveredEntity.image_url" class="h-32 w-full relative">
              <img :src="buildVisualImageUrl(hoveredEntity.image_url)" class="absolute inset-0 w-full h-full object-cover" />
              <div class="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent"></div>
            </div>

            <!-- Content -->
            <div class="p-4 bg-slate-900">
              <div class="flex items-center justify-between mb-1">
                <span class="text-sm font-bold text-white uppercase tracking-wider">{{ hoveredEntity.name }}</span>
                <span 
                  class="text-[8px] px-1.5 py-0.5 rounded border font-mono uppercase border-emerald-500/50 text-emerald-400"
                >
                  {{ hoveredEntity.type }}
                </span>
              </div>
              <p class="text-xs text-slate-400 leading-relaxed italic">{{ hoveredEntity.description }}</p>
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
                  <p class="text-slate-500 text-[10px] uppercase font-bold tracking-tighter">Target: {{ selectedVisual.label }}</p>
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
                      <h4 class="text-[10px] font-black text-slate-500 uppercase">Current description</h4>
                      <p class="text-xs text-slate-400 leading-relaxed italic line-clamp-3">"{{ selectedVisual.description }}"</p>
                    </div>
                  </div>
                </div>

                <div class="space-y-3">
                  <label class="block text-[10px] font-black text-slate-500 uppercase tracking-widest">Override Prompt</label>
                  <textarea 
                    v-model="visualPrompt" 
                    rows="5" 
                    placeholder="Describe exactly what you want to see. This will ignore the current asset description..." 
                    class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-sm text-white placeholder:text-slate-600 focus:border-cyan-500 outline-none transition-all leading-relaxed shadow-inner"
                  ></textarea>
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
                  <p class="text-slate-500 text-[10px] uppercase font-bold tracking-tighter">ID: {{ editEntityContext.id }}</p>
                </div>
                <button @click="showEditModal = false" class="text-slate-500 hover:text-white transition-colors">
                  <i class="ra ra-cancel text-xl"></i>
                </button>
              </div>

              <div class="space-y-6">
                <div class="space-y-3">
                  <label class="block text-[10px] font-black text-slate-500 uppercase tracking-widest">Entity Name</label>
                  <input v-model="editForm.name" class="w-full bg-black/40 border border-white/5 rounded-2xl px-6 py-4 text-2xl font-bold text-white focus:border-emerald-500 outline-none transition-all shadow-inner" />
                </div>
                <div class="space-y-3">
                  <label class="block text-[10px] font-black text-slate-500 uppercase tracking-widest">Description / Biography</label>
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
              <p class="text-[10px] font-black uppercase tracking-widest opacity-50">{{ n.type }}</p>
              <p class="text-xs font-bold leading-relaxed">{{ n.message }}</p>
            </div>
            <button @click="notifications = notifications.filter(x => x.id !== n.id)" class="opacity-50 hover:opacity-100 transition-opacity">
              <i class="ra ra-cancel text-xs"></i>
            </button>
          </div>
        </TransitionGroup>
      </div>
    </Teleport>

    <!-- REALITY WEAVING OVERLAY (Global Lock) -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="isAIEditing" class="fixed inset-0 z-[500] flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-2xl">
          <div class="relative w-32 h-32 mb-8">
            <div class="absolute inset-0 rounded-full border-4 border-emerald-500/10 animate-pulse"></div>
            <div class="absolute inset-2 rounded-full border-2 border-emerald-500/20 border-t-emerald-500 animate-spin"></div>
            <div class="absolute inset-0 flex items-center justify-center">
              <i class="ra ra-player-teleport text-4xl text-emerald-500 animate-pulse"></i>
            </div>
          </div>
          <h2 class="text-xl font-black text-white uppercase tracking-[0.4em] mb-2">Weaving Reality</h2>
          <p class="text-xs font-bold text-emerald-500/60 uppercase tracking-widest animate-pulse">The Chronicles are being rewritten...</p>
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

