import { onBeforeUnmount, ref, type Ref } from 'vue'

export interface DockMagnificationOptions {
  /** Distance in px from the pointer at which a card stops growing. */
  radius?: number
  /** Scale of the card right under the pointer. */
  maxScale?: number
}

/**
 * macOS-style dock magnification: cards near the pointer grow, smoothly falling off with
 * distance. Card centers are measured once at rest when the pointer enters, so growing cards
 * do not shift the positions the scale is computed from (no jitter). Off for touch input and
 * when the user prefers reduced motion.
 */
export function useDockMagnification(
  container: Ref<HTMLElement | null>,
  count: () => number,
  options: DockMagnificationOptions = {},
) {
  const radius = options.radius ?? 110
  const maxScale = options.maxScale ?? 1.6
  const scales = ref<number[]>([])
  let centers: number[] = []
  let frame = 0
  let pointerX: number | null = null

  const reducedMotion =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  function measure() {
    const items = container.value?.querySelectorAll<HTMLElement>('[data-dock-item]') ?? []
    centers = Array.from(items, (el) => {
      const rect = el.getBoundingClientRect()
      return rect.left + rect.width / 2
    })
  }

  function scaleFor(center: number, x: number): number {
    const distance = Math.abs(center - x)
    if (distance >= radius) return 1
    // Cosine falloff: full size under the pointer, smooth shoulder towards the radius.
    const strength = (Math.cos((distance / radius) * Math.PI) + 1) / 2
    return 1 + (maxScale - 1) * strength
  }

  function update() {
    frame = 0
    const x = pointerX
    scales.value = x === null ? [] : Array.from({ length: count() }, (_, i) => scaleFor(centers[i] ?? -1e6, x))
  }

  function onPointerEnter(event: PointerEvent) {
    if (reducedMotion || event.pointerType === 'touch') return
    scales.value = []
    measure()
  }

  function onPointerMove(event: PointerEvent) {
    if (reducedMotion || event.pointerType === 'touch') return
    if (!centers.length) measure()
    pointerX = event.clientX
    if (!frame) frame = requestAnimationFrame(update)
  }

  function onPointerLeave() {
    pointerX = null
    centers = []
    if (frame) cancelAnimationFrame(frame)
    frame = 0
    scales.value = []
  }

  onBeforeUnmount(() => {
    if (frame) cancelAnimationFrame(frame)
  })

  return {
    scaleOf: (index: number) => scales.value[index] ?? 1,
    onPointerEnter,
    onPointerMove,
    onPointerLeave,
  }
}
