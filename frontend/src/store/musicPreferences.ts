/**
 * The player's background-music preferences (volume, mute), shared by the in-game player
 * (useGameMusic), the music toggle, the in-game settings and the library hover preview.
 * Kept in localStorage, per browser.
 *
 * Speech (TTS) always plays at full volume, so the default music volume of 50% sits at about
 * half the loudness of the voices.
 */
import { ref, watch } from 'vue'

const VOLUME_KEY = 'game_music_volume'
const MUTED_KEY = 'game_music_muted'
export const MUSIC_DEFAULT_VOLUME = 0.5

function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key)
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
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : MUSIC_DEFAULT_VOLUME
}

function initialVolume(): number {
  const stored = readStored(VOLUME_KEY)
  return stored === null ? MUSIC_DEFAULT_VOLUME : clamp(Number(stored))
}

/** Music volume 0..1, relative to speech (which plays at 1). */
export const musicVolume = ref(initialVolume())
export const musicMuted = ref(readStored(MUTED_KEY) === '1')

watch(musicVolume, (value) => writeStored(VOLUME_KEY, String(clamp(value))))
watch(musicMuted, (value) => writeStored(MUTED_KEY, value ? '1' : '0'))

export function setMusicVolume(value: number): void {
  musicVolume.value = clamp(value)
}
