<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { authState } from '@/store/auth'
import { usePortalData } from '@/composables/usePortalData'
import { usePortalSectionRouting } from '@/composables/usePortalSectionRouting'
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

const { route, router, activeSection, pushSection } = usePortalSectionRouting()
const showAboutModal = ref(false)

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
  showImportWarning,
  importWarningType,
  importConflicts,
  importInput,
  loadingWordIndex,
  pendingCards,
  visibleTemplates,
  fetchPortalData,
  startSessionForTemplate,
  confirmDeleteSession,
  executeDeleteSession,
  confirmDeleteTemplate,
  executeDeleteTemplate,
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
} = usePortalData()

watch(importInput, () => undefined)

const isAdmin = computed(() => authState.user?.role === 'admin')

function playSession(gameId: string) {
  router.push({ name: 'game', params: { id: gameId } })
}

async function startSession(templateId: string) {
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

onMounted(() => {
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
    router.replace({ name: 'portal', query: {} })
  }
})

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
      @section="pushSection($event)"
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
        @close="closeTemplateDeleteConfirm"
        @confirm="executeDeleteTemplate"
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
    </Teleport>

  </div>
</template>

