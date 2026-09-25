import { Application, Container, Graphics, Sprite, Assets, Text, TextStyle, type Ticker } from 'pixi.js'
import { CombatVfxManager } from './CombatVfx'

export interface CombatantInfo {
  id?: string
  name: string
  imageUrl?: string | null
  hp: number
  maxHp: number
  stamina?: number
  maxStamina?: number
  isDefeated?: boolean
}

interface EmberParticle {
  graphic: Graphics
  x: number
  y: number
  vx: number
  vy: number
  size: number
  baseAlpha: number
  phase: number
}

interface FloatingNumber {
  container: Container
  vx: number
  vy: number
  life: number
  maxLife: number
}

interface ActiveTween {
  update: (deltaMs: number) => boolean
}

export class CombatantDisplay extends Container {
  public side: 'player' | 'enemy'
  public baseX = 0
  public baseY = 0
  public isDefeated = false
  public isCurrentTurn = false
  public hp = 100
  public maxHp = 100

  private shadowGraphic: Graphics
  private auraGraphic: Graphics
  private cardContainer: Container
  private cardBg: Graphics
  private cardBorder: Graphics
  private avatarSprite: Sprite | null = null
  private fallbackGraphic: Graphics
  private defeatedRibbon: Container
  private hpBarGraphic: Graphics
  private nameText: Text

  constructor(side: 'player' | 'enemy') {
    super()
    this.side = side

    // 1. Ground Shadow
    this.shadowGraphic = new Graphics()
    this.shadowGraphic.ellipse(0, 105, 55, 14).fill({ color: 0x020617, alpha: 0.65 })
    this.addChild(this.shadowGraphic)

    // 2. Aura Ring (Active turn indicator)
    this.auraGraphic = new Graphics()
    this.addChild(this.auraGraphic)

    // 3. Card Container with Mask
    this.cardContainer = new Container()
    this.addChild(this.cardContainer)

    const cardW = 140
    const cardH = 170
    const radius = 16

    // Card background
    this.cardBg = new Graphics()
    this.cardBg.roundRect(-cardW / 2, -cardH / 2, cardW, cardH, radius).fill({ color: 0x090d16, alpha: 0.95 })
    this.cardContainer.addChild(this.cardBg)

    // Card Mask
    const mask = new Graphics()
    mask.roundRect(-cardW / 2, -cardH / 2, cardW, cardH, radius).fill({ color: 0xffffff })
    this.cardContainer.addChild(mask)
    this.cardContainer.mask = mask

    // Fallback graphic if image is missing
    this.fallbackGraphic = new Graphics()
    this.drawFallbackIcon()
    this.cardContainer.addChild(this.fallbackGraphic)

    // Defeated Ribbon
    this.defeatedRibbon = new Container()
    this.buildDefeatedRibbon()
    this.defeatedRibbon.visible = false
    this.cardContainer.addChild(this.defeatedRibbon)

    // 4. Card Border Frame
    this.cardBorder = new Graphics()
    this.drawCardBorder()
    this.addChild(this.cardBorder)

    // 5. HP Bar
    this.hpBarGraphic = new Graphics()
    this.hpBarGraphic.y = 96
    this.addChild(this.hpBarGraphic)

    // 6. Nameplate Text
    const primaryColor = side === 'player' ? '#6ee7b7' : '#fda4af'
    this.nameText = new Text({
      text: side === 'player' ? 'Protagonist' : 'Enemy',
      style: new TextStyle({
        fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        fontSize: 14,
        fontWeight: 'bold',
        fill: primaryColor,
        stroke: { color: 0x020617, width: 3 },
        align: 'center',
      }),
    })
    this.nameText.anchor.set(0.5, 1)
    this.nameText.y = -95
    this.addChild(this.nameText)

    this.updateAura()
    this.updateHpBar()
  }

