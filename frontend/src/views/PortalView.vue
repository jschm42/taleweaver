<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'
import PortalSidebar from '@/components/portal/PortalSidebar.vue'
import PortalHeader from '@/components/portal/PortalHeader.vue'
import PendingAdventureCard from '@/components/portal/PendingAdventureCard.vue'
import AdventureCard from '@/components/portal/AdventureCard.vue'
import DeleteAdventureModal from '@/components/portal/DeleteAdventureModal.vue'
import PortalLibraryToolbar from '@/components/portal/PortalLibraryToolbar.vue'
import PortalCreateAdventureCard from '@/components/portal/PortalCreateAdventureCard.vue'

const router = useRouter()
const route = useRoute()

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
  is_ready: boolean
  creation_status?: string | null
  creation_error?: string | null
  genre?: string // Mocked for design
  progress?: number // Mocked for design
  description?: string // Mocked for design
  quest_count?: number
  completed_quest_count?: number
}

interface PendingAdventureCard {
  adventureId: string
  title: string
  status: string
  hasError: boolean
}

function prettifyStatus(status: string): string {
  if (!status) return 'Wird vorbereitet...'
  const spaced = status
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .trim()
  return spaced || status
}

function isFailureStatus(status: string): boolean {
  const value = (status || '').toLowerCase()
  return value.includes('failed') || value.includes('error')
}

const adventures = ref<Adventure[]>([])
const isLoading = ref(true)
const isLlmConfigured = ref(true)

const isImporting = ref(false)
const errorMsg = ref('')
const activeMenuId = ref<string | null>(null)
const showDeleteConfirm = ref(false)
const adventureToDelete = ref<Adventure | null>(null)

const handleGlobalClick = () => {
  activeMenuId.value = null
}

function confirmDelete(adventure: Adventure) {
  activeMenuId.value = null
  adventureToDelete.value = adventure
  showDeleteConfirm.value = true
}

async function executeDelete() {
  if (!adventureToDelete.value) return
  
  try {
    await api.deleteAdventure(adventureToDelete.value.adventure_id)
    adventures.value = adventures.value.filter((a) => a.adventure_id !== adventureToDelete.value?.adventure_id)
    showDeleteConfirm.value = false
    adventureToDelete.value = null
  } catch (error) {
    console.error('Error deleting adventure:', error)
  }
}

function toggleMenu(e: Event, adventureId: string) {
  e.stopPropagation()
  if (activeMenuId.value === adventureId) {
    activeMenuId.value = null
  } else {
    activeMenuId.value = adventureId
  }
}

function editAdventure(adventureId: string) {
  activeMenuId.value = null
  router.push({ name: 'adventure-editor', params: { adventureId } })
}

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

const pendingCards = computed(() => [
  ...pendingCreations.value.map((entry) => ({ ...entry, kind: 'creation' as const })),
  ...pendingImports.value.map((entry) => ({ ...entry, kind: 'import' as const })),
])

const isAdmin = computed(() => authState.user?.role === 'admin')

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
      status: 'Starting generation...',
      hasError: false,
    },
  ]
}

