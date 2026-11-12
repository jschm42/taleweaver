import type { AppliedEffect, CombatEventData, SpecialCategory } from '@/types'
import type { CombatSoundId, CombatSoundPlayer } from '../combatSounds'
import type { ArenaRenderer } from './ArenaRenderer'
import { MELEE_REACH, RANGED_REACH } from './cardMoves'
import type { ResourceStat } from './CombatantCard'
import type { Point } from './effects'
import { CATEGORY_COLORS, COLORS, effectColor, formatDelta } from './palette'

const PLAYER_ID = 'PLAYER'
const RESOURCE_STATS: ResourceStat[] = ['hp', 'mana', 'stamina']
/** Extra time an attacking NPC stays in front after its action resolved. */
const ENEMY_FRONT_HOLD_MS = 700
/** The pale "damage taken" part of an HP bar lingers this long before it drains. */
const GHOST_HOLD_MS = 350

type Handler = (data: CombatEventData) => Promise<void>
/** Shows a speech bubble for the combatant and resolves once it has been read. */
export type SpeakHandler = (entityId: string, line: string) => Promise<void>
/** How an attack travels and lands; decides its animation and sounds. */
type AttackStyle = 'MELEE' | 'RANGED' | 'MAGIC'

interface HitOptions {
  heavy?: boolean
  tint?: number
  style?: AttackStyle
  /** Attacker; the target is knocked away from it. */
  from?: string | null
}

const LAUNCH_SOUND: Record<AttackStyle, CombatSoundId> = { MELEE: 'swing_melee', RANGED: 'shot_ranged', MAGIC: 'cast_magic' }
const HIT_SOUND: Record<AttackStyle, CombatSoundId> = { MELEE: 'hit_melee', RANGED: 'hit_ranged', MAGIC: 'hit_magic' }
const SILENT: CombatSoundPlayer = { play: () => undefined }

/** Weapon attacks without a category are melee; social and other abilities travel like magic. */
function styleOf(category: SpecialCategory | undefined): AttackStyle {
  if (!category || category === 'MELEE') return 'MELEE'
  return category === 'RANGED' ? 'RANGED' : 'MAGIC'
}

/** Turns structured combat log events into arena animations and sounds. */
export class ArenaEventPlayer {
  private readonly handlers: Partial<Record<CombatEventData['kind'], Handler>>

  constructor(
    private readonly arena: ArenaRenderer,
    private readonly speak: SpeakHandler | null = null,
    private readonly sounds: CombatSoundPlayer = SILENT,
  ) {
    this.handlers = {
      banter: (d) => this.banter(d),
      attack: (d) => this.attack(d),
      special: (d) => this.special(d),
      rest: (d) => this.recover(d, 'rest'),
      consume: (d) => this.recover(d, 'consume'),
      event: (d) => this.gmEvent(d),
      engage: (d) => this.engage(d),
      defeat: (d) => this.defeat(d),
      fled: (d) => this.flee(d),
      initiative: (d) => this.announce(`ROUND ${d.round ?? ''}`.trim(), COLORS.gold, 'round_start', 450, 46),
      turn: (d) => this.turn(d),
      victory: () => this.victory(),
      game_over: () => this.gameOver(),
      run: (d) => this.announce(
        d.success ? 'ESCAPED!' : 'NO ESCAPE',
        d.success ? COLORS.player : COLORS.enemy,
        d.success ? 'escape_success' : 'escape_fail',
        500,
        44,
      ),
    }
  }

  async play(data: CombatEventData | undefined): Promise<void> {
    const handler = data ? this.handlers[data.kind] : undefined
    if (handler && data) await handler(data)
  }

  /** The protagonist and the companion fight on the player side. */
  private onPlayerSide(actorId: string | null | undefined): boolean {
    return actorId === PLAYER_ID || this.arena.card(actorId)?.data.side === 'player'
  }

  private sideColor(actorId: string | null | undefined): number {
    return this.onPlayerSide(actorId) ? COLORS.player : COLORS.enemy
  }

  private async announce(text: string, color: number, sound: CombatSoundId, hold: number, size: number): Promise<void> {
    this.sounds.play(sound)
    await this.arena.effects.banner(this.arena.center(), text, color, hold, size)
  }

  /**
   * Steps the actor in front for its whole action so the player sees who is acting. NPCs
   * wind up first and linger afterwards, which gives the player time to read the result.
   */
  private async inFront(d: CombatEventData, reach: number, action: () => Promise<void>): Promise<void> {
    const isEnemy = !this.onPlayerSide(d.actor)
    await this.arena.moves.advance(d.actor, d.target, reach)
    try {
      if (isEnemy) await this.arena.moves.windUp(d.actor, d.target)
      await action()
      if (isEnemy) await this.arena.tween.wait(ENEMY_FRONT_HOLD_MS)
    } finally {
      await this.arena.retreat(d.actor)
    }
  }

