import type { AppliedEffect, CombatEventData } from '@/types'
import type { ArenaRenderer } from './ArenaRenderer'
import type { ResourceStat } from './CombatantCard'
import { CATEGORY_COLORS, COLORS, effectColor, formatDelta } from './palette'

const PLAYER_ID = 'PLAYER'
const RESOURCE_STATS: ResourceStat[] = ['hp', 'mana', 'stamina']
/** Extra time an attacking NPC stays in front after its action resolved. */
const ENEMY_FRONT_HOLD_MS = 1500

type Handler = (data: CombatEventData) => Promise<void>
/** Shows a speech bubble for the combatant and resolves once it has been read. */
export type SpeakHandler = (entityId: string, line: string) => Promise<void>

/** Turns structured combat log events into arena animations. */
export class ArenaEventPlayer {
  private readonly handlers: Partial<Record<CombatEventData['kind'], Handler>>

  constructor(private readonly arena: ArenaRenderer, private readonly speak: SpeakHandler | null = null) {
    this.handlers = {
      banter: (d) => this.banter(d),
      attack: (d) => this.attack(d),
      special: (d) => this.special(d),
      rest: (d) => this.applyEffects(d.effects),
      consume: (d) => this.applyEffects(d.effects),
      event: (d) => this.gmEvent(d),
      engage: (d) => this.engage(d),
      defeat: (d) => this.knockOut(d, 'defeated'),
      fled: (d) => this.knockOut(d, 'fled'),
      initiative: (d) => this.arena.effects.banner(this.arena.center(), `ROUND ${d.round ?? ''}`.trim(), COLORS.gold, 450, 46),
      turn: (d) => this.turn(d),
      victory: () => this.arena.effects.banner(this.arena.center(), 'VICTORY', COLORS.gold, 900, 64),
      game_over: () => this.arena.effects.banner(this.arena.center(), 'DEFEAT', COLORS.hp, 900, 64),
      run: (d) => this.arena.effects.banner(this.arena.center(), d.success ? 'ESCAPED!' : 'NO ESCAPE', d.success ? COLORS.player : COLORS.enemy, 500, 44),
    }
  }

  async play(data: CombatEventData | undefined): Promise<void> {
    const handler = data ? this.handlers[data.kind] : undefined
    if (handler && data) await handler(data)
  }

  private sideColor(actorId: string | null | undefined): number {
    return actorId === PLAYER_ID ? COLORS.player : COLORS.enemy
  }

  /** Keeps an NPC card in front for its whole action so the player sees who is acting. */
  private async withEnemyInFront(d: CombatEventData, action: () => Promise<void>): Promise<void> {
    await this.arena.advance(d.actor, d.target)
    try {
      await action()
      await this.arena.tween.wait(ENEMY_FRONT_HOLD_MS)
    } finally {
      await this.arena.retreat(d.actor)
    }
  }

  private async attack(d: CombatEventData): Promise<void> {
    if (d.actor !== PLAYER_ID) {
      await this.withEnemyInFront(d, () => this.resolveAttack(d))
      return
    }
    await this.arena.lunge(d.actor, d.target)
    await this.resolveAttack(d)
  }

  private async resolveAttack(d: CombatEventData): Promise<void> {
    if (d.d20 !== undefined) {
      await this.arena.dice.roll({
        d20: d.d20,
        modifier: d.modifier,
        total: d.total,
        dc: d.dc,
        success: !!d.success,
        crit: d.crit,
        fumble: d.fumble,
        color: this.sideColor(d.actor),
        caption: d.label ? `${d.label} vs AC` : 'Attack vs AC',
      })
    }
    if (!d.success) {
      await this.arena.effects.floatText(this.arena.cardCenter(d.target), 'MISS', COLORS.miss, 30)
      return
    }
    await this.applyEffects(d.effects, !!d.crit)
  }

  private async special(d: CombatEventData): Promise<void> {
    if (d.actor !== PLAYER_ID && d.target) {
      await this.withEnemyInFront(d, () => this.resolveSpecial(d))
      return
    }
    await this.resolveSpecial(d)
  }

