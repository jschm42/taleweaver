import { ref, watch, type Ref } from 'vue'
import { audioService } from '@/services/audioService'
import { authState } from '@/store/auth'
import { configState } from '@/store/config'
import {
  DEFAULT_AUTO_SPEAK_SETTINGS,
  normalizeAutoSpeakSettings,
  type AutoSpeakSettings,
  type TtsPreferences,
} from '@/types/tts'

const STORAGE_KEY = 'tw_auto_speak_settings'
// Written by earlier versions that only knew "narration" and "dialogues".
const LEGACY_NARRATION_KEY = 'tw_autoSpeakNarration'
const LEGACY_DIALOGUES_KEY = 'tw_autoSpeakDialogues'

function readLegacySettings(): AutoSpeakSettings | null {
  const narration = localStorage.getItem(LEGACY_NARRATION_KEY)
  const dialogues = localStorage.getItem(LEGACY_DIALOGUES_KEY)
  if (narration === null && dialogues === null) return null
  const speakDialogues = dialogues !== 'false'
  return {
    ...DEFAULT_AUTO_SPEAK_SETTINGS,
    gm: narration !== 'false',
    protagonist: speakDialogues,
    npcs: speakDialogues,
  }
}

function readStoredSettings(): AutoSpeakSettings | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return readLegacySettings()
  try {
    return normalizeAutoSpeakSettings(JSON.parse(raw))
  } catch {
    return null
  }
}

function resolveSettings(sessionValue: unknown): AutoSpeakSettings {
  return (
    normalizeAutoSpeakSettings(sessionValue) ??
    normalizeAutoSpeakSettings(authState.user?.tts_preferences) ??
    readStoredSettings() ??
    { ...DEFAULT_AUTO_SPEAK_SETTINGS }
  )
}

/**
 * Auto-Speak voice channels of the running session. The session's own copy wins; the profile
 * defaults, the last local choice and the built-in defaults follow in that order.
 */
export function useSessionAutoSpeakSettings(sheet: Ref<any>) {
  const autoSpeakSettings = ref<AutoSpeakSettings>(resolveSettings(sheet.value?.tts_auto_speak))

  watch(
    () => sheet.value?.tts_auto_speak,
    (stored) => {
      autoSpeakSettings.value = resolveSettings(stored)
    },
  )

  // The session's master switch acts like the admin default: a toggle by the player still wins.
  watch(
    () => [sheet.value?.tts_auto_speak?.enabled, configState.isLoaded, configState.isTtsEnabled] as const,
    ([enabled, isLoaded, ttsEnabled]) => {
      if (typeof enabled !== 'boolean' || !isLoaded) return
      audioService.applyAutoSpeechDefault(enabled && ttsEnabled)
    },
    { immediate: true },
  )

  /** Applies the choice locally and returns the value to store on the session. */
  function applyAutoSpeakSettings(settings: AutoSpeakSettings, enabled: boolean): TtsPreferences {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    autoSpeakSettings.value = { ...settings }
    return { ...settings, enabled }
  }

  return { autoSpeakSettings, applyAutoSpeakSettings }
}
