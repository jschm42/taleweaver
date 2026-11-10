/**
 * Sound effects of the combat dialog.
 *
 * Every sound is a file in `frontend/public/assets/audio/combat/`. The files shipped with the
 * repository are silent placeholders: replace one with a real recording of the same name and
 * it plays, no code change needed (see the README in that folder). A missing or unreadable
 * file simply stays silent.
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
  'swing_melee', 'shot_ranged', 'cast_magic', 'hit_melee', 'hit_ranged', 'hit_magic', 'miss', 'dice_roll',
])
const PITCH_SPREAD = 0.12
/** The same sound is not stacked within this window (e.g. an area attack hitting five targets). */
const MIN_REPEAT_MS = 60

function soundUrl(id: CombatSoundId): string {
  return `${import.meta.env.BASE_URL}assets/audio/combat/${COMBAT_SOUND_FILES[id]}`
}

export class CombatSounds implements CombatSoundPlayer {
  private readonly clips = new Map<CombatSoundId, HTMLAudioElement>()
  private readonly unusable = new Set<CombatSoundId>()
  private readonly lastPlayed = new Map<CombatSoundId, number>()

  /** Starts loading every file so the first hit is not delayed. */
  preload(): void {
    for (const id of Object.keys(COMBAT_SOUND_FILES) as CombatSoundId[]) {
      this.clip(id)
    }
  }

  play(id: CombatSoundId): void {
    if (audioMuted.value || this.unusable.has(id)) return
    const now = performance.now()
    if (now - (this.lastPlayed.get(id) ?? -MIN_REPEAT_MS) < MIN_REPEAT_MS) return
    this.lastPlayed.set(id, now)

    // A copy per play lets the same sound overlap itself.
    const voice = this.clip(id).cloneNode(true) as HTMLAudioElement
    voice.volume = Math.min(1, Math.max(0, audioVolume.value * (GAIN[id] ?? 1)))
    if (VARIED.has(id)) {
      voice.preservesPitch = false
      voice.playbackRate = 1 - PITCH_SPREAD / 2 + Math.random() * PITCH_SPREAD
    }
    // Rejected while autoplay is still blocked or the file is unusable: stay silent.
    void voice.play().catch(() => undefined)
  }

  dispose(): void {
    for (const clip of this.clips.values()) {
      clip.removeAttribute('src')
      clip.load()
    }
    this.clips.clear()
  }

  private clip(id: CombatSoundId): HTMLAudioElement {
    const existing = this.clips.get(id)
    if (existing) return existing
    const clip = new Audio()
    clip.preload = 'auto'
    clip.addEventListener('error', () => this.unusable.add(id), { once: true })
    clip.src = soundUrl(id)
    this.clips.set(id, clip)
    return clip
  }
}
