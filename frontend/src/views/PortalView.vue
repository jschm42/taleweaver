<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import EditAdventureModal from '@/components/EditAdventureModal.vue'
import { api } from '@/composables/useApi'
import type { AdventureImportPayload, CreateAdventurePayload } from '@/types'

const router = useRouter()

interface Adventure {
  game_id: string
  adventure_id: string
  avatar_id: string
  adventure_title: string
  image_url: string | null
  scene_id: string
  current_scene_name?: string | null
  in_game_time: number
  is_paused: boolean
}

interface PendingAdventureCard {
  adventureId: string
  title: string
  status: string
  hasError: boolean
}

const adventures = ref<Adventure[]>([])
const isLoading = ref(true)

const showCreateModal = ref(false)
const showImportModal = ref(false)
const showEditModal = ref(false)
const selectedAdventureId = ref<string | null>(null)

const isSubmitting = ref(false)
const isImporting = ref(false)
const errorMsg = ref('')
const advancedValidationError = ref('')
const creationStatus = ref('')

const importInput = ref<HTMLInputElement | null>(null)
const pendingImports = ref<PendingAdventureCard[]>([])
const pendingCreations = ref<PendingAdventureCard[]>([])
const loadingWordIndex = ref(0)
const loadingWords = [
  'Manifest wird geprueft',
  'Weltstruktur entsteht',
  'Szenen werden gebaut',
  'Figuren werden gewebt',
]
let loadingWordTimer: number | null = null

const visibleAdventures = computed(() => {
  const pendingIds = new Set([
    ...pendingImports.value.map((entry) => entry.adventureId),
    ...pendingCreations.value.map((entry) => entry.adventureId),
  ])
  return adventures.value.filter((adv) => !pendingIds.has(adv.adventure_id))
})

const form = ref({
  id: '',
  mode: 'simple' as 'simple' | 'advanced',
  title: '',
  context: '',
  image_url: null as string | null,
  generate_npc_images: false,
  generate_item_images: false,
  generate_scene_images: false,
  automatic_cover_generation: false,
  time_per_turn: 5,
  story_idea: '',
  tone: '',
  characters_text: '',
  image_style: '',
  items_text: '',
  scenes_text: '',
  objects_text: '',
  npc_text: '',
  pacing_text: '',
  start_date: '',
  start_time: '',
  protagonist_role: '',
})

const importState = ref({
  manifest: null as AdventureImportPayload | null,
  titleOverride: '',
  generate_npc_images: false,
  generate_item_images: false,
  automatic_cover_generation: false,
})

function resetImportState() {
  importState.value = {
    manifest: null,
    titleOverride: '',
    generate_npc_images: false,
    generate_item_images: false,
    automatic_cover_generation: false,
  }
}

function closeImportModal() {
  showImportModal.value = false
  isImporting.value = false
  errorMsg.value = ''
  resetImportState()
}

function resetCreateForm() {
  form.value = {
    id: crypto.randomUUID(),
    mode: 'simple',
    title: '',
    context: '',
    image_url: null,
    generate_npc_images: false,
    generate_item_images: false,
    generate_scene_images: false,
    automatic_cover_generation: false,
    time_per_turn: 5,
    story_idea: '',
    tone: '',
    characters_text: '',
    image_style: '',
    items_text: '',
    scenes_text: '',
    objects_text: '',
    npc_text: '',
    pacing_text: '',
    start_date: '',
    start_time: '',
    protagonist_role: '',
  }
}

function addPendingImportCard(adventureId: string, title: string) {
  pendingImports.value = [
    ...pendingImports.value.filter((entry) => entry.adventureId !== adventureId),
    {
      adventureId,
      title,
      status: 'Import gestartet',
      hasError: false,
    },
  ]
}

function addPendingCreationCard(adventureId: string, title: string) {
  pendingCreations.value = [
    ...pendingCreations.value.filter((entry) => entry.adventureId !== adventureId),
    {
      adventureId,
      title,
      status: 'Generierung gestartet',
      hasError: false,
    },
  ]
}

function updatePendingImportStatus(adventureId: string, status: string, hasError = false) {
  pendingImports.value = pendingImports.value.map((entry) =>
    entry.adventureId === adventureId
      ? {
          ...entry,
          status,
          hasError,
        }
      : entry,
  )
}

