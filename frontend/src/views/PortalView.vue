<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { configState } from '@/store/config'
import { authState } from '@/store/auth'
import { api } from '@/composables/useApi'
import { usePortalData } from '@/composables/usePortalData'
import { usePortalSectionRouting } from '@/composables/usePortalSectionRouting'
import PortalSidebar from '@/components/portal/PortalSidebar.vue'
import SetupWarningBanner from '@/components/portal/SetupWarningBanner.vue'
import PortalLibraryToolbar from '@/components/portal/PortalLibraryToolbar.vue'
import PortalFilterToolbar from '@/components/portal/PortalFilterToolbar.vue'
import AdventureLibraryGrid from '@/components/portal/AdventureLibraryGrid.vue'
import AdventureLibraryTable from '@/components/portal/AdventureLibraryTable.vue'
import GameSessionsGrid from '@/components/portal/GameSessionsGrid.vue'
import GameSessionsTable from '@/components/portal/GameSessionsTable.vue'
import UserProfileContent from '@/components/portal/UserProfileContent.vue'
import PortalFooter from '@/components/portal/PortalFooter.vue'
import {
  usePortalFilters,
  extractAvailableTones,
  extractAvailableStyles
} from '@/composables/usePortalFilters'
import { isMobileSidebarOpen, closeMobileSidebar } from '@/store/layout'

import DeleteAdventureModal from '@/components/portal/DeleteAdventureModal.vue'
import DeleteAllAdventuresModal from '@/components/portal/DeleteAllAdventuresModal.vue'
import ImportExamplesModal from '@/components/portal/ImportExamplesModal.vue'
import ImportWarningModal from '@/components/portal/ImportWarningModal.vue'
import DeleteSessionModal from '@/components/portal/DeleteSessionModal.vue'
import DeleteAllSessionsModal from '@/components/portal/DeleteAllSessionsModal.vue'
import SessionNoteModal from '@/components/portal/SessionNoteModal.vue'
import AboutModal from '@/components/portal/AboutModal.vue'
import ImportConflictModal from '@/components/portal/ImportConflictModal.vue'
import SetupWarningModal from '@/components/portal/SetupWarningModal.vue'
import CloneProgressModal from '@/components/portal/CloneProgressModal.vue'
import GenerationProgressModal from '@/components/portal/GenerationProgressModal.vue'
import MigrateAdventureModal from '@/components/portal/MigrateAdventureModal.vue'
import type { AdventureTemplateSummary } from '@/types'


const { route, router, activeSection, pushSection } = usePortalSectionRouting()
const showAboutModal = ref(false)
const showSetupWarningModal = ref(false)
const hasCheckedSetup = ref(false)
const showDeleteAllAdventuresConfirm = ref(false)
const showDeleteAllSessionsConfirm = ref(false)
const isResuming = ref(false)
const activeProgressAdventure = ref<{ id: string; title: string } | null>(null)

function openProgressModal(pending: any) {
  activeProgressAdventure.value = {
    id: pending.adventureId,
    title: pending.title
  }
}