  public async setAvatar(imageUrl?: string | null): Promise<void> {
    if (!imageUrl) {
      if (this.avatarSprite) {
        this.avatarSprite.visible = false
      }
      this.fallbackGraphic.visible = true
      return
    }

    try {
      const texture = await Assets.load(imageUrl)
      if (!this.avatarSprite) {
        this.avatarSprite = new Sprite(texture)
        this.avatarSprite.anchor.set(0.5)
        this.cardContainer.addChild(this.avatarSprite)
      } else {
        this.avatarSprite.texture = texture
        this.avatarSprite.visible = true
      }

      // Scale to cover card
      const cardW = 140
      const cardH = 170
      const scale = Math.max(cardW / texture.width, cardH / texture.height)
      this.avatarSprite.scale.set(scale)
      this.fallbackGraphic.visible = false
    } catch {
      if (this.avatarSprite) this.avatarSprite.visible = false
      this.fallbackGraphic.visible = true
    }
  }

  public updateData(info: CombatantInfo): void {
    this.hp = Math.max(0, info.hp)
    this.maxHp = Math.max(1, info.maxHp)
    this.isDefeated = this.hp <= 0 || !!info.isDefeated
    this.nameText.text = info.name

    this.defeatedRibbon.visible = this.isDefeated
    if (this.avatarSprite) {
      this.avatarSprite.alpha = this.isDefeated ? 0.4 : 1
    }

    this.updateHpBar()
    this.updateAura()
  }

  public setTurn(isTurn: boolean): void {
    this.isCurrentTurn = isTurn
    this.updateAura()
  }

  private updateAura(): void {
    this.auraGraphic.clear()
    if (this.isDefeated) return

    const cardW = 148
    const cardH = 178
    const color = this.side === 'player' ? 0x10b981 : 0xf43f5e

    if (this.isCurrentTurn) {
      this.auraGraphic
        .roundRect(-cardW / 2, -cardH / 2, cardW, cardH, 20)
        .fill({ color, alpha: 0.18 })
        .stroke({ color, width: 2.5, alpha: 0.9 })
    }
  }

  private drawCardBorder(): void {
    const cardW = 140
    const cardH = 170
    const color = this.side === 'player' ? 0x10b981 : 0xf43f5e
    this.cardBorder.clear()
    this.cardBorder
      .roundRect(-cardW / 2, -cardH / 2, cardW, cardH, 16)
      .stroke({ color, width: 1.5, alpha: 0.6 })
  }

  private updateHpBar(): void {
    const barW = 110
    const barH = 6
    const ratio = Math.max(0, Math.min(1, this.hp / this.maxHp))
    const fillColor = ratio > 0.5 ? 0x10b981 : ratio > 0.25 ? 0xf59e0b : 0xef4444

    this.hpBarGraphic.clear()
    // Bar background
    this.hpBarGraphic
      .roundRect(-barW / 2, 0, barW, barH, 3)
      .fill({ color: 0x0f172a, alpha: 0.85 })
      .stroke({ color: 0x334155, width: 1, alpha: 0.6 })

    // Bar fill
    if (ratio > 0) {
      this.hpBarGraphic
        .roundRect(-barW / 2, 0, Math.max(4, barW * ratio), barH, 3)
        .fill({ color: fillColor, alpha: 0.95 })
    }
  }

  private drawFallbackIcon(): void {
    this.fallbackGraphic.clear()
    const color = this.side === 'player' ? 0x34d399 : 0xfb7185
    if (this.side === 'player') {
      // Shield
      this.fallbackGraphic
        .moveTo(0, -30)
        .lineTo(24, -18)
        .lineTo(18, 18)
        .lineTo(0, 32)
        .lineTo(-18, 18)
        .lineTo(-24, -18)
        .closePath()
        .fill({ color, alpha: 0.25 })
        .stroke({ color, width: 2, alpha: 0.7 })
    } else {
      // Skull
      this.fallbackGraphic
        .circle(0, -6, 22)
        .fill({ color, alpha: 0.25 })
        .stroke({ color, width: 2, alpha: 0.7 })
      this.fallbackGraphic
        .rect(-10, 10, 20, 12)
        .fill({ color, alpha: 0.25 })
        .stroke({ color, width: 2, alpha: 0.7 })
    }
  }

