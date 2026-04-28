<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'
import type { AdventureTemplateSummary, GameSession } from '@/types'
import PortalSidebar from '@/components/portal/PortalSidebar.vue'
import PendingAdventureCard from '@/components/portal/PendingAdventureCard.vue'
import DeleteAdventureModal from '@/components/portal/DeleteAdventureModal.vue'
import PortalLibraryToolbar from '@/components/portal/PortalLibraryToolbar.vue'
import UserProfileContent from '@/components/portal/UserProfileContent.vue'
import AdventureTemplateCard from '@/components/portal/AdventureTemplateCard.vue'
import GameSessionCard from '@/components/portal/GameSessionCard.vue'
import PortalCreateAdventureCard from '@/components/portal/PortalCreateAdventureCard.vue'
import ImportExamplesCard from '@/components/portal/ImportExamplesCard.vue'
import ImportExamplesModal from '@/components/portal/ImportExamplesModal.vue'

const router = useRouter()
const route = useRoute()

interface PendingAdventureCard {
  adventureId: string
  title: string
  status: string
  hasError: boolean
}

function prettifyStatus(status: string): string {
  if (!status) return 'Wird vorbereitet...'
  const lower = status.toLowerCase()
  if (lower.includes('generating world structure')) return 'Weltstruktur wird erschaffen...'
  if (lower.includes('forging scenes')) return 'Szenen werden geschmiedet...'
  if (lower.includes('weaving entities')) return 'Figuren & Objekte entstehen...'
  if (lower.includes('generating visual')) return 'Bilder werden generiert...'
  if (lower.includes('finalizing')) return 'Feinschliff wird vorgenommen...'
  if (lower.includes('cancelled')) return 'Abgebrochen'
  
  const spaced = status
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/_/g, ' ')
    .trim()
  return spaced || status
}

function isFailureStatus(status: string): boolean {
  const value = (status || '').toLowerCase()
  return value.includes('failed') || value.includes('error') || value.includes('cancelled')
}

function formatToneLabel(value?: string | null): string {
  if (!value) return ''
  const normalized = value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!normalized) return ''
  return normalized.replace(/\b\w/g, (ch) => ch.toUpperCase())
}

const templates = ref<AdventureTemplateSummary[]>([])
const sessions = ref<GameSession[]>([])
const activeSection = ref<'templates' | 'sessions' | 'profile'>('templates')
const isLoading = ref(true)

const isImporting = ref(false)
const errorMsg = ref('')
const showDeleteConfirm = ref(false)
const templateToDelete = ref<{ id: string; title: string } | null>(null)
const showImportConfirm = ref(false)
const isSeeding = ref(false)

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

const pendingCards = computed(() => [
  ...pendingCreations.value.map((entry) => ({ ...entry, kind: 'creation' as const })),
  ...pendingImports.value.map((entry) => ({ ...entry, kind: 'import' as const })),
])

const visibleTemplates = computed(() => {
  const pendingIds = new Set([
    ...pendingImports.value.map((entry) => entry.adventureId).filter(Boolean),
    ...pendingCreations.value.map((entry) => entry.adventureId).filter(Boolean),
  ])
  return templates.value.filter((entry) => !pendingIds.has(entry.template_id))
})

const isAdmin = computed(() => authState.user?.role === 'admin')

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
      templates.value = templates.value.filter((a) => a.template_id !== adventureId)
      sessions.value = sessions.value.filter((s) => (s.template_id || s.adventure_id) !== adventureId)
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

async function cancelAdventure(adventureId: string) {
  try {
    await api.cancelAdventure(adventureId)
    updatePendingCreationStatus(adventureId, 'Cancelled', true)
  } catch (error) {
    console.error('Error cancelling adventure:', error)
  }
}

