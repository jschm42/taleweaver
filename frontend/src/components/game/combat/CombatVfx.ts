import { Container, Graphics, type Ticker } from 'pixi.js'

export interface SparkParticle {
  graphic: Graphics
  x: number
  y: number
  vx: number
  vy: number
  size: number
  color: number
  alpha: number
  drag: number
  gravity: number
  life: number
  maxLife: number
}

export interface SlashEffect {
  graphic: Graphics
  x: number
  y: number
  angle: number
  scale: number
  maxScale: number
  color: number
  life: number
  maxLife: number
}

export interface MagicOrb {
  graphic: Graphics
  x: number
  y: number
  targetX: number
  targetY: number
  orbitRadius: number
  orbitAngle: number
  orbitSpeed: number
  color: number
  alpha: number
  life: number
  maxLife: number
}

export class CombatVfxManager {
  public container = new Container()
  private sparks: SparkParticle[] = []
  private slashes: SlashEffect[] = []
  private magicOrbs: MagicOrb[] = []

  constructor() {
    // Top-level VFX container
    this.container.label = 'VfxManager'
  }

  /**
   * Spawns a dramatic arc slash line across the target
   */
  public spawnSlash(x: number, y: number, isCrit = false, angleDeg = 35): void {
    const graphic = new Graphics()
    const color = isCrit ? 0xfbbf24 : 0x38bdf8
    const angleRad = (angleDeg * Math.PI) / 180

    // Draw crescent slash blade
    graphic.clear()
    // Outer arc
    graphic
      .arc(0, 0, isCrit ? 80 : 60, -Math.PI * 0.45, Math.PI * 0.45)
      .stroke({ color: 0xffffff, width: isCrit ? 5 : 3.5, alpha: 1 })
    // Inner glow
    graphic
      .arc(0, 0, isCrit ? 82 : 62, -Math.PI * 0.4, Math.PI * 0.4)
      .stroke({ color, width: isCrit ? 8 : 5, alpha: 0.7 })

    graphic.x = x
    graphic.y = y
    graphic.rotation = angleRad
    graphic.scale.set(0.6)

    this.container.addChild(graphic)
    this.slashes.push({
      graphic,
      x,
      y,
      angle: angleRad,
      scale: 0.6,
      maxScale: isCrit ? 1.5 : 1.2,
      color,
      life: 0,
      maxLife: isCrit ? 220 : 160,
    })
  }

  /**
   * Spawns radiant sparks and blood/impact particles bursting from the strike point
   */
  public spawnImpactSparks(x: number, y: number, isCrit = false): void {
    const count = isCrit ? 36 : 22
    const baseColors = isCrit
      ? [0xfef08a, 0xf59e0b, 0xef4444, 0xffffff]
      : [0x38bdf8, 0x67e8f9, 0xfbbf24, 0xffffff]

    for (let i = 0; i < count; i++) {
      const g = new Graphics()
      const color = baseColors[Math.floor(Math.random() * baseColors.length)]
      const size = (isCrit ? 2.5 : 1.8) + Math.random() * 2.2
      const angle = Math.random() * Math.PI * 2
      const speed = (isCrit ? 4.5 : 3.0) + Math.random() * (isCrit ? 7 : 4.5)

      g.circle(0, 0, size).fill({ color, alpha: 1 })
      g.x = x
      g.y = y

      this.container.addChild(g)
      this.sparks.push({
        graphic: g,
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 1.5,
        size,
        color,
        alpha: 1,
        drag: 0.94,
        gravity: 0.22,
        life: 0,
        maxLife: 300 + Math.random() * 260,
      })
    }

    // Impact shock ring
    const ring = new Graphics()
    const ringColor = isCrit ? 0xf59e0b : 0x38bdf8
    ring.circle(0, 0, 15).stroke({ color: ringColor, width: isCrit ? 4 : 2.5, alpha: 0.9 })
    ring.x = x
    ring.y = y
    this.container.addChild(ring)

    let ringLife = 0
    const ringMaxLife = 200
    const ringTween = () => {
      // Managed in active loop or simple interval
    }
    void ringTween
  }

  /**
   * Spawns rising healing motes or arcane swirling magic around the target
   */
  public spawnMagicSurge(x: number, y: number, type: 'heal' | 'arcane' | 'fire' = 'heal'): void {
    const colors = type === 'heal'
      ? [0x34d399, 0x10b981, 0x6ee7b7, 0xffffff]
      : type === 'fire'
      ? [0xf97316, 0xef4444, 0xfbbf24, 0xffffff]
      : [0xa855f7, 0x6366f1, 0xc084fc, 0x38bdf8]

    const count = 24
    for (let i = 0; i < count; i++) {
      const g = new Graphics()
      const color = colors[i % colors.length]
      const size = 2 + Math.random() * 2.5

      g.circle(0, 0, size).fill({ color, alpha: 0.9 })
      const startX = x + (Math.random() - 0.5) * 60
      const startY = y + (Math.random() - 0.5) * 60
      g.x = startX
      g.y = startY

      this.container.addChild(g)
      this.sparks.push({
        graphic: g,
        x: startX,
        y: startY,
        vx: (Math.random() - 0.5) * 1.8,
        vy: type === 'heal' ? -(1.8 + Math.random() * 2.5) : -(0.5 + Math.random() * 3),
        size,
        color,
        alpha: 1,
        drag: 0.98,
        gravity: type === 'heal' ? -0.05 : 0.08,
        life: 0,
        maxLife: 600 + Math.random() * 300,
      })
    }
  }

  /**
   * Updates all active VFX
   */
  public update(ticker: Ticker): void {
    const deltaMs = ticker.deltaMS

    // 1. Update Slashes
    for (let i = this.slashes.length - 1; i >= 0; i--) {
      const slash = this.slashes[i]
      slash.life += deltaMs
      const progress = slash.life / slash.maxLife

      if (progress >= 1) {
        this.container.removeChild(slash.graphic)
        slash.graphic.destroy()
        this.slashes.splice(i, 1)
        continue
      }

      // Scale up, fade out
      const currentScale = slash.scale + (slash.maxScale - slash.scale) * Math.sin(progress * Math.PI * 0.5)
      slash.graphic.scale.set(currentScale)
      slash.graphic.alpha = 1 - progress * progress
    }

    // 2. Update Sparks
    for (let i = this.sparks.length - 1; i >= 0; i--) {
      const spark = this.sparks[i]
      spark.life += deltaMs
      const progress = spark.life / spark.maxLife

      if (progress >= 1) {
        this.container.removeChild(spark.graphic)
        spark.graphic.destroy()
        this.sparks.splice(i, 1)
        continue
      }

      spark.vx *= spark.drag
      spark.vy += spark.gravity
      spark.x += spark.vx
      spark.y += spark.vy

      spark.graphic.x = spark.x
      spark.graphic.y = spark.y
      spark.graphic.alpha = 1 - progress

      // Spark scaling down near death
      const s = Math.max(0.2, 1 - progress * 0.7)
      spark.graphic.scale.set(s)
    }
  }

  public clear(): void {
    for (const slash of this.slashes) {
      this.container.removeChild(slash.graphic)
      slash.graphic.destroy()
    }
    this.slashes = []

    for (const spark of this.sparks) {
      this.container.removeChild(spark.graphic)
      spark.graphic.destroy()
    }
    this.sparks = []
  }
}