  private buildDefeatedRibbon(): void {
    const ribbon = new Graphics()
    ribbon
      .rect(-80, -12, 160, 24)
      .fill({ color: 0xdc2626, alpha: 0.9 })
      .stroke({ color: 0xfee2e2, width: 1, alpha: 0.6 })
    ribbon.rotation = -0.35

    const label = new Text({
      text: 'DEFEATED',
      style: new TextStyle({
        fontFamily: 'system-ui, sans-serif',
        fontSize: 11,
        fontWeight: '900',
        letterSpacing: 2,
        fill: '#ffffff',
        align: 'center',
      }),
    })
    label.anchor.set(0.5)
    label.rotation = -0.35

    this.defeatedRibbon.addChild(ribbon)
    this.defeatedRibbon.addChild(label)
  }

  public updateIdle(timeSec: number): void {
    if (this.isDefeated) {
      this.cardContainer.y = 4
      this.shadowGraphic.scale.set(1.05, 1.05)
      return
    }

    const freq = this.side === 'player' ? 2.2 : 2.5
    const bobOffset = Math.sin(timeSec * freq) * 4
    this.cardContainer.y = bobOffset
    this.cardBorder.y = bobOffset
    this.nameText.y = -95 + bobOffset * 0.4

    const shadowScale = 1 - (bobOffset / 4) * 0.08
    this.shadowGraphic.scale.set(shadowScale, shadowScale)
  }
}

export class CombatStage {
  public app!: Application
  public container = new Container()

  private bgContainer = new Container()
  private bgSprite: Sprite | null = null
  private bgVignette = new Graphics()
  private arenaFloor = new Graphics()
  private emberContainer = new Container()
  private fightersContainer = new Container()
  public vfxManager = new CombatVfxManager()
  private fxContainer = new Container()
  private bannerContainer = new Container()

  public playerUnit!: CombatantDisplay
  public enemyUnit!: CombatantDisplay

  private embers: EmberParticle[] = []
  private floatingNumbers: FloatingNumber[] = []
  private activeTweens: ActiveTween[] = []

  public virtualWidth = 840
  public virtualHeight = 360
  public prefersReducedMotion = false

  private elapsedSec = 0
  private baseStageScale = 1
  private currentZoom = 1
  private shakeOffset = { x: 0, y: 0 }
  private freezeFramesRemaining = 0

  public async init(app: Application): Promise<void> {
    this.app = app
    this.app.stage.addChild(this.container)

    // Layer stack
    this.container.addChild(this.bgContainer)
    this.container.addChild(this.bgVignette)
    this.container.addChild(this.arenaFloor)
    this.container.addChild(this.emberContainer)
    this.container.addChild(this.fightersContainer)
    this.container.addChild(this.vfxManager.container)
    this.container.addChild(this.fxContainer)
    this.container.addChild(this.bannerContainer)

    this.buildAtmosphere()
    this.buildArenaFloor()
    this.initEmbers()

    // Create combatants
    this.playerUnit = new CombatantDisplay('player')
    this.playerUnit.baseX = this.virtualWidth * 0.24
    this.playerUnit.baseY = this.virtualHeight * 0.54
    this.playerUnit.x = this.playerUnit.baseX
    this.playerUnit.y = this.playerUnit.baseY

    this.enemyUnit = new CombatantDisplay('enemy')
    this.enemyUnit.baseX = this.virtualWidth * 0.76
    this.enemyUnit.baseY = this.virtualHeight * 0.54
    this.enemyUnit.x = this.enemyUnit.baseX
    this.enemyUnit.y = this.enemyUnit.baseY

    this.fightersContainer.addChild(this.playerUnit)
    this.fightersContainer.addChild(this.enemyUnit)

    this.centerStage()
  }

