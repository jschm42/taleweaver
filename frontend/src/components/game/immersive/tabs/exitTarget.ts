/** What the player knows about the scene behind an exit (from the session's world map). */
export type ExitTargetInfo = {
  /** True once the target scene was visited; unvisited targets show as "?" on the map. */
  target_known: boolean
  target_image_url: string | null
}

type MapNode = { is_unknown?: boolean; image_url?: string | null }

/** Same node key as the backend's MapEngine._safe_id. */
function mapNodeKey(sceneId: string): string {
  return sceneId
    .replace(/-/g, '_')
    .replace(/[^\p{L}\p{N}_]/gu, '_')
    .toUpperCase()
}

export function exitTargetInfo(
  mapData: { nodes?: unknown } | null | undefined,
  sceneId: string | null | undefined,
  fallbackImage: (sceneId: string) => string | null,
): ExitTargetInfo {
  const nodes = mapData?.nodes
  if (!sceneId || !nodes || typeof nodes !== 'object') {
    return { target_known: false, target_image_url: null }
  }
  const node = (nodes as Record<string, MapNode | undefined>)[mapNodeKey(sceneId)]
  if (!node || node.is_unknown) {
    return { target_known: false, target_image_url: null }
  }
  return { target_known: true, target_image_url: node.image_url || fallbackImage(sceneId) }
}
