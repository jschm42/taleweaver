import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'
import { audioService } from '@/services/audioService'
import { SPEAKABLE_SELECTOR, SPEAKING_SELECTOR, speechRevealTarget } from './speechRevealTarget'

export interface FollowSpeechOptions {
  /** False while the reader browses an earlier scene: speech is not followed then. */
  canFollow: () => boolean
  /** Scrolls the feed to a position as the app (see useScrollToLatest.scrollToPosition). */
  scrollToPosition: (top: number) => void
  /** False once the reader scrolled up themselves. */
  isFollowing: () => boolean
}

/** Pause after speech stopped before the feed counts it as finished (the queue may go on). */
const SPEECH_END_GRACE_MS = 600

/**
 * Keeps the bubble that text-to-speech is reading in view (see speechRevealTarget); while the
 * last bubble of the feed is read, the feed scrolls all the way to the bottom. Once all speech
 * has finished, the feed ends at the bottom as well (unless the reader scrolled up).
 */
export function useFollowSpeech(container: Ref<HTMLElement | null>, options: FollowSpeechOptions): void {
  function revealSpeakingBubble(): void {
    const el = container.value
    if (!el || !audioService.isPlaying.value || !options.canFollow()) return
    const speaking = el.querySelector<HTMLElement>(SPEAKING_SELECTOR)
    if (!speaking) return
    const bubbles = el.querySelectorAll<HTMLElement>(SPEAKABLE_SELECTOR)
    const reservedBottom = parseFloat(window.getComputedStyle(el).paddingBottom) || 0
    const containerRect = el.getBoundingClientRect()
    const rect = speaking.getBoundingClientRect()
    const bubbleTop = rect.top - containerRect.top + el.scrollTop
    const target = speechRevealTarget({
      scrollTop: el.scrollTop,
      viewHeight: el.clientHeight - reservedBottom,
      scrollHeight: el.scrollHeight,
      bubbleTop,
      bubbleBottom: bubbleTop + rect.height,
      isLast: bubbles[bubbles.length - 1] === speaking,
    })
    if (target !== null) options.scrollToPosition(target)
  }

  let endTimer: ReturnType<typeof setTimeout> | null = null

  function scrollToEndAfterSpeech(): void {
    endTimer = null
    const el = container.value
    if (!el || audioService.isPlaying.value || audioService.isGenerating.value) return
    if (!options.canFollow() || !options.isFollowing()) return
    options.scrollToPosition(el.scrollHeight)
  }

  // A new spoken part (or speech starting): wait for the bubble's `is-speaking` class.
  watch(
    () => [audioService.currentText.value, audioService.isPlaying.value] as const,
    async ([, playing]) => {
      if (endTimer) clearTimeout(endTimer)
      endTimer = null
      if (!playing) {
        endTimer = setTimeout(scrollToEndAfterSpeech, SPEECH_END_GRACE_MS)
        return
      }
      await nextTick()
      requestAnimationFrame(revealSpeakingBubble)
    },
  )
  onBeforeUnmount(() => {
    if (endTimer) clearTimeout(endTimer)
  })
}
