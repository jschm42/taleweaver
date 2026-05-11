<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/composables/useApi'
import { authState } from '@/store/auth'
import type { AdventureTemplateSummary, GameSession } from '@/types'
import PortalSidebar from '@/components/portal/PortalSidebar.vue'
import LlmWarningBanner from '@/components/portal/LlmWarningBanner.vue'
import PortalLibraryToolbar from '@/components/portal/PortalLibraryToolbar.vue'
import AdventureLibraryGrid from '@/components/portal/AdventureLibraryGrid.vue'
import GameSessionsGrid from '@/components/portal/GameSessionsGrid.vue'
import UserProfileContent from '@/components/portal/UserProfileContent.vue'
import PortalFooter from '@/components/portal/PortalFooter.vue'

import DeleteAdventureModal from '@/components/portal/DeleteAdventureModal.vue'
import ImportExamplesModal from '@/components/portal/ImportExamplesModal.vue'
import ImportWarningModal from '@/components/portal/ImportWarningModal.vue'
import DeleteSessionModal from '@/components/portal/DeleteSessionModal.vue'
import AboutModal from '@/components/portal/AboutModal.vue'
import { configState } from '@/store/config'

const router = useRouter()
const route = useRoute()

interface PendingAdventureState {
  adventureId: string
  title: string
  status: string
  hasError: boolean
}

function prettifyStatus(status: string): string {
  if (!status) return 'Preparing...'
  const lower = status.toLowerCase()
  if (lower.includes('generating world structure')) return 'Creating world structure...'
  if (lower.includes('forging scenes')) return 'Forging scenes...'
  if (lower.includes('weaving entities')) return 'Weaving entities...'
  if (lower.includes('generating visual')) return 'Generating visuals...'
  if (lower.includes('finalizing')) return 'Finalizing...'
  if (lower.includes('cancelled')) return 'Cancelled'
  
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

function formatToneLabel(value?: any): string {
  if (!value) return ''
  let text = ''
  if (typeof value === 'object') {
    text = value.name || value.id || ''
  } else {
    text = String(value)
    if (text.startsWith('{')) {
      try {
        const obj = JSON.parse(text)
        text = obj.name || obj.id || text
      } catch (e) {
        // Not JSON, continue
      }
    }
  }
  const normalized = text
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!normalized) return ''
  return normalized.replace(/\b\w/g, (ch: string) => ch.toUpperCase())
}


const templates = ref<AdventureTemplateSummary[]>([])
const sessions = ref<GameSession[]>([])
const activeSection = ref<'templates' | 'sessions' | 'profile'>('sessions')
const isLoading = ref(true)

const showDeleteConfirm = ref(false)
const templateToDelete = ref<{ id: string; title: string } | null>(null)
const showDeleteSessionConfirm = ref(false)
const sessionToDelete = ref<{ id: string; title: string } | null>(null)
const isImporting = ref(false)
const errorMsg = ref('')
const showImportConfirm = ref(false)
const isSeeding = ref(false)
const isDeleting = ref(false)
const isDeletingSession = ref(false)
const showImportWarning = ref(false)
const showAboutModal = ref(false)
const importWarningType = ref<'defaults' | 'samples'>('defaults')
const importConflicts = ref<Array<{ title: string; already_exists: boolean }>>([])

