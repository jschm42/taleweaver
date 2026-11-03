/**
 * How an exit is named in the game.
 *
 * Every exit has a label that names the passage itself ("a heavy oak door"), the same from both
 * sides of a two-way exit; the tile adds "→ Target" once the target was visited. Older exits
 * without a label fall back to the target scene's name.
 */

/** The author's own label, or '' when none was given. Older "Door -> Hall" labels keep "Door". */
export function exitOwnLabel(label: unknown): string {
  const raw = typeof label === 'string' ? label.trim() : ''
  const arrowMatch = raw.match(/^(.+?)\s*(?:->|→)\s*.+$/)
  return arrowMatch ? arrowMatch[1].trim() : raw
}

/** The label, else the target scene's name, else a generic "Exit". */
export function exitDisplayName(label: unknown, targetName?: string | null): string {
  return exitOwnLabel(label) || String(targetName || '').trim() || 'Exit'
}
