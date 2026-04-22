<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import type { AdventureImportPayload, CreateAdventurePayload } from '@/types'

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

const adventures = ref<Adventure[]>([])
const isLoading = ref(true)
const isLlmConfigured = ref(true)

const showCreateModal = ref(false)
const showImportModal = ref(false)
const isSubmitting = ref(false)
const isImporting = ref(false)
const errorMsg = ref('')
const advancedValidationError = ref('')
const creationStatus = ref('')
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

async function fetchAdventures() {
  try {
    const fetched = await api.listAdventures()
    // Add mock data for design consistency
    adventures.value = fetched.map(adv => ({
      ...adv,
      genre: adv.genre || ['Dark Fantasy', 'Cosmic Horror', 'Eldritch Mystery', 'Steampunk'][Math.floor(Math.random() * 4)],
    }))

    for (const adv of fetched) {
      if (!adv.is_ready) {
        const isAlreadyPending = pendingCreations.value.some((p) => p.adventureId === adv.adventure_id)
        if (!isAlreadyPending) {
          addPendingCreationCard(adv.adventure_id, adv.adventure_title)
          updatePendingCreationStatus(adv.adventure_id, adv.creation_status || 'Wird vorbereitet...')
          
          void pollAdventureStatus(adv.adventure_id, {
            navigateOnReady: false,
            onStatus: (status) => updatePendingCreationStatus(adv.adventure_id, status),
            onReady: async () => {
              removePendingCreationCard(adv.adventure_id)
              await fetchAdventures()
            },
            onFailure: (status) => updatePendingCreationStatus(adv.adventure_id, status, true),
          })
        }
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
    const llm = settings.llm_settings
    const keys = settings.keys || {}
    const smallProvider = llm?.small_model_provider || 'openai'
    const complexProvider = llm?.complex_model_provider || 'openai'
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
  if (file.name.toLowerCase().endsWith('.adz')) {
    await executeAdzImport(file)
    target.value = ''
    return
  }
  try {
    const parsed = JSON.parse(await file.text()) as AdventureImportPayload
    resetImportState()
    importState.value.manifest = parsed
    importState.value.titleOverride = parsed.title
    showImportModal.value = true
  } catch (error: any) {
    errorMsg.value = error?.message || 'Failed to parse .adv file.'
  } finally {
    target.value = ''
  }
}

async function executeAdzImport(file: File) {
  isImporting.value = true
  const tempId = `adz-import-${Date.now()}`
  addPendingImportCard(tempId, file.name)
  try {
    const result = await api.importAdz(file)
    removePendingImportCard(tempId)
    await fetchAdventures()
  } catch (error: any) {
    updatePendingImportStatus(tempId, error?.message || 'ADZ Import fehlgeschlagen', true)
  } finally {
    isImporting.value = false
  }
}

async function pollAdventureStatus(adventureId: string, options?: any) {
  return new Promise<void>((resolve) => {
    const pollInterval = setInterval(async () => {
      try {
        const data = await api.getAdventureStatus(adventureId)
        options?.onStatus?.(data.status || 'Constructing world...')
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
  window.addEventListener('click', handleGlobalClick)
})

onUnmounted(() => {
  window.removeEventListener('click', handleGlobalClick)
})
</script>

<template>
  <div class="flex min-h-screen bg-[#050b14] text-slate-200 font-ui overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-72 bg-aether-background/95 backdrop-blur-2xl border-r border-white/5 flex flex-col z-50">
      <!-- Sidebar Header -->
      <div class="p-8 pb-4">
        <div class="flex items-center gap-3 mb-8">
          <div class="w-10 h-10 bg-aether-primary/10 rounded-lg flex items-center justify-center border border-aether-primary/20 shadow-ambient-emerald">
            <img src="@/assets/svg/app-logo.svg" class="w-6 h-6 drop-shadow-[0_0_8px_rgba(78,222,163,0.4)]" alt="Logo" />
          </div>
          <div>
            <h1 class="text-xl font-black text-white font-display tracking-tight">TaleWeaver</h1>
            <span class="text-[8px] font-bold text-aether-primary/40 tracking-[0.3em] uppercase">v2.4.0-Aether</span>
          </div>
        </div>

        <div class="mb-8"></div>

        <!-- Navigation Links -->
        <nav class="space-y-1">
          <button class="w-full flex items-center gap-4 px-4 py-3 rounded-xl bg-aether-primary/10 text-aether-primary border-l-4 border-aether-primary transition-all">
            <i class="ra ra-scroll-unfurled text-lg"></i>
            <span class="text-sm font-bold tracking-wide">My Library</span>
          </button>
          <button class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all">
            <i class="ra ra-crystal-ball text-lg"></i>
            <span class="text-sm font-bold tracking-wide">Community Stories</span>
          </button>
          <button @click="triggerImportPicker" class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all">
            <i class="ra ra-quill-ink text-lg"></i>
            <span class="text-sm font-bold tracking-wide">Import .adv / .adz</span>
          </button>
          <button class="w-full flex items-center gap-4 px-4 py-3 rounded-xl text-slate-400 hover:bg-white/5 hover:text-white transition-all">
            <i class="ra ra-person text-lg"></i>
            <span class="text-sm font-bold tracking-wide">Profile</span>
          </button>
        </nav>
      </div>

      <div class="mt-auto p-8">
        <button @click="openCreateModal" class="btn-primary w-full flex items-center justify-center gap-3 !py-4 shadow-ambient-emerald/20">
          <i class="ra ra-plus"></i>
          Start New Adventure
        </button>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col relative overflow-hidden">
      <!-- Page Header -->
      <header class="h-16 flex items-center justify-between px-10 border-b border-white/5 bg-[#050b14]/40 backdrop-blur-md z-40">
        <div class="flex-1 max-w-xl">
          <div class="relative group">
            <i class="ra ra-search absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-aether-primary transition-colors"></i>
            <input 
              type="text" 
              placeholder="Search your library..." 
              class="w-full bg-aether-surface/40 border border-white/5 rounded-xl py-2 px-12 text-sm focus:outline-none focus:border-aether-primary/40 transition-all"
            />
          </div>
        </div>

        <div class="flex items-center gap-4">
          <button class="text-slate-400 hover:text-white transition-colors">
            <i class="ra ra-bell"></i>
          </button>
          <button @click="router.push('/admin')" class="text-slate-400 hover:text-white transition-colors" title="Administration">
            <i class="ra ra-cog"></i>
          </button>
        </div>
      </header>

      <!-- Scrollable Content -->
      <div class="flex-1 overflow-y-auto p-10">
        <!-- Title Section -->
        <div class="flex items-end justify-between mb-12">
          <div>
            <h2 class="text-5xl font-black text-white font-display tracking-tight mb-3">My Library</h2>
            <p class="text-slate-500 font-narrative italic text-lg opacity-80">The chronicles of your journeys through the aether.</p>
          </div>
          <div class="flex bg-white/5 p-1 rounded-xl border border-white/5">
            <button class="px-4 py-1.5 rounded-lg bg-aether-primary/20 text-aether-primary text-xs font-bold transition-all">Grid</button>
            <button class="px-4 py-1.5 rounded-lg text-slate-500 text-xs font-bold hover:text-white transition-all">List</button>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading && adventures.length === 0" class="flex flex-col items-center justify-center py-32 gap-6">
          <div class="w-16 h-16 border-4 border-aether-primary/10 border-t-aether-primary rounded-full animate-spin"></div>
          <p class="text-aether-primary font-bold uppercase tracking-[0.3em] text-[10px]">Accessing Archives...</p>
        </div>

        <!-- Grid -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-8">
          <!-- Start New Card -->
          <button @click="openCreateModal" class="group flex flex-col items-center justify-center border-2 border-dashed border-white/10 rounded-xl aspect-[3/2] hover:border-aether-primary/30 transition-all bg-transparent">
            <div class="w-12 h-12 rounded-full bg-aether-primary/10 flex items-center justify-center mb-4 group-hover:scale-110 group-hover:bg-aether-primary/20 transition-all">
              <i class="ra ra-plus text-xl text-aether-primary"></i>
            </div>
            <h3 class="text-xl font-bold text-white mb-2">Start New</h3>
            <p class="text-slate-500 text-sm max-w-[140px] text-center opacity-60">Begin your legend.</p>
          </button>

          <!-- Adventure Cards -->
          <div 
            v-for="adv in adventures" 
            :key="adv.adventure_id"
            class="adventure-card flex flex-col group cursor-pointer relative rounded-xl"
            @click="playAdventure(adv.game_id)"
          >
            <!-- Image Area -->
            <div class="relative aspect-[3/2] overflow-hidden rounded-xl mb-6 bg-aether-surface/30 border border-white/5 flex items-center justify-center group-hover:bg-aether-surface/50 transition-all duration-500">
              <!-- Menu Button -->
              <button 
                @click.stop="toggleMenu($event, adv.adventure_id)" 
                class="absolute top-3 right-3 z-30 w-8 h-8 flex items-center justify-center rounded-full bg-black/40 backdrop-blur-md border border-white/10 text-white opacity-0 group-hover:opacity-100 transition-all hover:bg-black/60"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                </svg>
              </button>

              <!-- Dropdown Menu -->
              <div 
                v-if="activeMenuId === adv.adventure_id"
                class="absolute top-12 right-3 z-40 w-44 bg-slate-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-fade-in"
              >
                <button 
                  @click.stop="editAdventure(adv.adventure_id)"
                  class="w-full px-4 py-3 text-left text-[11px] font-black uppercase tracking-widest text-slate-300 hover:bg-aether-primary/20 hover:text-aether-primary transition-colors flex items-center gap-3 border-b border-white/5"
                >
                  <i class="ra ra-wrench text-sm"></i>
                  Edit Blueprint
                </button>
                <button 
                  @click.stop="playAdventure(adv.game_id)"
                  class="w-full px-4 py-3 text-left text-[11px] font-black uppercase tracking-widest text-slate-300 hover:bg-emerald-500/20 hover:text-emerald-400 transition-colors flex items-center gap-3 border-b border-white/5"
                >
                  <i class="ra ra-player text-sm"></i>
                  Play Chronicle
                </button>
                <button 
                  @click.stop="confirmDelete(adv)"
                  class="w-full px-4 py-3 text-left text-[11px] font-black uppercase tracking-widest text-red-400 hover:bg-red-500/20 transition-colors flex items-center gap-3"
                >
                  <i class="ra ra-burning-embers text-sm"></i>
                  Delete Adventure
                </button>
              </div>

              <img 
                v-if="adv.image_url"
                :src="adv.image_url" 
                class="absolute inset-0 w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                alt="Cover"
              />

              <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent"></div>
              
              <!-- Category Tag -->
              <div class="absolute top-4 left-4">
                <span class="px-3 py-1 bg-aether-secondary/20 backdrop-blur-md border border-white/10 rounded-full text-[9px] font-black uppercase tracking-widest text-aether-secondary">
                  {{ adv.genre || 'Epic Fantasy' }}
                </span>
              </div>
            </div>

            <!-- Info Area -->
            <div class="px-2">
              <h3 class="text-2xl font-black text-white mb-2 font-display line-clamp-1 group-hover:text-aether-primary transition-colors">
                {{ adv.adventure_title }}
              </h3>
              <p class="text-slate-400 text-sm font-narrative mb-6 line-clamp-2 opacity-70">
                {{ adv.description }}
              </p>

              <!-- Info Section -->
              <div class="space-y-3">
                <div class="flex flex-col gap-0.5">
                  <span class="text-[8px] font-black text-slate-500 uppercase tracking-[0.2em]">Location</span>
                  <span class="text-[10px] font-bold text-white truncate">{{ adv.current_scene_name || 'The Unknown' }}</span>
                </div>
                
                <div v-if="adv.quest_count > 0" class="space-y-2">
                  <div class="flex justify-between items-center text-[10px] font-black uppercase tracking-widest">
                    <span class="text-slate-500">Progress</span>
                    <span class="text-aether-primary">
                      {{ adv.completed_quest_count || 0 }} / {{ adv.quest_count }} Quests 
                      ({{ adv.progress }}%)
                    </span>
                  </div>
                  <div class="h-1 bg-white/5 rounded-full overflow-hidden">
                    <div 
                      class="h-full bg-gradient-to-r from-aether-primary/40 to-aether-primary shadow-ambient-emerald transition-all duration-1000"
                      :style="{ width: `${adv.progress}%` }"
                    ></div>
                  </div>
                </div>
                <div v-else class="text-[10px] font-black uppercase tracking-widest text-slate-600 flex items-center gap-2">
                  <i class="ra ra-scroll text-[8px] opacity-40"></i>
                  No Quests active
                </div>
              </div>
            </div>
          </div>
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
      <div v-if="showDeleteConfirm" class="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-black/80 backdrop-blur-md">
        <div class="w-full max-w-md bg-[#0a101a] border border-white/10 rounded-2xl p-8 shadow-2xl animate-fade-in">
          <div class="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-6 border border-red-500/20 mx-auto">
            <i class="ra ra-burning-embers text-3xl text-red-500"></i>
          </div>
          <h2 class="text-2xl font-black text-white text-center mb-2">Abandon Legend?</h2>
          <p class="text-slate-400 text-center text-sm mb-8">
            Are you sure you want to delete <span class="text-white font-bold">"{{ adventureToDelete?.adventure_title }}"</span>? This action will permanently erase this chronicle and all its progress.
          </p>
          <div class="flex gap-4">
            <button 
              @click="showDeleteConfirm = false" 
              class="flex-1 px-6 py-3 rounded-xl border border-white/10 text-xs font-black uppercase tracking-widest text-slate-400 hover:bg-white/5 transition-all"
            >
              Cancel
            </button>
            <button 
              @click="executeDelete" 
              class="flex-1 px-6 py-3 rounded-xl bg-red-500 text-white text-xs font-black uppercase tracking-widest hover:bg-red-600 shadow-lg shadow-red-500/20 transition-all"
            >
              Delete Forever
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.animate-shimmer {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0) 0%,
    rgba(255, 255, 255, 0.05) 50%,
    rgba(255, 255, 255, 0) 0%
  );
  background-size: 200% 100%;
  animation: shimmer 2s infinite linear;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.adventure-card {
  @apply transition-all duration-500;
}

.adventure-card:hover {
  transform: translateY(-8px);
}
</style>