  private async attack(d: CombatEventData): Promise<void> {
    const style = styleOf(d.category)
    const reach = style === 'MELEE' ? MELEE_REACH : RANGED_REACH
    await this.inFront(d, reach, async () => {
      await this.rollDice(d, this.sideColor(d.actor), d.label ? `${d.label} vs AC` : 'Attack vs AC')
      await this.launch(d, style, this.sideColor(d.actor))
      if (!d.success) {
        await this.miss(d)
        return
      }
      await this.applyEffects(d.effects, { heavy: !!d.crit, style, from: d.actor })
    })
  }

  private async rollDice(d: CombatEventData, color: number, caption: string): Promise<void> {
    if (d.d20 === undefined) return
    this.sounds.play('dice_roll')
    await this.arena.dice.roll({
      d20: d.d20,
      modifier: d.modifier,
      total: d.total,
      dc: d.dc,
      success: !!d.success,
      crit: d.crit,
      fumble: d.fumble,
      color,
      caption,
    })
  }

  /** The attack leaves the actor: a jab, a shot or a bolt of magic toward the target. */
  private async launch(d: CombatEventData, style: AttackStyle, color: number): Promise<void> {
    this.sounds.play(LAUNCH_SOUND[style])
    if (style === 'MELEE') {
      await this.arena.moves.strike(d.actor, d.target)
      return
    }
    const from = this.arena.cardCenter(d.actor)
    const to = this.aimPoint(d)
    void this.arena.moves.recoil(d.actor, d.target)
    if (style === 'RANGED') {
      await this.arena.impact.arrow(from, to, color)
      return
    }
    void this.arena.effects.burst(from, color, 10, 50)
    await this.arena.effects.projectile(from, to, color)
  }

  /** Where a shot ends: the target's centre, or past its shoulder when it misses. */
  private aimPoint(d: CombatEventData): Point {
    const target = this.arena.cardCenter(d.target)
    if (d.success) return target
    const from = this.arena.cardCenter(d.actor)
    return { x: target.x + (target.x - from.x) * 0.35, y: target.y - 70 }
  }

  private async miss(d: CombatEventData): Promise<void> {
    this.sounds.play(d.fumble ? 'fumble' : 'miss')
    await Promise.all([
      d.fumble ? this.arena.moves.wobble(d.actor) : this.arena.moves.dodge(d.target),
      this.arena.effects.floatText(this.arena.cardCenter(d.target), 'MISS', COLORS.miss, 30),
    ])
  }

  private async special(d: CombatEventData): Promise<void> {
    if (d.actor !== PLAYER_ID && d.target) {
      await this.inFront(d, RANGED_REACH, () => this.resolveSpecial(d))
      return
    }
    await this.resolveSpecial(d)
  }

  private async resolveSpecial(d: CombatEventData): Promise<void> {
    const category = d.category ?? 'MAGIC'
    const color = CATEGORY_COLORS[category]
    const style = styleOf(category)
    const actorPoint = this.arena.cardCenter(d.actor)
    this.sounds.play(category === 'SOCIAL' || category === 'OTHER' ? 'ability' : LAUNCH_SOUND[style])
    void this.arena.effects.burst(actorPoint, color, 14, 70)
    await this.arena.effects.floatText({ x: actorPoint.x, y: actorPoint.y - 40 }, d.action_name ?? 'Special', color, 26)
    if (d.rolled) await this.rollDice(d, color, `${(d.stat ?? '').toUpperCase()} check`)
    if (!d.success) {
      this.sounds.play(d.fumble ? 'fumble' : 'miss')
      await Promise.all([
        d.fumble ? this.arena.moves.wobble(d.actor) : Promise.resolve(),
        this.arena.effects.floatText(actorPoint, 'FAILED', COLORS.miss, 28),
      ])
      return
    }
    // Area attacks list every combatant caught in the area; one projectile flies to each.
    const targetIds = d.targets?.length ? d.targets.map((t) => t.id) : d.target ? [d.target] : []
    await Promise.all(targetIds.map((id) => this.arena.effects.projectile(actorPoint, this.arena.cardCenter(id), color)))
    const selfEffects = (d.effects ?? []).some((e) => e.entity === d.actor && e.delta !== 0)
    await Promise.all([
      this.applyEffects(d.effects, { heavy: !!d.crit, tint: color, style, from: d.actor }),
      selfEffects ? this.selfAura(d.actor, color) : Promise.resolve(),
      this.areaVerdicts(d),
    ])
  }

