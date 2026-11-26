/**
 * Which exits of the scene map lead into another region. MapTab draws those exits differently
 * and names the regions in the exit and scene tooltips; MapPage provides every scene's region.
 */

/** The region a scene belongs to; `id: null` only for scenes created at runtime. */
export interface SceneRegion {
  id: string | null
  label: string
}

/** Scene id -> its region, for every scene with or without a region. */
export function sceneRegionMap(
  scenes: { id: string; section_id?: string | null }[],
  sections: { id: string; label: string }[],
): Record<string, SceneRegion> {
  const labels = new Map(sections.map((s) => [s.id, s.label]))
  return Object.fromEntries(
    scenes.map((scene) => {
      const id = scene.section_id || null
      return [scene.id, { id, label: id ? labels.get(id) || id : 'No region' }]
    }),
  )
}

/**
 * The region an exit between `fromId` and `toId` leads into, or null when both scenes share a
 * region. Seen from `currentRegionId` (undefined = no region open), it is the end outside that
 * region; else the `to` end.
 */
export function exitTargetRegion(
  fromId: string,
  toId: string,
  regions: Record<string, SceneRegion> | undefined,
  currentRegionId?: string | null,
): string | null {
  const from = regions?.[fromId]
  const to = regions?.[toId]
  if (!from || !to || from.id === to.id) return null
  if (currentRegionId !== undefined && from.id !== currentRegionId && to.id === currentRegionId) return from.label
  return to.label
}
