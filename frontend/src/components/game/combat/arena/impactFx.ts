import { Container, Graphics } from 'pixi.js'
import { COLORS } from './palette'
import type { Point } from './effects'
import { easeInQuad, easeOutCubic, type Easing, type Tweener } from './tween'

const linear: Easing = (t) => t

/** Effects that sell a hit: weapon trails, impact rings, a shattering card, victory sparks. */
export class ImpactEffects {
  constructor(
    private readonly layer: Container,
    private readonly tween: Tweener,
  ) {}

  /** Blade trail across the target: a tapered streak that snaps open and fades. */
  async slash(at: Point, color: number, heavy = false): Promise<void> {
    const length = heavy ? 240 : 170
    const width = heavy ? 16 : 10
    const streak = new Graphics()
      .poly([-length / 2, 0, 0, -width / 2, length / 2, 0, 0, width / 2]).fill({ color, alpha: 0.9 })
      .poly([-length / 2, 0, 0, -width / 6, length / 2, 0, 0, width / 6]).fill({ color: COLORS.white })
    streak.position.set(at.x, at.y)
    streak.rotation = (Math.random() < 0.5 ? -1 : 1) * (0.55 + Math.random() * 0.3)
    streak.scale.set(0.15, 1)
    this.layer.addChild(streak)
    await this.tween.to(streak.scale, { x: 1 }, 90, easeOutCubic)
    await Promise.all([
      this.tween.to(streak, { alpha: 0 }, 240),
      this.tween.to(streak.scale, { x: 1.25, y: 0.3 }, 240),
    ])
    streak.destroy()
  }

  /** Shockwave ring that expands from the point of impact. */
  async ring(at: Point, color: number, radius = 70): Promise<void> {
    const ring = new Graphics().circle(0, 0, radius).stroke({ width: 5, color, alpha: 0.9 })
    ring.position.set(at.x, at.y)
    ring.scale.set(0.2)
    this.layer.addChild(ring)
    await Promise.all([
      this.tween.to(ring.scale, { x: 1, y: 1 }, 380),
      this.tween.to(ring, { alpha: 0 }, 380, easeInQuad),
    ])
    ring.destroy()
  }

  /** Fast straight shot (arrow, bolt, thrown blade) from the attacker to a point. */
  async arrow(from: Point, to: Point, color: number): Promise<void> {
    const shaft = new Graphics()
      .poly([-34, 0, 6, -2.5, 14, 0, 6, 2.5]).fill({ color, alpha: 0.85 })
      .poly([6, -5, 20, 0, 6, 5]).fill({ color: COLORS.white })
    shaft.position.set(from.x, from.y)
    shaft.rotation = Math.atan2(to.y - from.y, to.x - from.x)
    this.layer.addChild(shaft)
    await this.tween.to(shaft, { x: to.x, y: to.y }, 230, linear)
    shaft.destroy()
  }

  /** Brief wash of colour over the whole stage (critical hits, defeat). */
  async screenFlash(width: number, height: number, color: number, strength = 0.35): Promise<void> {
    const wash = new Graphics().rect(0, 0, width, height).fill({ color })
    wash.alpha = strength
    this.layer.addChild(wash)
    await this.tween.to(wash, { alpha: 0 }, 320)
    wash.destroy()
  }

  /** A card breaking apart: fragments start inside its outline, fly out and fall. */
  async shards(center: Point, width: number, height: number, color: number): Promise<void> {
    const pieces = Array.from({ length: 28 }, () => {
      const size = 5 + Math.random() * 11
      const tint = Math.random() < 0.3 ? COLORS.white : color
      const g = new Graphics().poly([0, -size, size * 0.7, size * 0.5, -size * 0.6, size * 0.6]).fill({ color: tint })
      const x = center.x + (Math.random() - 0.5) * width
      const y = center.y + (Math.random() - 0.5) * height
      g.position.set(x, y)
      this.layer.addChild(g)
      return {
        g,
        x,
        y,
        dx: (x - center.x) * (0.8 + Math.random()) + (Math.random() - 0.5) * 40,
        dy: (y - center.y) * 0.6 - 30 - Math.random() * 50,
        fall: 90 + Math.random() * 110,
        spin: (Math.random() - 0.5) * 9,
      }
    })
    await this.tween.run(820, (p) => {
      for (const s of pieces) {
        s.g.position.set(s.x + s.dx * p, s.y + s.dy * p + s.fall * p * p)
        s.g.rotation = s.spin * p
        s.g.alpha = p < 0.5 ? 1 : 1 - (p - 0.5) / 0.5
      }
    }, linear)
    pieces.forEach((s) => s.g.destroy())
  }

  /** Victory: sparks rise across the whole stage. */
  async celebrate(width: number, height: number, color: number): Promise<void> {
    const motes = Array.from({ length: 46 }, () => {
      const tint = Math.random() < 0.35 ? COLORS.white : color
      const g = new Graphics().circle(0, 0, 2 + Math.random() * 4).fill({ color: tint })
      const x = Math.random() * width
      const startY = height * (0.75 + Math.random() * 0.3)
      g.position.set(x, startY)
      g.alpha = 0
      this.layer.addChild(g)
      return { g, x, startY, rise: height * (0.5 + Math.random() * 0.5), sway: 8 + Math.random() * 18, delay: Math.random() * 0.4 }
    })
    await this.tween.run(1500, (p) => {
      for (const m of motes) {
        const local = Math.max(0, (p - m.delay) / (1 - m.delay))
        m.g.position.set(m.x + Math.sin(local * Math.PI * 3) * m.sway, m.startY - m.rise * local)
        m.g.alpha = local === 0 ? 0 : Math.min(1, (1 - local) * 2)
      }
    }, linear)
    motes.forEach((m) => m.g.destroy())
  }
}
