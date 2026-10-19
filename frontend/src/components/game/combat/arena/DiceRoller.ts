import { Container, Graphics, Text } from 'pixi.js'
import { ARENA_FONT, COLORS } from './palette'
import { easeOutBack, type Tweener } from './tween'

export interface DiceRollSpec {
  d20: number
  modifier?: number
  total?: number
  dc?: number
  success: boolean
  crit?: boolean
  fumble?: boolean
  color: number
  caption?: string
}

const SIZE = 54

/** Animated d20 that tumbles, lands on the rolled value and shows the verdict. */
export class DiceRoller extends Container {
  private readonly die = new Graphics()
  private readonly face: Text
  private readonly detail: Text
  private readonly verdict: Text
  private readonly caption: Text

  constructor(private readonly tween: Tweener) {
    super()
    const textStyle = { fontFamily: ARENA_FONT, fill: COLORS.white, stroke: { color: COLORS.ink, width: 4 } }
    this.face = new Text({ text: '20', style: { ...textStyle, fontSize: 34 } })
    this.detail = new Text({ text: '', style: { ...textStyle, fontSize: 16, fill: COLORS.goldSoft } })
    this.verdict = new Text({ text: '', style: { ...textStyle, fontSize: 24, letterSpacing: 3 } })
    this.caption = new Text({ text: '', style: { ...textStyle, fontSize: 15, fill: COLORS.goldSoft } })
    for (const t of [this.face, this.detail, this.verdict, this.caption]) {
      t.anchor.set(0.5)
    }
    this.detail.y = SIZE + 22
    this.verdict.y = SIZE + 50
    this.caption.y = -SIZE - 22
    this.addChild(this.die, this.face, this.detail, this.verdict, this.caption)
    this.alpha = 0
  }

  async roll(spec: DiceRollSpec): Promise<void> {
    this.drawDie(spec.color)
    this.caption.text = spec.caption || ''
    this.detail.text = ''
    this.verdict.text = ''
    this.alpha = 1
    this.scale.set(0.6)

    let lastSwap = 0
    await this.tween.run(700, (p) => {
      this.die.rotation = p * Math.PI * 4
      this.scale.set(0.6 + 0.4 * p)
      if (p - lastSwap > 0.08 && p < 0.92) {
        lastSwap = p
        this.face.text = String(1 + Math.floor(Math.random() * 20))
      }
    })
    this.die.rotation = 0
    this.face.text = String(spec.d20)
    this.face.style.fill = spec.crit ? COLORS.gold : spec.fumble ? COLORS.hp : COLORS.white
    await this.tween.to(this.face.scale, { x: 1.35, y: 1.35 }, 120)
    await this.tween.to(this.face.scale, { x: 1, y: 1 }, 260, easeOutBack)

    if (spec.total !== undefined && spec.dc !== undefined) {
      const mod = spec.modifier ?? spec.total - spec.d20
      this.detail.text = `${spec.d20} ${mod >= 0 ? '+' : '-'} ${Math.abs(mod)} = ${spec.total}  vs  ${spec.dc}`
    }
    this.verdict.text = this.verdictText(spec)
    this.verdict.style.fill = spec.success ? (spec.crit ? COLORS.gold : COLORS.player) : COLORS.enemy
    await this.tween.wait(650)
    await this.tween.to(this, { alpha: 0 }, 220)
  }

  private verdictText(spec: DiceRollSpec): string {
    if (spec.crit) return 'CRITICAL!'
    if (spec.fumble) return 'FUMBLE!'
    return spec.success ? 'SUCCESS' : 'FAILED'
  }

  private drawDie(color: number): void {
    const points: number[] = []
    for (let i = 0; i < 6; i += 1) {
      const angle = Math.PI / 6 + (i * Math.PI) / 3
      points.push(Math.cos(angle) * SIZE, Math.sin(angle) * SIZE)
    }
    const inner = [0, -SIZE * 0.62, SIZE * 0.54, SIZE * 0.31, -SIZE * 0.54, SIZE * 0.31]
    this.die.clear()
      .circle(0, 0, SIZE * 1.25).fill({ color, alpha: 0.12 })
      .poly(points).fill({ color: COLORS.ink }).stroke({ width: 3, color })
      .poly(inner).stroke({ width: 1.5, color, alpha: 0.6 })
    for (let i = 0; i < 6; i += 2) {
      this.die.moveTo(inner[i], inner[i + 1]).lineTo(points[(i + 2) % 12], points[(i + 3) % 12])
    }
    this.die.stroke({ width: 1.5, color, alpha: 0.4 })
  }
}
