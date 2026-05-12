import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { api } from '@/composables/useApi'
import type { AdventureTemplateSummary, GameSession } from '@/types'

interface PendingAdventureState {
  adventureId: string
  title: string
  status: string
  hasError: boolean
}

type PendingCard = PendingAdventureState & { kind: 'creation' | 'import' }

type PendingAdventureCollection = { value: PendingAdventureState[] }

interface PollAdventureOptions {
  onStatus?: (status: string) => void
  onReady?: () => void | Promise<void>
  onFailure?: (status: string) => void
}

export interface UsePortalPendingStateResult {
  loadingWordIndex: Ref<number>
  pendingCards: ComputedRef<PendingCard[]>
  visibleTemplates: ComputedRef<AdventureTemplateSummary[]>
  addPendingImportCard: (adventureId: string, title: string) => void
  updatePendingImportStatus: (adventureId: string, status: string, hasError?: boolean) => void
  removePendingImportCard: (adventureId: string) => void
  syncPendingFromTemplates: (refreshPortalData: () => Promise<void>) => Promise<void>
  removeFailedPendingCard: (adventureId: string, kind: 'creation' | 'import') => Promise<void>
  cancelAdventure: (adventureId: string) => Promise<void>
  trackNewAdventure: (adventureId: string, title: string, refreshPortalData: () => Promise<void>) => void
  startLoadingWords: () => void
  stopLoadingWords: () => void
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

export function usePortalPendingState(
  templates: Ref<AdventureTemplateSummary[]>,
  sessions: Ref<GameSession[]>,
): UsePortalPendingStateResult {
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

  function upsertPendingCard(
    collection: PendingAdventureCollection,
    adventureId: string,
    title: string,
    initialStatus: string,
  ) {
    collection.value = [
      ...collection.value.filter((entry) => entry.adventureId !== adventureId),
      {
        adventureId,
        title,
        status: initialStatus,
        hasError: false,
      },
    ]
  }

  function updatePendingCardStatus(
    collection: PendingAdventureCollection,
    adventureId: string,
    status: string,
    hasError = false,
  ) {
    collection.value = collection.value.map((entry) =>
      entry.adventureId === adventureId
        ? {
            ...entry,
            status: prettifyStatus(status),
            hasError,
          }
        : entry,
    )
  }

  function removePendingCard(collection: PendingAdventureCollection, adventureId: string) {
    collection.value = collection.value.filter((entry) => entry.adventureId !== adventureId)
  }

  function addPendingImportCard(adventureId: string, title: string) {
    upsertPendingCard(pendingImports, adventureId, title, 'Import started')
  }

  function updatePendingImportStatus(adventureId: string, status: string, hasError = false) {
    updatePendingCardStatus(pendingImports, adventureId, status, hasError)
  }

  function removePendingImportCard(adventureId: string) {
    removePendingCard(pendingImports, adventureId)
  }

  function addPendingCreationCard(adventureId: string, title: string) {
    upsertPendingCard(pendingCreations, adventureId, title, 'Starting generation...')
  }

  function updatePendingCreationStatus(adventureId: string, status: string, hasError = false) {
    updatePendingCardStatus(pendingCreations, adventureId, status, hasError)
  }

  function removePendingCreationCard(adventureId: string) {
    removePendingCard(pendingCreations, adventureId)
  }

  async function pollAdventureStatus(adventureId: string, options?: PollAdventureOptions) {
    return new Promise<void>((resolve) => {
      const pollInterval = setInterval(async () => {
        try {
          const data = await api.getAdventureStatus(adventureId)
          const statusText = data.status || 'Constructing world...'
          options?.onStatus?.(statusText)

          if (isFailureStatus(statusText) || (data.error && !data.error.startsWith('Notice:'))) {
            clearInterval(pollInterval)
            const detail = data.error || statusText || 'Generation failed.'
            options?.onFailure?.(detail)
            resolve()
            return
          }

          if (data.is_ready) {
            clearInterval(pollInterval)
            await options?.onReady?.()
            resolve()
          }
        } catch (err: unknown) {
          // Stop polling only when the adventure was explicitly deleted (404).
          // For transient network errors, keep retrying on the next tick.
          const isNotFound =
            err instanceof Error && err.message.startsWith('API 404')
          if (isNotFound) {
            clearInterval(pollInterval)
            options?.onFailure?.('Adventure not found')
            resolve()
          }
        }
      }, 1500)
    })
  }

  /** Creates background polling for all non-ready templates currently loaded. */
  async function syncPendingFromTemplates(refreshPortalData: () => Promise<void>) {
    for (const template of templates.value) {
      if (!template.is_ready) {
        const isAlreadyPending = pendingCreations.value.some((pending) => pending.adventureId === template.template_id)
        if (!isAlreadyPending) {
          addPendingCreationCard(template.template_id, template.title)
          updatePendingCreationStatus(
            template.template_id,
            template.creation_error || template.creation_status || 'Preparing...',
            (Boolean(template.creation_error) && !template.creation_error?.startsWith('Notice:')) ||
              isFailureStatus(template.creation_status || ''),
          )

          void pollAdventureStatus(template.template_id, {
            onStatus: (status: string) => updatePendingCreationStatus(template.template_id, status),
            onReady: async () => {
              removePendingCreationCard(template.template_id)
              await refreshPortalData()
            },
            onFailure: (status: string) => updatePendingCreationStatus(template.template_id, status, true),
          })
        }
      } else {
        removePendingCreationCard(template.template_id)
      }
    }
  }

  /** Removes a failed pending card and cleans up persisted adventure data when applicable. */
  async function removeFailedPendingCard(adventureId: string, kind: 'creation' | 'import') {
    const isTemporaryImport =
      kind === 'import' && (adventureId.startsWith('adv-import-') || adventureId.startsWith('adz-import-'))

    try {
      if (!isTemporaryImport) {
        await api.deleteAdventure(adventureId)
        templates.value = templates.value.filter((entry) => entry.template_id !== adventureId)
        sessions.value = sessions.value.filter((entry) => (entry.template_id || entry.adventure_id) !== adventureId)
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

  /** Requests backend cancellation for an in-progress adventure generation. */
  async function cancelAdventure(adventureId: string) {
    try {
      await api.cancelAdventure(adventureId)
      updatePendingCreationStatus(adventureId, 'Cancelled', true)
    } catch (error) {
      console.error('Error cancelling adventure:', error)
    }
  }

  /** Starts tracking a newly created adventure until generation succeeds or fails. */
  function trackNewAdventure(adventureId: string, title: string, refreshPortalData: () => Promise<void>) {
    addPendingCreationCard(adventureId, title)
    updatePendingCreationStatus(adventureId, 'Starting generation...')

    void pollAdventureStatus(adventureId, {
      onStatus: (status: string) => updatePendingCreationStatus(adventureId, status || 'Preparing...'),
      onReady: async () => {
        removePendingCreationCard(adventureId)
        await refreshPortalData()
      },
      onFailure: (status: string) => updatePendingCreationStatus(adventureId, status || 'Generation failed', true),
    })
  }

  /** Starts the rotating loading word timer used by the portal UI. */
  function startLoadingWords() {
    loadingWordTimer = window.setInterval(() => {
      loadingWordIndex.value = (loadingWordIndex.value + 1) % loadingWords.length
    }, 1200)
  }

  /** Stops the rotating loading word timer. */
  function stopLoadingWords() {
    if (loadingWordTimer !== null) {
      clearInterval(loadingWordTimer)
      loadingWordTimer = null
    }
  }

  return {
    loadingWordIndex,
    pendingCards,
    visibleTemplates,
    addPendingImportCard,
    updatePendingImportStatus,
    removePendingImportCard,
    syncPendingFromTemplates,
    removeFailedPendingCard,
    cancelAdventure,
    trackNewAdventure,
    startLoadingWords,
    stopLoadingWords,
  }
}
