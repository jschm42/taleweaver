import { nextTick, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

/** Distance (px) from the top at which older messages start loading. */
const LOAD_THRESHOLD_PX = 300

export interface LoadOlderOptions {
  /** Whether the server has older messages than the loaded ones. */
  hasMore: () => boolean
  /** Loads the next older page and prepends it to the feed. */
  load: () => Promise<void>
  /** False while auto-follow owns the scroll position (e.g. right after the session opened). */
  readerScrolled: () => boolean
}

/**
 * Loads older story messages when the reader nears the top of the feed.
 *
 * The prepended content would push everything down, so the scroll position is shifted by the
 * added height: the message the reader was looking at stays where it was. While the loaded
 * content does not even fill the feed (no scrollbar yet), pages keep loading until it does.
 */
export function useLoadOlderOnScroll(container: Ref<HTMLElement | null>, options: LoadOlderOptions) {
  const isLoadingOlder = ref(false)

  function wantsMore(el: HTMLElement): boolean {
    if (!options.hasMore() || isLoadingOlder.value) return false
    if (el.scrollHeight <= el.clientHeight) return true
    return options.readerScrolled() && el.scrollTop < LOAD_THRESHOLD_PX
  }

  async function loadOlder(): Promise<void> {
    const el = container.value
    if (!el || !wantsMore(el)) return
    isLoadingOlder.value = true
    const heightBefore = el.scrollHeight
    const topBefore = el.scrollTop
    try {
      await options.load()
      await nextTick()
      el.scrollTop = topBefore + (el.scrollHeight - heightBefore)
    } finally {
      isLoadingOlder.value = false
    }
    // Still near the top (short page) or the feed is not filled yet: keep going.
    requestAnimationFrame(() => void loadOlder())
  }

  const handleScroll = () => void loadOlder()

  onMounted(() => {
    container.value?.addEventListener('scroll', handleScroll, { passive: true })
  })

  onBeforeUnmount(() => {
    container.value?.removeEventListener('scroll', handleScroll)
  })

  return { isLoadingOlder, loadOlder }
}
