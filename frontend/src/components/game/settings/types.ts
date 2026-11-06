import type { SkinPreference } from '@/skins/skinRegistry'
import type { TextDensity } from '@/skins/useTextDensity'
import type { NarrationStyle } from './narrationStyles'
import type { AutoSpeakSettings } from '@/types/tts'

export type SessionSettingsPayload = {
  turns: number
  narrationStyle: NarrationStyle
  enableCompression: boolean
  autoSpeech: boolean
  autoSpeakSettings: AutoSpeakSettings
  language: string
  skin: SkinPreference
  density: TextDensity
  textScale: number
  sceneSidebar: boolean
}

export type SettingsTabId = 'memory' | 'voice' | 'translation' | 'display'