  /** Marks area targets that resisted: a successful save or a miss. */
  private async areaVerdicts(d: CombatEventData): Promise<void> {
    const jobs = (d.targets ?? []).map((t) => {
      const label = t.save?.success ? 'SAVED' : t.hit === false ? 'MISS' : null
      if (!label) return Promise.resolve()
      const point = this.arena.cardCenter(t.id)
      return this.arena.effects.floatText({ x: point.x, y: point.y - 36 }, label, COLORS.miss, 22)
    })
    await Promise.all(jobs)
  }

  /** Shows that an ability affected its own caster (heals, buffs, stances). */
  private async selfAura(actorId: string | null | undefined, color: number): Promise<void> {
    const card = this.arena.card(actorId)
    if (!card) return
    const flash = card.flashColor(color)
    flash.alpha = 0.6
    const w = card.cardWidth * card.home.scale
    const h = card.cardHeight * card.home.scale
    await Promise.all([
      this.arena.tween.to(flash, { alpha: 0 }, 700),
      this.arena.effects.aura({ x: card.home.x, y: card.home.y }, w, h, color),
    ])
  }

  private async recover(d: CombatEventData, sound: CombatSoundId): Promise<void> {
    this.sounds.play(sound)
    await this.applyEffects(d.effects)
  }

  private async gmEvent(d: CombatEventData): Promise<void> {
    const player = this.arena.card(PLAYER_ID)
    if (player) {
      const flash = player.flashColor(CATEGORY_COLORS.MAGIC)
      void this.arena.tween.to(flash, { alpha: 0 }, 600)
    }
    await this.applyEffects(d.effects, { heavy: true, style: 'MAGIC' })
  }

  private async engage(d: CombatEventData): Promise<void> {
    const card = this.arena.card(d.entity)
    if (!card) return
    this.sounds.play('engage')
    await this.arena.tween.to(card.scale, { x: card.home.scale * 1.12, y: card.home.scale * 1.12 }, 160)
    void this.arena.tween.to(card.scale, { x: card.home.scale, y: card.home.scale }, 260)
    await this.arena.effects.floatText(this.arena.cardCenter(d.entity), 'ENGAGED!', COLORS.enemy, 26)
  }

  /** A beaten combatant's card flashes, shudders and breaks apart. */
  private async defeat(d: CombatEventData): Promise<void> {
    const card = this.arena.card(d.entity)
    if (!card) return
    this.sounds.play('enemy_defeated')
    const center = { x: card.home.x, y: card.home.y }
    const scale = card.home.scale
    void this.arena.effects.floatText(this.arena.cardCenter(d.entity), 'DEFEATED', COLORS.goldSoft, 30)
    void this.arena.tween.to(card.flashColor(COLORS.white), { alpha: 0 }, 300)
    this.arena.hitStop(90)
    await this.arena.effects.shake(card, 9, 260)
    card.gone = true
    card.eventMode = 'none'
    await Promise.all([
      this.arena.impact.shards(center, card.cardWidth * scale, card.cardHeight * scale, this.sideColor(d.entity)),
      this.arena.tween.to(card, { alpha: 0, y: card.y + 26, rotation: card.rotation + 0.16 }, 480),
      this.arena.tween.to(card.scale, { x: scale * 0.88, y: scale * 0.88 }, 480),
    ])
    card.markOut('defeated')
    await this.grantXp(d)
  }

  private async flee(d: CombatEventData): Promise<void> {
    const card = this.arena.card(d.entity)
    if (!card) return
    this.sounds.play('enemy_fled')
    void this.arena.effects.floatText(this.arena.cardCenter(d.entity), 'FLED!', COLORS.goldSoft, 30)
    await this.arena.tween.to(card, { rotation: card.rotation + 0.25, alpha: 0.5 }, 420)
    card.markOut('fled')
    await this.grantXp(d)
  }

  private async grantXp(d: CombatEventData): Promise<void> {
    if (!d.xp) return
    await this.arena.effects.floatText(this.arena.cardCenter(PLAYER_ID), `+${d.xp} XP`, COLORS.gold, 26)
  }