  public async setSceneBackground(imageUrl?: string | null): Promise<void> {
    if (!imageUrl) {
      if (this.bgSprite) {
        this.bgSprite.visible = false
      }
      return
    }

    try {
      const texture = await Assets.load(imageUrl)
      if (!this.bgSprite) {
        this.bgSprite = new Sprite(texture)
        this.bgSprite.anchor.set(0.5)
        this.bgSprite.x = this.virtualWidth / 2
        this.bgSprite.y = this.virtualHeight / 2
        this.bgContainer.addChild(this.bgSprite)
      } else {
        this.bgSprite.texture = texture
        this.bgSprite.visible = true
      }

      // Scale to cover arena and set cinematic dimming
      const scale = Math.max(this.virtualWidth / texture.width, this.virtualHeight / texture.height)
      this.bgSprite.scale.set(scale)
      this.bgSprite.alpha = 0.35 // Subtle atmospheric backdrop
    } catch {
      if (this.bgSprite) this.bgSprite.visible = false
    }
  }

  private buildAtmosphere(): void {
    const bg = new Graphics()
    // Dark outer stage
    bg.rect(0, 0, this.virtualWidth, this.virtualHeight).fill({ color: 0x05070d })

    // Ambient radial lighting in background
    bg.ellipse(this.virtualWidth * 0.24, this.virtualHeight * 0.5, 180, 120).fill({
      color: 0x064e3b,
      alpha: 0.22,
    })
    bg.ellipse(this.virtualWidth * 0.76, this.virtualHeight * 0.5, 180, 120).fill({
      color: 0x881337,
      alpha: 0.22,
    })
    this.bgContainer.addChild(bg)

    // Vignette overlay
    this.bgVignette.clear()
    this.bgVignette
      .rect(0, 0, this.virtualWidth, this.virtualHeight)
      .fill({ color: 0x020617, alpha: 0.25 })
  }

  private buildArenaFloor(): void {
    this.arenaFloor.clear()
    const cx = this.virtualWidth * 0.5
    const cy = this.virtualHeight * 0.68

    // Arena Platform Dias
    this.arenaFloor
      .ellipse(cx, cy, this.virtualWidth * 0.44, 90)
      .fill({ color: 0x0b1120, alpha: 0.88 })
      .stroke({ color: 0x334155, width: 1.5, alpha: 0.5 })

    // Inner glowing combat ring
    this.arenaFloor
      .ellipse(cx, cy, this.virtualWidth * 0.38, 75)
      .stroke({ color: 0xd97706, width: 1.5, alpha: 0.35 })

    // Arcade grid lines across platform
    this.arenaFloor
      .ellipse(cx, cy, 30, 12)
      .stroke({ color: 0xf59e0b, width: 1, alpha: 0.4 })
  }

  private initEmbers(): void {
    this.emberContainer.removeChildren()
    this.embers = []
    const count = 35

    for (let i = 0; i < count; i++) {
      const g = new Graphics()
      const size = 1.2 + Math.random() * 2.2
      const isGold = Math.random() > 0.35
      const color = isGold ? 0xfbbf24 : 0x38bdf8

      g.circle(0, 0, size).fill({ color, alpha: 1 })

      const ember: EmberParticle = {
        graphic: g,
        x: Math.random() * this.virtualWidth,
        y: Math.random() * this.virtualHeight,
        vx: (Math.random() - 0.5) * 0.5,
        vy: -(0.3 + Math.random() * 0.8),
        size,
        baseAlpha: 0.25 + Math.random() * 0.65,
        phase: Math.random() * Math.PI * 2,
      }

      g.x = ember.x
      g.y = ember.y
      g.alpha = ember.baseAlpha

      this.emberContainer.addChild(g)
      this.embers.push(ember)
    }
  }

