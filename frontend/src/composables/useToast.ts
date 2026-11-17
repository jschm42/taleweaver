/**
 * App-wide toast notifications. `UiToastHost` (mounted once in App.vue) renders the list.
 * Module-level state, so services can notify as well as components.
 */
import { reactive } from 'vue'

export type ToastTone = 'success' | 'info' | 'warn' | 'error' | 'ai'

export interface Toast {
  id: number
  tone: ToastTone
  message: string
  title?: string
}

export interface ToastOptions {
  tone?: ToastTone
  title?: string
  /** Milliseconds until the toast closes itself; 0 keeps it until dismissed. */
  timeout?: number
}

const DEFAULT_TIMEOUT_MS = 4500
const ERROR_TIMEOUT_MS = 8000
const MAX_TOASTS = 5

export const toastState = reactive<{ items: Toast[] }>({ items: [] })

let nextId = 1

export function dismissToast(id: number): void {
  const index = toastState.items.findIndex((item) => item.id === id)
  if (index >= 0) {
    toastState.items.splice(index, 1)
  }
}

/** Shows a toast and returns its id. */
export function showToast(message: string, options: ToastOptions = {}): number {
  const tone = options.tone ?? 'info'
  const id = nextId++
  toastState.items.push({ id, tone, message, title: options.title })
  if (toastState.items.length > MAX_TOASTS) {
    toastState.items.shift()
  }
  const timeout = options.timeout ?? (tone === 'error' ? ERROR_TIMEOUT_MS : DEFAULT_TIMEOUT_MS)
  if (timeout > 0) {
    setTimeout(() => dismissToast(id), timeout)
  }
  return id
}

export interface ToastApi {
  show: typeof showToast
  success: (message: string, title?: string) => number
  info: (message: string, title?: string) => number
  warn: (message: string, title?: string) => number
  error: (message: string, title?: string) => number
  dismiss: typeof dismissToast
}

export function useToast(): ToastApi {
  return {
    show: showToast,
    success: (message, title) => showToast(message, { tone: 'success', title }),
    info: (message, title) => showToast(message, { tone: 'info', title }),
    warn: (message, title) => showToast(message, { tone: 'warn', title }),
    error: (message, title) => showToast(message, { tone: 'error', title }),
    dismiss: dismissToast,
  }
}
