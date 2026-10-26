import { onBeforeUnmount, onMounted } from 'vue'

interface GameShortcutHandlers {
  /** SPACE: jump to the latest message in the story feed. */
  scrollToLatestMessage: () => void
  /** ENTER: put the caret into the command input. */
  focusInput: () => void
}

const INTERACTIVE_SELECTOR = 'input, textarea, select, button, a[href], [contenteditable="true"], [role="button"]'

function shouldIgnore(e: KeyboardEvent): boolean {
  if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return true
  const target = e.target as HTMLElement | null
  // Typing or activating a focused control keeps its native Space/Enter behaviour.
  if (target?.closest(INTERACTIVE_SELECTOR)) return true
  return document.querySelector('[aria-modal="true"]') !== null
}

/**
 * Global keyboard shortcuts of the immersive game view.
 */
export function useGameShortcuts(handlers: GameShortcutHandlers) {
  function handleKeydown(e: KeyboardEvent) {
    if (e.key !== ' ' && e.key !== 'Enter') return
    if (shouldIgnore(e)) return

    e.preventDefault()
    if (e.repeat) return
    if (e.key === ' ') {
      handlers.scrollToLatestMessage()
      return
    }
    handlers.focusInput()
  }

  onMounted(() => window.addEventListener('keydown', handleKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
}
