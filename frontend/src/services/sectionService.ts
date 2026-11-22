/**
 * World sections (regions) of an adventure: the editor's section list and scene assignment.
 * Spec: docs/specs/world_sections.md.
 */
import { API_BASE, authHeaders } from '@/services/http'
import type { StoredRegionSettings } from '@/composables/regionBuilder/regionBuilderForm'
import type { MapLayout } from '@/types'

export type SectionStatus = 'built' | 'stub' | 'generating'

export interface PlannedLink {
  to_section_id: string
  travel_minutes: number | null
  note: string
  /** Scenes of the target region a new region connects to first (Region Builder). */
  gateway_scene_ids?: string[]
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
  /** The Region Builder's last settings of this region (docs/specs/region_builder.md, 8.3). */
  generation_settings?: StoredRegionSettings | null
  /** What the Region Builder added; set only on regions it built (they can be discarded). */
  generated?: GeneratedRecord | null
}

export interface GeneratedRecord {
  scene_ids: string[]
  entity_ids: string[]
  quest_ids: string[]
  award_keys: string[]
  sequence_ids: string[]
  script_ids: string[]
}

export interface DiscardResult {
  status: string
  removed: Record<string, number>
}

/** One block of the region prompt as POST .../generate/preview reports it. */
export interface RegionPromptBlock {
  id: string
  tokens: number
  items: number
  empty: boolean
  always: boolean
  included: boolean
  detail: string
}

export interface BlueprintIssue {
  line: number
  message: string
  severity: 'error' | 'warning'
}

/** The region blueprint as the preview reports it (null for a plain-text idea). */
export interface RegionBlueprintReport {
  issues: BlueprintIssue[]
  kinds: Record<string, number>
}

export interface RegionPromptPreview {
  blocks: RegionPromptBlock[]
  total_tokens: number
  blueprint?: RegionBlueprintReport | null
  prompt?: string
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

export interface MapPromptInfo {
  prompt: string
  style: string
  tone: string
}

export interface MapTileOptions {
  col: number
  row: number
  prompt: string
  use_style: boolean
  use_tone: boolean
}

/** The layout as the editor payload holds it (adventure.world_map_layout). */
export function layoutOf(adventure: Record<string, unknown> | null | undefined): MapLayout | null {
  const raw = adventure?.world_map_layout as MapLayout | null | undefined
  return raw && Array.isArray(raw.tiles) ? raw : null
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

  /**
   * Starts building a planned region in the background; poll the editor assets for the result.
   * `body` is the Region Builder payload (brief, mode, context, options).
   */
  async generateSection(adventureId: string, sectionId: string, body: Record<string, unknown>): Promise<void> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/${encodeURIComponent(sectionId)}/generate`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(body),
    })
    if (!res.ok) throw await failure(res, 'Failed to start the region generation.')
  },

  /** Takes a region the Region Builder built out again; it becomes a planned region. */
  async discardSection(adventureId: string, sectionId: string): Promise<DiscardResult> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/${encodeURIComponent(sectionId)}/discard`, {
      method: 'POST',
      headers: authHeaders(false),
    })
    if (!res.ok) throw await failure(res, 'Failed to discard the region.')
    return await res.json()
  },

  /** The prompt blocks of a region build with token estimates (no LLM call). */
  async previewSection(
    adventureId: string,
    sectionId: string,
    body: Record<string, unknown>,
    includePrompt = false,
  ): Promise<RegionPromptPreview> {
    const query = includePrompt ? '?include_prompt=true' : ''
    const res = await fetch(
      `${API_BASE}/adventures/${adventureId}/editor/sections/${encodeURIComponent(sectionId)}/generate/preview${query}`,
      { method: 'POST', headers: authHeaders(true), body: JSON.stringify(body) },
    )
    if (!res.ok) throw await failure(res, 'Failed to measure the region prompt.')
    return await res.json()
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

  /** The default prompt of one map tile plus the adventure's image style and tone. */
  async getMapPrompt(adventureId: string, col: number, row: number): Promise<MapPromptInfo> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/map-image/prompt?col=${col}&row=${row}`, {
      headers: authHeaders(false),
    })
    if (!res.ok) throw await failure(res, 'Failed to load the map prompt.')
    return await res.json()
  },

  /** Draws one map tile (image model); a tile next to the map grows it. */
  async generateMapTile(adventureId: string, options: MapTileOptions): Promise<MapLayout | null> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/map-image`, {
      method: 'POST',
      headers: authHeaders(true),
      body: JSON.stringify(options),
    })
    if (!res.ok) throw await failure(res, 'Failed to draw the map tile.')
    return (await res.json()).world_map_layout
  },

  /** Uploads an own image as one map tile (PNG, JPEG or WEBP, up to 4096 px and 12 MB). */
  async uploadMapTile(adventureId: string, col: number, row: number, file: File): Promise<MapLayout | null> {
    const payload = new FormData()
    payload.append('col', String(col))
    payload.append('row', String(row))
    payload.append('file', file)
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/map-image/upload`, {
      method: 'POST',
      headers: authHeaders(false),
      body: payload,
    })
    if (!res.ok) throw await failure(res, 'Failed to upload the map tile.')
    return (await res.json()).world_map_layout
  },

  /** Removes one map tile; empty last columns and rows are dropped. */
  async removeMapTile(adventureId: string, col: number, row: number): Promise<MapLayout | null> {
    const res = await fetch(`${API_BASE}/adventures/${adventureId}/editor/sections/map-image?col=${col}&row=${row}`, {
      method: 'DELETE',
      headers: authHeaders(false),
    })
    if (!res.ok) throw await failure(res, 'Failed to remove the map tile.')
    return (await res.json()).world_map_layout
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
