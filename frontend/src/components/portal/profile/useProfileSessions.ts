import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import {
  api,
  type PlayerSessionCounts,
  type PlayerSessionSort,
  type PlayerSessionStatus,
  type PlayerSessionSummary,
} from '@/composables/useApi'
import type { SessionFilter } from './sessionStatus'

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 300

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback
}

function emptyCounts(): PlayerSessionCounts {
  return { all: 0, active: 0, completed: 0, game_over: 0, archived: 0 }
}

export interface ProfileSessions {
  items: Ref<PlayerSessionSummary[]>
  total: Ref<number>
  counts: Ref<PlayerSessionCounts>
  totals: Ref<PlayerSessionCounts>
  filter: Ref<SessionFilter>
  search: Ref<string>
  sort: Ref<PlayerSessionSort>
  isLoading: Ref<boolean>
  isLoadingMore: Ref<boolean>
  error: Ref<string>
  hasMore: ComputedRef<boolean>
  reload: () => Promise<void>
  loadMore: () => Promise<void>
}

/**
 * Server-side paged adventure history: filters, search and sort run in the backend, so
 * the profile only ever holds the pages the player actually scrolled to.
 */
export function useProfileSessions(): ProfileSessions {
  const items = ref<PlayerSessionSummary[]>([])
  const total = ref(0)
  const counts = ref<PlayerSessionCounts>(emptyCounts())
  const totals = ref<PlayerSessionCounts>(emptyCounts())

  const filter = ref<SessionFilter>('all')
  const search = ref('')
  const sort = ref<PlayerSessionSort>('recent')

  const isLoading = ref(true)
  const isLoadingMore = ref(false)
  const error = ref('')

  // Responses of superseded requests (fast typing, filter clicks) are dropped.
  let requestId = 0
  let searchTimer: ReturnType<typeof setTimeout> | undefined

  const hasMore = computed(() => items.value.length < total.value)

  async function fetchPage(offset: number): Promise<PlayerSessionSummary[] | null> {
    const current = ++requestId
    const page = await api.getMySessions({
      status: filter.value === 'all' ? null : (filter.value as PlayerSessionStatus),
      search: search.value,
      sort: sort.value,
      limit: PAGE_SIZE,
      offset,
    })
    if (current !== requestId) return null
    total.value = page.total
    counts.value = page.counts
    totals.value = page.totals
    return page.items
  }

  async function reload(): Promise<void> {
    isLoading.value = true
    error.value = ''
    try {
      const page = await fetchPage(0)
      if (page) items.value = page
    } catch (err: unknown) {
      error.value = errorMessage(err, 'Failed to load your adventures.')
    } finally {
      isLoading.value = false
    }
  }

  async function loadMore(): Promise<void> {
    if (!hasMore.value || isLoadingMore.value) return
    isLoadingMore.value = true
    try {
      const page = await fetchPage(items.value.length)
      if (page) items.value = [...items.value, ...page]
    } catch (err: unknown) {
      error.value = errorMessage(err, 'Failed to load more adventures.')
    } finally {
      isLoadingMore.value = false
    }
  }

  watch([filter, sort], () => { void reload() })
  watch(search, () => {
    clearTimeout(searchTimer)
    searchTimer = setTimeout(() => { void reload() }, SEARCH_DEBOUNCE_MS)
  })

  return {
    items, total, counts, totals, filter, search, sort,
    isLoading, isLoadingMore, error, hasMore,
    reload, loadMore,
  }
}
