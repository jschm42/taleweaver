/**
 * Keeps keyboard focus inside an open dialog panel and gives it back to the element that
 * opened the dialog. Used by UiModal and UiDrawer.
 */
import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function focusables(panel: HTMLElement): HTMLElement[] {
  return [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null)
}

export interface FocusTrapOptions {
  onEscape: () => void
}

export function useFocusTrap(
  panel: Ref<HTMLElement | null>,
  active: Readonly<Ref<boolean>>,
  options: FocusTrapOptions,
): void {
  let previous: HTMLElement | null = null

  const handleKeydown = (event: KeyboardEvent): void => {
    if (event.key === 'Escape') {
      event.stopPropagation()
      options.onEscape()
      return
    }
    if (event.key !== 'Tab' || !panel.value) {
      return
    }
    const items = focusables(panel.value)
    if (items.length === 0) {
      event.preventDefault()
      return
    }
    const first = items[0]
    const last = items[items.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
      return
    }
    if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  async function activate(): Promise<void> {
    previous = document.activeElement as HTMLElement | null
    document.addEventListener('keydown', handleKeydown, true)
    await nextTick()
    if (!panel.value) {
      return
    }
    const preferred = panel.value.querySelector<HTMLElement>('[data-autofocus]')
    const target = preferred ?? focusables(panel.value)[0] ?? panel.value
    target.focus()
  }

  function deactivate(): void {
    document.removeEventListener('keydown', handleKeydown, true)
    previous?.focus?.()
    previous = null
  }

  watch(
    active,
    (isActive) => {
      if (isActive) {
        void activate()
        return
      }
      deactivate()
    },
    { immediate: true },
  )

  onBeforeUnmount(deactivate)
}
