import { getCurrentInstance, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/** Distance (px) from the bottom below which the feed counts as "at the latest message". */
const AT_BOTTOM_THRESHOLD_PX = 32

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
 * Auto-follow stops as soon as the user scrolls up (mouse wheel, touch, keys, or scrollbar)
 * and resumes once they scroll all the way back down to the latest message, or when
 * `resumeFollowing()` / `scrollToLatest()` is called.
 */
export function useScrollToLatest(container: Ref<HTMLElement | null>, options: ScrollToLatestOptions = {}) {
  const hasContentBelow = ref(false)
  const isFollowing = ref(true)
  let resizeObserver: ResizeObserver | null = null
  let mutationObserver: MutationObserver | null = null
  let frame = 0
  let lastScrollTop = 0
  let isProgrammaticScroll = false
  let touchStartY = 0

  function followTop(el: HTMLElement): number {
    const bottom = el.scrollHeight - el.clientHeight
    const limit = options.maxFollowTop?.() ?? null
    return limit === null ? bottom : Math.min(bottom, limit)
  }

  function follow(el: HTMLElement) {
    if (!isFollowing.value || options.canFollow?.() === false) return
    const target = followTop(el)
    // Only ever move down: following must not yank the reader back up.
    if (target > el.scrollTop) {
      isProgrammaticScroll = true
      lastScrollTop = target
      el.scrollTop = target
    }
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

  function handleWheel(e: WheelEvent) {
    if (e.deltaY < 0) {
      // User is scrolling UP: stop auto-following immediately so follow() does not snap back down.
      isFollowing.value = false
    }
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'ArrowUp' || e.key === 'PageUp' || e.key === 'Home') {
      isFollowing.value = false
    }
  }

  function handleTouchStart(e: TouchEvent) {
    if (e.touches.length > 0) {
      touchStartY = e.touches[0].clientY
    }
  }

  function handleTouchMove(e: TouchEvent) {
    if (e.touches.length > 0) {
      const deltaY = e.touches[0].clientY - touchStartY
      // Pulling downwards moves content down, which scrolls up to older content.
      if (deltaY > 8) {
        isFollowing.value = false
      }
    }
  }

  function handleScroll() {
    const el = container.value
    if (!el) return

    const currentTop = el.scrollTop
    const delta = currentTop - lastScrollTop
    lastScrollTop = currentTop

    if (isProgrammaticScroll) {
      isProgrammaticScroll = false
      scheduleMeasure()
      return
    }

    if (delta < 0) {
      // Any upward scroll (scrollbar drag, trackpad, keys) stops auto-follow.
      isFollowing.value = false
    } else if (el.scrollHeight - currentTop - el.clientHeight <= AT_BOTTOM_THRESHOLD_PX) {
      // User scrolled all the way back down to the bottom: resume auto-follow.
      isFollowing.value = true
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
      isProgrammaticScroll = true
      lastScrollTop = el.scrollHeight
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }

  function scrollToTop() {
    const el = container.value
    if (!el) return
    isProgrammaticScroll = true
    lastScrollTop = 0
    el.scrollTop = 0
    scheduleMeasure()
  }

  function attach(el: HTMLElement) {
    lastScrollTop = el.scrollTop
    el.addEventListener('scroll', handleScroll, { passive: true })
    el.addEventListener('wheel', handleWheel, { passive: true })
    el.addEventListener('keydown', handleKeyDown, { passive: true })
    el.addEventListener('touchstart', handleTouchStart, { passive: true })
    el.addEventListener('touchmove', handleTouchMove, { passive: true })
    resizeObserver = new ResizeObserver(scheduleMeasure)
    resizeObserver.observe(el)
    mutationObserver = new MutationObserver(scheduleMeasure)
    mutationObserver.observe(el, { childList: true, subtree: true, characterData: true })
    scheduleMeasure()
  }

  function detach(el: HTMLElement) {
    el.removeEventListener('scroll', handleScroll)
    el.removeEventListener('wheel', handleWheel)
    el.removeEventListener('keydown', handleKeyDown)
    el.removeEventListener('touchstart', handleTouchStart)
    el.removeEventListener('touchmove', handleTouchMove)
    resizeObserver?.disconnect()
    mutationObserver?.disconnect()
    if (frame) {
      cancelAnimationFrame(frame)
    }
  }

  if (container.value) {
    attach(container.value)
  }

  if (getCurrentInstance()) {
    onMounted(() => {
      if (container.value && !resizeObserver) {
        attach(container.value)
      }
    })

    onBeforeUnmount(() => {
      if (container.value) {
        detach(container.value)
      }
    })
  }

  return { hasContentBelow, isFollowing, scrollToLatest, scrollToTop, resumeFollowing }
}