  private async resolveSpecial(d: CombatEventData): Promise<void> {
    const color = CATEGORY_COLORS[d.category ?? 'MAGIC']
    const actorPoint = this.arena.cardCenter(d.actor)
    void this.arena.effects.burst(actorPoint, color, 14, 70)
    await this.arena.effects.floatText({ x: actorPoint.x, y: actorPoint.y - 40 }, d.action_name ?? 'Special', color, 26)
    if (d.rolled && d.d20 !== undefined) {
      await this.arena.dice.roll({
        d20: d.d20,
        modifier: d.modifier,
        total: d.total,
        dc: d.dc,
        success: !!d.success,
        crit: d.crit,
        fumble: d.fumble,
        color,
        caption: `${(d.stat ?? '').toUpperCase()} check`,
      })
    }
    if (!d.success) {
      await this.arena.effects.floatText(actorPoint, 'FAILED', COLORS.miss, 28)
      return
    }
    // Area attacks list every combatant caught in the area; one projectile flies to each.
    const targetIds = d.targets?.length ? d.targets.map((t) => t.id) : d.target ? [d.target] : []
    await Promise.all(targetIds.map((id) => this.arena.effects.projectile(actorPoint, this.arena.cardCenter(id), color)))
    const selfEffects = (d.effects ?? []).some((e) => e.entity === d.actor && e.delta !== 0)
    await Promise.all([
      this.applyEffects(d.effects, !!d.crit, color),
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

  private async gmEvent(d: CombatEventData): Promise<void> {
    const player = this.arena.card(PLAYER_ID)
    if (player) {
      const flash = player.flashColor(CATEGORY_COLORS.MAGIC)
      void this.arena.tween.to(flash, { alpha: 0 }, 600)
    }
    await this.applyEffects(d.effects, true)
  }

  private async engage(d: CombatEventData): Promise<void> {
    const card = this.arena.card(d.entity)
    if (!card) return
    await this.arena.tween.to(card.scale, { x: card.home.scale * 1.12, y: card.home.scale * 1.12 }, 160)
    void this.arena.tween.to(card.scale, { x: card.home.scale, y: card.home.scale }, 260)
    await this.arena.effects.floatText(this.arena.cardCenter(d.entity), 'ENGAGED!', COLORS.enemy, 26)
  }

  private async knockOut(d: CombatEventData, kind: 'defeated' | 'fled'): Promise<void> {
    const card = this.arena.card(d.entity)
    if (!card) return
    const label = kind === 'fled' ? 'FLED!' : 'DEFEATED'
    void this.arena.effects.floatText(this.arena.cardCenter(d.entity), label, COLORS.goldSoft, 30)
    await this.arena.tween.to(card, { rotation: card.rotation + 0.25, alpha: 0.5 }, 420)
    card.markOut(kind)
    if (d.xp) {
      await this.arena.effects.floatText(this.arena.cardCenter(PLAYER_ID), `+${d.xp} XP`, COLORS.gold, 26)
    }
  }

  /** Lifts the speaker out of the stack while its speech bubble is shown. */
  private async banter(d: CombatEventData): Promise<void> {
    const card = this.arena.card(d.actor)
    if (!card || !d.line || !this.speak) return
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
    await this.arena.effects.banner(this.arena.center(), 'YOUR TURN', COLORS.player, 300, 36)
  }

  private async applyEffects(effects: AppliedEffect[] | undefined, heavy = false, tint?: number): Promise<void> {
    const jobs = (effects ?? []).filter((e) => e.delta !== 0).map((e) => this.applyEffect(e, heavy, tint))
    await Promise.all(jobs)
  }

  private async applyEffect(effect: AppliedEffect, heavy: boolean, tint?: number): Promise<void> {
    const card = this.arena.card(effect.entity)
    if (!card) return
    const point = this.arena.cardCenter(effect.entity)
    const jobs: Promise<void>[] = [
      this.arena.effects.floatText(point, formatDelta(effect.stat, effect.delta), effectColor(effect.stat, effect.delta), heavy ? 38 : 30),
    ]
    if (RESOURCE_STATS.includes(effect.stat as ResourceStat)) {
      const stat = effect.stat as ResourceStat
      const from = card.displayed[stat]
      jobs.push(this.arena.tween.run(500, (p) => card.setDisplayed(stat, from + effect.delta * p)))
    } else {
      const modifiers = { ...card.data.modifiers }
      modifiers[effect.stat] = (modifiers[effect.stat] ?? 0) + effect.delta
      card.setData({ ...card.data, modifiers })
    }
    if (effect.stat === 'hp' && effect.delta < 0) {
      const flash = card.flashColor(COLORS.hp)
      jobs.push(this.arena.tween.to(flash, { alpha: 0 }, 450))
      jobs.push(this.arena.effects.shake(heavy ? this.arena.stage : card, heavy ? 12 : 8))
      jobs.push(this.arena.effects.burst(point, tint ?? COLORS.hp, heavy ? 26 : 16))
    }
    await Promise.all(jobs)
  }
}
