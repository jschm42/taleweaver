import { computed, onBeforeUnmount, watch } from 'vue'
import type { WorldSection } from '@/services/sectionService'

const POLL_MS = 5000

/** Polls the editor data while any region has status `generating`. */
export function useRegionBuildPoll(
  getSections: () => WorldSection[],
  refresh: () => Promise<unknown> | void,
): void {
  const generating = computed(() => getSections().some((s) => s.status === 'generating'))
  let pollTimer: ReturnType<typeof setInterval> | null = null

  watch(
    generating,
    (busy) => {
      if (busy && !pollTimer) {
        pollTimer = setInterval(() => void refresh(), POLL_MS)
        return
      }
      if (!busy && pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    if (pollTimer) clearInterval(pollTimer)
  })
}
