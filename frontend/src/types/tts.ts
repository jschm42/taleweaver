/** Which story voices are read aloud automatically while Auto-Speak is on. */
export interface AutoSpeakSettings {
  gm: boolean
  protagonist: boolean
  npcs: boolean
  system: boolean
  readables: boolean
}

export const DEFAULT_AUTO_SPEAK_SETTINGS: AutoSpeakSettings = {
  gm: true,
  protagonist: true,
  npcs: true,
  system: false,
  readables: true,
}

/** Profile defaults for new sessions: the voice channels plus the master switch. */
export interface TtsPreferences extends AutoSpeakSettings {
  enabled: boolean
}

export const DEFAULT_TTS_PREFERENCES: TtsPreferences = {
  enabled: true,
  ...DEFAULT_AUTO_SPEAK_SETTINGS,
}

export type AutoSpeakChannel = keyof AutoSpeakSettings

export const AUTO_SPEAK_CHANNELS: { key: AutoSpeakChannel; label: string; description: string; icon: string }[] = [
  { key: 'gm', label: 'Game Master', description: 'Narrator scene and event descriptions', icon: 'ra-crystal-ball' },
  { key: 'protagonist', label: 'Protagonist', description: 'Your own dialogue', icon: 'ra-player' },
  { key: 'npcs', label: 'NPCs', description: 'Non-player characters', icon: 'ra-double-team' },
  { key: 'readables', label: 'Readables', description: 'Books, scrolls and documents you open', icon: 'ra-book' },
  { key: 'system', label: 'System Messages', description: 'Dice rolls, status updates and system notes', icon: 'ra-perspective-dice-six' },
]

/** Copies the known flags from untrusted data (API, localStorage); missing flags use the defaults. */
export function normalizeAutoSpeakSettings(raw: unknown): AutoSpeakSettings | null {
  if (!raw || typeof raw !== 'object') return null
  const source = raw as Record<string, unknown>
  const result = { ...DEFAULT_AUTO_SPEAK_SETTINGS }
  for (const { key } of AUTO_SPEAK_CHANNELS) {
    if (typeof source[key] === 'boolean') result[key] = source[key] as boolean
  }
  return result
}

export function normalizeTtsPreferences(raw: unknown): TtsPreferences {
  const channels = normalizeAutoSpeakSettings(raw) ?? DEFAULT_AUTO_SPEAK_SETTINGS
  const enabled = (raw as Record<string, unknown> | null)?.enabled
  return { ...channels, enabled: typeof enabled === 'boolean' ? enabled : DEFAULT_TTS_PREFERENCES.enabled }
}
