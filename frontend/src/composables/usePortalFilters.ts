import { ref, computed, watch, type Ref, type ComputedRef } from 'vue'
import type { AdventureTemplateSummary, GameSession, CatalogTile } from '@/types'

export type PortalSectionType = 'templates' | 'sessions'
export type RuleTypeFilter = 'all' | 'rpg' | 'story' | 'chat'
export type ViewMode = 'grid' | 'table'

export interface PortalFilterOptions {
  searchQuery: string
  selectedType: RuleTypeFilter
  selectedTone: string
  selectedStyle: string
}

export interface UsePortalFiltersResult<T> {
  searchQuery: Ref<string>
  selectedType: Ref<RuleTypeFilter>
  selectedTone: Ref<string>
  selectedStyle: Ref<string>
  viewMode: Ref<ViewMode>
  displayedCount: Ref<number>
  pageSize: number
  filteredItems: ComputedRef<T[]>
  paginatedItems: ComputedRef<T[]>
  hasMore: ComputedRef<boolean>
  isFiltered: ComputedRef<boolean>
  totalCount: ComputedRef<number>
  filteredCount: ComputedRef<number>
  loadMore: () => void
  resetFilters: () => void
}

export function formatCatalogLabel(val?: unknown): string {
  if (!val) return ''
  let text = ''

  if (typeof val === 'object' && val !== null) {
    const obj = val as Record<string, unknown>
    text = String(obj.name || obj.id || '')
  } else {
    text = String(val)
    if (text.startsWith('{')) {
      try {
        const obj = JSON.parse(text) as Record<string, unknown>
        text = String(obj.name || obj.id || text)
      } catch {
        // ignore parse error
      }
    }
  }

  const cleaned = text.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim()
  if (!cleaned) return ''
  return cleaned.replace(/\b\w/g, (ch) => ch.toUpperCase())
}

export function extractToneId(val?: unknown): string {
  if (!val) return ''
  if (typeof val === 'object' && val !== null) {
    const obj = val as Record<string, unknown>
    return String(obj.id || obj.name || '').trim().toLowerCase()
  }
  const s = String(val).trim()
  if (s.startsWith('{')) {
    try {
      const obj = JSON.parse(s) as Record<string, unknown>
      return String(obj.id || obj.name || '').trim().toLowerCase()
    } catch {
      // ignore
    }
  }
  return s.toLowerCase()
}

export function extractStyleIds(styles?: unknown): string[] {
  if (!styles || !Array.isArray(styles)) return []
  return styles
    .map((item) => {
      if (!item) return ''
      if (typeof item === 'object') {
        const obj = item as Record<string, unknown>
        return String(obj.id || obj.name || '').trim().toLowerCase()
      }
      return String(item).trim().toLowerCase()
    })
    .filter(Boolean)
}

