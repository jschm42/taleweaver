import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/** Distance (px) from the bottom below which the feed counts as "at the latest message". */
const AT_BOTTOM_THRESHOLD_PX = 32

/** A scroll within this time (ms) after wheel/touch/key/pointer input counts as user-driven. */
const USER_SCROLL_WINDOW_MS = 800

export interface ScrollToLatestOptions {
  /** Whether new content may be followed at all (e.g. false while browsing history). */
  canFollow?: () => boolean
  /** Highest scrollTop auto-follow may reach, e.g. to keep the newest message's start in view. */
  maxFollowTop?: () => number | null
}

/**
 * Tracks whether a scroll container has content below the visible area, offers a smooth
 * jump to its end, and follows new content automatically.
 *
 * Auto-follow stops as soon as the user scrolls up and resumes once they scroll back down
 * to the follow position, or when `resumeFollowing()` is called.
 */
export function useScrollToLatest(container: Ref<HTMLElement | null>, options: ScrollToLatestOptions = {}) {
  const hasContentBelow = ref(false)
  const isFollowing = ref(true)
  let resizeObserver: ResizeObserver | null = null
  let mutationObserver: MutationObserver | null = null
  let frame = 0
  let lastUserInputAt = 0

  function followTop(el: HTMLElement): number {
    const bottom = el.scrollHeight - el.clientHeight
    const limit = options.maxFollowTop?.() ?? null
    return limit === null ? bottom : Math.min(bottom, limit)
  }

  function follow(el: HTMLElement) {
    if (!isFollowing.value || options.canFollow?.() === false) return
    const target = followTop(el)
    // Only ever move down: following must not yank the reader back up.
    if (target > el.scrollTop) el.scrollTop = target
  }

  function measure() {
    frame = 0
    const el = container.value
    if (!el) {
      hasContentBelow.value = false
      return
    }
    follow(el)
    hasContentBelow.value = el.scrollHeight - el.scrollTop - el.clientHeight > AT_BOTTOM_THRESHOLD_PX
  }

  function scheduleMeasure() {
    if (!frame) {
      frame = requestAnimationFrame(measure)
    }
  }

  function markUserInput() {
    lastUserInputAt = Date.now()
  }

  function handleScroll() {
    const el = container.value
    if (el && Date.now() - lastUserInputAt < USER_SCROLL_WINDOW_MS) {
      isFollowing.value = el.scrollTop >= followTop(el) - AT_BOTTOM_THRESHOLD_PX
    }
    scheduleMeasure()
  }

  function resumeFollowing() {
    isFollowing.value = true
    scheduleMeasure()
  }

  function scrollToLatest() {
    const el = container.value
    isFollowing.value = true
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }

  const userInputEvents = ['wheel', 'touchstart', 'pointerdown', 'keydown'] as const

  onMounted(() => {
    const el = container.value
    if (!el) {
      return
    }
    el.addEventListener('scroll', handleScroll, { passive: true })
    userInputEvents.forEach((name) => el.addEventListener(name, markUserInput, { passive: true }))
    resizeObserver = new ResizeObserver(scheduleMeasure)
    resizeObserver.observe(el)
    mutationObserver = new MutationObserver(scheduleMeasure)
    mutationObserver.observe(el, { childList: true, subtree: true, characterData: true })
    scheduleMeasure()
  })

  onBeforeUnmount(() => {
    const el = container.value
    el?.removeEventListener('scroll', handleScroll)
    userInputEvents.forEach((name) => el?.removeEventListener(name, markUserInput))
    resizeObserver?.disconnect()
    mutationObserver?.disconnect()
    if (frame) {
      cancelAnimationFrame(frame)
    }
  })

  return { hasContentBelow, isFollowing, scrollToLatest, resumeFollowing }
}
