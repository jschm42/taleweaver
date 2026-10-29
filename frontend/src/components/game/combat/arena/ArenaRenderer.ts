import { Application, Container, Graphics, type FederatedPointerEvent } from 'pixi.js'
import { CombatantCard, type CardData } from './CombatantCard'
import { DiceRoller } from './DiceRoller'
import { ArenaEffects, type Point } from './effects'
import { COLORS } from './palette'
import { easeOutBack, easeOutCubic, Tweener } from './tween'

export interface ArenaView {
  player: CardData
  enemies: CardData[]
  selectedId: string | null
  activeId: string | null
}

const CARD_RATIO = 0.7
const PLAYER_X = 0.19
const STACK_X = 0.62
const STACK_ROTATION = 0.07
const STACK_SCALE_STEP = 0.07
const EDGE_MARGIN = 12

/** Owns the Pixi application and lays out the protagonist card and the enemy card stack. */
export class ArenaRenderer {
  readonly app = new Application()
  readonly cards = new Map<string, CombatantCard>()
  tween!: Tweener
  effects!: ArenaEffects
  dice!: DiceRoller
  readonly stage = new Container()
  onSelect: ((id: string) => void) | null = null
  onHover: ((id: string | null, event: MouseEvent | null) => void) | null = null

  private readonly backdrop = new Graphics()
  private readonly cardLayer = new Container({ sortableChildren: true })
  private readonly fxLayer = new Container()
  private view: ArenaView | null = null
  private phase = 0
  private ready = false
  private destroyed = false

  async init(host: HTMLElement): Promise<boolean> {
    try {
      await document.fonts?.load('20px Acme')
    } catch {
      // Fallback fonts are fine.
    }
    await this.app.init({
      resizeTo: host,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(2, window.devicePixelRatio || 1),
    })
    if (this.destroyed) {
      this.app.destroy(true, { children: true })
      return false
    }
    host.appendChild(this.app.canvas)
    this.tween = new Tweener(this.app.ticker)
    this.effects = new ArenaEffects(this.fxLayer, this.tween)
    this.dice = new DiceRoller(this.tween)
    this.stage.addChild(this.backdrop, this.cardLayer, this.fxLayer, this.dice)
    this.app.stage.addChild(this.stage)
    this.app.renderer.on('resize', () => this.relayout(false))
    this.app.ticker.add((ticker) => {
      this.phase += ticker.deltaMS / 280
      this.cards.forEach((card) => card.pulse(this.phase))
    })
    this.ready = true
    if (this.view) this.sync(this.view, true)
    return true
  }

  get width(): number {
    return this.ready ? this.app.screen.width : 0
  }

  get height(): number {
    return this.ready ? this.app.screen.height : 0
  }

  /** Midpoint between the protagonist and the enemy stack. */
  center(): Point {
    return { x: this.width * 0.405, y: this.height * 0.42 }
  }

  card(id: string | null | undefined): CombatantCard | undefined {
    return id ? this.cards.get(id) : undefined
  }

  cardCenter(id: string | null | undefined): Point {
    const card = this.card(id)
    return card ? { x: card.home.x, y: card.home.y - card.cardHeight * 0.15 } : this.center()
  }

  /** Top centre of a card in canvas (CSS pixel) coordinates, e.g. to anchor a speech bubble. */
  cardTop(id: string | null | undefined): Point {
    const card = this.card(id)
    if (!card) return this.center()
    return { x: card.home.x, y: card.home.y - (card.cardHeight * card.home.scale) / 2 }
  }

  /** Restores every card to its layout slot (z-order included) without animation. */
  relayoutCards(): void {
    this.relayout(false)
  }

  sync(view: ArenaView, snapDisplayed: boolean): void {
    this.view = view
    if (!this.ready) return
    const all = [view.player, ...view.enemies]
    const ids = new Set(all.map((d) => d.id))
    for (const [id, card] of this.cards) {
      if (!ids.has(id)) {
        card.destroy({ children: true })
        this.cards.delete(id)
      }
    }
    const size = this.cardSize()
    for (const data of all) {
      const existing = this.cards.get(data.id)
      if (existing) {
        existing.setData(data, snapDisplayed)
      } else {
        this.cards.set(data.id, this.createCard(data, size.w, size.h))
      }
      this.cards.get(data.id)!.setHighlight(data.id === view.selectedId, data.id === view.activeId)
    }
    this.relayout(true)
  }

  /** Moves the actor card toward the target and back. */
  async lunge(actorId: string | null | undefined, targetId: string | null | undefined): Promise<void> {
    await this.advance(actorId, targetId)
    await this.retreat(actorId)
  }