function updatePendingCreationStatus(adventureId: string, status: string, hasError = false) {
  pendingCreations.value = pendingCreations.value.map((entry) =>
    entry.adventureId === adventureId
      ? {
          ...entry,
          status,
          hasError,
        }
      : entry,
  )
}

function removePendingImportCard(adventureId: string) {
  pendingImports.value = pendingImports.value.filter((entry) => entry.adventureId !== adventureId)
}

function removePendingCreationCard(adventureId: string) {
  pendingCreations.value = pendingCreations.value.filter((entry) => entry.adventureId !== adventureId)
}

function dismissPendingImportCard(adventureId: string) {
  removePendingImportCard(adventureId)
}

async function fetchAdventures() {
  try {
    adventures.value = await api.listAdventures()
  } catch (error) {
    console.error('API Error:', error)
  } finally {
    isLoading.value = false
  }
}

async function deleteAdventure(adventureId: string) {
  if (!confirm('Are you sure you want to delete this adventure? This action cannot be undone.')) {
    return
  }
  try {
    await api.deleteAdventure(adventureId)
    adventures.value = adventures.value.filter((a) => a.adventure_id !== adventureId)
  } catch (error) {
    console.error('Error deleting adventure:', error)
  }
}

function playAdventure(gameId: string) {
  router.push({ name: 'game', params: { id: gameId } })
}

function displayLocationName(adventure: Adventure) {
  return adventure.current_scene_name || adventure.scene_id
}

function openCreateModal() {
  resetCreateForm()
  errorMsg.value = ''
  advancedValidationError.value = ''
  isSubmitting.value = false
  creationStatus.value = ''
  showCreateModal.value = true
}

function openEditModal(adventureId: string) {
  selectedAdventureId.value = adventureId
  showEditModal.value = true
}

function handleAdventureUpdate() {
  fetchAdventures()
}

function triggerImportPicker() {
  importInput.value?.click()
}

async function onImportFileSelected(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) {
    return
  }

  const file = target.files[0]
  try {
    const parsed = JSON.parse(await file.text()) as AdventureImportPayload
    if (!parsed.version || !parsed.title) {
      throw new Error('Invalid ADV file. Missing required version/title.')
    }

    resetImportState()
    importState.value.manifest = parsed
    importState.value.titleOverride = parsed.title
    importState.value.generate_npc_images = false
    importState.value.generate_item_images = false
    importState.value.automatic_cover_generation = false
    isImporting.value = false
    errorMsg.value = ''
    showImportModal.value = true
  } catch (error: any) {
    errorMsg.value = error?.message || 'Failed to parse .adv file.'
  } finally {
    target.value = ''
  }
}

async function executeImport(userInitiated = false) {
  if (!userInitiated) {
    return
  }

  if (!importState.value.manifest) {
    return
  }
  if (!importState.value.titleOverride.trim()) {
    errorMsg.value = 'Title is required.'
    return
  }

  isImporting.value = true
  errorMsg.value = ''

  try {
    const payload: AdventureImportPayload = {
      ...importState.value.manifest,
      title: importState.value.titleOverride.trim(),
      generate_npc_images: importState.value.generate_npc_images,
      generate_item_images: importState.value.generate_item_images,
      automatic_cover_generation: importState.value.automatic_cover_generation,
    }

    const result = await api.importAdventure(payload)
    addPendingImportCard(result.adventure_id, payload.title)
    showImportModal.value = false
    await fetchAdventures()
    void pollAdventureStatus(result.adventure_id, {
      navigateOnReady: false,
      onStatus: (status) => updatePendingImportStatus(result.adventure_id, status),
      onReady: async () => {
        removePendingImportCard(result.adventure_id)
        await fetchAdventures()
      },
      onFailure: (status) => updatePendingImportStatus(result.adventure_id, status, true),
    })
  } catch (error: any) {
    errorMsg.value = error?.message || 'Import failed.'
  } finally {
    isImporting.value = false
  }
}

async function handleImageUpload(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) {
    return
  }

  const file = target.files[0]
  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await fetch(`http://localhost:8000/api/data/image?type=adventure&adventure_id=${form.value.id}`, {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      throw new Error('Failed to upload adventure image. Max dimensions 512x512.')
    }

    const data = await res.json()
    form.value.image_url = data.url
    errorMsg.value = ''
  } catch (error: any) {
    errorMsg.value = error?.message || 'Network error uploading image.'
  }
}