const importInput = ref<HTMLInputElement | null>(null)
const pendingImports = ref<PendingAdventureState[]>([])
const pendingCreations = ref<PendingAdventureState[]>([])
const loadingWordIndex = ref(0)
const loadingWords = [
  'Checking manifest',
  'Creating world structure',
  'Building scenes',
  'Weaving characters',
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
      status: 'Import started',
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
  const isTemporaryImport =
    kind === 'import' && (adventureId.startsWith('adv-import-') || adventureId.startsWith('adz-import-'))

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

    templates.value = Array.isArray(fetchedTemplates)
      ? fetchedTemplates.map((entry) => ({
          ...entry,
          selected_tone: formatToneLabel(entry.selected_tone),
        }))
      : []
    sessions.value = Array.isArray(fetchedSessions) ? fetchedSessions : []

    for (const template of templates.value) {
      if (!template.is_ready) {
        const isAlreadyPending = pendingCreations.value.some((p) => p.adventureId === template.template_id)
        if (!isAlreadyPending) {
          addPendingCreationCard(template.template_id, template.title)
          updatePendingCreationStatus(
            template.template_id,
            template.creation_error || template.creation_status || 'Preparing...',
            (Boolean(template.creation_error) && !template.creation_error?.startsWith('Notice:')) || isFailureStatus(template.creation_status || ''),
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
    errorMsg.value = error?.message || 'Session could not be started.'
  }
}

function confirmDeleteSession(gameId: string, title: string) {
  sessionToDelete.value = { id: gameId, title }
  showDeleteSessionConfirm.value = true
}

async function executeDeleteSession() {
  if (!sessionToDelete.value) return

  isDeletingSession.value = true
  try {
    await api.deleteSession(sessionToDelete.value.id)
    sessions.value = sessions.value.filter((s) => s.game_id !== sessionToDelete.value?.id)
    showDeleteSessionConfirm.value = false
    sessionToDelete.value = null
  } catch (error: any) {
    errorMsg.value = error?.message || 'Session could not be deleted.'
  } finally {
    isDeletingSession.value = false
  }
}

function editAdventure(templateId: string) {
  router.push({ 
    name: 'adventure-editor', 
    params: { adventureId: templateId },
    query: { from: activeSection.value }
  })
}

function confirmDeleteTemplate(templateId: string, title: string) {
  templateToDelete.value = { id: templateId, title }
  showDeleteConfirm.value = true
}

async function executeDeleteTemplate() {
  if (!templateToDelete.value) return

  isDeleting.value = true
  try {
    await api.deleteAdventure(templateToDelete.value.id)
    templates.value = templates.value.filter((entry) => entry.template_id !== templateToDelete.value?.id)
    sessions.value = sessions.value.filter((entry) => (entry.template_id || entry.adventure_id) !== templateToDelete.value?.id)
    showDeleteConfirm.value = false
    templateToDelete.value = null
  } catch (error) {
    console.error('Error deleting template:', error)
  } finally {
    isDeleting.value = false
  }
}

function openCreateModal() {
  router.push({ name: 'adventure-create' })
}

async function handleImportSamplesClick() {
  try {
    const checkRes = await api.checkExamples()
    const conflicts = checkRes.available_imports.filter(i => i.already_exists)
    
    if (conflicts.length > 0) {
      importConflicts.value = checkRes.available_imports
      importWarningType.value = 'samples'
      showImportWarning.value = true
    } else {
      showImportConfirm.value = true
    }
  } catch (error) {
    console.error('Error checking for example conflicts:', error)
    // Fallback if check fails
    showImportConfirm.value = true
  }
}

async function executeImportExamples() {
  showImportConfirm.value = false
  
  // Check for conflicts first
  try {
    const checkRes = await api.checkExamples()
    const conflicts = checkRes.available_imports.filter(i => i.already_exists)
    
    if (conflicts.length > 0) {
      importConflicts.value = checkRes.available_imports
      importWarningType.value = 'samples'
      showImportWarning.value = true
      return
    }
  } catch (error) {
    console.error('Error checking for example conflicts:', error)
  }

  await performImportExamples()
}

async function performImportExamples() {
  showImportWarning.value = false
  isSeeding.value = true
  try {
    await api.importExamples()
    await fetchPortalData()
  } catch (error: any) {
    errorMsg.value = error?.message || 'Import of examples failed.'
  } finally {
    isSeeding.value = false
  }
}

async function executeRestoreDefaults() {
  // Check for conflicts first
  try {
    const checkRes = await api.checkDefaults()
    const conflicts = checkRes.available_imports.filter(i => i.already_exists)
    
    if (conflicts.length > 0) {
      importConflicts.value = checkRes.available_imports
      importWarningType.value = 'defaults'
      showImportWarning.value = true
      return
    }
  } catch (error) {
    console.error('Error checking for default conflicts:', error)
  }

  await performRestoreDefaults()
}

async function performRestoreDefaults() {
  showImportWarning.value = false
  isSeeding.value = true
  try {
    await api.reimportDefaults()
    await fetchPortalData()
  } catch (error: any) {
    errorMsg.value = error?.message || 'Restoration of defaults failed.'
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
    errorMsg.value = 'Only .adv and .adz are supported as import formats.'
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
    errorMsg.value = error?.message || 'Import failed.'
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
    updatePendingImportStatus(tempId, error?.message || 'ADV import failed', true)
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
    updatePendingImportStatus(tempId, error?.message || 'ADZ import failed', true)
  } finally {
    isImporting.value = false
  }
}

function makeSafeFilename(title: string, ext: string) {
  const safe = (title || 'adventure').replace(/[^a-zA-Z0-9 _-]/g, '').trim().replace(/\s+/g, '_')
  return `${safe || 'adventure'}.${ext}`
}

async function exportAdventureAdz(adventureId: string, title: string) {
  try {
    const blob = await api.downloadAdventureAdz(adventureId)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = makeSafeFilename(title, 'adz')
    a.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    errorMsg.value = error?.message || 'ADZ export failed'
  }
}

async function exportAdventureAdv(adventureId: string, title: string) {
  try {
    const data = await api.downloadAdventureAdv(adventureId)
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = makeSafeFilename(title, 'adv')
    a.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    errorMsg.value = error?.message || 'ADV export failed'
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
  if (authState.token) {
    void fetchPortalData()
  } else {
    isLoading.value = false
  }

  loadingWordTimer = window.setInterval(() => {
    loadingWordIndex.value = (loadingWordIndex.value + 1) % loadingWords.length
  }, 1200)

  const newId = typeof route.query.new_id === 'string' ? route.query.new_id : ''
  const newTitle = typeof route.query.new_title === 'string' ? route.query.new_title : 'New Adventure'

  if (newId) {
    addPendingCreationCard(newId, newTitle)
    updatePendingCreationStatus(newId, 'Starting generation...')
    void pollAdventureStatus(newId, {
      onStatus: (status: string) => updatePendingCreationStatus(newId, status || 'Preparing...'),
      onReady: async () => {
        removePendingCreationCard(newId)
        await fetchPortalData()
      },
      onFailure: (status: string) => updatePendingCreationStatus(newId, status || 'Generation failed', true),
    })
    router.replace({ name: 'portal', query: {} })
  }
})

watch(
  () => authState.token,
  (token) => {
    if (token) {
      isLoading.value = true
      void fetchPortalData()
    }
  },
)

watch(() => route.query.section, (section) => {
  if (section === 'profile') activeSection.value = 'profile'
  else if (section === 'templates') activeSection.value = 'templates'
  else if (section === 'sessions') activeSection.value = 'sessions'
}, { immediate: true })

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
      @section="router.push({ query: { ...route.query, section: $event } })"
      @admin="router.push('/admin')"
      @about="showAboutModal = true"
    />

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col relative overflow-hidden">
      <!-- Scrollable Content -->
      <div class="flex-1 overflow-y-auto" :class="activeSection !== 'profile' ? 'p-10' : ''">
        
        <LlmWarningBanner :active-section="activeSection" />

        <PortalLibraryToolbar
          v-if="activeSection !== 'profile'"
          :active-section="activeSection"
          @change-section="activeSection = $event"
          @create="openCreateModal"
          @import="triggerImportPicker"
          @restore-defaults="executeRestoreDefaults"
        />

        <!-- Loading State -->
        <div v-if="isLoading && templates.length === 0 && sessions.length === 0 && pendingCards.length === 0" class="flex flex-col items-center justify-center py-32 gap-6">
          <div class="w-16 h-16 border-4 border-aether-primary/10 border-t-aether-primary rounded-full animate-spin"></div>
          <p class="text-aether-primary font-bold uppercase tracking-[0.3em] text-xxs">Accessing Archives...</p>
        </div>

        <div v-else>
          <div v-if="activeSection === 'templates'">
            <AdventureLibraryGrid
              :visible-templates="visibleTemplates"
              :pending-cards="pendingCards"
              :is-seeding="isSeeding"
              :loading-word-index="loadingWordIndex"
              @create="openCreateModal"
              @import-samples="handleImportSamplesClick"
              @remove-failed-pending="removeFailedPendingCard"
              @cancel-pending="cancelAdventure"
              @start-session="startSession"
              @edit="editAdventure"
              @export-adz="exportAdventureAdz"
              @export-adv="exportAdventureAdv"
              @delete="confirmDeleteTemplate"
            />
          </div>

          <div v-else-if="activeSection === 'sessions'">
            <GameSessionsGrid
              :sessions="sessions"
              @resume="playSession"
              @delete="confirmDeleteSession"
              @switch-to-templates="activeSection = 'templates'"
            />
          </div>

          <div v-else-if="activeSection === 'profile'">
            <UserProfileContent />
          </div>
        </div>

        <PortalFooter />
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
        :is-deleting="isDeleting"
        @close="showDeleteConfirm = false"
        @confirm="executeDeleteTemplate"
      />
      
      <ImportExamplesModal
        v-if="showImportConfirm"
        @close="showImportConfirm = false"
        @confirm="executeImportExamples"
      />

      <DeleteSessionModal
        v-if="showDeleteSessionConfirm"
        :session-title="sessionToDelete?.title || ''"
        :is-deleting="isDeletingSession"
        @close="showDeleteSessionConfirm = false"
        @confirm="executeDeleteSession"
      />

      <ImportWarningModal
        v-if="showImportWarning"
        :type="importWarningType"
        :conflicts="importConflicts"
        :is-importing="isSeeding"
        @close="showImportWarning = false"
        @confirm="importWarningType === 'defaults' ? performRestoreDefaults() : performImportExamples()"
      />

      <AboutModal
        :isOpen="showAboutModal"
        @close="showAboutModal = false"
      />
    </Teleport>

  </div>
</template>

