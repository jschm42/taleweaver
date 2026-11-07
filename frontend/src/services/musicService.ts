import { ref } from 'vue'

/**
 * Scene background music, hover previews (adventure cards, editor) and one-shot sound effects.
 *
 * Mute and volume are player preferences (localStorage). Browsers may block playback until the
 * user interacted with the page; such rejections are swallowed and the next playMusic() retries.
 */

const MUTED_KEY = 'tw_music_muted'
const VOLUME_KEY = 'tw_music_volume'
const DEFAULT_VOLUME = 0.6
/** Previews play quieter than in-game music so hovering a card is not startling. */
const PREVIEW_VOLUME_SCALE = 0.5

export interface AudioEvent {
  action: string
  url?: string
  loop?: boolean
  volume?: number
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_VOLUME
  return Math.min(1, Math.max(0, value))
}

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Storage may be unavailable (private mode); the preference then lasts for this page only.
  }
}

function loadVolume(): number {
  const stored = readStorage(VOLUME_KEY)
  if (stored === null) return DEFAULT_VOLUME
  return clamp01(Number.parseFloat(stored))
}

/** Plays an element, ignoring autoplay rejections and aborted loads. */
async function safePlay(audio: HTMLAudioElement, label: string): Promise<boolean> {
  try {
    await audio.play()
    return true
  } catch (error: unknown) {
    if ((error as Error | null)?.name !== 'AbortError') console.warn(`[music] ${label} playback blocked:`, error)
    return false
  }
}

function releaseElement(audio: HTMLAudioElement | null): void {
  if (!audio) return
  audio.pause()
  audio.removeAttribute('src')
  audio.load()
}

class MusicService {
  readonly isPlaying = ref(false)
  readonly isMuted = ref(readStorage(MUTED_KEY) === 'true')
  readonly volume = ref(loadVolume())
  readonly currentUrl = ref<string | null>(null)
  readonly previewPlayingUrl = ref<string | null>(null)

  private bgAudio: HTMLAudioElement | null = null
  private previewAudio: HTMLAudioElement | null = null
  /** Track volume requested by the caller (e.g. a script), multiplied with the player volume. */
  private trackVolume = 1

  private effectiveVolume(trackVolume = 1): number {
    if (this.isMuted.value) return 0
    return clamp01(this.volume.value * clamp01(trackVolume))
  }

  async playMusic(url: string, loop: boolean = true, customVolume?: number): Promise<void> {
    if (!url) {
      this.stopMusic()
      return
    }
    this.trackVolume = customVolume ?? 1
    if (this.currentUrl.value === url && this.isPlaying.value && this.bgAudio) {
      this.bgAudio.loop = loop
      this.bgAudio.volume = this.effectiveVolume(this.trackVolume)
      return
    }
    releaseElement(this.bgAudio)
    const audio = new Audio(url)
    audio.loop = loop
    audio.volume = this.effectiveVolume(this.trackVolume)
    audio.addEventListener('ended', () => {
      if (this.bgAudio === audio) this.isPlaying.value = false
    })
    this.bgAudio = audio
    this.currentUrl.value = url
    this.isPlaying.value = await safePlay(audio, 'music')
  }

  stopMusic(): void {
    releaseElement(this.bgAudio)
    this.bgAudio = null
    this.currentUrl.value = null
    this.isPlaying.value = false
  }

  async playSound(url: string, customVolume?: number): Promise<void> {
    if (!url || this.isMuted.value) return
    const audio = new Audio(url)
    audio.volume = this.effectiveVolume(customVolume ?? 1)
    await safePlay(audio, 'sound')
  }

  async playPreview(url: string): Promise<void> {
    this.stopPreview()
    if (!url) return
    const audio = new Audio(url)
    audio.loop = true
    audio.volume = this.effectiveVolume(PREVIEW_VOLUME_SCALE)
    this.previewAudio = audio
    this.previewPlayingUrl.value = url
    const started = await safePlay(audio, 'preview')
    if (!started && this.previewAudio === audio) this.stopPreview()
  }

  stopPreview(): void {
    releaseElement(this.previewAudio)
    this.previewAudio = null
    this.previewPlayingUrl.value = null
  }

  setVolume(val: number): void {
    this.volume.value = clamp01(val)
    writeStorage(VOLUME_KEY, String(this.volume.value))
    this.applyVolume()
  }

  setMuted(val: boolean): void {
    this.isMuted.value = val
    writeStorage(MUTED_KEY, String(val))
    this.applyVolume()
  }

  toggleMute(): void {
    this.setMuted(!this.isMuted.value)
  }

  /** Plays the `tw.audio` commands of a turn (`audio_events`) in order. */
  handleAudioEvents(events: AudioEvent[]): void {
    for (const event of events) {
      this.handleAudioEvent(event)
    }
  }

  private handleAudioEvent(event: AudioEvent): void {
    switch (event?.action) {
      case 'play_music':
        void this.playMusic(event.url || '', event.loop ?? true, event.volume)
        return
      case 'stop_music':
        this.stopMusic()
        return
      case 'play_sound':
        void this.playSound(event.url || '', event.volume)
        return
      case 'play':
        if (event.loop) {
          void this.playMusic(event.url || '', true, event.volume)
          return
        }
        void this.playSound(event.url || '', event.volume)
        return
      default:
        console.warn('[music] unknown audio event:', event?.action)
    }
  }

  private applyVolume(): void {
    if (this.bgAudio) this.bgAudio.volume = this.effectiveVolume(this.trackVolume)
    if (this.previewAudio) this.previewAudio.volume = this.effectiveVolume(PREVIEW_VOLUME_SCALE)
  }
}

export const musicService = new MusicService()
export default musicService
