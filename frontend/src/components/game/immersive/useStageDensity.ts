/**
 * useStageDensity — fits the character cards of the left stage into the available height.
 *
 * Up to five characters stand in one column; from STAGE_TWO_COLUMN_MIN characters on, the stage
 * switches to two narrower columns. A full card is a 2:3 portrait; when the cast does not fit at
 * that size, every card shrinks to the height that fits all rows. Below certain aspect ratios the
 * cards switch to a denser layout:
 *   - full    (height >= 1.5 x width): portrait with name and role
 *   - compact (height >= 0.75 x width): squarish, name only
 *   - mini    (smaller):               short strip, small name, defeated shown as an icon
 * Cards never shrink below MIN_RATIO x width; past that point the column scrolls as before.
 *
 * The stage reserves its scrollbar gutter (`scrollbar-gutter: stable`), so a scrollbar appearing
 * does not change the measured width. Without that, the width change re-sized the cards, the
 * scrollbar vanished again and the cards jittered in a resize loop.
 */
import { computed, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

export type StageDensity = 'full' | 'compact' | 'mini'

/** Gap between cards in px (matches the `gap-2` of the card grid). */
export const STAGE_CARD_GAP_PX = 8

/** From this many characters on, the stage uses two columns. */
export const STAGE_TWO_COLUMN_MIN = 6

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
    width: Math.max(0, Math.floor(el.clientWidth - padX)),
    height: Math.max(0, Math.floor(el.clientHeight - padY))
  }
}

export function stageColumns(count: number): 1 | 2 {
  return count >= STAGE_TWO_COLUMN_MIN ? 2 : 1
}

/** Width of one card column in px. */
export function columnWidth(width: number, columns: number): number {
  return Math.max(0, (width - STAGE_CARD_GAP_PX * (columns - 1)) / columns)
}

/** Card height in px for `count` cards in a box; 0 when the box has not been measured yet. */
export function fitCardHeight(box: StageBox, count: number): number {
  if (!box.width || !box.height || count <= 0) {
    return 0
  }
  const columns = stageColumns(count)
  const rows = Math.ceil(count / columns)
  const cardWidth = columnWidth(box.width, columns)
  const fullHeight = cardWidth * FULL_RATIO
  const minHeight = Math.max(MIN_CARD_PX, cardWidth * MIN_RATIO)
  const perCard = (box.height - STAGE_CARD_GAP_PX * (rows - 1)) / rows
  return Math.floor(Math.min(fullHeight, Math.max(minHeight, perCard)))
}

export function densityFor(cardHeight: number, width: number): StageDensity {
  if (!cardHeight || !width || cardHeight >= Math.floor(width * FULL_RATIO)) {
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
    const next = contentBox(container.value)
    // Only whole-pixel changes count; sub-pixel noise must not re-layout the cards.
    if (next.width === box.value.width && next.height === box.value.height) {
      return
    }
    box.value = next
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

  const columns = computed(() => stageColumns(count()))
  const cardHeight = computed(() => fitCardHeight(box.value, count()))
  const density = computed(() => densityFor(cardHeight.value, columnWidth(box.value.width, columns.value)))
  /** Inline style for each card: an explicit height once shrunk, the 2:3 aspect otherwise. */
  const cardStyle = computed(() => {
    if (density.value === 'full') {
      return { aspectRatio: '2 / 3' }
    }
    return { height: `${cardHeight.value}px` }
  })

  return { columns, density, cardStyle }
}