  public update(ticker: Ticker): void {
    const deltaMs = ticker.deltaMS

    // Hit-stop freeze frame
    if (this.freezeFramesRemaining > 0) {
      this.freezeFramesRemaining -= deltaMs
      return
    }

    this.elapsedSec += deltaMs * 0.001

    // 1. Update Combatants Idle Animation
    if (!this.prefersReducedMotion) {
      this.playerUnit.updateIdle(this.elapsedSec)
      this.enemyUnit.updateIdle(this.elapsedSec)
    }

    // 2. Update VFX Manager (Slashes & Sparks)
    this.vfxManager.update(ticker)

    // 3. Update Ambient Embers
    if (!this.prefersReducedMotion) {
      for (const ember of this.embers) {
        ember.y += ember.vy
        ember.x += ember.vx + Math.sin(this.elapsedSec * 1.5 + ember.phase) * 0.35

        if (ember.y < -10) {
          ember.y = this.virtualHeight + 10
          ember.x = Math.random() * this.virtualWidth
        }
        if (ember.x < -10) ember.x = this.virtualWidth + 10
        if (ember.x > this.virtualWidth + 10) ember.x = -10

        ember.graphic.x = ember.x
        ember.graphic.y = ember.y
        ember.graphic.alpha = ember.baseAlpha * (0.6 + 0.4 * Math.sin(this.elapsedSec * 2 + ember.phase))
      }
    }

    // 4. Update Floating Damage Numbers
    for (let i = this.floatingNumbers.length - 1; i >= 0; i--) {
      const item = this.floatingNumbers[i]
      item.life += deltaMs
      const progress = item.life / item.maxLife

      item.container.x += item.vx
      item.container.y += item.vy
      item.vy += 0.18 // Gravity arc

      item.container.alpha = Math.max(0, 1 - progress * progress)

      if (item.life >= item.maxLife) {
        this.fxContainer.removeChild(item.container)
        this.floatingNumbers.splice(i, 1)
      }
    }

    // 5. Update Tweens (lunges, camera shakes)
    for (let i = this.activeTweens.length - 1; i >= 0; i--) {
      const finished = this.activeTweens[i].update(deltaMs)
      if (finished) {
        this.activeTweens.splice(i, 1)
      }
    }
  }

  /**
   * Camera screen shake
   */
  public shakeCamera(intensity = 12, durationMs = 240): void {
    if (this.prefersReducedMotion) return

    let elapsed = 0
    this.activeTweens.push({
      update: (deltaMs: number) => {
        elapsed += deltaMs
        if (elapsed < durationMs) {
          const decay = 1 - elapsed / durationMs
          this.shakeOffset.x = (Math.random() - 0.5) * intensity * decay * 2
          this.shakeOffset.y = (Math.random() - 0.5) * intensity * decay * 2
          this.applyCameraTransform()
          return false
        } else {
          this.shakeOffset.x = 0
          this.shakeOffset.y = 0
          this.applyCameraTransform()
          return true
        }
      },
    })
  }

  /**
   * Camera zoom punch on critical strikes
   */
  public zoomPunch(targetZoom = 1.05, durationMs = 200): void {
    if (this.prefersReducedMotion) return

    let elapsed = 0
    this.activeTweens.push({
      update: (deltaMs: number) => {
        elapsed += deltaMs
        if (elapsed <= durationMs * 0.4) {
          const t = elapsed / (durationMs * 0.4)
          this.currentZoom = 1 + (targetZoom - 1) * t
          this.applyCameraTransform()
          return false
        } else if (elapsed < durationMs) {
          const t = (elapsed - durationMs * 0.4) / (durationMs * 0.6)
          this.currentZoom = targetZoom - (targetZoom - 1) * t
          this.applyCameraTransform()
          return false
        } else {
          this.currentZoom = 1
          this.applyCameraTransform()
          return true
        }
      },
    })
  }

  public freezeFrame(freezeMs = 70): void {
    if (this.prefersReducedMotion) return
    this.freezeFramesRemaining = freezeMs
  }

  private applyCameraTransform(): void {
    if (!this.app?.renderer) return
    const w = this.app.renderer.width
    const h = this.app.renderer.height
    const scale = this.baseStageScale * this.currentZoom
    this.container.scale.set(scale)
    this.container.x = (w - this.virtualWidth * scale) / 2 + this.shakeOffset.x
    this.container.y = (h - this.virtualHeight * scale) / 2 + this.shakeOffset.y
  }

