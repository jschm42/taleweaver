/**
 * useStageDensity — fits the character cards of the left stage into the available height.
 *
 * The stage column has a fixed width. A full card is a 2:3 portrait; when the cast does not fit
 * at that size, every card shrinks to the height that fits them all. Below certain aspect ratios
 * the cards switch to a denser layout:
 *   - full    (height >= 1.5 x width): portrait with name and role
 *   - compact (height >= 0.75 x width): squarish, name only
 *   - mini    (smaller):               short strip, small name, defeated shown as an icon
 * Cards never shrink below MIN_RATIO x width; past that point the column scrolls as before.
 */
import { computed, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

export type StageDensity = 'full' | 'compact' | 'mini'

/** Vertical gap between cards in px (matches the `gap-2` of the card list). */
export const STAGE_CARD_GAP_PX = 8

const FULL_RATIO = 1.5
const COMPACT_RATIO = 0.75
const MIN_RATIO = 0.55
const MIN_CARD_PX = 44

interface StageBox {
  width: number
  height: number
}

function contentBox(el: HTMLElement): StageBox {
  const style = window.getComputedStyle(el)
  const padX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight)
  const padY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
  return {
    width: Math.max(0, el.clientWidth - padX),
    height: Math.max(0, el.clientHeight - padY)
  }
}

/** Card height in px for `count` cards in a box; 0 when the box has not been measured yet. */
export function fitCardHeight(box: StageBox, count: number): number {
  if (!box.width || !box.height || count <= 0) {
    return 0
  }
  const fullHeight = box.width * FULL_RATIO
  const minHeight = Math.max(MIN_CARD_PX, box.width * MIN_RATIO)
  const perCard = (box.height - STAGE_CARD_GAP_PX * (count - 1)) / count
  return Math.min(fullHeight, Math.max(minHeight, Math.floor(perCard)))
}

export function densityFor(cardHeight: number, width: number): StageDensity {
  if (!cardHeight || !width || cardHeight >= width * FULL_RATIO - 0.5) {
    return 'full'
  }
  return cardHeight >= width * COMPACT_RATIO ? 'compact' : 'mini'
}

export function useStageDensity(container: Ref<HTMLElement | null>, count: () => number) {
  const box = ref<StageBox>({ width: 0, height: 0 })
  let observer: ResizeObserver | null = null

  function measure() {
    if (!container.value) {
      return
    }
    box.value = contentBox(container.value)
  }

  onMounted(() => {
    measure()
    if (typeof ResizeObserver === 'undefined' || !container.value) {
      return
    }
    observer = new ResizeObserver(measure)
    observer.observe(container.value)
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  const cardHeight = computed(() => fitCardHeight(box.value, count()))
  const density = computed(() => densityFor(cardHeight.value, box.value.width))
  /** Inline style for each card: an explicit height once shrunk, the 2:3 aspect otherwise. */
  const cardStyle = computed(() => {
    if (density.value === 'full') {
      return { aspectRatio: '2 / 3' }
    }
    return { height: `${cardHeight.value}px` }
  })

  return { density, cardStyle }
}
