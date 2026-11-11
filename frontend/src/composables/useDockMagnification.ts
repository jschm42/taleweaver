import { onBeforeUnmount, ref, type Ref } from 'vue'

export interface DockMagnificationOptions {
  /**
   * Falloff distance in card widths, measured at rest. Covers the same number of neighbours at
   * every resolution and card size.
   */
  radiusFactor?: number
  /** Peak scale of the selected card directly under the pointer. */
  maxScale?: number
}

export interface DockMagnification {
  activeIndex: Ref<number | null>
  scaleOf: (index: number) => number
  pushOf: (index: number) => number
  onPointerEnter: (event: PointerEvent) => void
  onPointerMove: (event: PointerEvent) => void
  onPointerLeave: () => void
  onItemFocus: (index: number) => void
  onItemBlur: (index: number) => void
}

/**
 * Card-hand dock magnification: the hovered/focused card zooms up prominently (`maxScale`), while
 * immediate neighbours rise smoothly and part slightly to frame the selected card.
 *
 * Item centers are stored in normalized container coordinates `[0, 1]` so horizontal expansion of
 * the flex shelf never causes pointer-to-card drift at the outer edges.
 */
export function useDockMagnification(
  container: Ref<HTMLElement | null>,
  count: () => number,
  options: DockMagnificationOptions = {},
): DockMagnification {
  const radiusFactor = options.radiusFactor ?? 2.05
  const maxScale = options.maxScale ?? 1.72

  const activeIndex = ref<number | null>(null)
  const scales = ref<number[]>([])
  const pushes = ref<number[]>([])

  let normCenters: number[] = []
  let normRadius = 0.28
  let frame = 0
  let pointerX: number | null = null
  let hoveredIdx: number | null = null

  const reducedMotion =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  function measure(): void {
    const el = container.value
    if (!el) return
    const containerRect = el.getBoundingClientRect()
    const items = el.querySelectorAll<HTMLElement>('[data-dock-item]')
    if (!items.length || containerRect.width <= 0) return

    const rects = Array.from(items, (item) => item.getBoundingClientRect())
    normCenters = rects.map((rect) => (rect.left + rect.width / 2 - containerRect.left) / containerRect.width)
    normRadius = (rects[0].width * radiusFactor) / containerRect.width
  }

  function resolveHoveredIndex(target: EventTarget | null): number | null {
    if (!(target instanceof Element) || !container.value) return null
    const itemEl = target.closest<HTMLElement>('[data-dock-item]')
    if (!itemEl) return null
    const items = Array.from(container.value.querySelectorAll<HTMLElement>('[data-dock-item]'))
    const idx = items.indexOf(itemEl)
    return idx >= 0 ? idx : null
  }

  function update(): void {
    frame = 0
    const el = container.value
    const total = count()
    if (pointerX === null || !el || !normCenters.length) {
      scales.value = []
      pushes.value = []
      return
    }

    const liveRect = el.getBoundingClientRect()
    if (liveRect.width <= 0) return

    const uPointer = (pointerX - liveRect.left) / liveRect.width
    const nextScales: number[] = []
    const nextPushes: number[] = []

    // Determine primary focal index (hovered card or closest center).
    let focalIdx = hoveredIdx
    if (focalIdx === null) {
      let bestDist = Infinity
      for (let i = 0; i < total; i++) {
        const d = Math.abs((normCenters[i] ?? -10) - uPointer)
        if (d < bestDist) {
          bestDist = d
          focalIdx = i
        }
      }
    }
    activeIndex.value = focalIdx

    for (let i = 0; i < total; i++) {
      const center = normCenters[i] ?? -10
      const distance = Math.abs(center - uPointer)

      if (i === focalIdx && hoveredIdx !== null) {
        // The directly hovered card always gets full hero magnification.
        nextScales.push(maxScale)
        nextPushes.push(0)
        continue
      }

      if (distance >= normRadius) {
        nextScales.push(1)
        nextPushes.push(0)
        continue
      }

      // Smooth cosine bell shaped with an exponent so the selected card stands well above neighbours.
      const cosine = (Math.cos((distance / normRadius) * Math.PI) + 1) / 2
      const neighborCap = 1 + (maxScale - 1) * 0.52
      const rawScale = 1 + (maxScale - 1) * Math.pow(cosine, 1.45)
      const scale = hoveredIdx !== null && i !== focalIdx ? Math.min(rawScale, neighborCap) : rawScale
      nextScales.push(scale)

      // Neighbours gently part away from the focal card.
      if (focalIdx !== null && i !== focalIdx) {
        const dir = i < focalIdx ? -1 : 1
        const idxDist = Math.abs(i - focalIdx)
        const pushFactor = idxDist === 1 ? 1 : idxDist === 2 ? 0.4 : 0
        nextPushes.push(dir * pushFactor)
      } else {
        nextPushes.push(0)
      }
    }

    scales.value = nextScales
    pushes.value = nextPushes
  }

  const isCompactMobile = (): boolean =>
    typeof window !== 'undefined' && window.matchMedia?.('(max-width: 767px)').matches

  function onPointerEnter(event: PointerEvent): void {
    if (reducedMotion || event.pointerType === 'touch' || isCompactMobile()) return
    scales.value = []
    pushes.value = []
    measure()
    hoveredIdx = resolveHoveredIndex(event.target)
    pointerX = event.clientX
    if (!frame) frame = requestAnimationFrame(update)
  }

  function onPointerMove(event: PointerEvent): void {
    if (reducedMotion || event.pointerType === 'touch' || isCompactMobile()) return
    if (!normCenters.length) measure()
    hoveredIdx = resolveHoveredIndex(event.target)
    pointerX = event.clientX
    if (!frame) frame = requestAnimationFrame(update)
  }

  function onPointerLeave(): void {
    pointerX = null
    hoveredIdx = null
    activeIndex.value = null
    normCenters = []
    if (frame) cancelAnimationFrame(frame)
    frame = 0
    scales.value = []
    pushes.value = []
  }

  function onItemFocus(index: number): void {
    activeIndex.value = index
    if (reducedMotion || pointerX !== null) return
    const total = count()
    scales.value = Array.from({ length: total }, (_, i) => {
      const diff = Math.abs(i - index)
      if (diff === 0) return maxScale
      if (diff === 1) return 1 + (maxScale - 1) * 0.32
      return 1
    })
    pushes.value = Array.from({ length: total }, (_, i) => {
      if (i === index) return 0
      const diff = i - index
      if (Math.abs(diff) === 1) return Math.sign(diff)
      return 0
    })
  }

  function onItemBlur(index: number): void {
    if (pointerX !== null) return
    if (activeIndex.value === index) {
      activeIndex.value = null
      scales.value = []
      pushes.value = []
    }
  }

  onBeforeUnmount(() => {
    if (frame) cancelAnimationFrame(frame)
  })

  return {
    activeIndex,
    scaleOf: (index: number): number => scales.value[index] ?? 1,
    pushOf: (index: number): number => pushes.value[index] ?? 0,
    onPointerEnter,
    onPointerMove,
    onPointerLeave,
    onItemFocus,
    onItemBlur,
  }
}
