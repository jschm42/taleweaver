import { Container, Graphics, Text } from 'pixi.js'
import { ARENA_FONT, COLORS } from './palette'
import { easeInQuad, easeOutBack, easeOutCubic, type Tweener } from './tween'

export interface Point {
  x: number
  y: number
}

/** Short-lived visual effects (floating numbers, bursts, projectiles, banners). */
export class ArenaEffects {
  constructor(
    private readonly layer: Container,
    private readonly tween: Tweener,
  ) {}

  async floatText(at: Point, text: string, color: number, size = 30): Promise<void> {
    const label = new Text({
      text,
      style: {
        fontFamily: ARENA_FONT,
        fontSize: size,
        fill: color,
        stroke: { color: COLORS.ink, width: 5 },
        dropShadow: { color, blur: 10, distance: 0, alpha: 0.7 },
      },
    })
    label.anchor.set(0.5)
    label.position.set(at.x + (Math.random() - 0.5) * 30, at.y)
    label.scale.set(0.4)
    this.layer.addChild(label)
    await this.tween.to(label.scale, { x: 1, y: 1 }, 220, easeOutBack)
    await Promise.all([
      this.tween.to(label, { y: label.y - 70 }, 1100, easeOutCubic),
      this.tween.run(1100, (p) => { label.alpha = p < 0.6 ? 1 : 1 - (p - 0.6) / 0.4 }, (t) => t),
    ])
    label.destroy()
  }

  async burst(at: Point, color: number, count = 18, radius = 90): Promise<void> {
    const sparks = Array.from({ length: count }, () => {
      const g = new Graphics().circle(0, 0, 2 + Math.random() * 4).fill({ color })
      g.position.set(at.x, at.y)
      this.layer.addChild(g)
      const angle = Math.random() * Math.PI * 2
      const dist = radius * (0.4 + Math.random() * 0.6)
      return { g, dx: Math.cos(angle) * dist, dy: Math.sin(angle) * dist }
    })
    await this.tween.run(650, (p) => {
      for (const s of sparks) {
        s.g.position.set(at.x + s.dx * p, at.y + s.dy * p)
        s.g.alpha = 1 - p
      }
    })
    sparks.forEach((s) => s.g.destroy())
  }

  async projectile(from: Point, to: Point, color: number): Promise<void> {
    const orb = new Graphics()
      .circle(0, 0, 16).fill({ color, alpha: 0.25 })
      .circle(0, 0, 9).fill({ color, alpha: 0.6 })
      .circle(0, 0, 4).fill({ color: COLORS.white })
    orb.position.set(from.x, from.y)
    this.layer.addChild(orb)
    const arc = -Math.min(120, Math.abs(to.x - from.x) * 0.25)
    await this.tween.run(520, (p) => {
      orb.position.set(from.x + (to.x - from.x) * p, from.y + (to.y - from.y) * p + Math.sin(p * Math.PI) * arc)
      orb.rotation = p * 8
    }, easeInQuad)
    orb.destroy()
  }

  /** Self-buff / heal: a glowing frame that swells around the card while sparks rise up it. */
  async aura(center: Point, width: number, height: number, color: number): Promise<void> {
    const ring = new Graphics()
      .roundRect(-width / 2 - 6, -height / 2 - 6, width + 12, height + 12, 18)
      .stroke({ width: 6, color, alpha: 0.9 })
    ring.position.set(center.x, center.y)
    this.layer.addChild(ring)

    const motes = Array.from({ length: 22 }, () => {
      const g = new Graphics().circle(0, 0, 2 + Math.random() * 3).fill({ color })
      const x = center.x + (Math.random() - 0.5) * width * 0.9
      const startY = center.y + height * (0.2 + Math.random() * 0.3)
      g.position.set(x, startY)
      this.layer.addChild(g)
      return { g, x, startY, rise: height * (0.5 + Math.random() * 0.4), delay: Math.random() * 0.35 }
    })

    await Promise.all([
      this.tween.run(750, (p) => {
        ring.scale.set(1 + p * 0.12)
        ring.alpha = 1 - p
      }),
      this.tween.run(1000, (p) => {
        for (const m of motes) {
          const local = Math.max(0, (p - m.delay) / (1 - m.delay))
          m.g.position.set(m.x + Math.sin(local * Math.PI * 2) * 6, m.startY - m.rise * local)
          m.g.alpha = local === 0 ? 0 : 1 - local
        }
      }, (t) => t),
    ])
    ring.destroy()
    motes.forEach((m) => m.g.destroy())
  }

  async banner(center: Point, text: string, color: number, hold = 650, size = 52): Promise<void> {
    const label = new Text({
      text,
      style: {
        fontFamily: ARENA_FONT,
        fontSize: size,
        fill: color,
        stroke: { color: COLORS.ink, width: 7 },
        letterSpacing: 6,
        dropShadow: { color, blur: 18, distance: 0, alpha: 0.8 },
      },
    })
    label.anchor.set(0.5)
    label.position.set(center.x, center.y)
    label.alpha = 0
    label.scale.set(1.6)
    this.layer.addChild(label)
    await Promise.all([
      this.tween.to(label, { alpha: 1 }, 200),
      this.tween.to(label.scale, { x: 1, y: 1 }, 320, easeOutBack),
    ])
    await this.tween.wait(hold)
    await this.tween.to(label, { alpha: 0 }, 260)
    label.destroy()
  }

  async shake(target: Container, strength = 10, duration = 380): Promise<void> {
    const origin = { x: target.x, y: target.y }
    await this.tween.run(duration, (p) => {
      const decay = 1 - p
      target.position.set(
        origin.x + (Math.random() - 0.5) * strength * 2 * decay,
        origin.y + (Math.random() - 0.5) * strength * 2 * decay,
      )
    }, (t) => t)
    target.position.set(origin.x, origin.y)
  }
}