function buildAdvancedManifest() {
  const startDateTime = form.value.start_date && form.value.start_time
    ? new Date(`${form.value.start_date}T${form.value.start_time}`)
    : null

  return {
    version: '1.0',
    title: form.value.title,
    story_idea: form.value.story_idea || form.value.context,
    tone: form.value.tone || undefined,
    image_style: form.value.image_style || undefined,
    time_per_turn: form.value.time_per_turn,
    start_date: form.value.start_date || undefined,
    start_time: form.value.start_time || undefined,
    start_datetime: startDateTime && !Number.isNaN(startDateTime.getTime()) ? startDateTime.toISOString() : undefined,
    protagonist: form.value.protagonist_role
      ? {
          role: form.value.protagonist_role,
        }
      : undefined,
    pacing: form.value.pacing_text
      ? {
          notes: form.value.pacing_text,
        }
      : undefined,
    metadata: {
      characters_text: form.value.characters_text || undefined,
      npc_text: form.value.npc_text || undefined,
      scenes_text: form.value.scenes_text || undefined,
      items_text: form.value.items_text || undefined,
      objects_text: form.value.objects_text || undefined,
    },
  }
}

async function createAdventure() {
  if (!form.value.title.trim()) {
    errorMsg.value = 'Title is required.'
    return
  }

  if (form.value.mode === 'advanced') {
    if (!form.value.start_date || !form.value.start_time) {
      advancedValidationError.value = 'Start date and start time are required in advanced mode.'
      return
    }

    const startDateTime = new Date(`${form.value.start_date}T${form.value.start_time}`)
    if (Number.isNaN(startDateTime.getTime())) {
      advancedValidationError.value = 'Please provide a valid start date and time.'
      return
    }
  }

  isSubmitting.value = true
  errorMsg.value = ''
  advancedValidationError.value = ''
  creationStatus.value = 'Initializing...'

  try {
    const payload: CreateAdventurePayload = {
      id: form.value.id,
      title: form.value.title.trim(),
      context: form.value.context,
      image_url: form.value.image_url,
      strict_rules: true,
      generate_npc_images: form.value.generate_npc_images,
      generate_item_images: form.value.generate_item_images,
      generate_scene_images: form.value.generate_scene_images,
      heartbeat_enabled: false,
      time_per_turn: form.value.time_per_turn,
    }

    if (form.value.automatic_cover_generation) {
      payload.automatic_cover_generation = true
    }

    if (form.value.mode === 'advanced') {
      payload.original_manifest = buildAdvancedManifest()
      payload.pacing = form.value.pacing_text
        ? { notes: form.value.pacing_text }
        : undefined
    }

    const result = await api.createAdventure(payload)
    addPendingCreationCard(result.adventure_id, payload.title)
    showCreateModal.value = false
    await fetchAdventures()
    await pollAdventureStatus(result.adventure_id, {
      navigateOnReady: false,
      onStatus: (status) => updatePendingCreationStatus(result.adventure_id, status),
      onReady: async () => {
        removePendingCreationCard(result.adventure_id)
        await fetchAdventures()
      },
      onFailure: (status) => updatePendingCreationStatus(result.adventure_id, status, true),
    })
  } catch (error: any) {
    errorMsg.value = error?.message || 'Failed to start creation.'
    isSubmitting.value = false
  }
}

