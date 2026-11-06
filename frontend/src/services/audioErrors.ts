/**
 * Player-facing text for voice playback errors (shown as a toast by the game view).
 *
 * Browsers report a lost connection with terse, browser-specific texts ("Failed to fetch",
 * "NetworkError when attempting to fetch resource.", "Load failed"); a streaming <audio>
 * element reports MEDIA_ERR_NETWORK (code 2). Those become one readable message, the raw
 * text stays in the console. Other errors (e.g. "TTS Provider error: ... quota ...") already
 * tell the player something useful and are shown as they are.
 */

export const AUTOPLAY_BLOCKED_MESSAGE =
  'Audio blocked by browser autoplay policy. Click once in the game to unlock voice playback.'

export const CONNECTION_LOST_MESSAGE =
  'Voice output failed for one line (connection lost). The story continues; the next lines are read as usual.'

const AUTOPLAY_HINTS = ['notallowederror', "user didn't interact", 'audiocontext was not allowed to start', 'suspended']

const NETWORK_HINTS = ['failed to fetch', 'networkerror', 'network error', 'load failed', 'err_connection', 'code:2 ']

export function describePlaybackError(rawMessage: string): string {
  const normalized = `${rawMessage.toLowerCase()} `
  if (AUTOPLAY_HINTS.some((hint) => normalized.includes(hint))) return AUTOPLAY_BLOCKED_MESSAGE
  if (NETWORK_HINTS.some((hint) => normalized.includes(hint))) return CONNECTION_LOST_MESSAGE
  return rawMessage
}
