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