async function fetchPortalData() {
  try {
    const [fetchedTemplates, fetchedSessions] = await Promise.all([
      api.listAdventureTemplates(),
      api.listSessions(),
    ])

    templates.value = fetchedTemplates.map((entry) => ({
      ...entry,
      selected_tone: formatToneLabel(entry.selected_tone),
    }))
    sessions.value = fetchedSessions

    for (const template of fetchedTemplates) {
      if (!template.is_ready) {
        const isAlreadyPending = pendingCreations.value.some((p) => p.adventureId === template.template_id)
        if (!isAlreadyPending) {
          addPendingCreationCard(template.template_id, template.title)
          updatePendingCreationStatus(
            template.template_id,
            template.creation_error || template.creation_status || 'Wird vorbereitet...',
            Boolean(template.creation_error) || isFailureStatus(template.creation_status || ''),
          )

          void pollAdventureStatus(template.template_id, {
            onStatus: (status: string) => updatePendingCreationStatus(template.template_id, status),
            onReady: async () => {
              removePendingCreationCard(template.template_id)
              await fetchPortalData()
            },
            onFailure: (status: string) => updatePendingCreationStatus(template.template_id, status, true),
          })
        }
      } else {
        removePendingCreationCard(template.template_id)
      }
    }
  } catch (error) {
    console.error('API Error:', error)
  } finally {
    isLoading.value = false
  }
}

function playSession(gameId: string) {
  router.push({ name: 'game', params: { id: gameId } })
}

async function startSession(templateId: string) {
  try {
    const result = await api.startSessionForTemplate(templateId)
    await fetchPortalData()
    playSession(result.game_id)
  } catch (error: any) {
    errorMsg.value = error?.message || 'Session konnte nicht gestartet werden.'
  }
}

async function pauseSession(templateId: string) {
  try {
    await api.pauseSession(templateId)
    await fetchPortalData()
  } catch (error: any) {
    errorMsg.value = error?.message || 'Session konnte nicht pausiert werden.'
  }
}

async function resumeHeartbeat(templateId: string) {
  try {
    await api.resumeSession(templateId)
    await fetchPortalData()
  } catch (error: any) {
    errorMsg.value = error?.message || 'Session konnte nicht fortgesetzt werden.'
  }
}

async function resetSession(templateId: string) {
  try {
    await api.resetSession(templateId)
    await fetchPortalData()
  } catch (error: any) {
    errorMsg.value = error?.message || 'Session konnte nicht zurueckgesetzt werden.'
  }
}

async function deleteSession(gameId: string) {
  try {
    await api.deleteSession(gameId)
    sessions.value = sessions.value.filter((s) => s.game_id !== gameId)
    await fetchPortalData()
  } catch (error: any) {
    errorMsg.value = error?.message || 'Session konnte nicht geloescht werden.'
  }
}

function editAdventure(templateId: string) {
  router.push({ name: 'adventure-editor', params: { adventureId: templateId } })
}

function confirmDeleteTemplate(templateId: string, title: string) {
  templateToDelete.value = { id: templateId, title }
  showDeleteConfirm.value = true
}

async function executeDeleteTemplate() {
  if (!templateToDelete.value) return

  try {
    await api.deleteAdventure(templateToDelete.value.id)
    templates.value = templates.value.filter((entry) => entry.template_id !== templateToDelete.value?.id)
    sessions.value = sessions.value.filter((entry) => (entry.template_id || entry.adventure_id) !== templateToDelete.value?.id)
    showDeleteConfirm.value = false
    templateToDelete.value = null
  } catch (error) {
    console.error('Error deleting template:', error)
  }
}

function openCreateModal() {
  router.push({ name: 'adventure-create' })
}

async function executeImportExamples() {
  showImportConfirm.value = false
  isSeeding.value = true
  try {
    await api.importExamples()
    await fetchPortalData()
  } catch (error: any) {
    errorMsg.value = error?.message || 'Import der Beispiele fehlgeschlagen.'
  } finally {
    isSeeding.value = false
  }
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
    errorMsg.value = 'Nur .adv und .adz werden als Importformat unterstuetzt.'
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
    await fetchPortalData()
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
    await fetchPortalData()
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
  try {
    await downloadAdventureExport(api.exportAdzUrl(adventureId), makeSafeFilename(title, 'adz'))
  } catch (error: any) {
    errorMsg.value = error?.message || 'ADZ Export fehlgeschlagen'
  }
}

async function exportAdventureAdv(adventureId: string, title: string) {
  try {
    await downloadAdventureExport(api.exportAdvUrl(adventureId), makeSafeFilename(title, 'adv'))
  } catch (error: any) {
    errorMsg.value = error?.message || 'ADV Export fehlgeschlagen'
  }
}

interface PollAdventureOptions {
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
  void fetchPortalData()

  loadingWordTimer = window.setInterval(() => {
    loadingWordIndex.value = (loadingWordIndex.value + 1) % loadingWords.length
  }, 1200)