const {
  templates,
  sessions,
  isLoading,
  showDeleteConfirm,
  templateToDelete,
  showDeleteSessionConfirm,
  sessionToDelete,
  showImportConfirm,
  isSeeding,
  isDeleting,
  isDeletingSession,
  isStartingSession,
  startingSessionTemplateId,
  startingSessionTitle,
  showImportWarning,
  importWarningType,
  importConflicts,
  importInput,
  importAccept,
  loadingWordIndex,
  pendingCards,
  visibleTemplates,
  updatingTemplateIds,
  migratingTemplateIds,
  isUpdatingAll,
  availableUpdatesCount,
  updateAdventure,
  migrateAdventure,
  updateAllAdventures,
  fetchPortalData,
  startSessionForTemplate,
  confirmDeleteSession,
  executeDeleteSession,
  executeDeleteAllSessions,
  copySession,
  confirmDeleteTemplate,
  executeDeleteTemplate,
  executeDeleteAllTemplates,
  closeTemplateDeleteConfirm,
  closeSessionDeleteConfirm,
  closeImportExamplesConfirm,
  closeImportWarning,
  handleImportSamplesClick,
  executeImportExamples,
  performImportExamples,
  executeRestoreDefaults,
  performRestoreDefaults,
  triggerImportPicker,
  onImportFileSelected,
  exportAdventureAdz,
  exportAdventureAdv,
  removeFailedPendingCard,
  cancelAdventure,
  trackNewAdventure,
  startLoadingWords,
  stopLoadingWords,
  setLoadingState,
  showConflictModal,
  activeConflict,
  closeConflictModal,
  confirmConflictOverwrite,
  dismissWarning,
  exportProgressState,
  cloneProgressState,
  editNoteSessionId,
  editNoteValue,
  isSavingNote,
  openEditNote,
  saveSessionNote,
  exportSessionAds,
  imageStylesCatalog,
  toneCatalog,
} = usePortalData()

const templateFilters = usePortalFilters(visibleTemplates, 'templates', 18)
const sessionFilters = usePortalFilters(sessions, 'sessions', 18)

const availableTones = computed(() => {
  return extractAvailableTones(visibleTemplates.value, sessions.value, toneCatalog.value)
})

const availableStyles = computed(() => {
  return extractAvailableStyles(visibleTemplates.value, sessions.value, imageStylesCatalog.value)
})

watch(importInput, () => undefined)

watch(
  activeSection,
  (section) => {
    importAccept.value = section === 'sessions' ? '.ads' : '.adv,.adz'
  },
  { immediate: true }
)

function handleImport(kind?: 'templates' | 'sessions') {
  const targetKind = kind || (activeSection.value === 'sessions' ? 'session' : 'adventure')
  triggerImportPicker(targetKind === 'sessions' ? 'session' : 'adventure')
}

const isAdmin = computed(() => authState.user?.role === 'admin')

async function playSession(gameId: string) {
  if (isStartingSession.value) {
    const template = templates.value.find((t) => t.template_id === startingSessionTemplateId.value)
    await router.push({
      name: 'game',
      params: { id: gameId },
      query: { title: template?.title || '', is_new: 'true' }
    })
    return
  }

  isStartingSession.value = true
  isResuming.value = true
  const session = sessions.value.find((s) => s.game_id === gameId)
  startingSessionTitle.value = session?.adventure_title || 'Adventure'

  // Smooth loading delay so the transition feels premium
  await new Promise((resolve) => setTimeout(resolve, 600))

  try {
    await router.push({
      name: 'game',
      params: { id: gameId },
      query: { title: session?.adventure_title || '', resuming: 'true' }
    })
  } finally {
    isStartingSession.value = false
    startingSessionTitle.value = ''
    isResuming.value = false
  }
}

async function startSession(templateId: string) {
  if (isStartingSession.value) return
  await startSessionForTemplate(templateId, playSession)
}

function editAdventure(templateId: string) {
  router.push({ 
    name: 'adventure-editor', 
    params: { adventureId: templateId },
    query: { from: activeSection.value }
  })
}

function openCreateModal() {
  router.push({ name: 'adventure-create' })
}

async function createEmptyAdventure() {
  setLoadingState(true)
  try {
    const payload = {
      title: 'New Adventure',
      skip_generation: true,
      rule_enforcement_mode: 'rpg' as const
    }
    const result = await api.createAdventure(payload)
    router.push({ 
      name: 'adventure-editor', 
      params: { adventureId: result.adventure_id },
      query: { from: activeSection.value }
    })
  } catch (error: any) {
    console.error('Failed to create empty adventure:', error)
    errorMsg.value = error?.message || 'Failed to create empty adventure.'
  } finally {
    setLoadingState(false)
  }
}