  /** Lifts the speaker out of the stack while its speech bubble is shown. */
  private async banter(d: CombatEventData): Promise<void> {
    const card = this.arena.card(d.actor)
    if (!card || !d.line || !this.speak) return
    this.sounds.play('taunt')
    card.zIndex = 500
    await this.arena.tween.to(card.scale, { x: card.home.scale * 1.06, y: card.home.scale * 1.06 }, 180)
    try {
      await this.speak(card.entityId, d.line)
    } finally {
      await this.arena.tween.to(card.scale, { x: card.home.scale, y: card.home.scale }, 220)
      this.arena.relayoutCards()
    }
  }

  private async turn(d: CombatEventData): Promise<void> {
    if (d.actor !== PLAYER_ID) return
    await this.announce('YOUR TURN', COLORS.player, 'player_turn', 300, 36)
  }

  private async victory(): Promise<void> {
    this.sounds.play('victory')
    await Promise.all([
      this.arena.effects.banner(this.arena.center(), 'VICTORY', COLORS.gold, 900, 64, this.arena.width),
      this.arena.impact.celebrate(this.arena.width, this.arena.height, COLORS.gold),
    ])
  }

  private async gameOver(): Promise<void> {
    this.sounds.play('defeat')
    void this.arena.flash(COLORS.hp, 0.4)
    void this.arena.quake(10)
    await this.arena.effects.banner(this.arena.center(), 'DEFEAT', COLORS.hp, 900, 64, this.arena.width)
  }

  private async applyEffects(effects: AppliedEffect[] | undefined, options: HitOptions = {}): Promise<void> {
    const jobs = (effects ?? []).filter((e) => e.delta !== 0).map((e) => this.applyEffect(e, options))
    await Promise.all(jobs)
  }

  private async applyEffect(effect: AppliedEffect, options: HitOptions): Promise<void> {
    const card = this.arena.card(effect.entity)
    if (!card) return
    const heavy = !!options.heavy
    const point = this.arena.cardCenter(effect.entity)
    const jobs: Promise<void>[] = [
      this.arena.effects.floatText(point, formatDelta(effect.stat, effect.delta), effectColor(effect.stat, effect.delta), heavy ? 38 : 30),
    ]
    if (RESOURCE_STATS.includes(effect.stat as ResourceStat)) {
      jobs.push(this.changeResource(effect))
    } else {
      this.sounds.play(effect.delta > 0 ? 'buff' : 'debuff')
      const modifiers = { ...card.data.modifiers }
      modifiers[effect.stat] = (modifiers[effect.stat] ?? 0) + effect.delta
      card.setData({ ...card.data, modifiers })
    }
    if (effect.stat === 'hp' && effect.delta < 0) jobs.push(this.impact(effect, point, options))
    if (effect.stat === 'hp' && effect.delta > 0) this.sounds.play('heal')
    await Promise.all(jobs)
  }

  /** Animates a bar; lost HP leaves a pale segment behind that drains a moment later. */
  private async changeResource(effect: AppliedEffect): Promise<void> {
    const card = this.arena.card(effect.entity)
    if (!card) return
    const stat = effect.stat as ResourceStat
    const from = card.displayed[stat]
    await this.arena.tween.run(stat === 'hp' && effect.delta < 0 ? 220 : 500, (p) => card.setDisplayed(stat, from + effect.delta * p))
    if (stat !== 'hp' || effect.delta > 0) return
    const ghostFrom = card.ghostHp
    await this.arena.tween.wait(GHOST_HOLD_MS)
    await this.arena.tween.run(450, (p) => card.setGhostHp(ghostFrom + (card.displayed.hp - ghostFrom) * p))
  }

  /** The moment a blow lands: hit-stop, flash, weapon trail, knockback and, for crits, a quake. */
  private async impact(effect: AppliedEffect, point: Point, options: HitOptions): Promise<void> {
    const card = this.arena.card(effect.entity)
    if (!card) return
    const heavy = !!options.heavy
    const style = options.style ?? 'MELEE'
    const color = options.tint ?? COLORS.hp
    this.sounds.play(heavy ? 'hit_crit' : HIT_SOUND[style])
    this.arena.hitStop(heavy ? 130 : 70)
    const jobs: Promise<void>[] = [
      this.arena.tween.to(card.flashColor(heavy ? COLORS.white : COLORS.hp), { alpha: 0 }, 450),
      this.arena.effects.burst(point, color, heavy ? 26 : 16),
      style === 'MELEE' ? this.arena.impact.slash(point, COLORS.white, heavy) : this.arena.impact.ring(point, color, heavy ? 95 : 70),
      options.from ? this.arena.moves.knockback(effect.entity, options.from, heavy) : this.arena.effects.shake(card, 8),
    ]
    if (heavy) jobs.push(this.arena.quake(12), this.arena.flash(COLORS.white, 0.3))
    await Promise.all(jobs)
  }
}