  /**
   * Arcade Banner (Round Start / Critical Hit / Victory)
   */
  public showArcadeBanner(title: string, subtitle?: string, isCrit = false): void {
    this.bannerContainer.removeChildren()
    const banner = new Container()
    banner.x = this.virtualWidth / 2
    banner.y = this.virtualHeight * 0.28

    const color = isCrit ? '#f59e0b' : '#38bdf8'
    const label = new Text({
      text: title,
      style: new TextStyle({
        fontFamily: 'Impact, "Arial Black", system-ui, sans-serif',
        fontSize: 32,
        fontWeight: '900',
        letterSpacing: 3,
        fill: color,
        stroke: { color: 0x020617, width: 6 },
        align: 'center',
      }),
    })
    label.anchor.set(0.5)
    banner.addChild(label)

    if (subtitle) {
      const subLabel = new Text({
        text: subtitle,
        style: new TextStyle({
          fontFamily: 'system-ui, sans-serif',
          fontSize: 13,
          fontWeight: 'bold',
          letterSpacing: 2,
          fill: '#f1f5f9',
          stroke: { color: 0x020617, width: 3 },
          align: 'center',
        }),
      })
      subLabel.anchor.set(0.5)
      subLabel.y = 26
      banner.addChild(subLabel)
    }

    banner.scale.set(1.4)
    banner.alpha = 0
    this.bannerContainer.addChild(banner)

    let elapsed = 0
    const duration = 1200
    this.activeTweens.push({
      update: (deltaMs: number) => {
        elapsed += deltaMs
        if (elapsed <= 200) {
          // Punch in
          const t = elapsed / 200
          banner.scale.set(1.4 - 0.4 * t)
          banner.alpha = t
          return false
        } else if (elapsed <= 900) {
          // Hold
          banner.scale.set(1.0)
          banner.alpha = 1
          return false
        } else if (elapsed < duration) {
          // Fade out
          const t = (elapsed - 900) / (duration - 900)
          banner.alpha = 1 - t
          banner.y = this.virtualHeight * 0.28 - 20 * t
          return false
        } else {
          this.bannerContainer.removeChild(banner)
          banner.destroy({ children: true })
          return true
        }
      },
    })
  }

  public playAttack(
    attacker: 'player' | 'enemy',
    options?: { isCrit?: boolean; isHit?: boolean },
    onImpact?: () => void,
  ): void {
    if (this.prefersReducedMotion) {
      onImpact?.()
      return
    }

    const isCrit = options?.isCrit ?? false
    const isHit = options?.isHit ?? true

    const unit = attacker === 'player' ? this.playerUnit : this.enemyUnit
    const target = attacker === 'player' ? this.enemyUnit : this.playerUnit
    const dir = attacker === 'player' ? 1 : -1
    const startX = unit.baseX
    const targetX = target.baseX - dir * 105

    let elapsed = 0
    const windupDur = 160
    const lungeDur = 110
    const impactDur = 140
    const returnDur = 240
    let impactTriggered = false

    this.activeTweens.push({
      update: (deltaMs: number) => {
        elapsed += deltaMs

        if (elapsed <= windupDur) {
          // Windup: step back slightly
          const t = elapsed / windupDur
          unit.x = startX - dir * 18 * Math.sin(t * (Math.PI / 2))
          return false
        } else if (elapsed <= windupDur + lungeDur) {
          // Rapid forward dash
          const t = (elapsed - windupDur) / lungeDur
          unit.x = (startX - dir * 18) + (targetX - (startX - dir * 18)) * t
          return false
        } else if (elapsed <= windupDur + lungeDur + impactDur) {
          // Impact hold
          if (!impactTriggered) {
            impactTriggered = true

            // Trigger VFX
            if (isHit) {
              this.vfxManager.spawnSlash(target.baseX, target.baseY - 10, isCrit, attacker === 'player' ? 35 : -35)
              this.vfxManager.spawnImpactSparks(target.baseX, target.baseY - 10, isCrit)
              this.shakeCamera(isCrit ? 16 : 9, isCrit ? 300 : 200)

              if (isCrit) {
                this.zoomPunch(1.06, 220)
                this.freezeFrame(70)
                this.showArcadeBanner('CRITICAL HIT!', 'MASSIVE STRIKE', true)
              }
            }

            onImpact?.()
            this.playHitReaction(attacker === 'player' ? 'enemy' : 'player', isCrit)
          }
          return false
        } else if (elapsed <= windupDur + lungeDur + impactDur + returnDur) {
          // Snap return with ease-out
          const t = (elapsed - windupDur - lungeDur - impactDur) / returnDur
          const easeOut = Math.sin(t * (Math.PI / 2))
          unit.x = targetX + (startX - targetX) * easeOut
          return false
        } else {
          unit.x = startX
          return true
        }
      },
    })
  }

