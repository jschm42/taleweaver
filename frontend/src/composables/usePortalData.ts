import { ref, type ComputedRef, type Ref } from 'vue'
import { api } from '@/composables/useApi'
import { usePortalModals, type PortalImportWarningType } from '@/composables/usePortalModals'
import { usePortalPendingState } from '@/composables/usePortalPendingState'
import type { AdventureTemplateSummary, GameSession } from '@/types'

type ImportKind = 'adv' | 'adz'
type PendingCard = { adventureId: string; title: string; status: string; hasError: boolean; kind: 'creation' | 'import' }

export interface UsePortalDataResult {
  templates: Ref<AdventureTemplateSummary[]>
  sessions: Ref<GameSession[]>
  isLoading: Ref<boolean>
  showDeleteConfirm: Ref<boolean>
  templateToDelete: Ref<{ id: string; title: string } | null>
  showDeleteSessionConfirm: Ref<boolean>
  sessionToDelete: Ref<{ id: string; title: string } | null>
  isImporting: Ref<boolean>
  errorMsg: Ref<string>
  showImportConfirm: Ref<boolean>
  isSeeding: Ref<boolean>
  isDeleting: Ref<boolean>
  isDeletingSession: Ref<boolean>
  showImportWarning: Ref<boolean>
  importWarningType: Ref<PortalImportWarningType>
  importConflicts: Ref<Array<{ title: string; already_exists: boolean }>>
  importInput: Ref<HTMLInputElement | null>
  loadingWordIndex: Ref<number>
  pendingCards: ComputedRef<PendingCard[]>
  visibleTemplates: ComputedRef<AdventureTemplateSummary[]>
  fetchPortalData: () => Promise<void>
  startSessionForTemplate: (templateId: string, onStarted: (gameId: string) => void | Promise<void>) => Promise<void>
  confirmDeleteSession: (gameId: string, title: string) => void
  executeDeleteSession: () => Promise<void>
  confirmDeleteTemplate: (templateId: string, title: string) => void
  executeDeleteTemplate: () => Promise<void>
  closeTemplateDeleteConfirm: () => void
  closeSessionDeleteConfirm: () => void
  closeImportExamplesConfirm: () => void
  closeImportWarning: () => void
  handleImportSamplesClick: () => Promise<void>
  executeImportExamples: () => Promise<void>
  performImportExamples: () => Promise<void>
  executeRestoreDefaults: () => Promise<void>
  performRestoreDefaults: () => Promise<void>
  triggerImportPicker: () => void
  onImportFileSelected: (event: Event) => Promise<void>
  exportAdventureAdz: (adventureId: string, title: string) => Promise<void>
  exportAdventureAdv: (adventureId: string, title: string) => Promise<void>
  removeFailedPendingCard: (adventureId: string, kind: 'creation' | 'import') => Promise<void>
  cancelAdventure: (adventureId: string) => Promise<void>
  trackNewAdventure: (adventureId: string, title: string) => void
  startLoadingWords: () => void
  stopLoadingWords: () => void
  setLoadingState: (value: boolean) => void
}

