/** Bubbles that text-to-speech reads; the one being read carries `is-speaking`. */
export const SPEAKABLE_SELECTOR = '.tw-narration, .tw-bubble'
export const SPEAKING_SELECTOR = '.tw-narration.is-speaking, .tw-bubble.is-speaking'
/** Space (px) kept around the spoken bubble when it is scrolled into view. */
export const REVEAL_MARGIN_PX = 16

export interface RevealGeometry {
  /** Current scrollTop of the feed. */
  scrollTop: number
  /** Visible height of the feed without the padding reserved for the overlaid input bar. */
  viewHeight: number
  /** Total scroll height of the feed. */
  scrollHeight: number
  /** Top and bottom of the spoken bubble in feed coordinates (scroll offset included). */
  bubbleTop: number
  bubbleBottom: number
  /** The spoken bubble is the last speakable bubble of the feed. */
  isLast: boolean
}

/**
 * Where the feed has to scroll so the spoken bubble is in view; `null` when it already is.
 * The last bubble scrolls to the very bottom. A bubble below the view is shown completely, or
 * from its top when it is taller than the view; one above is scrolled down to.
 */
export function speechRevealTarget(g: RevealGeometry): number | null {
  if (g.isLast) return g.scrollHeight
  const viewTop = g.scrollTop
  const viewBottom = g.scrollTop + g.viewHeight
  if (g.bubbleTop < viewTop + REVEAL_MARGIN_PX) return g.bubbleTop - REVEAL_MARGIN_PX
  if (g.bubbleBottom <= viewBottom - REVEAL_MARGIN_PX) return null
  const fitsInView = g.bubbleBottom - g.bubbleTop + 2 * REVEAL_MARGIN_PX <= g.viewHeight
  return fitsInView ? g.scrollTop + (g.bubbleBottom + REVEAL_MARGIN_PX - viewBottom) : g.bubbleTop - REVEAL_MARGIN_PX
}
