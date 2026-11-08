/**
 * The player's background-audio preferences (volume, mute), shared by the in-game player
 * (useGameAudio), the audio toggle, the in-game settings and the library hover preview.
 * Kept in localStorage, per browser.
 *
 * Speech (TTS) always plays at full volume, so the default audio volume of 50% sits at about
 * half the loudness of the voices.
 */
import { ref, watch } from 'vue'

const VOLUME_KEY = 'game_audio_volume'
const MUTED_KEY = 'game_audio_muted'
// Keys used before the rename to audio; read once so players keep their setting.
const LEGACY_KEYS: Record<string, string> = { [VOLUME_KEY]: 'game_music_volume', [MUTED_KEY]: 'game_music_muted' }
export const AUDIO_DEFAULT_VOLUME = 0.5

function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key) ?? localStorage.getItem(LEGACY_KEYS[key] ?? '')
  } catch {
    return null
  }
}

function writeStored(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Storage blocked: the choice lasts for this page view only.
  }
}

function clamp(value: number): number {
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : AUDIO_DEFAULT_VOLUME
}

function initialVolume(): number {
  const stored = readStored(VOLUME_KEY)
  return stored === null ? AUDIO_DEFAULT_VOLUME : clamp(Number(stored))
}

/** Audio volume 0..1, relative to speech (which plays at 1). */
export const audioVolume = ref(initialVolume())
export const audioMuted = ref(readStored(MUTED_KEY) === '1')

watch(audioVolume, (value) => writeStored(VOLUME_KEY, String(clamp(value))))
watch(audioMuted, (value) => writeStored(MUTED_KEY, value ? '1' : '0'))

export function setAudioVolume(value: number): void {
  audioVolume.value = clamp(value)
}