  public playHitReaction(target: 'player' | 'enemy', isCrit = false): void {
    if (this.prefersReducedMotion) return

    const unit = target === 'player' ? this.playerUnit : this.enemyUnit
    const startX = unit.baseX
    const dir = target === 'player' ? -1 : 1
    const intensity = isCrit ? 22 : 12

    let elapsed = 0
    const duration = isCrit ? 400 : 250

    this.activeTweens.push({
      update: (deltaMs: number) => {
        elapsed += deltaMs
        if (elapsed < duration) {
          const decay = 1 - elapsed / duration
          const shake = Math.sin(elapsed * 0.06) * intensity * decay
          unit.x = startX + dir * (intensity * 0.4 * decay) + shake
          return false
        } else {
          unit.x = startX
          return true
        }
      },
    })
  }

  public playMagicSurge(target: 'player' | 'enemy', type: 'heal' | 'arcane' | 'fire' = 'heal'): void {
    const unit = target === 'player' ? this.playerUnit : this.enemyUnit
    this.vfxManager.spawnMagicSurge(unit.baseX, unit.baseY, type)
    if (type !== 'heal') {
      this.shakeCamera(8, 200)
    }
  }

  public spawnDamageNumber(
    target: 'player' | 'enemy',
    amount: number | string,
    type: 'damage' | 'crit' | 'heal' | 'miss' = 'damage',
  ): void {
    const unit = target === 'player' ? this.playerUnit : this.enemyUnit
    const container = new Container()
    container.x = unit.baseX + (Math.random() - 0.5) * 40
    container.y = unit.baseY - 45

    let color = '#f43f5e'
    let prefix = '-'
    let fontSize = 24
    let text = `${amount}`

    if (type === 'crit') {
      color = '#fbbf24'
      prefix = '💥 CRIT! -'
      fontSize = 30
    } else if (type === 'heal') {
      color = '#34d399'
      prefix = '💚 +'
      fontSize = 24
    } else if (type === 'miss') {
      color = '#94a3b8'
      prefix = '💨 '
      text = 'MISS'
      fontSize = 20
    }

    const label = new Text({
      text: `${prefix}${text}`,
      style: new TextStyle({
        fontFamily: 'Impact, "Arial Black", "Trebuchet MS", system-ui, sans-serif',
        fontSize,
        fontWeight: '900',
        letterSpacing: 1.5,
        fill: color,
        stroke: { color: 0x020617, width: 4.5 },
        align: 'center',
      }),
    })
    label.anchor.set(0.5)
    container.addChild(label)

    this.fxContainer.addChild(container)
    this.floatingNumbers.push({
      container,
      vx: (Math.random() - 0.5) * 2,
      vy: -4.5 - Math.random() * 2,
      life: 0,
      maxLife: 950,
    })
  }

  public resize(width: number, height: number): void {
    if (width <= 0 || height <= 0) return

    this.baseStageScale = Math.min(width / this.virtualWidth, height / this.virtualHeight)
    this.applyCameraTransform()
  }

  private centerStage(): void {
    if (this.app?.renderer) {
      this.resize(this.app.renderer.width, this.app.renderer.height)
    }
  }

  public destroy(): void {
    this.activeTweens = []
    this.floatingNumbers = []
    this.embers = []
    this.vfxManager.clear()
    this.container.destroy({ children: true })
  }
}