export function extractAvailableTones(
  templates: AdventureTemplateSummary[],
  sessions: GameSession[],
  catalogTones: CatalogTile[] = []
): Array<{ id: string; name: string }> {
  const map = new Map<string, string>()

  for (const cat of catalogTones) {
    if (cat.id) {
      map.set(cat.id.toLowerCase(), cat.name || formatCatalogLabel(cat.id))
    }
  }

  for (const t of templates) {
    const id = extractToneId(t.selected_tone)
    if (id && !map.has(id)) {
      map.set(id, formatCatalogLabel(t.selected_tone) || formatCatalogLabel(id))
    }
  }

  for (const s of sessions) {
    const id = extractToneId(s.selected_tone)
    if (id && !map.has(id)) {
      map.set(id, formatCatalogLabel(s.selected_tone) || formatCatalogLabel(id))
    }
  }

  return Array.from(map.entries())
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

export function extractAvailableStyles(
  templates: AdventureTemplateSummary[],
  sessions: GameSession[],
  catalogStyles: CatalogTile[] = []
): Array<{ id: string; name: string }> {
  const map = new Map<string, string>()

  for (const cat of catalogStyles) {
    if (cat.id) {
      map.set(cat.id.toLowerCase(), cat.name || formatCatalogLabel(cat.id))
    }
  }

  for (const t of templates) {
    const ids = extractStyleIds(t.selected_image_styles)
    for (const id of ids) {
      if (!map.has(id)) {
        map.set(id, formatCatalogLabel(id))
      }
    }
  }

  for (const s of sessions) {
    const ids = extractStyleIds(s.selected_image_styles)
    for (const id of ids) {
      if (!map.has(id)) {
        map.set(id, formatCatalogLabel(id))
      }
    }
  }

  return Array.from(map.entries())
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

export function usePortalFilters<T extends AdventureTemplateSummary | GameSession>(
  items: Ref<T[]> | ComputedRef<T[]>,
  section: PortalSectionType,
  pageSize = 18
): UsePortalFiltersResult<T> {
  const filterStorageKey = `tw_portal_filters_${section}`
  const viewModeStorageKey = `tw_portal_view_mode_${section}`

  // Load saved filter options
  let initialFilters: PortalFilterOptions = {
    searchQuery: '',
    selectedType: 'all',
    selectedTone: 'all',
    selectedStyle: 'all',
  }

  try {
    const savedFiltersRaw = localStorage.getItem(filterStorageKey)
    if (savedFiltersRaw) {
      const parsed = JSON.parse(savedFiltersRaw)
      initialFilters = {
        searchQuery: typeof parsed.searchQuery === 'string' ? parsed.searchQuery : '',
        selectedType: ['all', 'rpg', 'story', 'chat'].includes(parsed.selectedType)
          ? parsed.selectedType
          : 'all',
        selectedTone: typeof parsed.selectedTone === 'string' ? parsed.selectedTone : 'all',
        selectedStyle: typeof parsed.selectedStyle === 'string' ? parsed.selectedStyle : 'all',
      }
    }
  } catch (err) {
    console.warn(`[PortalFilters] Failed to parse saved filters for ${section}:`, err)
  }

  // Load saved view mode
  let initialViewMode: ViewMode = 'grid'
  try {
    const savedMode = localStorage.getItem(viewModeStorageKey)
    if (savedMode === 'grid' || savedMode === 'table') {
      initialViewMode = savedMode
    }
  } catch (err) {
    console.warn(`[PortalFilters] Failed to parse view mode for ${section}:`, err)
  }

  const searchQuery = ref(initialFilters.searchQuery)
  const selectedType = ref<RuleTypeFilter>(initialFilters.selectedType)
  const selectedTone = ref(initialFilters.selectedTone)
  const selectedStyle = ref(initialFilters.selectedStyle)
  const viewMode = ref<ViewMode>(initialViewMode)
  const displayedCount = ref(pageSize)

  // Persist view mode changes
  watch(viewMode, (mode) => {
    try {
      localStorage.setItem(viewModeStorageKey, mode)
    } catch (err) {
      console.warn(`[PortalFilters] Failed to save view mode for ${section}:`, err)
    }
  })

  // Persist filter changes
  watch(
    [searchQuery, selectedType, selectedTone, selectedStyle],
    ([query, type, tone, style]) => {
      try {
        const payload: PortalFilterOptions = {
          searchQuery: query,
          selectedType: type,
          selectedTone: tone,
          selectedStyle: style,
        }
        localStorage.setItem(filterStorageKey, JSON.stringify(payload))
      } catch (err) {
        console.warn(`[PortalFilters] Failed to save filters for ${section}:`, err)
      }
      // Reset displayed count on filter changes
      displayedCount.value = pageSize
    }
  )

  const isFiltered = computed(() => {
    return (
      searchQuery.value.trim().length > 0 ||
      selectedType.value !== 'all' ||
      selectedTone.value !== 'all' ||
      selectedStyle.value !== 'all'
    )
  })

  const filteredItems = computed(() => {
    const query = searchQuery.value.trim().toLowerCase()
    const typeFilter = selectedType.value
    const toneFilter = selectedTone.value.toLowerCase()
    const styleFilter = selectedStyle.value.toLowerCase()

    return items.value.filter((item) => {
      // 1. Name / text search
      if (query) {
        const title = ((item as AdventureTemplateSummary).title || (item as GameSession).adventure_title || '').toLowerCase()
        const teaser = ((item as AdventureTemplateSummary).teaser || '').toLowerCase()
        const creator = ((item as AdventureTemplateSummary).creator || (item as GameSession).creator || '').toLowerCase()
        const sceneName = ((item as GameSession).current_scene_name || (item as AdventureTemplateSummary).current_scene_name || '').toLowerCase()
        const note = ((item as GameSession).status_note || '').toLowerCase()

        const matchesQuery =
          title.includes(query) ||
          teaser.includes(query) ||
          creator.includes(query) ||
          sceneName.includes(query) ||
          note.includes(query)

        if (!matchesQuery) return false
      }

      // 2. Type (rule enforcement mode: rpg, story, chat)
      if (typeFilter !== 'all') {
        let rawMode = (item.rule_enforcement_mode || 'rpg').toLowerCase()
        if (rawMode === 'strict') rawMode = 'rpg'
        if (rawMode !== typeFilter) return false
      }

      // 3. Tone
      if (toneFilter !== 'all') {
        const itemTone = extractToneId(item.selected_tone)
        if (itemTone !== toneFilter) return false
      }

      // 4. Style
      if (styleFilter !== 'all') {
        const itemStyles = extractStyleIds(item.selected_image_styles)
        if (!itemStyles.includes(styleFilter)) return false
      }

      return true
    })
  })

  const paginatedItems = computed(() => {
    return filteredItems.value.slice(0, displayedCount.value)
  })

  const hasMore = computed(() => {
    return displayedCount.value < filteredItems.value.length
  })

  const totalCount = computed(() => items.value.length)
  const filteredCount = computed(() => filteredItems.value.length)

  function loadMore() {
    if (hasMore.value) {
      displayedCount.value += pageSize
    }
  }

  function resetFilters() {
    searchQuery.value = ''
    selectedType.value = 'all'
    selectedTone.value = 'all'
    selectedStyle.value = 'all'
    displayedCount.value = pageSize
  }

  return {
    searchQuery,
    selectedType,
    selectedTone,
    selectedStyle,
    viewMode,
    displayedCount,
    pageSize,
    filteredItems,
    paginatedItems,
    hasMore,
    isFiltered,
    totalCount,
    filteredCount,
    loadMore,
    resetFilters,
  }
}
