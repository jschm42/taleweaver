/**
 * Region and scene filter of the editor's lists (Scenes, Characters, Items). A list hands in
 * its entries per scene (`PlaceGroup`); the filter keeps one region (or the scenes without a
 * region) and, within that, one scene. Entries without a known scene form the `ELSEWHERE`
 * group, which only "All regions" shows. The choice per adventure and list survives a trip
 * to another page and back. Spec: docs/specs/world_sections.md.
 */
import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import type { WorldSection } from '@/services/sectionService'

export const ALL = ''
export const NO_REGION = '__none__'
export const ELSEWHERE = '__UNASSIGNED__'

/** The entries of one scene; `sceneId` null holds the entries without a known scene. */
export interface PlaceGroup {
  sceneId: string | null
  label: string
  count: number
}

export interface FilterOption {
  value: string
  label: string
}

export interface PlaceFilterSource {
  /** Key of the remembered choice, e.g. "items:<adventure id>". */
  memoryKey: () => string
  sections: () => WorldSection[]
  /** Region id of each scene id (null: no region). */
  sectionOfScene: () => Map<string, string | null>
  groups: () => PlaceGroup[]
}

export interface PlaceFilter {
  regionFilter: Ref<string>
  sceneFilter: Ref<string>
  hasRegions: ComputedRef<boolean>
  isActive: ComputedRef<boolean>
  regionOptions: ComputedRef<FilterOption[]>
  sceneOptions: ComputedRef<FilterOption[]>
  /** Whether the entries of this scene (null: no known scene) pass the filter. */
  matches: (sceneId: string | null | undefined) => boolean
  setRegion: (value: unknown) => void
  setScene: (value: unknown) => void
  clear: () => void
}

const lastChoice = new Map<string, { region: string; scene: string }>()

/** Group key of a scene id (scene ids are compared case-insensitively). */
export function placeKey(sceneId: string | null | undefined): string {
  const id = String(sceneId || '').trim().toUpperCase()
  return id || ELSEWHERE
}

export function usePlaceFilter(source: PlaceFilterSource): PlaceFilter {
  const saved = lastChoice.get(source.memoryKey())
  const regionFilter = ref<string>(saved?.region ?? ALL)
  const sceneFilter = ref<string>(saved?.scene ?? ALL)
  watch([regionFilter, sceneFilter], ([region, scene]) => lastChoice.set(source.memoryKey(), { region, scene }))

  const hasRegions = computed(() => source.sections().length > 0)
  const isActive = computed(() => Boolean(regionFilter.value || sceneFilter.value))

  const regionByKey = computed<Map<string, string | null>>(() => {
    const map = new Map<string, string | null>()
    for (const [sceneId, sectionId] of source.sectionOfScene()) map.set(placeKey(sceneId), sectionId)
    return map
  })

  function inRegion(sceneId: string | null | undefined, region: string): boolean {
    if (!hasRegions.value || region === ALL) return true
    const key = placeKey(sceneId)
    if (key === ELSEWHERE) return false
    const sectionId = regionByKey.value.get(key) ?? null
    return region === NO_REGION ? !sectionId : sectionId === region
  }

  const regionOptions = computed<FilterOption[]>(() => {
    const total = (region: string): number =>
      source.groups().filter((g) => inRegion(g.sceneId, region)).reduce((sum, g) => sum + g.count, 0)
    return [
      { value: ALL, label: `All regions (${total(ALL)})` },
      ...source.sections().map((s) => ({ value: s.id, label: `${s.label || s.id} (${total(s.id)})` })),
      { value: NO_REGION, label: `No region (${total(NO_REGION)})` },
    ]
  })

  const sceneOptions = computed<FilterOption[]>(() => [
    { value: ALL, label: 'All scenes' },
    ...source
      .groups()
      .filter((g) => g.count > 0 && inRegion(g.sceneId, regionFilter.value))
      .map((g) => ({ value: placeKey(g.sceneId), label: `${g.label} (${g.count})` })),
  ])

  // A choice that no longer exists (region deleted, scene outside the region) falls back to all;
  // not while the data is still loading.
  watch(regionOptions, (options) => {
    if (hasRegions.value && !options.some((o) => o.value === regionFilter.value)) regionFilter.value = ALL
  })
  watch(sceneOptions, (options) => {
    if (source.groups().length && !options.some((o) => o.value === sceneFilter.value)) sceneFilter.value = ALL
  })

  function matches(sceneId: string | null | undefined): boolean {
    if (!inRegion(sceneId, regionFilter.value)) return false
    return sceneFilter.value === ALL || sceneFilter.value === placeKey(sceneId)
  }

  function clear(): void {
    regionFilter.value = ALL
    sceneFilter.value = ALL
  }

  function setRegion(value: unknown): void {
    regionFilter.value = String(value ?? ALL)
  }

  function setScene(value: unknown): void {
    sceneFilter.value = String(value ?? ALL)
  }

  return { regionFilter, sceneFilter, hasRegions, isActive, regionOptions, sceneOptions, matches, setRegion, setScene, clear }
}

/** Region id per scene id, read from the editor's scene rows. */
export function sectionMapOf(scenes: { id?: string; section_id?: string | null }[] | null | undefined): Map<string, string | null> {
  return new Map((scenes || []).filter((s) => s?.id).map((s) => [String(s.id), s.section_id ?? null]))
}

/** One group per scene id the entries name, labelled with the scene's name; unknown scenes go to `ELSEWHERE`. */
export function groupsByScene(
  entries: { current_scene_id?: string | null }[],
  scenes: { id?: string; label?: string; name?: string }[] | null | undefined,
): PlaceGroup[] {
  const labels = new Map((scenes || []).filter((s) => s?.id).map((s) => [placeKey(s.id), String(s.name || s.label || s.id)]))
  const groups = new Map<string, PlaceGroup>()
  for (const entry of entries) {
    const key = labels.has(placeKey(entry.current_scene_id)) ? placeKey(entry.current_scene_id) : ELSEWHERE
    const group = groups.get(key) ?? { sceneId: key === ELSEWHERE ? null : String(entry.current_scene_id), label: labels.get(key) || 'Unassigned / elsewhere', count: 0 }
    group.count += 1
    groups.set(key, group)
  }
  return [...groups.values()]
}
