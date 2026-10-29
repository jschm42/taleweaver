import { BlurFilter, ColorMatrixFilter, Container, Graphics, Sprite, Text, Texture } from 'pixi.js'
import type { CombatStat } from '@/types'
import { ARENA_FONT, COLORS, STAT_SHORT } from './palette'

export type CardSide = 'player' | 'enemy'
export type ResourceStat = 'hp' | 'mana' | 'stamina'

export interface CardData {
  id: string
  name: string
  imageUrl: string | null
  side: CardSide
  hp: number
  maxHp: number
  mana: number
  maxMana: number
  stamina: number
  maxStamina: number
  modifiers: Partial<Record<CombatStat, number>>
  engaged: boolean
  out: 'defeated' | 'fled' | null
  /** Initiative total this round; null while the combatant is not in the order. */
  initiative: number | null
}

const PORTRAIT_RATIO = 0.64
const RADIUS = 14

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`Image failed: ${url}`))
    img.src = url
  })
}

/** A playing-card style combatant with portrait, resource bars and status tags. */
export class CombatantCard extends Container {
  readonly entityId: string
  readonly displayed: Record<ResourceStat, number> = { hp: 0, mana: 0, stamina: 0 }
  data: CardData
  cardWidth: number
  cardHeight: number
  selected = false
  active = false
  /** Layout target, used by the renderer when animating the stack. */
  home = { x: 0, y: 0, rotation: 0, scale: 1, alpha: 1 }

  private readonly glow = new Graphics()
  private readonly frame = new Graphics()
  private readonly portraitMask = new Graphics()
  private readonly portraitBg = new Graphics()
  private readonly placeholder: Text
  private readonly nameText: Text
  private readonly hpText: Text
  private readonly modsText: Text
  private readonly tagText: Text
  private readonly tagBg = new Graphics()
  private readonly initText: Text
  private readonly initBg = new Graphics()
  private readonly bars = new Graphics()
  private readonly flash = new Graphics()
  private readonly stamp: Text
  private readonly greyscale = new ColorMatrixFilter()
  private portrait: Sprite | null = null
  private portraitUrl: string | null = null

  constructor(data: CardData, width: number, height: number) {
    super()
    this.entityId = data.id
    this.data = data
    this.cardWidth = width
    this.cardHeight = height
    this.greyscale.desaturate()

    this.placeholder = new Text({
      text: data.side === 'player' ? '⚔' : '☠',
      style: { fontFamily: ARENA_FONT, fontSize: 48, fill: data.side === 'player' ? COLORS.player : COLORS.enemy },
    })
    this.nameText = new Text({ text: '', style: { fontFamily: ARENA_FONT, fontSize: 16, fill: COLORS.white } })
    this.hpText = new Text({ text: '', style: { fontFamily: ARENA_FONT, fontSize: 12, fill: COLORS.goldSoft } })
    this.modsText = new Text({ text: '', style: { fontFamily: ARENA_FONT, fontSize: 11, fill: COLORS.attribute } })
    this.tagText = new Text({ text: '', style: { fontFamily: ARENA_FONT, fontSize: 10, fill: COLORS.ink, letterSpacing: 1.5 } })
    this.initText = new Text({ text: '', style: { fontFamily: ARENA_FONT, fontSize: 11, fill: COLORS.goldSoft, letterSpacing: 1 } })
    this.stamp = new Text({
      text: '',
      style: {
        fontFamily: ARENA_FONT,
        fontSize: 26,
        fill: COLORS.hp,
        stroke: { color: COLORS.ink, width: 4 },
        letterSpacing: 3,
      },
    })
    this.stamp.anchor.set(0.5)
    this.placeholder.anchor.set(0.5)

    this.glow.filters = [new BlurFilter({ strength: 6 })]
    this.addChild(this.glow, this.frame, this.portraitBg, this.placeholder, this.portraitMask, this.flash)
    this.addChild(this.bars, this.nameText, this.hpText, this.modsText, this.tagBg, this.tagText, this.initBg, this.initText, this.stamp)
    this.flash.alpha = 0

    this.setData(data, true)
  }

