/** Parses an entity's metadata_json, which arrives either as an object or as a JSON string. */
export function parseMetadata(raw: unknown): Record<string, any> {
  let meta: any = raw
  if (typeof meta === 'string') {
    try {
      meta = JSON.parse(meta)
    } catch {
      meta = {}
    }
  }
  return meta && typeof meta === 'object' ? meta : {}
}

/** Formats an id as a readable name (e.g. BRONZE_KEY -> Bronze Key). */
export function formatIdToName(id: string): string {
  return id
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

/** Ignores global shortcut keys while the player types into a field (e.g. the chat input). */
export function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null
  return !!element && (element.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName))
}
