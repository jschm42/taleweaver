/**
 * Labels for the dividers of the endless story feed.
 *
 * The feed shows every page (one per scene + sequence, see comicPages.ts) in one stream; a thin
 * divider marks where the player entered another scene or a new chapter began.
 */
import type { ComicTurn } from '@/composables/comicPages'

export interface StoryDivider {
  /** Scene the new page plays in, when it changed (or is unknown for legacy messages). */
  scene: string | null
  /** Title of the chapter that began, when the sequence changed. */
  chapter: string | null
}

function splitKey(key: string | null): { scene: string; sequence: string } | null {
  if (!key) return null
  const [scene = '', sequence = ''] = key.split('|')
  return { scene, sequence }
}

function sceneLabel(sceneId: string, sceneNodes: Record<string, any>): string {
  const node = sceneNodes?.[sceneId]
  return String(node?.label || node?.name || sceneId)
}

/** Divider shown in front of `page`, or null when nothing worth marking changed. */
export function dividerBefore(
  previous: ComicTurn | undefined,
  page: ComicTurn,
  sceneNodes: Record<string, any>,
  sequenceTitles: Record<string, string>
): StoryDivider | null {
  if (!previous) return null
  const before = splitKey(previous.sceneKey)
  const now = splitKey(page.sceneKey)
  // Legacy messages without scene info: the page break itself is the only hint.
  if (!before || !now) return { scene: null, chapter: null }

  const sceneChanged = before.scene !== now.scene
  const chapterChanged = before.sequence !== now.sequence && Boolean(now.sequence)
  if (!sceneChanged && !chapterChanged) return null
  return {
    scene: sceneChanged ? sceneLabel(now.scene, sceneNodes) : null,
    chapter: chapterChanged ? sequenceTitles?.[now.sequence] || 'New chapter' : null,
  }
}

/** All pages played in one scene: the story feed shows one segment at a time. */
export interface SceneSegment {
  /** Scene id, or null for legacy messages without scene info. */
  sceneId: string | null
  pages: ComicTurn[]
}

/**
 * Groups consecutive pages of the same scene. A scene change (or a legacy page break) starts a
 * new segment; a chapter change within the scene stays inside it (shown as a divider).
 */
export function groupSceneSegments(pages: ComicTurn[]): SceneSegment[] {
  const segments: SceneSegment[] = []
  pages.forEach((page, i) => {
    const sceneId = splitKey(page.sceneKey)?.scene ?? null
    const previous = segments[segments.length - 1]
    const sameScene = previous && sceneId !== null && previous.sceneId === sceneId && i > 0
    if (sameScene) previous.pages.push(page)
    else segments.push({ sceneId, pages: [page] })
  })
  return segments
}

/** Display name of a segment's scene. */
export function segmentSceneLabel(segment: SceneSegment | undefined, sceneNodes: Record<string, any>): string {
  if (!segment?.sceneId) return 'Story'
  return sceneLabel(segment.sceneId, sceneNodes)
}
