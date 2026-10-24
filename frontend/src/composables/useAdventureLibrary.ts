import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { adventureLibraryService } from '@/services/adventureLibrary'
import type { AdventureCatalogResponse, AdventureLibraryItem } from '@/types/adventureLibrary'

/** What the locked dialog is busy with; `null` while it is idle. */
export interface AdventureInstallStatus {
  phase: 'installing' | 'refreshing'
  title: string
  current: number
  total: number
}

export interface UseAdventureLibraryOptions {
  /** Runs after the last install, while the dialog is still locked (e.g. reload the portal). */
  onInstalled?: () => Promise<void>
}

export interface UseAdventureLibraryResult {
  isOpen: Ref<boolean>
  items: Ref<AdventureLibraryItem[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  staleCatalog: Ref<boolean>
  selectedIds: Ref<Set<string>>
  selectedCount: ComputedRef<number>
  selectedTotalBytes: ComputedRef<number>
  catalogTotalBytes: ComputedRef<number>
  allSelectableSelected: ComputedRef<boolean>
  installErrors: Ref<string[]>
  installingId: Ref<string | null>
  installStatus: Ref<AdventureInstallStatus | null>
  isSubmitting: Ref<boolean>
  openDialog: () => Promise<void>
  closeDialog: () => void
  load: () => Promise<void>
  refresh: () => Promise<void>
  isSelectable: (item: AdventureLibraryItem) => boolean
  isSelected: (id: string) => boolean
  toggle: (id: string) => void
  selectAll: () => void
  clearSelection: () => void
  downloadSelected: () => Promise<void>
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

/** Owns the adventure library dialog: catalog, selection and sequential installs. */
export function useAdventureLibrary(options: UseAdventureLibraryOptions = {}): UseAdventureLibraryResult {
  const isOpen = ref(false)
  const items = ref<AdventureLibraryItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const staleCatalog = ref(false)
  const selectedIds = ref<Set<string>>(new Set())
  const isSubmitting = ref(false)
  const installingId = ref<string | null>(null)
  const installErrors = ref<string[]>([])
  const installStatus = ref<AdventureInstallStatus | null>(null)

  const selectedItems = computed(() => items.value.filter((item) => selectedIds.value.has(item.entry.id)))
  const selectedCount = computed(() => selectedItems.value.length)
  const selectedTotalBytes = computed(() => selectedItems.value.reduce((sum, item) => sum + item.entry.size_bytes, 0))
  const catalogTotalBytes = computed(() => items.value.reduce((sum, item) => sum + item.entry.size_bytes, 0))
  const selectableItems = computed(() => items.value.filter(isSelectable))
  const allSelectableSelected = computed(
    () => selectableItems.value.length > 0 && selectableItems.value.every((item) => selectedIds.value.has(item.entry.id)),
  )

  /** Single selection rule, shared by `selectAll()` and the card checkboxes. */
  function isSelectable(item: AdventureLibraryItem): boolean {
    return !isSubmitting.value && item.installed_version !== item.entry.version
  }

  function isSelected(id: string): boolean {
    return selectedIds.value.has(id)
  }

  function toggle(id: string) {
    const item = items.value.find((candidate) => candidate.entry.id === id)
    const next = new Set(selectedIds.value)
    if (next.has(id)) {
      next.delete(id)
    } else if (item && isSelectable(item)) {
      next.add(id)
    }
    selectedIds.value = next
  }

  function selectAll() {
    selectedIds.value = new Set(selectableItems.value.map((item) => item.entry.id))
  }

  function clearSelection() {
    selectedIds.value = new Set()
  }

  function applyCatalog(response: AdventureCatalogResponse) {
    items.value = response.items
    staleCatalog.value = response.stale
    // Drop selections that are no longer selectable (installed meanwhile, removed).
    const selectable = new Set(selectableItems.value.map((item) => item.entry.id))
    selectedIds.value = new Set([...selectedIds.value].filter((id) => selectable.has(id)))
  }

  async function fetchInto(fetcher: () => Promise<AdventureCatalogResponse>, fallback: string) {
    loading.value = true
    try {
      applyCatalog(await fetcher())
    } catch (err) {
      error.value = errorMessage(err, fallback)
    } finally {
      loading.value = false
    }
  }

  function load(): Promise<void> {
    return fetchInto(adventureLibraryService.fetchCatalog, 'Failed to load the adventure catalog.')
  }

  function refresh(): Promise<void> {
    error.value = null
    return fetchInto(adventureLibraryService.refreshCatalog, 'Failed to refresh the adventure catalog.')
  }

  /** Installs one adventure; returns false and records the message when it fails. */
  async function installOne(item: AdventureLibraryItem): Promise<boolean> {
    try {
      await adventureLibraryService.install(item.entry.id)
      return true
    } catch (err) {
      installErrors.value = [...installErrors.value, `${item.entry.title}: ${errorMessage(err, 'Install failed.')}`]
      return false
    }
  }

  /** Lets the caller catch up (e.g. reload the portal) before the dialog unlocks. */
  async function notifyInstalled() {
    if (!options.onInstalled) {
      return
    }
    installStatus.value = { phase: 'refreshing', title: '', current: 0, total: 0 }
    try {
      await options.onInstalled()
    } catch (err) {
      console.error('[AdventureLibrary] Refresh after install failed', err)
    }
  }

  /**
   * Installs the selection one adventure at a time; a failure does not stop the rest.
   * The dialog stays locked until the imports are visible: in the catalog view and,
   * through `onInstalled`, wherever the caller lists adventures.
   */
  async function downloadSelected() {
    const queue = selectedItems.value.filter(isSelectable)
    if (queue.length === 0 || isSubmitting.value) {
      return
    }
    error.value = null
    installErrors.value = []
    isSubmitting.value = true
    try {
      let installed = 0
      for (const [index, item] of queue.entries()) {
        installingId.value = item.entry.id
        installStatus.value = { phase: 'installing', title: item.entry.title, current: index + 1, total: queue.length }
        installed += (await installOne(item)) ? 1 : 0
      }
      installingId.value = null
      clearSelection()
      if (installed > 0) {
        await notifyInstalled()
      }
      // Reload so `installed_version` reflects the imports.
      await load()
    } finally {
      installingId.value = null
      installStatus.value = null
      isSubmitting.value = false
    }
  }

  async function openDialog() {
    isOpen.value = true
    error.value = null
    await load()
  }

  /** Closes the dialog; ignored while an install is running (the dialog is locked). */
  function closeDialog() {
    if (isSubmitting.value) {
      return
    }
    isOpen.value = false
  }

  return {
    isOpen,
    items,
    loading,
    error,
    staleCatalog,
    selectedIds,
    selectedCount,
    selectedTotalBytes,
    catalogTotalBytes,
    allSelectableSelected,
    installErrors,
    installingId,
    installStatus,
    isSubmitting,
    openDialog,
    closeDialog,
    load,
    refresh,
    isSelectable,
    isSelected,
    toggle,
    selectAll,
    clearSelection,
    downloadSelected,
  }
}