  setData(data: CardData, snapDisplayed = false): void {
    this.data = data
    if (snapDisplayed) {
      this.displayed.hp = data.hp
      this.displayed.mana = data.mana
      this.displayed.stamina = data.stamina
    }
    if (data.imageUrl !== this.portraitUrl) {
      this.portraitUrl = data.imageUrl
      void this.loadPortrait(data.imageUrl)
    }
    this.redraw()
  }

  resize(width: number, height: number): void {
    this.cardWidth = width
    this.cardHeight = height
    this.redraw()
  }

  setDisplayed(stat: ResourceStat, value: number): void {
    this.displayed[stat] = value
    this.drawBars()
  }

  setHighlight(selected: boolean, active: boolean): void {
    if (this.selected === selected && this.active === active) return
    this.selected = selected
    this.active = active
    this.redraw()
  }

  /** Called every frame by the renderer to pulse the glow. */
  pulse(phase: number): void {
    if (this.selected || this.active) {
      this.glow.alpha = 0.65 + Math.sin(phase) * 0.35
    }
  }

  /** Marks the card out of the fight right away (used during playback before the final sync). */
  markOut(kind: 'defeated' | 'fled'): void {
    this.setData({ ...this.data, out: kind })
  }

  flashColor(color: number): Graphics {
    this.flash.clear()
      .roundRect(0, 0, this.cardWidth, this.cardHeight, RADIUS)
      .fill({ color, alpha: 0.55 })
    this.flash.alpha = 1
    return this.flash
  }

  private async loadPortrait(url: string | null): Promise<void> {
    if (this.portrait) {
      this.portrait.destroy()
      this.portrait = null
    }
    if (!url) {
      this.redraw()
      return
    }
    try {
      const img = await loadImage(url)
      if (this.destroyed || url !== this.portraitUrl) return
      this.portrait = new Sprite(Texture.from(img))
      this.portrait.mask = this.portraitMask
      this.addChildAt(this.portrait, this.getChildIndex(this.portraitMask))
      this.redraw()
    } catch {
      this.redraw()
    }
  }

  private redraw(): void {
    const w = this.cardWidth
    const h = this.cardHeight
    this.pivot.set(w / 2, h / 2)
    const accent = this.accentColor()
    const out = this.data.out !== null

    this.frame.clear()
      .roundRect(0, 0, w, h, RADIUS).fill({ color: COLORS.ink })
      .roundRect(3, 3, w - 6, h - 6, RADIUS - 3).fill({ color: COLORS.panel })
      .roundRect(0, 0, w, h, RADIUS).stroke({ width: 2, color: accent, alpha: 0.85 })
      .roundRect(6, h * PORTRAIT_RATIO + 2, w - 12, 1, 0).fill({ color: accent, alpha: 0.35 })

    this.drawPortrait(w, h)
    this.layoutTexts(w, h, accent)
    this.drawBars()
    this.drawGlow(1)

    this.stamp.text = out ? (this.data.out === 'fled' ? 'FLED' : 'DEFEATED') : ''
    this.stamp.position.set(w / 2, h * 0.36)
    this.stamp.rotation = -0.32
    this.filters = out ? [this.greyscale] : []
  }

  private drawPortrait(w: number, h: number): void {
    const ph = h * PORTRAIT_RATIO
    const accent = this.accentColor()
    this.portraitBg.clear()
      .roundRect(6, 6, w - 12, ph - 6, RADIUS - 6).fill({ color: COLORS.panelLight })
      .circle(w / 2, ph / 2, Math.min(w, ph) * 0.3).fill({ color: accent, alpha: 0.08 })
    this.portraitMask.clear().roundRect(6, 6, w - 12, ph - 6, RADIUS - 6).fill({ color: 0xffffff })
    this.portraitMask.visible = !!this.portrait
    this.placeholder.position.set(w / 2, ph / 2)
    this.placeholder.style.fontSize = Math.round(Math.min(w, ph) * 0.3)
    this.placeholder.visible = !this.portrait
    if (!this.portrait) return
    const tex = this.portrait.texture
    const scale = Math.max((w - 12) / tex.width, (ph - 6) / tex.height)
    this.portrait.scale.set(scale)
    this.portrait.position.set(w / 2 - (tex.width * scale) / 2, 6)
  }

