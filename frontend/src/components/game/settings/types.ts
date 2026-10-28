import type { SkinPreference } from '@/skins/skinRegistry'
import type { TextDensity } from '@/skins/useTextDensity'
import type { NarrationStyle } from './narrationStyles'

export type SessionSettingsPayload = {
  turns: number
  narrationStyle: NarrationStyle
  enableCompression: boolean
  autoSpeech: boolean
  autoSpeakNarration: boolean
  autoSpeakDialogues: boolean
  language: string
  skin: SkinPreference
  density: TextDensity
  textScale: number
  sceneSidebar: boolean
}

export type SettingsTabId = 'memory' | 'voice' | 'translation' | 'display'
