/**
 * The scene graph of one region in the players' map: the region's known scenes plus the scenes
 * one known edge away (the ways out), and only the edges between them. Nodes without a region
 * (unexplored placeholders, scenes of adventures without regions) belong to `NO_REGION`.
 */
import type { WorldMapData } from '@/types'

export const NO_REGION = '__no_region__'

export function regionOf(node: { section_id?: string | null } | undefined): string {
  return node?.section_id || NO_REGION
}

export function filterRegionMap(data: WorldMapData, regionId: string): WorldMapData {
  const nodes = data.nodes || {}
  const inside = new Set(Object.keys(nodes).filter((key) => regionOf(nodes[key] as { section_id?: string | null }) === regionId))
  const keyOf = (raw: string): string => raw.replace(/-/g, '_').replace(/[^\p{L}\p{N}_]/gu, '_').toUpperCase()
  const kept = new Set(inside)
  for (const edge of data.edges || []) {
    const from = keyOf(String(edge.from))
    const to = keyOf(String(edge.to))
    if (inside.has(from) && nodes[to]) kept.add(to)
    if (inside.has(to) && nodes[from]) kept.add(from)
  }
  return {
    ...data,
    nodes: Object.fromEntries(Object.entries(nodes).filter(([key]) => kept.has(key))),
    edges: (data.edges || []).filter((edge) => kept.has(keyOf(String(edge.from))) && kept.has(keyOf(String(edge.to)))),
  }
}

/** Number of known (not unexplored) scenes per region. */
export function knownScenesPerRegion(data: WorldMapData | null): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const node of Object.values(data?.nodes || {}) as Array<{ section_id?: string | null; is_unknown?: boolean }>) {
    if (node.is_unknown) continue
    const region = regionOf(node)
    counts[region] = (counts[region] || 0) + 1
  }
  return counts
}
