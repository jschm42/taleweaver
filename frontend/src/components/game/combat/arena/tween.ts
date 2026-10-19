import type { Ticker } from 'pixi.js'

export type Easing = (t: number) => number

export const easeOutCubic: Easing = (t) => 1 - Math.pow(1 - t, 3)
export const easeInOutQuad: Easing = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2)
export const easeOutBack: Easing = (t) => {
  const c1 = 1.70158
  const c3 = c1 + 1
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2)
}
export const easeInQuad: Easing = (t) => t * t

interface TweenJob {
  elapsed: number
  duration: number
  update: (progress: number) => void
  resolve: () => void
}

/** Minimal promise-based tween engine driven by the Pixi ticker. */
export class Tweener {
  /** Playback speed multiplier (e.g. 4 for fast-forward). */
  speed = 1
  private readonly jobs = new Set<TweenJob>()

  constructor(private readonly ticker: Ticker) {
    ticker.add(this.tick, this)
  }

  run(duration: number, update: (progress: number) => void, ease: Easing = easeOutCubic): Promise<void> {
    return new Promise((resolve) => {
      if (duration <= 0) {
        update(1)
        resolve()
        return
      }
      this.jobs.add({ elapsed: 0, duration, update: (p) => update(ease(p)), resolve })
    })
  }

  /** Tweens numeric properties (e.g. `x`, `alpha`, or `scale` via `card.scale`) to target values. */
  to(target: object, props: Record<string, number>, duration: number, ease: Easing = easeOutCubic): Promise<void> {
    const record = target as Record<string, number>
    const keys = Object.keys(props)
    const from = keys.map((key) => record[key])
    const to = keys.map((key) => props[key])
    return this.run(duration, (p) => {
      keys.forEach((key, i) => {
        record[key] = from[i] + (to[i] - from[i]) * p
      })
    }, ease)
  }

  wait(ms: number): Promise<void> {
    return this.run(ms, () => undefined)
  }

  /** Completes every running tween immediately. */
  finishAll(): void {
    for (const job of this.jobs) {
      job.update(1)
      job.resolve()
    }
    this.jobs.clear()
  }

  destroy(): void {
    this.finishAll()
    this.ticker.remove(this.tick, this)
  }

  private tick(ticker: Ticker): void {
    for (const job of [...this.jobs]) {
      job.elapsed += ticker.deltaMS * this.speed
      const progress = Math.min(1, job.elapsed / job.duration)
      job.update(progress)
      if (progress >= 1) {
        this.jobs.delete(job)
        job.resolve()
      }
    }
  }
}
