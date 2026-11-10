import { Application, Container, Graphics, type FederatedPointerEvent } from 'pixi.js'
import { CardMoves } from './cardMoves'
import { CombatantCard, type CardData } from './CombatantCard'
import { DiceRoller } from './DiceRoller'
import { ArenaEffects, type Point } from './effects'
import { ImpactEffects } from './impactFx'
import { COLORS } from './palette'
import { easeOutBack, Tweener } from './tween'

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
const INTRO_STAGGER_MS = 90

/** Owns the Pixi application and lays out the protagonist card and the enemy card stack. */
export class ArenaRenderer {
  readonly app = new Application()
  readonly cards = new Map<string, CombatantCard>()
  tween!: Tweener
  effects!: ArenaEffects
  impact!: ImpactEffects
  moves!: CardMoves
  dice!: DiceRoller
  /** Reduced motion: no screen flashes, shakes or hit-stops. */
  calm = false
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
    this.impact = new ImpactEffects(this.fxLayer, this.tween)
    this.moves = new CardMoves(this.tween, (id) => this.card(id))
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

  /** Returns an advanced actor card to its place in the layout. */
  async retreat(actorId: string | null | undefined): Promise<void> {
    const actor = this.card(actorId)
    if (!actor) return
    await this.tween.to(actor, { x: actor.home.x, y: actor.home.y }, 260, easeOutBack)
    this.relayout(false)
  }

  /** Stage-wide flash; left out when the player asked for reduced motion. */
  async flash(color: number, strength = 0.35): Promise<void> {
    if (this.calm) return
    await this.impact.screenFlash(this.width, this.height, color, strength)
  }

  /** Shakes the whole stage (heavy hits); left out when the player asked for reduced motion. */
  async quake(strength = 12): Promise<void> {
    if (this.calm) return
    await this.effects.shake(this.stage, strength)
  }

  /** Hit-stop: freezes the action for a few frames at the moment of impact. */
  hitStop(ms: number): void {
    if (!this.calm) this.tween.freeze(ms)
  }

  /** Fight opening: the cards are dealt in from both sides, then the banner drops. */
  async playIntro(): Promise<void> {
    if (!this.ready || !this.view) return
    const order = [this.view.player, ...this.stackOrder(this.view)]
    const entrances = order.map((data, index) => this.dealIn(this.cards.get(data.id), index * INTRO_STAGGER_MS))
    await Promise.all(entrances)
    await this.effects.banner(this.center(), 'FIGHT!', COLORS.gold, 420, 60, this.width)
  }

  private async dealIn(card: CombatantCard | undefined, delay: number): Promise<void> {
    if (!card) return
    const offstage = card.data.side === 'player' ? -card.cardWidth : this.width + card.cardWidth
    card.position.x = offstage
    card.alpha = 0
    await this.tween.wait(delay)
    await Promise.all([
      this.tween.to(card, { x: card.home.x }, 420, easeOutBack),
      this.tween.to(card, { alpha: card.home.alpha }, 260),
    ])
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
    // A shattered card keeps its place in the layout but stays invisible.
    const alpha = card.gone ? 0 : home.alpha
    if (!animate) {
      card.position.set(home.x, home.y)
      card.rotation = home.rotation
      card.scale.set(home.scale)
      card.alpha = alpha
      return
    }
    void this.tween.to(card, { x: home.x, y: home.y, rotation: home.rotation, alpha }, 380)
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
