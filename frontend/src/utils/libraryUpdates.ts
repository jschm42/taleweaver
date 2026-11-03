import type { AdventureTemplateSummary } from '@/types'
import type { AdventureLibraryUpdate } from '@/types/adventureLibrary'

/** Numeric segments of a dotted version; `"1.2.0-beta"` -> `[1, 2, 0]`. */
function versionParts(version: string): number[] {
  const parts: number[] = []
  for (const segment of version.trim().split('.')) {
    const match = /^\d+/.exec(segment)
    if (!match) break
    parts.push(Number(match[0]))
    if (match[0].length !== segment.length) break
  }
  return parts
}

/** True when version `a` is strictly higher than `b` (missing segments count as 0). */
export function isVersionHigher(a: string, b: string): boolean {
  const left = versionParts(a)
  const right = versionParts(b)
  for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
    const diff = (left[i] ?? 0) - (right[i] ?? 0)
    if (diff !== 0) return diff > 0
  }
  return false
}

/**
 * Marks templates that have a newer version in the adventure library.
 *
 * The portal's update badge then works as for local files; updating installs the newer
 * library version (see backend/services/adventure_library/updates.py). A higher local
 * version is kept.
 */
export function withLibraryUpdates(
  templates: AdventureTemplateSummary[],
  updates: AdventureLibraryUpdate[],
): AdventureTemplateSummary[] {
  if (updates.length === 0) return templates
  const byTemplate = new Map(updates.map((update) => [update.template_id, update.version]))
  return templates.map((template) => {
    const libraryVersion = byTemplate.get(template.template_id)
    if (!libraryVersion) return template
    const localVersion = template.has_update ? template.available_version : null
    if (localVersion && !isVersionHigher(libraryVersion, localVersion)) return template
    return { ...template, has_update: true, available_version: libraryVersion, update_source: 'library' }
  })
}
