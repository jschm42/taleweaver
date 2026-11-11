/**
 * Sound effects of the combat dialog.
 *
 * Every sound is a file in `frontend/public/assets/audio/combat/`.
 * Supports both Web Audio API (instant, resilient against autoplay blocks once unlocked)
 * and HTMLAudioElement fallback.
 *
 * Effects follow the player's audio volume and mute setting (store/audioPreferences).
 */
import { audioMuted, audioVolume } from '@/store/audioPreferences'

export const COMBAT_SOUND_FILES = {
  fight_start: 'fight_start.mp3',
  round_start: 'round_start.mp3',
  player_turn: 'player_turn.mp3',
  dice_roll: 'dice_roll.mp3',
  swing_melee: 'swing_melee.mp3',
  shot_ranged: 'shot_ranged.mp3',
  cast_magic: 'cast_magic.mp3',
  ability: 'ability.mp3',
  hit_melee: 'hit_melee.mp3',
  hit_ranged: 'hit_ranged.mp3',
  hit_magic: 'hit_magic.mp3',
  hit_crit: 'hit_crit.mp3',
  miss: 'miss.mp3',
  fumble: 'fumble.mp3',
  heal: 'heal.mp3',
  buff: 'buff.mp3',
  debuff: 'debuff.mp3',
  consume: 'consume.mp3',
  rest: 'rest.mp3',
  engage: 'engage.mp3',
  taunt: 'taunt.mp3',
  enemy_defeated: 'enemy_defeated.mp3',
  enemy_fled: 'enemy_fled.mp3',
  escape_success: 'escape_success.mp3',
  escape_fail: 'escape_fail.mp3',
  victory: 'victory.mp3',
  defeat: 'defeat.mp3',
} as const

export type CombatSoundId = keyof typeof COMBAT_SOUND_FILES

/** Anything that can play a combat sound; lets the event player run without audio. */
export interface CombatSoundPlayer {
  play(id: CombatSoundId): void
}

/** Loudness relative to the player's audio volume; stings may be louder than the hits. */
const GAIN: Partial<Record<CombatSoundId, number>> = {
  dice_roll: 0.7,
  player_turn: 0.7,
  taunt: 0.6,
  hit_crit: 1.2,
  victory: 1.2,
  defeat: 1.2,
}

/** Repeated often, so each play is pitched slightly differently. */
const VARIED: ReadonlySet<CombatSoundId> = new Set([
  'swing_melee',
  'shot_ranged',
  'cast_magic',
  'hit_melee',
  'hit_ranged',
  'hit_magic',
  'miss',
  'dice_roll',
])
const PITCH_SPREAD = 0.12
/** The same sound is not stacked within this window (e.g. an area attack hitting five targets). */
const MIN_REPEAT_MS = 60

function soundUrl(id: CombatSoundId): string {
  return `${import.meta.env.BASE_URL}assets/audio/combat/${COMBAT_SOUND_FILES[id]}`
}

export class CombatSounds implements CombatSoundPlayer {
  private audioCtx: AudioContext | null = null
  private readonly buffers = new Map<CombatSoundId, AudioBuffer>()
  private readonly clips = new Map<CombatSoundId, HTMLAudioElement>()
  private readonly lastPlayed = new Map<CombatSoundId, number>()
  private unlockHandler: (() => void) | null = null
  private warnedMuted = false
  private disposed = false

  constructor() {
    this.initAudioContext()
    this.setupUnlockListeners()
  }

  private initAudioContext(): void {
    if (typeof window === 'undefined') return
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass()
      }
    } catch {
      this.audioCtx = null
    }
  }

  private setupUnlockListeners(): void {
    if (typeof window === 'undefined') return
    const unlock = () => {
      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume().catch(() => undefined)
      }
    }
    this.unlockHandler = unlock
    window.addEventListener('pointerdown', unlock, { passive: true })
    window.addEventListener('keydown', unlock, { passive: true })
  }

  /** Starts loading every file so the first hit is not delayed. */
  preload(): void {
    for (const id of Object.keys(COMBAT_SOUND_FILES) as CombatSoundId[]) {
      void this.loadSound(id)
    }
  }

  private async loadSound(id: CombatSoundId): Promise<void> {
    const url = soundUrl(id)
    if (this.audioCtx) {
      try {
        const response = await fetch(url)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const arrayBuf = await response.arrayBuffer()
        if (this.disposed || !this.audioCtx) return
        const audioBuf = await this.audioCtx.decodeAudioData(arrayBuf)
        this.buffers.set(id, audioBuf)
        return
      } catch (err) {
        // Fall back to HTMLAudioElement
      }
    }

    if (!this.clips.has(id)) {
      const clip = new Audio(url)
      clip.preload = 'auto'
      this.clips.set(id, clip)
    }
  }

  play(id: CombatSoundId): void {
    if (this.disposed) return

    if (audioMuted.value) {
      if (!this.warnedMuted) {
        this.warnedMuted = true
        console.info(
          '[CombatSounds] Audio is muted in game settings (audioMuted=true). Unmute in game header or combat dialog to hear SFX.',
        )
      }
      return
    }

    const vol = audioVolume.value
    if (vol <= 0) return

    const now = performance.now()
    if (now - (this.lastPlayed.get(id) ?? -MIN_REPEAT_MS) < MIN_REPEAT_MS) return
    this.lastPlayed.set(id, now)

    const targetGain = Math.min(1, Math.max(0, vol * (GAIN[id] ?? 1)))
    const pitch = VARIED.has(id) ? 1 - PITCH_SPREAD / 2 + Math.random() * PITCH_SPREAD : 1

    // 1. Try Web Audio playback (reliable for async callbacks once unlocked)
    if (this.audioCtx && this.buffers.has(id)) {
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume().catch(() => undefined)
      }
      try {
        const source = this.audioCtx.createBufferSource()
        source.buffer = this.buffers.get(id)!
        source.playbackRate.value = pitch

        const gainNode = this.audioCtx.createGain()
        gainNode.gain.value = targetGain

        source.connect(gainNode)
        gainNode.connect(this.audioCtx.destination)
        source.start(0)
        return
      } catch (err) {
        console.warn(`[CombatSounds] WebAudio play failed for "${id}":`, err)
      }
    }

    // 2. Fallback to HTMLAudioElement
    try {
      let clip = this.clips.get(id)
      if (!clip) {
        clip = new Audio(soundUrl(id))
        this.clips.set(id, clip)
      }
      const voice = clip.paused ? clip : (clip.cloneNode(true) as HTMLAudioElement)
      voice.volume = targetGain
      if (VARIED.has(id)) {
        voice.preservesPitch = false
        voice.playbackRate = pitch
      }
      voice.currentTime = 0
      void voice.play().catch((err) => {
        console.warn(`[CombatSounds] HTMLAudio play failed for "${id}":`, err)
      })
    } catch (err) {
      console.warn(`[CombatSounds] Fallback error for "${id}":`, err)
    }
  }

  dispose(): void {
    this.disposed = true
    if (this.unlockHandler && typeof window !== 'undefined') {
      window.removeEventListener('pointerdown', this.unlockHandler)
      window.removeEventListener('keydown', this.unlockHandler)
      this.unlockHandler = null
    }
    for (const clip of this.clips.values()) {
      clip.removeAttribute('src')
      clip.load()
    }
    this.clips.clear()
    this.buffers.clear()
    if (this.audioCtx && this.audioCtx.state !== 'closed') {
      this.audioCtx.close().catch(() => undefined)
      this.audioCtx = null
    }
  }
}