  /** Brings the actor card in front and toward the target; it stays there until `retreat`. */
  async advance(actorId: string | null | undefined, targetId: string | null | undefined): Promise<void> {
    const actor = this.card(actorId)
    const target = this.card(targetId)
    if (!actor || !target) return
    const dx = (target.home.x - actor.home.x) * 0.22
    const dy = (target.home.y - actor.home.y) * 0.22
    actor.zIndex = 500
    await this.tween.to(actor, { x: actor.home.x + dx, y: actor.home.y + dy }, 180, easeOutCubic)
  }

  /** Returns an advanced actor card to its place in the layout. */
  async retreat(actorId: string | null | undefined): Promise<void> {
    const actor = this.card(actorId)
    if (!actor) return
    await this.tween.to(actor, { x: actor.home.x, y: actor.home.y }, 260, easeOutBack)
    this.relayout(false)
  }

  destroy(): void {
    this.destroyed = true
    if (!this.ready) return
    this.ready = false
    this.tween.destroy()
    this.app.destroy(true, { children: true })
    this.cards.clear()
  }

  private createCard(data: CardData, w: number, h: number): CombatantCard {
    const card = new CombatantCard(data, w, h)
    card.eventMode = 'static'
    card.cursor = data.side === 'enemy' ? 'pointer' : 'default'
    card.on('pointertap', () => {
      if (card.data.side === 'enemy' && !card.data.out) this.onSelect?.(card.entityId)
    })
    card.on('pointerover', (e: FederatedPointerEvent) => this.onHover?.(card.entityId, e.nativeEvent as MouseEvent))
    card.on('pointermove', (e: FederatedPointerEvent) => this.onHover?.(card.entityId, e.nativeEvent as MouseEvent))
    card.on('pointerout', () => this.onHover?.(null, null))
    this.cardLayer.addChild(card)
    return card
  }

  private cardSize(): { w: number; h: number } {
    const byHeight = Math.min(360, Math.max(150, this.height * 0.72))
    const byWidth = (this.width * 0.36) / CARD_RATIO
    const h = Math.max(140, Math.min(byHeight, byWidth))
    return { w: Math.round(h * CARD_RATIO), h: Math.round(h) }
  }

  /** Selected target on top, then engaged enemies, passive ones, and finally those out of the fight. */
  private stackOrder(view: ArenaView): CardData[] {
    const rank = (d: CardData): number => {
      if (d.out) return 3
      if (d.id === view.selectedId) return 0
      return d.engaged ? 1 : 2
    }
    return [...view.enemies].sort((a, b) => rank(a) - rank(b))
  }

  private relayout(animate: boolean): void {
    if (!this.ready || !this.view) return
    this.drawBackdrop()
    const center = this.center()
    this.dice.position.set(center.x, center.y)
    const { w, h } = this.cardSize()
    const playerCard = this.cards.get(this.view.player.id)
    if (playerCard) {
      playerCard.resize(w, h)
      this.place(playerCard, { x: this.width * PLAYER_X, y: this.height * 0.5, rotation: -0.03, scale: 1, alpha: 1 }, 50, animate)
    }

    const order = this.stackOrder(this.view)
    const stackX = this.width * STACK_X
    const room = this.width - stackX - w * 0.5 - EDGE_MARGIN
    const spacing = order.length > 1 ? Math.min(w * 0.42, room / (order.length - 1)) : 0
    order.forEach((data, k) => {
      const card = this.cards.get(data.id)
      if (!card) return
      card.resize(w, h)
      const home = {
        x: stackX + k * spacing,
        y: this.height * 0.5 - k * 10,
        rotation: k * STACK_ROTATION,
        scale: Math.max(0.6, 1 - k * STACK_SCALE_STEP),
        alpha: data.out ? 0.55 : data.engaged ? 1 : 0.82,
      }
      this.place(card, home, 100 - k, animate)
    })
  }

  private place(card: CombatantCard, home: CombatantCard['home'], z: number, animate: boolean): void {
    card.home = home
    card.zIndex = z
    if (!animate) {
      card.position.set(home.x, home.y)
      card.rotation = home.rotation
      card.scale.set(home.scale)
      card.alpha = home.alpha
      return
    }
    void this.tween.to(card, { x: home.x, y: home.y, rotation: home.rotation, alpha: home.alpha }, 380)
    void this.tween.to(card.scale, { x: home.scale, y: home.scale }, 380)
  }

  private drawBackdrop(): void {
    const w = this.width
    const h = this.height
    this.backdrop.clear()
    for (let i = 6; i >= 1; i -= 1) {
      this.backdrop.ellipse(w * 0.45, h * 0.86, w * 0.08 * i, h * 0.035 * i).fill({ color: COLORS.gold, alpha: 0.012 * (7 - i) })
    }
    this.backdrop.ellipse(w * PLAYER_X, h * 0.5 + h * 0.36, w * 0.12, h * 0.04).fill({ color: COLORS.player, alpha: 0.08 })
    this.backdrop.ellipse(w * 0.7, h * 0.5 + h * 0.36, w * 0.2, h * 0.05).fill({ color: COLORS.enemy, alpha: 0.07 })
  }
}