  private layoutTexts(w: number, h: number, accent: number): void {
    const infoTop = h * PORTRAIT_RATIO + 8
    const fontScale = Math.max(0.75, Math.min(1.25, w / 190))
    this.nameText.style.fontSize = Math.round(16 * fontScale)
    this.nameText.text = this.truncate(this.data.name, Math.floor(w / (8.5 * fontScale)))
    this.nameText.position.set(10, infoTop)
    this.hpText.style.fontSize = Math.round(12 * fontScale)
    this.hpText.position.set(10, infoTop + 22 * fontScale)
    this.modsText.style.fontSize = Math.round(11 * fontScale)
    this.modsText.text = this.modifierLine()
    this.modsText.position.set(10, h - 18 * fontScale)

    this.layoutInitiative(w)

    const tag = this.tagLabel()
    this.tagText.text = tag
    this.tagBg.clear()
    this.tagText.visible = !!tag
    this.tagBg.visible = !!tag
    if (!tag) return
    this.tagText.position.set(16, 12)
    this.tagBg.roundRect(10, 9, this.tagText.width + 12, this.tagText.height + 6, 6).fill({ color: accent })
  }

  private layoutInitiative(w: number): void {
    const value = this.data.out ? null : this.data.initiative
    this.initText.visible = value !== null
    this.initBg.visible = value !== null
    this.initBg.clear()
    if (value === null) return
    this.initText.text = `INIT ${value}`
    const x = w - this.initText.width - 16
    this.initText.position.set(x, 12)
    this.initBg.roundRect(x - 6, 9, this.initText.width + 12, this.initText.height + 6, 6)
      .fill({ color: COLORS.ink, alpha: 0.8 })
      .stroke({ width: 1, color: COLORS.gold, alpha: 0.6 })
  }

  private drawBars(): void {
    const w = this.cardWidth
    const h = this.cardHeight
    const fontScale = Math.max(0.75, Math.min(1.25, w / 190))
    const top = h * PORTRAIT_RATIO + 42 * fontScale
    const barW = w - 20
    const d = this.data
    this.bars.clear()
    this.drawBar(10, top, barW, 8 * fontScale, this.displayed.hp, d.maxHp, COLORS.hp)
    let y = top + 12 * fontScale
    if (d.maxStamina > 0) {
      this.drawBar(10, y, barW, 4 * fontScale, this.displayed.stamina, d.maxStamina, COLORS.stamina)
      y += 7 * fontScale
    }
    if (d.maxMana > 0) {
      this.drawBar(10, y, barW, 4 * fontScale, this.displayed.mana, d.maxMana, COLORS.mana)
    }
    this.hpText.text = `HP ${Math.max(0, Math.round(this.displayed.hp))} / ${d.maxHp}`
  }

  private drawBar(x: number, y: number, w: number, h: number, value: number, max: number, color: number): void {
    const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0
    this.bars.roundRect(x, y, w, h, h / 2).fill({ color: COLORS.panelLight })
    if (pct > 0) {
      this.bars.roundRect(x, y, Math.max(h, w * pct), h, h / 2).fill({ color })
    }
  }

  private drawGlow(alpha: number): void {
    const show = (this.selected || this.active) && this.data.out === null
    this.glow.clear()
    if (!show) return
    const color = this.active ? COLORS.gold : this.accentColor()
    this.glow.roundRect(-6, -6, this.cardWidth + 12, this.cardHeight + 12, RADIUS + 6)
      .stroke({ width: 8, color, alpha: 0.9 })
    this.glow.alpha = alpha
  }

  private accentColor(): number {
    if (this.data.out) return COLORS.muted
    if (this.data.side === 'player') return COLORS.player
    return this.data.engaged ? COLORS.enemy : COLORS.passive
  }

  private tagLabel(): string {
    if (this.data.out) return ''
    if (this.data.side === 'player') return 'YOU'
    if (!this.data.engaged) return 'PASSIVE'
    return this.selected ? 'TARGET' : ''
  }

  private modifierLine(): string {
    const parts = Object.entries(this.data.modifiers || {})
      .filter(([, v]) => typeof v === 'number' && v !== 0)
      .map(([k, v]) => `${STAT_SHORT[k as CombatStat] ?? k} ${v! > 0 ? '+' : ''}${v}`)
    return parts.join('  ')
  }

  private truncate(text: string, max: number): string {
    return text.length > max ? `${text.slice(0, Math.max(1, max - 1))}…` : text
  }
}
