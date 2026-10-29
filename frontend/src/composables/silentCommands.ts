/**
 * Commands that run in the background: the backend handles them deterministically and never saves
 * them to the chat history, so the story feed must not show them as a player message either.
 * Showing one optimistically would flash the raw command until the history reloads after the turn.
 *
 * Commands the GM narrates (/say, /read, /search, ...) and debug commands are saved by the backend
 * and stay visible, except the ones in HIDDEN_NARRATED_COMMANDS (see below).
 */
const SILENT_COMMANDS = new Set([
  // Pickup, drop, crafting and containers (deterministic item handling)
  '/take',
  '/take_direct',
  '/drop',
  '/craft',
  '/container_take_all',
  '/container_take_item',
  '/container_drop_scene',
  // Equipment and consumables
  '/equip',
  '/unequip',
  '/consume',
  // World mechanics and movement
  '/switch',
  '/traverse_exit',
  '/rule-pass',
  // Combat start (the fight dialog takes over)
  '/fight',
  '/attack',
  // Character sheet and suggestion chips
  '/sheet',
  '/inventory',
  '/stats',
  '/shuffle',
  '/suggest',
  '/suggestions',
])

/**
 * Commands the backend saves (the GM needs them as the player's action) but that the story feed
 * hides: they are mostly sent by clicks, and the GM's narration already tells what happened.
 */
const HIDDEN_NARRATED_COMMANDS = new Set(['/inspect'])

/** True when a player message must not be shown in the story feed (live or reloaded). */
export function isHiddenPlayerMessage(content: string): boolean {
  const command = String(content || '').trim().split(/\s+/, 1)[0].toLowerCase()
  return SILENT_COMMANDS.has(command) || HIDDEN_NARRATED_COMMANDS.has(command)
}
