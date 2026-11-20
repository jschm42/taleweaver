import type { CombatantCard } from './CombatantCard'
import { easeInQuad, easeOutBack, easeOutCubic, type Tweener } from './tween'

type CardId = string | null | undefined
type CardLookup = (id: CardId) => CombatantCard | undefined

/** How far an attacker steps toward its target, as a share of the distance. */
export const MELEE_REACH = 0.22
export const RANGED_REACH = 0.07

/** Body language of the cards during an action: stepping up, striking, recoiling, dodging. */
export class CardMoves {
  constructor(
    private readonly tween: Tweener,
    private readonly card: CardLookup,
  ) {}

  /** Brings the actor card in front and toward the target; it stays there until the renderer's `retreat`. */
  async advance(actorId: CardId, targetId: CardId, reach = MELEE_REACH): Promise<void> {
    const actor = this.card(actorId)
    const target = this.card(targetId)
    if (!actor || !target) return
    const dx = (target.home.x - actor.home.x) * reach
    const dy = (target.home.y - actor.home.y) * reach
    actor.zIndex = 500
    await this.tween.to(actor, { x: actor.home.x + dx, y: actor.home.y + dy }, 180, easeOutCubic)
  }

  /** Anticipation before an attack: the card rears back and swells. */
  async windUp(actorId: CardId, targetId: CardId): Promise<void> {
    const actor = this.card(actorId)
    if (!actor) return
    const away = -this.direction(actor, this.card(targetId))
    const scale = actor.home.scale * 1.07
    await Promise.all([
      this.tween.to(actor, { x: actor.x + away * 14, rotation: actor.home.rotation + away * 0.05 }, 260),
      this.tween.to(actor.scale, { x: scale, y: scale }, 260),
    ])
  }

  /** The blow itself: a fast jab from wherever the card stands toward the target. */
  async strike(actorId: CardId, targetId: CardId): Promise<void> {
    const actor = this.card(actorId)
    const target = this.card(targetId)
    if (!actor || !target) return
    const x = actor.x + (target.home.x - actor.x) * 0.3
    const y = actor.y + (target.home.y - actor.y) * 0.3
    await Promise.all([
      this.tween.to(actor, { x, y, rotation: actor.home.rotation }, 90, easeInQuad),
      this.tween.to(actor.scale, { x: actor.home.scale, y: actor.home.scale }, 90),
    ])
  }

  /** Kick of a shot or a spell: the card snaps back from the target and settles. */
  async recoil(actorId: CardId, targetId: CardId): Promise<void> {
    const actor = this.card(actorId)
    if (!actor) return
    const origin = actor.x
    const away = -this.direction(actor, this.card(targetId))
    void this.tween.to(actor.scale, { x: actor.home.scale, y: actor.home.scale }, 120)
    await this.tween.to(actor, { x: origin + away * 16, rotation: actor.home.rotation }, 70)
    await this.tween.to(actor, { x: origin }, 220, easeOutBack)
  }

  /** A hit shoves the target away from its attacker before it swings back into place. */
  async knockback(targetId: CardId, fromId: CardId, heavy = false): Promise<void> {
    const target = this.card(targetId)
    const from = this.card(fromId)
    if (!target || !from || target === from || target.gone) return
    const push = this.direction(from, target) * (heavy ? 30 : 16)
    await this.tween.to(target, { x: target.home.x + push, rotation: target.home.rotation + push * 0.004 }, 80)
    await this.tween.to(target, { x: target.home.x, rotation: target.home.rotation }, 320, easeOutBack)
  }

  /** The target slips aside from a blow that missed. */
  async dodge(targetId: CardId): Promise<void> {
    const target = this.card(targetId)
    if (!target || target.gone) return
    await this.tween.to(target, { y: target.home.y - 20, rotation: target.home.rotation - 0.06 }, 110)
    await this.tween.to(target, { y: target.home.y, rotation: target.home.rotation }, 300, easeOutBack)
  }

  /** A fumbled action: the card wobbles on the spot. */
  async wobble(actorId: CardId): Promise<void> {
    const actor = this.card(actorId)
    if (!actor) return
    const rest = actor.rotation
    await this.tween.run(520, (p) => {
      actor.rotation = rest + Math.sin(p * Math.PI * 5) * 0.09 * (1 - p)
    }, (t) => t)
    actor.rotation = rest
  }

  /** -1 when `to` lies left of `from`, otherwise 1 (also without a target). */
  private direction(from: CombatantCard, to: CombatantCard | undefined): number {
    return to && to.home.x < from.home.x ? -1 : 1
  }
}
