import { ref, type Ref } from 'vue'

export type PortalImportWarningType = 'defaults' | 'samples'

type PortalDeleteTarget = { id: string; title: string }
type PortalConflictEntry = { title: string; already_exists: boolean }

export interface UsePortalModalsResult {
  showDeleteConfirm: Ref<boolean>
  templateToDelete: Ref<PortalDeleteTarget | null>
  showDeleteSessionConfirm: Ref<boolean>
  sessionToDelete: Ref<PortalDeleteTarget | null>
  showImportConfirm: Ref<boolean>
  showImportWarning: Ref<boolean>
  importWarningType: Ref<PortalImportWarningType>
  importConflicts: Ref<PortalConflictEntry[]>
  openTemplateDeleteConfirm: (templateId: string, title: string) => void
  closeTemplateDeleteConfirm: () => void
  openSessionDeleteConfirm: (gameId: string, title: string) => void
  closeSessionDeleteConfirm: () => void
  openImportExamplesConfirm: () => void
  closeImportExamplesConfirm: () => void
  openImportWarning: (type: PortalImportWarningType, conflicts: PortalConflictEntry[]) => void
  closeImportWarning: () => void
}

export function usePortalModals(): UsePortalModalsResult {
  const showDeleteConfirm = ref(false)
  const templateToDelete = ref<PortalDeleteTarget | null>(null)

  const showDeleteSessionConfirm = ref(false)
  const sessionToDelete = ref<PortalDeleteTarget | null>(null)

  const showImportConfirm = ref(false)
  const showImportWarning = ref(false)
  const importWarningType = ref<PortalImportWarningType>('defaults')
  const importConflicts = ref<PortalConflictEntry[]>([])

  /** Opens template deletion confirmation with selected template context. */
  function openTemplateDeleteConfirm(templateId: string, title: string) {
    templateToDelete.value = { id: templateId, title }
    showDeleteConfirm.value = true
  }

  /** Closes template deletion confirmation and resets selected template. */
  function closeTemplateDeleteConfirm() {
    showDeleteConfirm.value = false
    templateToDelete.value = null
  }

  /** Opens session deletion confirmation with selected session context. */
  function openSessionDeleteConfirm(gameId: string, title: string) {
    sessionToDelete.value = { id: gameId, title }
    showDeleteSessionConfirm.value = true
  }

  /** Closes session deletion confirmation and resets selected session. */
  function closeSessionDeleteConfirm() {
    showDeleteSessionConfirm.value = false
    sessionToDelete.value = null
  }

  /** Opens the examples import confirmation dialog. */
  function openImportExamplesConfirm() {
    showImportConfirm.value = true
  }

  /** Closes the examples import confirmation dialog. */
  function closeImportExamplesConfirm() {
    showImportConfirm.value = false
  }

  function openImportWarning(
    type: PortalImportWarningType,
    conflicts: PortalConflictEntry[],
  ) {
    importWarningType.value = type
    importConflicts.value = conflicts
    showImportWarning.value = true
  }

  /** Closes import warning dialog while keeping current warning payload. */
  function closeImportWarning() {
    showImportWarning.value = false
  }

  return {
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
  }
}