function formatToneLabel(value?: unknown): string {
  if (!value) return ''
  let text = ''

  if (typeof value === 'object' && value !== null) {
    const objectValue = value as Record<string, unknown>
    text = String(objectValue.name || objectValue.id || '')
  } else {
    text = String(value)
    if (text.startsWith('{')) {
      try {
        const objectValue = JSON.parse(text) as Record<string, unknown>
        text = String(objectValue.name || objectValue.id || text)
      } catch {
        // Value is not parseable JSON, keep raw string.
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

function makeSafeFilename(title: string, ext: string) {
  const safe = (title || 'adventure').replace(/[^a-zA-Z0-9 _-]/g, '').trim().replace(/\s+/g, '_')
  return `${safe || 'adventure'}.${ext}`
}

export function usePortalData(): UsePortalDataResult {
  const templates = ref<AdventureTemplateSummary[]>([])
  const sessions = ref<GameSession[]>([])
  const isLoading = ref(true)

  const {
    showDeleteConfirm,
    templateToDelete,
    showDeleteSessionConfirm,
    sessionToDelete,
    showImportConfirm,
    showImportWarning,
    importWarningType,
    importConflicts,
    openTemplateDeleteConfirm,
    closeTemplateDeleteConfirm,
    openSessionDeleteConfirm,
    closeSessionDeleteConfirm,
    openImportExamplesConfirm,
    closeImportExamplesConfirm,
    openImportWarning,
    closeImportWarning,
  } = usePortalModals()

  const {
    loadingWordIndex,
    pendingCards,
    visibleTemplates,
    addPendingImportCard,
    updatePendingImportStatus,
    removePendingImportCard,
    syncPendingFromTemplates,
    removeFailedPendingCard,
    cancelAdventure,
    trackNewAdventure: trackPendingNewAdventure,
    startLoadingWords,
    stopLoadingWords,
  } = usePortalPendingState(templates, sessions)

  const isImporting = ref(false)
  const errorMsg = ref('')
  const isSeeding = ref(false)
  const isDeleting = ref(false)
  const isDeletingSession = ref(false)

  const importInput = ref<HTMLInputElement | null>(null)

  /** Loads templates and sessions and synchronizes pending generation state. */
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

      await syncPendingFromTemplates(fetchPortalData)
    } catch (error) {
      console.error('API Error:', error)
    } finally {
      isLoading.value = false
    }
  }

  /** Opens delete confirmation for a specific game session. */
  function confirmDeleteSession(gameId: string, title: string) {
    openSessionDeleteConfirm(gameId, title)
  }

  /** Executes deletion for the currently selected game session. */
  async function executeDeleteSession() {
    if (!sessionToDelete.value) return

    isDeletingSession.value = true
    try {
      await api.deleteSession(sessionToDelete.value.id)
      sessions.value = sessions.value.filter((entry) => entry.game_id !== sessionToDelete.value?.id)
      closeSessionDeleteConfirm()
    } catch (error: any) {
      errorMsg.value = error?.message || 'Session could not be deleted.'
    } finally {
      isDeletingSession.value = false
    }
  }

  /** Starts a game session from template and calls the provided continuation callback. */
  async function startSessionForTemplate(
    templateId: string,
    onStarted: (gameId: string) => void | Promise<void>,
  ) {
    try {
      const result = await api.startSessionForTemplate(templateId)
      await fetchPortalData()
      await onStarted(result.game_id)
    } catch (error: any) {
      errorMsg.value = error?.message || 'Session could not be started.'
    }
  }

  /** Opens delete confirmation for a specific template. */
  function confirmDeleteTemplate(templateId: string, title: string) {
    openTemplateDeleteConfirm(templateId, title)
  }

  /** Executes deletion for the currently selected template. */
  async function executeDeleteTemplate() {
    if (!templateToDelete.value) return

    isDeleting.value = true
    try {
      await api.deleteAdventure(templateToDelete.value.id)
      templates.value = templates.value.filter((entry) => entry.template_id !== templateToDelete.value?.id)
      sessions.value = sessions.value.filter(
        (entry) => (entry.template_id || entry.adventure_id) !== templateToDelete.value?.id,
      )
      closeTemplateDeleteConfirm()
    } catch (error) {
      console.error('Error deleting template:', error)
    } finally {
      isDeleting.value = false
    }
  }

  /** Checks import conflicts and opens warning modal when conflicts exist. */
  async function hasImportConflicts(
    type: PortalImportWarningType,
    checkFn: () => Promise<{ available_imports: Array<{ title: string; already_exists: boolean }> }>,
  ) {
    const checkRes = await checkFn()
    const conflicts = checkRes.available_imports.filter((item) => item.already_exists)

    if (conflicts.length === 0) {
      return false
    }

    openImportWarning(type, checkRes.available_imports)
    return true
  }

  /** Handles import examples CTA by checking conflicts first. */
  async function handleImportSamplesClick() {
    try {
      const hasConflicts = await hasImportConflicts('samples', api.checkExamples)
      if (!hasConflicts) {
        openImportExamplesConfirm()
      }
    } catch (error) {
      console.error('Error checking for example conflicts:', error)
      openImportExamplesConfirm()
    }
  }

  /** Confirms examples import flow including a second conflict check. */
  async function executeImportExamples() {
    closeImportExamplesConfirm()

    try {
      const hasConflicts = await hasImportConflicts('samples', api.checkExamples)
      if (hasConflicts) {
        return
      }
    } catch (error) {
      console.error('Error checking for example conflicts:', error)
    }

    await performImportExamples()
  }

  /** Performs examples import and refreshes portal data. */
  async function performImportExamples() {
    closeImportWarning()
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

  /** Starts defaults restore flow with conflict pre-check. */
  async function executeRestoreDefaults() {
    try {
      const hasConflicts = await hasImportConflicts('defaults', api.checkDefaults)
      if (hasConflicts) {
        return
      }
    } catch (error) {
      console.error('Error checking for default conflicts:', error)
    }

    await performRestoreDefaults()
  }

  /** Reimports defaults and refreshes portal data. */
  async function performRestoreDefaults() {
    closeImportWarning()
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

  /** Opens hidden file picker for manual adventure import. */
  function triggerImportPicker() {
    importInput.value?.click()
  }

  async function executeFileImport(
    file: File,
    kind: ImportKind,
    importFn: (input: File) => Promise<unknown>,
    fallbackError: string,
  ) {
    isImporting.value = true
    const tempId = `${kind}-import-${Date.now()}`
    addPendingImportCard(tempId, file.name)
    try {
      await importFn(file)
      removePendingImportCard(tempId)
      await fetchPortalData()
    } catch (error: any) {
      updatePendingImportStatus(tempId, error?.message || fallbackError, true)
    } finally {
      isImporting.value = false
    }
  }

  /** Parses selected import file and routes to ADV or ADZ import handler. */
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
        await executeFileImport(file, 'adz', api.importAdz, 'ADZ import failed')
      } else {
        await executeFileImport(file, 'adv', api.importAdv, 'ADV import failed')
      }
    } catch (error: any) {
      errorMsg.value = error?.message || 'Import failed.'
    } finally {
      target.value = ''
    }
  }

  async function exportAdventureFile(adventureId: string, title: string, format: ImportKind) {
    try {
      const blob =
        format === 'adz'
          ? await api.downloadAdventureAdz(adventureId)
          : new Blob([JSON.stringify(await api.downloadAdventureAdv(adventureId), null, 2)], {
              type: 'application/json',
            })

      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = makeSafeFilename(title, format)
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (error: any) {
      errorMsg.value = error?.message || `${format.toUpperCase()} export failed`
    }
  }

  async function exportAdventureAdz(adventureId: string, title: string) {
    await exportAdventureFile(adventureId, title, 'adz')
  }

  async function exportAdventureAdv(adventureId: string, title: string) {
    await exportAdventureFile(adventureId, title, 'adv')
  }

  /** Tracks a newly created adventure in pending state until completion. */
  function trackNewAdventure(adventureId: string, title: string) {
    trackPendingNewAdventure(adventureId, title, fetchPortalData)
  }

  function setLoadingState(value: boolean) {
    isLoading.value = value
  }

  return {
    templates,
    sessions,
    isLoading,
    showDeleteConfirm,
    templateToDelete,
    showDeleteSessionConfirm,
    sessionToDelete,
    isImporting,
    errorMsg,
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
  }
}