  const newId = typeof route.query.new_id === 'string' ? route.query.new_id : ''
  const newTitle = typeof route.query.new_title === 'string' ? route.query.new_title : 'New Adventure'
  
  if (route.query.section === 'profile') {
    activeSection.value = 'profile'
  }

  if (newId) {
    addPendingCreationCard(newId, newTitle)
    updatePendingCreationStatus(newId, 'Starting generation...')
    void pollAdventureStatus(newId, {
      onStatus: (status: string) => updatePendingCreationStatus(newId, status || 'Wird vorbereitet...'),
      onReady: async () => {
        removePendingCreationCard(newId)
        await fetchPortalData()
      },
      onFailure: (status: string) => updatePendingCreationStatus(newId, status || 'Generierung fehlgeschlagen', true),
    })
    router.replace({ name: 'portal', query: {} })
  }
})

onUnmounted(() => {
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
      :active-section="activeSection"
      @section="activeSection = $event"
      @admin="router.push('/admin')"
    />

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col relative overflow-hidden">
      <!-- Scrollable Content -->
      <div class="flex-1 overflow-y-auto" :class="activeSection !== 'profile' ? 'p-10' : ''">
        <PortalLibraryToolbar
          v-if="activeSection !== 'profile'"
          :active-section="activeSection"
          @change-section="activeSection = $event"
          @create="openCreateModal"
          @import="triggerImportPicker"
        />

        <!-- Loading State -->
        <div v-if="isLoading && templates.length === 0 && sessions.length === 0 && pendingCards.length === 0" class="flex flex-col items-center justify-center py-32 gap-6">
          <div class="w-16 h-16 border-4 border-aether-primary/10 border-t-aether-primary rounded-full animate-spin"></div>
          <p class="text-aether-primary font-bold uppercase tracking-[0.3em] text-[10px]">Accessing Archives...</p>
        </div>

        <div v-else>
          <div v-if="activeSection === 'templates'" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-8">
            <PortalCreateAdventureCard @click="openCreateModal" />
            
            <ImportExamplesCard 
              v-if="templates.length === 0 && !isSeeding" 
              @import="showImportConfirm = true" 
            />

            <!-- Loading indicator for seeding -->
            <div v-if="isSeeding" class="flex flex-col items-center justify-center border-2 border-dashed border-white/10 rounded-xl aspect-[3/2] bg-white/5 gap-3">
              <div class="w-8 h-8 border-2 border-aether-primary/10 border-t-aether-primary rounded-full animate-spin"></div>
              <span class="text-[10px] text-aether-primary uppercase tracking-widest font-bold">Importing Tales...</span>
            </div>

            <PendingAdventureCard
              v-for="pending in pendingCards"
              :key="`pending-${pending.adventureId}`"
              :pending="pending"
              :loading-word-index="loadingWordIndex"
              @remove-failed="removeFailedPendingCard"
              @cancel="cancelAdventure"
            />

            <AdventureTemplateCard
              v-for="entry in visibleTemplates"
              :key="entry.template_id"
              :template="entry"
              @start-session="startSession"
              @edit="editAdventure"
              @export-adz="exportAdventureAdz"
              @export-adv="exportAdventureAdv"
              @delete="confirmDeleteTemplate"
            />
          </div>

          <div v-else-if="activeSection === 'sessions'" class="space-y-6">
            <div v-if="sessions.length === 0" class="rounded-xl border border-white/10 bg-aether-surface/20 p-6 text-slate-400">
              No active sessions yet. Start one from the Adventures area.
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-8">
              <GameSessionCard
                v-for="entry in sessions"
                :key="entry.game_id"
                :session="entry"
                @resume="playSession"
                @pause="pauseSession"
                @resume-heartbeat="resumeHeartbeat"
                @reset="resetSession"
                @delete="deleteSession"
              />
            </div>
          </div>

          <div v-else-if="activeSection === 'profile'">
            <UserProfileContent />
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
      <DeleteAdventureModal
        v-if="showDeleteConfirm"
        :adventure-title="templateToDelete?.title || ''"
        @close="showDeleteConfirm = false"
        @confirm="executeDeleteTemplate"
      />
      
      <ImportExamplesModal
        v-if="showImportConfirm"
        @close="showImportConfirm = false"
        @confirm="executeImportExamples"
      />
    </Teleport>

  </div>
</template>
