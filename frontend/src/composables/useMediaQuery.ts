import { onScopeDispose, ref, type Ref } from 'vue'

/** Reactive `window.matchMedia(query).matches`, updated when the viewport changes. */
export function useMediaQuery(query: string): Ref<boolean> {
  const matches = ref(false)
  if (typeof window === 'undefined' || !window.matchMedia) return matches

  const mediaQuery = window.matchMedia(query)
  matches.value = mediaQuery.matches
  const update = (event: MediaQueryListEvent) => {
    matches.value = event.matches
  }
  mediaQuery.addEventListener('change', update)
  onScopeDispose(() => mediaQuery.removeEventListener('change', update))
  return matches
}