async function pollAdventureStatus(
  adventureId: string,
  options?: {
    navigateOnReady?: boolean
    onStatus?: (status: string) => void
    onReady?: () => void
    onFailure?: (status: string) => void
  },
) {
  return new Promise<void>((resolve) => {
    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/adventures/${adventureId}/status`)
        if (!res.ok) {
          clearInterval(pollInterval)
          const failStatus = 'Generierung fehlgeschlagen'
          errorMsg.value = 'Generation failed. Please try again with a different setup.'
          options?.onFailure?.(failStatus)
          isSubmitting.value = false
          isImporting.value = false
          resolve()
          return
        }

        const data = await res.json()
        const statusText = data.status || 'Constructing world...'
        creationStatus.value = statusText
        options?.onStatus?.(statusText)

        const hasGenerationError = Boolean(data.error) || /failed/i.test(statusText)
        if (hasGenerationError) {
          clearInterval(pollInterval)
          const detail = data.error ? ` (${data.error})` : ''
          errorMsg.value = `Generation failed${detail}. Please review your model/image settings.`
          options?.onFailure?.(statusText)
          isSubmitting.value = false
          isImporting.value = false
          resolve()
          return
        }

        if (data.is_ready) {
          clearInterval(pollInterval)
          creationStatus.value = ''
          isSubmitting.value = false
          isImporting.value = false
          options?.onReady?.()
          if (options?.navigateOnReady) {
            router.push({ name: 'game', params: { id: adventureId } })
          }
          resolve()
        }
      } catch {
        clearInterval(pollInterval)
        errorMsg.value = 'Lost connection while tracking generation status.'
        options?.onFailure?.('Verbindung unterbrochen')
        isSubmitting.value = false
        isImporting.value = false
        resolve()
      }
    }, 1500)
  })
}

function goToAdmin() {
  router.push({ name: 'admin' })
}

onMounted(() => {
  resetCreateForm()
  fetchAdventures()
  loadingWordTimer = window.setInterval(() => {
    loadingWordIndex.value = (loadingWordIndex.value + 1) % loadingWords.length
  }, 1300)
})

onUnmounted(() => {
  if (loadingWordTimer !== null) {
    clearInterval(loadingWordTimer)
  }
})
</script>

<template>
  <div class="min-h-screen bg-slate-950 text-slate-200 font-sans p-8 flex flex-col items-center">
    <header class="w-full max-w-6xl mb-12 flex justify-between items-center px-4">
      <h1 class="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-500">
        TaleWeaver
      </h1>
      <div class="flex items-center gap-4">
        <button
          @click="router.push({ name: 'characters' })"
          class="group flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 hover:border-emerald-500/50 transition-all duration-300"
        >
          <span class="text-sm font-medium">Characters</span>
          <i class="ra ra-helmet text-emerald-400"></i>
        </button>
        <button
          @click="goToAdmin"
          class="group flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 hover:bg-white/10 transition-all duration-300"
        >
          <span class="text-sm font-medium">Settings</span>
          <i class="ra ra-gear text-emerald-400"></i>
        </button>
      </div>
    </header>

    <main class="w-full max-w-6xl flex-grow px-4 relative">
      <div v-if="isLoading" class="flex justify-center items-center h-64">
        <div class="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-emerald-500"></div>
      </div>

      <div v-else-if="adventures.length === 0 && pendingImports.length === 0 && pendingCreations.length === 0" class="text-center py-20 bg-white/5 rounded-3xl border border-white/10 backdrop-blur-md">
        <h2 class="text-2xl font-bold text-white mb-2">No active adventures</h2>
        <p class="text-slate-400 mb-8 max-w-md mx-auto">Start your first world or import a prepared ADV manifest.</p>
        <div class="flex items-center justify-center gap-3">
          <button
            @click="openCreateModal"
            class="px-8 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-bold rounded-xl transition-all duration-300"
          >
            Begin New Adventure
          </button>
          <button
            @click="triggerImportPicker"
            class="px-8 py-3 bg-slate-800 hover:bg-slate-700 text-white font-bold rounded-xl transition-all duration-300"
          >
            Import .ADV
          </button>
        </div>
      </div>

      <div v-else>
        <div class="flex justify-between items-end mb-8">
          <div>
            <h2 class="text-2xl font-bold text-white">Your Journeys</h2>
            <p class="text-slate-400 text-sm mt-1">Continue where you left off</p>
          </div>
          <div class="flex gap-2">
            <button
              @click="openCreateModal"
              class="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-semibold rounded-lg"
            >
              New Adventure
            </button>
            <button
              @click="triggerImportPicker"
              class="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-semibold rounded-lg"
            >
              Import
            </button>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="pending in pendingCreations"
            :key="pending.adventureId"
            class="relative bg-slate-900 rounded-2xl border border-emerald-500/40 overflow-hidden flex flex-col"
          >
            <div class="aspect-[2/1] bg-slate-800 relative overflow-hidden flex items-center justify-center loading-placeholder-gradient">
              <div v-if="!pending.hasError && pending.status !== 'Fertig generiert'" class="absolute inset-0 loading-placeholder-shimmer"></div>
              <i class="ra ra-scroll-unfurled text-4xl text-emerald-300/80 z-10"></i>
            </div>

            <div class="p-6 flex-grow flex flex-col">
              <div class="flex items-center justify-between mb-4">
                <span class="text-xs font-mono text-emerald-400/90 bg-emerald-500/10 px-2 py-1 rounded">WIRD ERZEUGT</span>
                <span :class="['text-[10px] px-2 py-1 rounded uppercase tracking-wider font-bold', pending.hasError ? 'bg-red-500/20 text-red-300' : 'bg-emerald-500/20 text-emerald-200']">
                  {{ pending.hasError ? 'Fehler' : 'Create' }}
                </span>
              </div>

              <h3 class="text-xl font-bold text-white mb-2 line-clamp-1">
                {{ pending.title }}
              </h3>

              <div class="flex-grow space-y-3 mt-2">
                <div class="flex justify-between text-[11px] pb-2 border-b border-white/5">
                  <span class="text-slate-500 uppercase tracking-widest font-semibold">Status</span>
                  <span :class="['font-medium', pending.hasError ? 'text-red-300' : 'text-emerald-200']">{{ pending.status }}</span>
                </div>
                <div class="text-xs text-slate-400 flex items-center gap-2">
                  <span v-if="!pending.hasError && pending.status !== 'Fertig generiert'" class="loading-word animate-wordfade">Aktueller Schritt: {{ pending.status }}</span>
                  <span v-if="!pending.hasError && pending.status !== 'Fertig generiert'" class="loading-dots" aria-hidden="true"></span>
                </div>
              </div>

              <div class="mt-6">
                <button
                  :disabled="!(pending.hasError || pending.status === 'Fertig generiert')"
                  @click="removePendingCreationCard(pending.adventureId)"
                  :class="[
                    'w-full py-3 font-bold rounded-xl transition-all duration-200',
                    (pending.hasError || pending.status === 'Fertig generiert')
                      ? 'bg-red-600/20 text-red-200 hover:bg-red-600/30 border border-red-400/30'
                      : 'bg-emerald-900/40 text-emerald-200/70 cursor-not-allowed'
                  ]"
                >
                  {{ (pending.hasError || pending.status === 'Fertig generiert') ? 'Kachel entfernen' : 'Bitte warten...' }}
                </button>
              </div>
            </div>
          </div>

          <div
            v-for="pending in pendingImports"
            :key="pending.adventureId"
            class="relative bg-slate-900 rounded-2xl border border-cyan-500/40 overflow-hidden flex flex-col"
          >
              <div class="aspect-[2/1] bg-slate-800 relative overflow-hidden flex items-center justify-center loading-placeholder-gradient">
              <div v-if="!pending.hasError && pending.status !== 'Fertig generiert'" class="absolute inset-0 loading-placeholder-shimmer"></div>
              <i class="ra ra-quill-ink text-4xl text-cyan-300/80 z-10"></i>
            </div>

            <div class="p-6 flex-grow flex flex-col">
              <div class="flex items-center justify-between mb-4">
                <span class="text-xs font-mono text-cyan-400/90 bg-cyan-500/10 px-2 py-1 rounded">WIRD ERZEUGT</span>
                <span :class="['text-[10px] px-2 py-1 rounded uppercase tracking-wider font-bold', pending.hasError ? 'bg-red-500/20 text-red-300' : 'bg-cyan-500/20 text-cyan-200']">
                  {{ pending.hasError ? 'Fehler' : 'Import' }}
                </span>
              </div>

              <h3 class="text-xl font-bold text-white mb-2 line-clamp-1">
                {{ pending.title }}
              </h3>

              <div class="flex-grow space-y-3 mt-2">
                <div class="flex justify-between text-[11px] pb-2 border-b border-white/5">
                  <span class="text-slate-500 uppercase tracking-widest font-semibold">Status</span>
                  <span :class="['font-medium', pending.hasError ? 'text-red-300' : 'text-cyan-200']">{{ pending.status }}</span>
                </div>
                <div class="text-xs text-slate-400 flex items-center gap-2">
                  <span v-if="!pending.hasError && pending.status !== 'Fertig generiert'" class="loading-word animate-wordfade">Aktueller Schritt: {{ pending.status }}</span>
                  <span v-if="!pending.hasError && pending.status !== 'Fertig generiert'" class="loading-dots" aria-hidden="true"></span>
                </div>
              </div>

              <div class="mt-6">
                <button
                  :disabled="!(pending.hasError || pending.status === 'Fertig generiert')"
                  @click="dismissPendingImportCard(pending.adventureId)"
                  :class="[
                    'w-full py-3 font-bold rounded-xl transition-all duration-200',
                    (pending.hasError || pending.status === 'Fertig generiert')
                      ? 'bg-red-600/20 text-red-200 hover:bg-red-600/30 border border-red-400/30'
                      : 'bg-cyan-900/40 text-cyan-200/70 cursor-not-allowed'
                  ]"
                >
                  {{ (pending.hasError || pending.status === 'Fertig generiert') ? 'Kachel entfernen' : 'Bitte warten...' }}
                </button>
              </div>
            </div>
          </div>

          <div
            v-for="adv in visibleAdventures"
            :key="adv.game_id"
            class="group relative mx-auto w-full max-w-[21rem] bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden hover:border-emerald-500/50 transition-all duration-500 flex flex-col"
          >
            <div class="aspect-[2/1] bg-slate-800 relative overflow-hidden flex items-center justify-center">
              <template v-if="adv.image_url">
                <img :src="'http://localhost:8000' + adv.image_url" class="w-full h-full object-cover" />
              </template>
              <template v-else>
                <i class="ra ra-scroll-unfurled text-6xl text-slate-700 opacity-50"></i>
              </template>
              <div class="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/75 via-black/42 to-transparent"></div>
              <div class="absolute inset-x-0 top-0 px-3 pt-3 pb-5">
                <span class="block truncate text-lg font-extrabold text-white [text-shadow:0_2px_4px_rgba(0,0,0,0.95),0_0_10px_rgba(0,0,0,0.5)]">
                  {{ adv.adventure_title }}
                </span>
              </div>
            </div>

            <div class="p-5 flex-grow flex flex-col">
              <div class="flex items-center justify-between mb-3">
                <span class="text-[9px] font-mono text-emerald-400/75 bg-emerald-500/5 px-2 py-0.5 rounded">{{ adv.game_id.substring(0, 8) }}</span>
                <span class="text-[10px] px-2 py-1 bg-slate-800 rounded uppercase text-slate-500 tracking-wider font-bold">{{ adv.is_paused ? 'PAUSED' : 'ACTIVE' }}</span>
              </div>

              <div class="flex-grow space-y-2 mt-1">
                <div class="flex justify-between text-[11px] pb-2 border-b border-white/5 gap-3">
                  <span class="text-slate-500 uppercase tracking-widest font-semibold">Location</span>
                  <span class="text-slate-200 text-right truncate">{{ displayLocationName(adv) }}</span>
                </div>
              </div>

              <div class="mt-4 grid grid-cols-[1fr_auto_auto] gap-2">
                <button
                  @click="playAdventure(adv.game_id)"
                  class="flex items-center justify-center gap-2 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl transition-all duration-300"
                >
                  <span aria-hidden="true">▶</span>
                  Play
                </button>
                <button
                  @click="openEditModal(adv.adventure_id)"
                  class="flex items-center justify-center px-3 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-xl border border-slate-700 transition-all duration-300"
                  title="Edit Adventure"
                >
                  <span aria-hidden="true">✎</span>
                </button>
                <button
                  @click="deleteAdventure(adv.adventure_id)"
                  class="flex items-center justify-center px-3 py-2.5 bg-slate-800 hover:bg-red-900/30 text-slate-400 hover:text-red-400 rounded-xl border border-slate-700 transition-all duration-300"
                  title="Delete Adventure"
                >
                  <span aria-hidden="true">🗑</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <input ref="importInput" type="file" accept=".adv,application/json" @change="onImportFileSelected" class="hidden" />
    </main>

    <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center pt-10">
      <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="showCreateModal = false"></div>

      <div class="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-3xl max-h-[90vh] overflow-y-auto relative z-10 shadow-2xl p-8 flex flex-col">
        <button @click="showCreateModal = false" class="absolute top-6 right-6 text-slate-500 hover:text-white transition-colors">X</button>

        <h2 class="text-3xl font-extrabold text-white mb-2">Create New Adventure</h2>
        <p class="text-slate-400 mb-6 text-base">Simple for quick starts, advanced for full prompt control.</p>

        <div class="mb-6 flex gap-2 border-b border-slate-700 pb-4">
          <button
            @click="form.mode = 'simple'"
            :class="[
              'px-4 py-2 rounded-lg font-semibold transition-all',
              form.mode === 'simple' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            ]"
          >
            Simple
          </button>
          <button
            @click="form.mode = 'advanced'"
            :class="[
              'px-4 py-2 rounded-lg font-semibold transition-all',
              form.mode === 'advanced' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
            ]"
          >
            Advanced
          </button>
        </div>

        <div class="space-y-5 max-h-[calc(90vh-280px)] overflow-y-auto custom-scrollbar">
          <div>
            <label class="block text-base font-semibold text-slate-300 mb-2">Adventure Title *</label>
            <input v-model="form.title" type="text" maxlength="70" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
          </div>

          <div>
            <label class="block text-base font-semibold text-slate-300 mb-2">Story Idea / Context</label>
            <textarea v-model="form.context" rows="4" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
          </div>

          <template v-if="form.mode === 'advanced'">
            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">Story Idea (Advanced)</label>
              <textarea v-model="form.story_idea" rows="3" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>

            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">Tone</label>
              <textarea v-model="form.tone" rows="2" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>

            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">Image Style</label>
              <textarea v-model="form.image_style" rows="2" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>

            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">Characters</label>
              <textarea v-model="form.characters_text" rows="3" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>

            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">NPCs</label>
              <textarea v-model="form.npc_text" rows="3" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>

            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">Scenes</label>
              <textarea v-model="form.scenes_text" rows="3" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>

            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">Items</label>
              <textarea v-model="form.items_text" rows="3" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>

            <div>
              <label class="block text-base font-semibold text-slate-300 mb-2">Objects</label>
              <textarea v-model="form.objects_text" rows="3" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
            </div>

            <div class="p-6 bg-slate-950 border border-slate-800 rounded-2xl space-y-4">
              <div class="flex items-center gap-3">
                <div class="p-2 bg-emerald-500/10 rounded-lg text-emerald-500">
                  <i class="ra ra-hourglass text-xl"></i>
                </div>
                <div>
                  <h3 class="text-sm font-bold text-white uppercase tracking-wider">Time Pacing</h3>
                  <p class="text-[10px] text-slate-500">Minutes advanced per action.</p>
                </div>
              </div>

              <div class="flex items-center gap-6">
                <input type="range" v-model.number="form.time_per_turn" min="1" max="60" step="1" class="flex-grow accent-emerald-500" />
                <div class="w-20 text-center">
                  <span class="text-xl font-bold text-emerald-500">{{ form.time_per_turn }}</span>
                  <span class="text-[10px] text-slate-500 block uppercase pt-0.5">Minutes</span>
                </div>
              </div>

              <div>
                <label class="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Pacing Notes</label>
                <textarea v-model="form.pacing_text" rows="2" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white resize-none"></textarea>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label class="block text-sm font-semibold text-slate-300 mb-2">Start Date</label>
                <input v-model="form.start_date" type="date" required class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
              </div>
              <div>
                <label class="block text-sm font-semibold text-slate-300 mb-2">Start Time</label>
                <input v-model="form.start_time" type="time" required class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
              </div>
              <div>
                <label class="block text-sm font-semibold text-slate-300 mb-2">Protagonist Role</label>
                <input v-model="form.protagonist_role" type="text" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
              </div>
            </div>

            <p v-if="advancedValidationError" class="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
              {{ advancedValidationError }}
            </p>
          </template>

          <div>
            <label class="block text-base font-semibold text-slate-300 mb-2">Adventure Cover Image</label>
            <div class="relative w-full h-28 rounded-xl border-2 border-dashed border-slate-700 bg-slate-950/50 flex items-center justify-center overflow-hidden">
              <img v-if="form.image_url" :src="'http://localhost:8000' + form.image_url" class="absolute inset-0 w-full h-full object-cover" />
              <span class="text-xs text-slate-400">Click to upload (max 512x512)</span>
              <input type="file" @change="handleImageUpload" accept="image/png, image/jpeg, image/webp" class="absolute inset-0 opacity-0 cursor-pointer" />
            </div>
          </div>

          <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-4">
            <div class="flex items-center justify-between cursor-pointer" @click="form.generate_npc_images = !form.generate_npc_images">
              <span class="text-sm font-bold text-white">Generate NPC Images</span>
              <input type="checkbox" v-model="form.generate_npc_images" />
            </div>
            <div class="flex items-center justify-between cursor-pointer" @click="form.generate_item_images = !form.generate_item_images">
              <span class="text-sm font-bold text-white">Generate Item Images</span>
              <input type="checkbox" v-model="form.generate_item_images" />
            </div>
            <div class="flex items-center justify-between cursor-pointer" @click="form.generate_scene_images = !form.generate_scene_images">
              <span class="text-sm font-bold text-white">Generate Scene Images</span>
              <input type="checkbox" v-model="form.generate_scene_images" />
            </div>
            <div class="flex items-center justify-between cursor-pointer" @click="form.automatic_cover_generation = !form.automatic_cover_generation">
              <span class="text-sm font-bold text-white">Automatic Cover Generation</span>
              <input type="checkbox" v-model="form.automatic_cover_generation" />
            </div>
          </div>

          <div v-if="errorMsg" class="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-lg">
            {{ errorMsg }}
          </div>
        </div>

        <div class="mt-8 flex justify-end gap-4 border-t border-slate-700 pt-6">
          <button @click="showCreateModal = false" class="px-6 py-2.5 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800">Cancel</button>
          <button @click="createAdventure" :disabled="isSubmitting || !form.title" class="px-8 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold rounded-xl disabled:opacity-50">
            {{ isSubmitting ? (creationStatus || 'Creating...') : 'Forge Adventure' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showImportModal" class="fixed inset-0 z-50 flex items-center justify-center pt-10">
      <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" @click="closeImportModal"></div>

      <div class="bg-slate-900 border border-slate-700 rounded-3xl w-full max-w-2xl relative z-10 shadow-2xl p-8 flex flex-col" @keydown.enter.prevent="executeImport(true)">
        <button @click="closeImportModal" class="absolute top-6 right-6 text-slate-500 hover:text-white transition-colors">X</button>

        <h2 class="text-3xl font-extrabold text-white mb-2">Import Adventure</h2>
        <p class="text-slate-400 mb-6 text-base">Set import options and create directly from the ADV manifest.</p>

        <div class="space-y-5">
          <div>
            <label class="block text-base font-semibold text-slate-300 mb-2">Adventure Title *</label>
            <input v-model="importState.titleOverride" type="text" maxlength="70" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-white" />
          </div>

          <div class="p-4 bg-slate-950 border border-slate-800 rounded-2xl space-y-4">
            <div class="flex items-center justify-between cursor-pointer" @click="importState.generate_npc_images = !importState.generate_npc_images">
              <span class="text-sm font-bold text-white">Generate NPC Images</span>
              <input type="checkbox" v-model="importState.generate_npc_images" />
            </div>
            <div class="flex items-center justify-between cursor-pointer" @click="importState.generate_item_images = !importState.generate_item_images">
              <span class="text-sm font-bold text-white">Generate Item Images</span>
              <input type="checkbox" v-model="importState.generate_item_images" />
            </div>
            <div class="flex items-center justify-between cursor-pointer" @click="importState.automatic_cover_generation = !importState.automatic_cover_generation">
              <span class="text-sm font-bold text-white">Automatic Cover Generation</span>
              <input type="checkbox" v-model="importState.automatic_cover_generation" />
            </div>
          </div>

          <div v-if="errorMsg" class="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-lg">
            {{ errorMsg }}
          </div>
        </div>

        <div class="mt-8 flex justify-end gap-4 border-t border-slate-700 pt-6">
          <button @click="closeImportModal" class="px-6 py-2.5 rounded-xl border border-slate-700 text-slate-300 hover:bg-slate-800">Cancel</button>
          <button @click="executeImport(true)" :disabled="isImporting || !importState.titleOverride" class="px-8 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold rounded-xl disabled:opacity-50">
            {{ isImporting ? 'Importing...' : 'Import & Create' }}
          </button>
        </div>
      </div>
    </div>

    <EditAdventureModal
      :open="showEditModal"
      :adventure-id="selectedAdventureId"
      @close="showEditModal = false"
      @updated="handleAdventureUpdate"
    />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(16, 185, 129, 0.3);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(16, 185, 129, 0.5);
}

.loading-placeholder-gradient {
  background: linear-gradient(120deg, rgba(15, 23, 42, 1) 0%, rgba(8, 47, 73, 0.9) 50%, rgba(15, 23, 42, 1) 100%);
}

.loading-placeholder-shimmer {
  background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.18), transparent);
  transform: translateX(-100%);
  animation: shimmer 1.8s infinite;
}

.loading-word {
  min-width: 170px;
}

.loading-dots::after {
  content: '...';
  display: inline-block;
  width: 1em;
  overflow: hidden;
  vertical-align: bottom;
  animation: dots 1.2s steps(4, end) infinite;
}

@keyframes shimmer {
  100% {
    transform: translateX(100%);
  }
}

@keyframes dots {
  0% {
    width: 0;
  }
  100% {
    width: 1em;
  }
}

@keyframes wordfade {
  0% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.45;
  }
}

.animate-wordfade {
  animation: wordfade 1.2s ease-in-out infinite;
}
</style>