async function onDeleteAllAdventures() {
  if (templates.length === 0 || isDeleting.value) return
  showDeleteAllAdventuresConfirm.value = true
}

function closeDeleteAllAdventuresConfirm() {
  showDeleteAllAdventuresConfirm.value = false
}

async function confirmDeleteAllAdventures() {
  await executeDeleteAllTemplates()
  showDeleteAllAdventuresConfirm.value = false
}

async function onDeleteAllSessions() {
  if (sessions.length === 0 || isDeletingSession.value) return
  showDeleteAllSessionsConfirm.value = true
}

function closeDeleteAllSessionsConfirm() {
  showDeleteAllSessionsConfirm.value = false
}

async function confirmDeleteAllSessions() {
  await executeDeleteAllSessions()
  showDeleteAllSessionsConfirm.value = false
}

function openCoverCreate(templateId: string) {
  router.push({ name: 'adventure-create', query: { cover_from: templateId } })
}

const showMigrateModal = ref(false)
const templateToMigrate = ref<AdventureTemplateSummary | null>(null)

function openMigrateModal(template: AdventureTemplateSummary) {
  templateToMigrate.value = template
  showMigrateModal.value = true
}

function closeMigrateModal() {
  showMigrateModal.value = false
  templateToMigrate.value = null
}

async function handleMigrateFormat(templateId: string) {
  await migrateAdventure(templateId)
  closeMigrateModal()
}

function handleMigrateCover(templateId: string) {
  closeMigrateModal()
  openCoverCreate(templateId)
}

onMounted(() => {
  isMobileSidebarOpen.value = false
  if (authState.token) {
    void fetchPortalData()
  } else {
    setLoadingState(false)
  }

  startLoadingWords()

  const newId = typeof route.query.new_id === 'string' ? route.query.new_id : ''
  const newTitle = typeof route.query.new_title === 'string' ? route.query.new_title : 'New Adventure'

  if (newId) {
    trackNewAdventure(newId, newTitle)
    // Remove tracking params from URL but keep the section so the library stays visible
    const { new_id: _a, new_title: _b, ...remainingQuery } = route.query
    router.replace({ name: 'portal', query: remainingQuery })
  }
})

watch(
  () => configState.isLoaded,
  (loaded) => {
    if (loaded && !hasCheckedSetup.value) {
      const isDismissed = localStorage.getItem('taleweaver_setup_warning_dismissed') === 'true'
      const needsLlm = !configState.hasLlmConfig
      const needsT2i = !configState.hasT2iConfig

      // Show if critical (LLM) missing OR if T2i missing and not dismissed
      if (needsLlm || (needsT2i && !isDismissed)) {
        showSetupWarningModal.value = true
      }
      hasCheckedSetup.value = true
    }
  },
  { immediate: true }
)

function dismissSetupWarning() {
  showSetupWarningModal.value = false
  if (configState.hasLlmConfig) {
    localStorage.setItem('taleweaver_setup_warning_dismissed', 'true')
  }
}

watch(
  () => authState.token,
  (token) => {
    if (token) {
      setLoadingState(true)
      void fetchPortalData()
    }
  },
)

onUnmounted(() => {
  stopLoadingWords()
})
</script>

