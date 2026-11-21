/**
 * World sections (regions) of an adventure: the editor's section list and scene assignment.
 * Spec: docs/specs/world_sections.md.
 */
import { API_BASE, authHeaders } from '@/services/http'

export type SectionStatus = 'built' | 'stub' | 'generating'

export interface PlannedLink {
  to_section_id: string
  travel_minutes: number | null
  note: string
}

export interface WorldSection {
  id: string
  label: string
  description: string
  map_x: number
  map_y: number
  order_index: number
  status: SectionStatus
  brief: string
  summary: string
  planned_links: PlannedLink[]
  /** Why the last generation of a planned region failed ("" = none). */
  generation_error?: string
  /** What to check after a generation: fix-ups and new validation findings. */
  generation_notes?: string[]
}

export interface OutlineSection {
  id: string
  purpose: string
  gating: string
  plants: string[]
  resolves: string[]
}

export interface OutlineThread {
  id: string
  opened_in: string | null
  resolved_in: string | null
  status: 'open' | 'resolved'
  note: string
}

/** The campaign outline that region generation follows (AdventureTemplate.world_outline). */
export interface WorldOutline {
  premise: string
  arc: string[]
  sections: OutlineSection[]
  threads: OutlineThread[]
}

export interface RegionPlan {
  outline: WorldOutline | null
  sections: WorldSection[]
}

export function emptyOutline(): WorldOutline {
  return { premise: '', arc: [], sections: [], threads: [] }
}

/** The outline as the editor payload holds it (adventure.world_outline). */
export function outlineOf(adventure: Record<string, unknown> | null | undefined): WorldOutline {
  const raw = adventure?.world_outline as Partial<WorldOutline> | null | undefined
  return { ...emptyOutline(), ...(raw || {}) }
}

export interface SectionAssignResult {
  section_id: string | null
  scene_ids: string[]
  sections: WorldSection[]
}

async function failure(res: Response, fallback: string): Promise<Error> {
  const data = await res.json().catch(() => ({}))
  return new Error(typeof data.detail === 'string' ? data.detail : fallback)
}

/** The section list as the editor payload holds it (adventure.world_sections). */
export function sectionsOf(adventure: Record<string, unknown> | null | undefined): WorldSection[] {
  const raw = adventure?.world_sections
  return Array.isArray(raw) ? (raw as WorldSection[]) : []
}

export const sectionService = {
  /** Replaces the section list; scenes of deleted sections lose their section. */
  async saveSections(adventureId: string, sections: WorldSection[]): Promise<{ sections: WorldSection[]; cleared_scene_ids: string[] }> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections`, {
      method: 'PUT',
      headers: authHeaders(true),
      body: JSON.stringify({ sections }),
    })
    if (!res.ok) throw await failure(res, 'Failed to save the regions.')
    return await res.json()
  },

  /** Stores the campaign outline (null clears it). */
  async saveOutline(adventureId: string, outline: WorldOutline | null): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}`, {
      method: 'PATCH',
      headers: authHeaders(true),
      body: JSON.stringify({ world_outline: outline }),
    })
    if (!res.ok) throw await failure(res, 'Failed to save the campaign outline.')
  },

  /** Starts building a planned region in the background; poll the editor assets for the result. */
  async generateSection(adventureId: string, sectionId: string, brief: string): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/${encodeURIComponent(sectionId)}/generate`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({ brief }),
    })
    if (!res.ok) throw await failure(res, 'Failed to start the region generation.')
  },

  /** A proposal of planned regions and an outline from the World-Builder (nothing is stored). */
  async planSections(adventureId: string, count: number, direction: string): Promise<RegionPlan> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/plan`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({ count, direction }),
    })
    if (!res.ok) throw await failure(res, 'Failed to plan the regions.')
    return await res.json()
  },

  /** Moves scenes into a section (a planned one becomes built), or out of all with null. */
  async assignScenes(adventureId: string, sectionId: string | null, sceneIds: string[]): Promise<SectionAssignResult> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/assign`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify({ section_id: sectionId, scene_ids: sceneIds }),
    })
    if (!res.ok) throw await failure(res, 'Failed to move the scenes.')
    return await res.json()
  },
}
