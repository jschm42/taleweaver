import type { Directive } from 'vue'

/** Applied while the text is too short for a drop cap (see base.css). */
const NO_DROPCAP_CLASS = 'tw-narration-text--no-dropcap'

/** The drop cap needs room to flow around: fewer lines than this keep a plain first letter. */
const MIN_DROPCAP_LINES = 2

const observers = new WeakMap<HTMLElement, ResizeObserver>()

function lineHeightOf(style: CSSStyleDeclaration): number {
  const lineHeight = parseFloat(style.lineHeight)
  if (!Number.isNaN(lineHeight)) {
    return lineHeight
  }
  return parseFloat(style.fontSize) * 1.2
}

/**
 * Counts the lines without the drop cap, so the result does not depend on the drop cap
 * itself (no toggling back and forth). Reads happen before the next paint, so nothing flickers.
 */
function updateDropCap(el: HTMLElement) {
  el.classList.add(NO_DROPCAP_CLASS)
  const lineHeight = lineHeightOf(getComputedStyle(el))
  if (!lineHeight) {
    return
  }
  const lines = Math.round(el.clientHeight / lineHeight)
  el.classList.toggle(NO_DROPCAP_CLASS, lines < MIN_DROPCAP_LINES)
}

/** `v-drop-cap` on a `.tw-narration-text`: shows the drop cap only from two lines of text on. */
export const vDropCap: Directive<HTMLElement> = {
  mounted(el) {
    updateDropCap(el)
    const observer = new ResizeObserver(() => updateDropCap(el))
    observer.observe(el)
    observers.set(el, observer)
  },
  updated(el) {
    updateDropCap(el)
  },
  unmounted(el) {
    observers.get(el)?.disconnect()
    observers.delete(el)
  },
}
