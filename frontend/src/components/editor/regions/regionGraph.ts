/**
 * Pure helpers for the editor's region views: which scenes belong to which region, and the
 * links between regions (exits whose two scenes lie in different regions, plus the planned
 * links of planned regions). Spec: docs/specs/world_sections.md.
 */
import type { WorldSection } from '@/services/sectionService'

export interface RegionLink {
  from: string
  to: string
  /** true: only planned (a planned region has no exits yet). */
  planned: boolean
  travelMinutes: number | null
}

interface SceneLike {
  id?: string
  section_id?: string | null
}

interface ExitLike {
  from_scene_id?: string
  to_scene_id?: string
}

/** "UNASSIGNED" filter key for scenes without a region. */
export const UNASSIGNED = '__unassigned__'

export function sceneSections(scenes: SceneLike[]): Map<string, string | null> {
  return new Map(scenes.filter((s) => s.id).map((s) => [String(s.id), s.section_id || null]))
}

export function sceneCount(scenes: SceneLike[], sectionId: string): number {
  return scenes.filter((s) => (s.section_id || null) === sectionId).length
}

function pairKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`
}

/** One link per region pair: built ones from exits, planned ones from the planned links. */
export function regionLinks(sections: WorldSection[], scenes: SceneLike[], exits: ExitLike[]): RegionLink[] {
  const bySceneId = sceneSections(scenes)
  const links = new Map<string, RegionLink>()
  for (const exit of exits) {
    const a = bySceneId.get(String(exit.from_scene_id || ''))
    const b = bySceneId.get(String(exit.to_scene_id || ''))
    if (!a || !b || a === b) continue
    links.set(pairKey(a, b), { from: a, to: b, planned: false, travelMinutes: null })
  }
  for (const section of sections) {
    for (const link of section.planned_links || []) {
      const key = pairKey(section.id, link.to_section_id)
      if (!links.has(key)) {
        links.set(key, { from: section.id, to: link.to_section_id, planned: true, travelMinutes: link.travel_minutes })
      }
    }
  }
  return [...links.values()]
}

/**
 * The scenes the map shows for a region filter: the region's scenes plus the scenes one exit
 * away (shown dimmed as the way out). An empty filter shows everything.
 */
export function regionSceneIds(filter: string, scenes: SceneLike[], exits: ExitLike[]): { inside: Set<string>; border: Set<string> } | null {
  if (!filter) return null
  const wanted = filter === UNASSIGNED ? null : filter
  const inside = new Set(scenes.filter((s) => s.id && (s.section_id || null) === wanted).map((s) => String(s.id)))
  const border = new Set<string>()
  for (const exit of exits) {
    const from = String(exit.from_scene_id || '')
    const to = String(exit.to_scene_id || '')
    if (inside.has(from) && !inside.has(to)) border.add(to)
    if (inside.has(to) && !inside.has(from)) border.add(from)
  }
  return { inside, border }
}

/** A new region id from a label: "Harbor Town" -> HARBOR_TOWN, unique among `taken`. */
export function regionIdFor(label: string, taken: Set<string>): string {
  const base = label.toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 44) || 'REGION'
  let id = base
  for (let n = 2; taken.has(id); n += 1) id = `${base}_${n}`
  return id
}

export function formatTravel(minutes: number | null | undefined): string {
  if (!minutes) return ''
  if (minutes < 60) return `${minutes} min`
  const hours = minutes / 60
  return Number.isInteger(hours) ? `${hours} h` : `${hours.toFixed(1)} h`
}