<template>
  <div class="flex h-full min-h-0 bg-[#050b14] text-slate-200 font-ui overflow-hidden">
    <PortalSidebar
      :is-admin="isAdmin"
      :active-section="activeSection"
      :is-mobile-open="isMobileSidebarOpen"
      @section="pushSection($event)"
      @admin="router.push('/admin')"
      @about="showAboutModal = true"
      @close-mobile="closeMobileSidebar"
    />

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col relative overflow-hidden min-w-0">
      <!-- Scrollable Content -->
      <div class="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-10" :class="activeSection === 'profile' ? 'lg:p-10' : ''">
        
        <SetupWarningBanner :active-section="activeSection" />

        <PortalLibraryToolbar
          v-if="activeSection !== 'profile'"
          :active-section="activeSection"
          :template-count="templates.length"
          :is-deleting-templates="isDeleting"
          :session-count="sessions.length"
          :is-deleting-sessions="isDeletingSession"
          :update-count="availableUpdatesCount"
          :is-updating-all="isUpdatingAll"
          @change-section="activeSection = $event"
          @delete-all-adventures="onDeleteAllAdventures"
          @import="handleImport"
          @restore-defaults="executeRestoreDefaults"
          @update-all="updateAllAdventures"
          @delete-all-sessions="onDeleteAllSessions"
        />

        <PortalFilterToolbar
          v-if="activeSection !== 'profile' && !isLoading"
          :section="activeSection"
          :search-query="activeSection === 'templates' ? templateFilters.searchQuery.value : sessionFilters.searchQuery.value"
          :selected-type="activeSection === 'templates' ? templateFilters.selectedType.value : sessionFilters.selectedType.value"
          :selected-tone="activeSection === 'templates' ? templateFilters.selectedTone.value : sessionFilters.selectedTone.value"
          :selected-style="activeSection === 'templates' ? templateFilters.selectedStyle.value : sessionFilters.selectedStyle.value"
          :view-mode="activeSection === 'templates' ? templateFilters.viewMode.value : sessionFilters.viewMode.value"
          :available-tones="availableTones"
          :available-styles="availableStyles"
          :total-count="activeSection === 'templates' ? templateFilters.totalCount.value : sessionFilters.totalCount.value"
          :filtered-count="activeSection === 'templates' ? templateFilters.filteredCount.value : sessionFilters.filteredCount.value"
          :is-filtered="activeSection === 'templates' ? templateFilters.isFiltered.value : sessionFilters.isFiltered.value"
          @update:search-query="activeSection === 'templates' ? (templateFilters.searchQuery.value = $event) : (sessionFilters.searchQuery.value = $event)"
          @update:selected-type="activeSection === 'templates' ? (templateFilters.selectedType.value = $event) : (sessionFilters.selectedType.value = $event)"
          @update:selected-tone="activeSection === 'templates' ? (templateFilters.selectedTone.value = $event) : (sessionFilters.selectedTone.value = $event)"
          @update:selected-style="activeSection === 'templates' ? (templateFilters.selectedStyle.value = $event) : (sessionFilters.selectedStyle.value = $event)"
          @update:view-mode="activeSection === 'templates' ? (templateFilters.viewMode.value = $event) : (sessionFilters.viewMode.value = $event)"
          @reset-filters="activeSection === 'templates' ? templateFilters.resetFilters() : sessionFilters.resetFilters()"
        />

        <!-- Loading State -->
        <div v-if="isLoading && templates.length === 0 && sessions.length === 0 && pendingCards.length === 0" class="flex flex-col items-center justify-center py-20 sm:py-32 gap-6">
          <div class="w-12 h-12 sm:w-16 sm:h-16 border-4 border-aether-primary/10 border-t-aether-primary rounded-full animate-spin"></div>
          <p class="text-aether-primary font-bold uppercase tracking-[0.3em] text-xxs">Accessing Archives...</p>
        </div>

        <div v-else>
          <div v-if="activeSection === 'templates'">
            <AdventureLibraryGrid
              v-if="templateFilters.viewMode.value === 'grid'"
              :visible-templates="templateFilters.paginatedItems.value"
              :pending-cards="pendingCards"
              :is-seeding="isSeeding"
              :loading-word-index="loadingWordIndex"
              :is-starting-session="isStartingSession"
              :starting-session-template-id="startingSessionTemplateId"
              :updating-template-ids="updatingTemplateIds"
              :has-more="templateFilters.hasMore.value"
              :total-filtered-count="templateFilters.filteredCount.value"
              @load-more="templateFilters.loadMore"
              @create="createEmptyAdventure"
              @generate-world="openCreateModal"
              @import-samples="handleImportSamplesClick"
              @remove-failed-pending="removeFailedPendingCard"
              @cancel-pending="cancelAdventure"
              @start-session="startSession"
              @update-adventure="updateAdventure"
              @migrate="openMigrateModal"
              @cover="openCoverCreate"
              @edit="editAdventure"
              @export-adz="exportAdventureAdz"
              @export-adv="exportAdventureAdv"
              @delete="confirmDeleteTemplate"
              @dismiss-warning="dismissWarning"
              @click-pending="openProgressModal"
            />
            <AdventureLibraryTable
              v-else
              :visible-templates="templateFilters.paginatedItems.value"
              :all-filtered-templates="templateFilters.filteredItems.value"
              :pending-cards="pendingCards"
              :is-seeding="isSeeding"
              :loading-word-index="loadingWordIndex"
              :is-starting-session="isStartingSession"
              :starting-session-template-id="startingSessionTemplateId"
              :updating-template-ids="updatingTemplateIds"
              :has-more="templateFilters.hasMore.value"
              :total-filtered-count="templateFilters.filteredCount.value"
              @load-more="templateFilters.loadMore"
              @create="createEmptyAdventure"
              @generate-world="openCreateModal"
              @import-samples="handleImportSamplesClick"
              @remove-failed-pending="removeFailedPendingCard"
              @cancel-pending="cancelAdventure"
              @start-session="startSession"
              @update-adventure="updateAdventure"
              @migrate="openMigrateModal"
              @cover="openCoverCreate"
              @edit="editAdventure"
              @export-adz="exportAdventureAdz"
              @export-adv="exportAdventureAdv"
              @delete="confirmDeleteTemplate"
              @dismiss-warning="dismissWarning"
              @click-pending="openProgressModal"
            />
          </div>

          <div v-else-if="activeSection === 'sessions'">
            <GameSessionsGrid
              v-if="sessionFilters.viewMode.value === 'grid'"
              :sessions="sessionFilters.paginatedItems.value"
              :has-more="sessionFilters.hasMore.value"
              :total-filtered-count="sessionFilters.filteredCount.value"
              @load-more="sessionFilters.loadMore"
              @resume="playSession"
              @delete="confirmDeleteSession"
              @copy="copySession"
              @edit-note="openEditNote"
              @export="(id) => exportSessionAds(id, sessions.find(s => s.game_id === id)?.adventure_title || 'session')"
              @switch-to-templates="activeSection = 'templates'"
            />
            <GameSessionsTable
              v-else
              :sessions="sessionFilters.paginatedItems.value"
              :all-filtered-sessions="sessionFilters.filteredItems.value"
              :has-more="sessionFilters.hasMore.value"
              :total-filtered-count="sessionFilters.filteredCount.value"
              @load-more="sessionFilters.loadMore"
              @resume="playSession"
              @delete="confirmDeleteSession"
              @copy="copySession"
              @edit-note="openEditNote"
              @export="(id) => exportSessionAds(id, sessions.find(s => s.game_id === id)?.adventure_title || 'session')"
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
      :accept="importAccept"
      @change="onImportFileSelected"
    />

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <DeleteAdventureModal
        v-if="showDeleteConfirm"
        :adventure-title="templateToDelete?.title || ''"
        :is-deleting="isDeleting"
        @close="closeTemplateDeleteConfirm"
        @confirm="executeDeleteTemplate"
      />

      <DeleteAllAdventuresModal
        v-if="showDeleteAllAdventuresConfirm"
        :adventure-count="templates.length"
        :is-deleting="isDeleting"
        @close="closeDeleteAllAdventuresConfirm"
        @confirm="confirmDeleteAllAdventures"
      />
      
      <ImportExamplesModal
        v-if="showImportConfirm"
        @close="closeImportExamplesConfirm"
        @confirm="executeImportExamples"
      />

      <DeleteSessionModal
        v-if="showDeleteSessionConfirm"
        :session-title="sessionToDelete?.title || ''"
        :is-deleting="isDeletingSession"
        @close="closeSessionDeleteConfirm"
        @confirm="executeDeleteSession"
      />

      <DeleteAllSessionsModal
        v-if="showDeleteAllSessionsConfirm"
        :session-count="sessions.length"
        :is-deleting="isDeletingSession"
        @close="closeDeleteAllSessionsConfirm"
        @confirm="confirmDeleteAllSessions"
      />

      <SessionNoteModal
        v-if="editNoteSessionId"
        :initial-note="editNoteValue"
        :is-saving="isSavingNote"
        @close="editNoteSessionId = null"
        @save="saveSessionNote"
      />

      <ImportWarningModal
        v-if="showImportWarning"
        :type="importWarningType"
        :conflicts="importConflicts"
        :is-importing="isSeeding"
        @close="closeImportWarning"
        @confirm="importWarningType === 'defaults' ? performRestoreDefaults() : performImportExamples()"
      />

      <AboutModal
        :isOpen="showAboutModal"
        @close="showAboutModal = false"
      />

      <ImportConflictModal
        v-if="showConflictModal"
        :conflict="activeConflict"
        :is-importing="isImporting"
        @close="closeConflictModal"
        @confirm="confirmConflictOverwrite"
      />

      <SetupWarningModal
        :isOpen="showSetupWarningModal"
        @close="dismissSetupWarning"
      />

      <ExportProgressModal
        v-if="exportProgressState.isOpen"
        :adventure-title="exportProgressState.adventureTitle"
        :format="exportProgressState.format"
        :progress="exportProgressState.progress"
        :error-msg="exportProgressState.errorMsg"
        @close="exportProgressState.isOpen = false"
      />

      <CloneProgressModal
        v-if="cloneProgressState.isOpen"
        :session-title="cloneProgressState.sessionTitle"
        :progress="cloneProgressState.progress"
        :stage="cloneProgressState.stage"
        :error-msg="cloneProgressState.errorMsg"
        @close="cloneProgressState.isOpen = false"
      />

      <GenerationProgressModal
        v-if="activeProgressAdventure"
        :adventure-id="activeProgressAdventure.id"
        :adventure-title="activeProgressAdventure.title"
        @close="activeProgressAdventure = null"
      />

      <MigrateAdventureModal
        :is-open="showMigrateModal"
        :template="templateToMigrate"
        :is-migrating="templateToMigrate ? migratingTemplateIds.has(templateToMigrate.template_id) : false"
        @close="closeMigrateModal"
        @migrate-format="handleMigrateFormat"
        @cover="handleMigrateCover"
      />

      <div
        v-if="isStartingSession"
        class="fixed inset-0 z-[220] bg-slate-950/75 backdrop-blur-sm flex items-center justify-center px-6"
      >
        <div class="w-full max-w-md rounded-2xl border border-white/15 bg-slate-900/95 p-7 shadow-2xl">
          <div class="flex items-start gap-4">
            <div class="w-12 h-12 rounded-xl bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center shrink-0">
              <i class="ra ra-cycle animate-spin text-emerald-400 text-xl"></i>
            </div>
            <div class="space-y-2">
              <h3 class="text-lg font-black text-white tracking-tight">
                {{ isResuming ? 'Resuming Session' : 'Session Is Starting' }}
              </h3>
              <p class="text-sm text-slate-300 leading-relaxed">
                {{ isResuming ? 'Loading assets for' : 'Assets are copied for' }} <span class="font-bold text-emerald-300">{{ startingSessionTitle || 'Adventure' }}</span>.
                Please wait a moment.
              </p>
              <p class="text-[11px] uppercase tracking-[0.18em] text-slate-500 font-bold">
                {{ isResuming ? 'Establishing connection...' : 'Preventing duplicate starts...' }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>

