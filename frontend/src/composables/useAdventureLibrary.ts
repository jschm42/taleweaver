import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { adventureLibraryService } from '@/services/adventureLibrary'
import type { AdventureCatalogResponse, AdventureLibraryItem } from '@/types/adventureLibrary'

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
export function useAdventureLibrary(): UseAdventureLibraryResult {
  const isOpen = ref(false)
  const items = ref<AdventureLibraryItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const staleCatalog = ref(false)
  const selectedIds = ref<Set<string>>(new Set())
  const isSubmitting = ref(false)
  const installingId = ref<string | null>(null)
  const installErrors = ref<string[]>([])

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

  /** Installs the selection one adventure at a time; a failure does not stop the rest. */
  async function downloadSelected() {
    const queue = selectedItems.value.filter(isSelectable)
    if (queue.length === 0 || isSubmitting.value) {
      return
    }
    error.value = null
    installErrors.value = []
    isSubmitting.value = true
    try {
      for (const item of queue) {
        installingId.value = item.entry.id
        try {
          await adventureLibraryService.install(item.entry.id)
        } catch (err) {
          installErrors.value = [...installErrors.value, `${item.entry.title}: ${errorMessage(err, 'Install failed.')}`]
        }
      }
    } finally {
      installingId.value = null
      isSubmitting.value = false
    }
    clearSelection()
    // Reload so `installed_version` reflects the imports.
    await load()
  }

  async function openDialog() {
    isOpen.value = true
    error.value = null
    await load()
  }

  /** Closes the dialog; an install already sent keeps running on the server. */
  function closeDialog() {
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