function updatePendingImportStatus(adventureId: string, status: string, hasError = false) {
  pendingImports.value = pendingImports.value.map((entry) =>
    entry.adventureId === adventureId
      ? {
          ...entry,
          status: prettifyStatus(status),
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
          status: prettifyStatus(status),
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

async function removeFailedPendingCard(adventureId: string, kind: 'creation' | 'import') {
  const isTemporaryImport = kind === 'import' && adventureId.startsWith('adz-import-')

  try {
    if (!isTemporaryImport) {
      await api.deleteAdventure(adventureId)
      adventures.value = adventures.value.filter((a) => a.adventure_id !== adventureId)
    }
  } catch (error) {
    console.error('Error deleting failed pending adventure:', error)
    return
  }

  if (kind === 'import') {
    removePendingImportCard(adventureId)
    return
  }
  removePendingCreationCard(adventureId)
}

async function fetchAdventures() {
  try {
    const fetched = (await api.listAdventures()) as Adventure[]
    // Add mock data for design consistency
    adventures.value = fetched.map((adv) => ({
      ...adv,
      genre: adv.genre || ['Dark Fantasy', 'Cosmic Horror', 'Eldritch Mystery', 'Steampunk'][Math.floor(Math.random() * 4)],
    }))

    for (const adv of fetched) {
      if (!adv.is_ready) {
        const isAlreadyPending = pendingCreations.value.some((p) => p.adventureId === adv.adventure_id)
        if (!isAlreadyPending) {
          addPendingCreationCard(adv.adventure_id, adv.adventure_title)
          updatePendingCreationStatus(
            adv.adventure_id,
            adv.creation_error || adv.creation_status || 'Wird vorbereitet...',
            Boolean(adv.creation_error) || isFailureStatus(adv.creation_status || ''),
          )
          
          void pollAdventureStatus(adv.adventure_id, {
            navigateOnReady: false,
            onStatus: (status: string) => updatePendingCreationStatus(adv.adventure_id, status),
            onReady: async () => {
              removePendingCreationCard(adv.adventure_id)
              await fetchAdventures()
            },
            onFailure: (status: string) => updatePendingCreationStatus(adv.adventure_id, status, true),
          })
        }
      } else {
        removePendingCreationCard(adv.adventure_id)
      }
    }
  } catch (error) {
    console.error('API Error:', error)
  } finally {
    isLoading.value = false
  }
}

async function fetchSettings() {
  try {
    const settings = await api.getSettings()
    const llm = (settings.llm_settings || {}) as Record<string, string | undefined>
    const keys = (settings.keys || {}) as Record<string, string | undefined>
    const smallProvider = llm.small_model_provider || 'openai'
    const complexProvider = llm.complex_model_provider || 'openai'
    const isSmallOk = smallProvider === 'ollama' || !!keys[smallProvider]
    const isComplexOk = complexProvider === 'ollama' || !!keys[complexProvider]
    isLlmConfigured.value = isSmallOk && isComplexOk
  } catch (error) {
    console.error('Settings API Error:', error)
  }
}

function playAdventure(gameId: string) {
  router.push({ name: 'game', params: { id: gameId } })
}

function openCreateModal() {
  router.push({ name: 'adventure-create' })
}

function triggerImportPicker() {
  importInput.value?.click()
}

async function onImportFileSelected(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return
  const file = target.files[0]

  const lower = file.name.toLowerCase()
  if (!lower.endsWith('.adz') && !lower.endsWith('.adv')) {
    errorMsg.value = 'Nur .adv und .adz werden als Importformat unterstützt.'
    target.value = ''
    return
  }

  try {
    if (lower.endsWith('.adz')) {
      await executeAdzImport(file)
    } else {
      await executeAdvImport(file)
    }
  } catch (error: any) {
    errorMsg.value = error?.message || 'Import fehlgeschlagen.'
  } finally {
    target.value = ''
  }
}

async function executeAdvImport(file: File) {
  isImporting.value = true
  const tempId = `adv-import-${Date.now()}`
  addPendingImportCard(tempId, file.name)
  try {
    await api.importAdv(file)
    removePendingImportCard(tempId)
    await fetchAdventures()
  } catch (error: any) {
    updatePendingImportStatus(tempId, error?.message || 'ADV Import fehlgeschlagen', true)
  } finally {
    isImporting.value = false
  }
}

async function executeAdzImport(file: File) {
  isImporting.value = true
  const tempId = `adz-import-${Date.now()}`
  addPendingImportCard(tempId, file.name)
  try {
    await api.importAdz(file)
    removePendingImportCard(tempId)
    await fetchAdventures()
  } catch (error: any) {
    updatePendingImportStatus(tempId, error?.message || 'ADZ Import fehlgeschlagen', true)
  } finally {
    isImporting.value = false
  }
}

async function downloadAdventureExport(url: string, filename: string) {
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error('Export fehlgeschlagen')
  }
  const blob = await res.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  a.click()
  URL.revokeObjectURL(blobUrl)
}

function makeSafeFilename(title: string, ext: string) {
  const safe = (title || 'adventure').replace(/[^a-zA-Z0-9 _-]/g, '').trim().replace(/\s+/g, '_')
  return `${safe || 'adventure'}.${ext}`
}

async function exportAdventureAdz(adventureId: string, title: string) {
  activeMenuId.value = null
  try {
    await downloadAdventureExport(api.exportAdzUrl(adventureId), makeSafeFilename(title, 'adz'))
  } catch (error: any) {
    errorMsg.value = error?.message || 'ADZ Export fehlgeschlagen'
  }
}

async function exportAdventureAdv(adventureId: string, title: string) {
  activeMenuId.value = null
  try {
    await downloadAdventureExport(api.exportAdvUrl(adventureId), makeSafeFilename(title, 'adv'))
  } catch (error: any) {
    errorMsg.value = error?.message || 'ADV Export fehlgeschlagen'
  }
}

interface PollAdventureOptions {
  navigateOnReady?: boolean
  onStatus?: (status: string) => void
  onReady?: () => void | Promise<void>
  onFailure?: (status: string) => void
}

async function pollAdventureStatus(adventureId: string, options?: PollAdventureOptions) {
  return new Promise<void>((resolve) => {
    const pollInterval = setInterval(async () => {
      try {
        const data = await api.getAdventureStatus(adventureId)
        const statusText = data.status || 'Constructing world...'
        options?.onStatus?.(statusText)

        if (isFailureStatus(statusText) || data.error) {
          clearInterval(pollInterval)
          const detail = data.error || statusText || 'Generation failed.'
          options?.onFailure?.(detail)
          resolve()
          return
        }

        if (data.is_ready) {
          clearInterval(pollInterval)
          options?.onReady?.()
          resolve()
        }
      } catch {
        clearInterval(pollInterval)
        resolve()
      }
    }, 1500)
  })
}

onMounted(() => {
  resetCreateForm()
  void fetchSettings()
  fetchAdventures()

  loadingWordTimer = window.setInterval(() => {
    loadingWordIndex.value = (loadingWordIndex.value + 1) % loadingWords.length
  }, 1200)

  const newId = typeof route.query.new_id === 'string' ? route.query.new_id : ''
  const newTitle = typeof route.query.new_title === 'string' ? route.query.new_title : 'New Adventure'
  if (newId) {
    addPendingCreationCard(newId, newTitle)
    updatePendingCreationStatus(newId, 'Starting generation...')
    void pollAdventureStatus(newId, {
      navigateOnReady: false,
      onStatus: (status: string) => updatePendingCreationStatus(newId, status || 'Wird vorbereitet...'),
      onReady: async () => {
        removePendingCreationCard(newId)
        await fetchAdventures()
      },
      onFailure: (status: string) => updatePendingCreationStatus(newId, status || 'Generierung fehlgeschlagen', true),
    })
    router.replace({ name: 'portal', query: {} })
  }

  window.addEventListener('click', handleGlobalClick)
})

onUnmounted(() => {
  window.removeEventListener('click', handleGlobalClick)
  if (loadingWordTimer !== null) {
    clearInterval(loadingWordTimer)
    loadingWordTimer = null
  }
})
</script>

<template>
  <div class="flex h-full min-h-0 bg-[#050b14] text-slate-200 font-ui overflow-hidden">
    <PortalSidebar
      :is-admin="isAdmin"
      @import="triggerImportPicker"
      @create="openCreateModal"
      @admin="router.push('/admin')"
    />

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col relative overflow-hidden">
      <PortalHeader />

      <!-- Scrollable Content -->
      <div class="flex-1 overflow-y-auto p-10">
        <PortalLibraryToolbar />

        <!-- Loading State -->
        <div v-if="isLoading && adventures.length === 0 && pendingCards.length === 0" class="flex flex-col items-center justify-center py-32 gap-6">
          <div class="w-16 h-16 border-4 border-aether-primary/10 border-t-aether-primary rounded-full animate-spin"></div>
          <p class="text-aether-primary font-bold uppercase tracking-[0.3em] text-[10px]">Accessing Archives...</p>
        </div>

        <!-- Grid -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-8">
          <PortalCreateAdventureCard @create="openCreateModal" />

          <PendingAdventureCard
            v-for="pending in pendingCards"
            :key="`pending-${pending.adventureId}`"
            :pending="pending"
            :loading-word-index="loadingWordIndex"
            @remove-failed="removeFailedPendingCard"
          />

          <!-- Adventure Cards -->
          <AdventureCard
            v-for="adv in visibleAdventures"
            :key="adv.adventure_id"
            :adv="adv"
            :active-menu-id="activeMenuId"
            @play="playAdventure"
            @toggle-menu="toggleMenu"
            @edit="editAdventure"
            @export-adz="exportAdventureAdz"
            @export-adv="exportAdventureAdv"
            @delete="confirmDelete"
          />
        </div>
      </div>
    </main>

    <!-- Modals & Pickers -->
    <input
      type="file"
      ref="importInput"
      style="display: none"
      accept=".adv,.adz"
      @change="onImportFileSelected"
    />

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <DeleteAdventureModal
        v-if="showDeleteConfirm"
        :adventure-title="adventureToDelete?.adventure_title || ''"
        @close="showDeleteConfirm = false"
        @confirm="executeDelete"
      />
    </Teleport>
  </div>
</template>
