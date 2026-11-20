import { computed } from 'vue'
import { dismissToast, showToast, toastState } from '@/composables/useToast'

export interface Notification {
  id: number
  message: string
  type: 'error' | 'success' | 'info'
}

/**
 * Notification service kept for existing callers (editor, portal, entity transfer).
 * Messages go to the app-wide toasts (`useToast`, rendered by UiToastHost in App.vue), so they
 * show on every page, not only where a page renders its own toast component.
 */
class NotificationService {
  get all() {
    return computed<Notification[]>(() =>
      toastState.items.map((item) => ({
        id: item.id,
        message: item.message,
        type: item.tone === 'error' ? 'error' : item.tone === 'success' ? 'success' : 'info',
      })),
    )
  }

  add(message: string, type: 'error' | 'success' | 'info' = 'info'): number {
    return showToast(message, { tone: type })
  }

  remove(id: number): void {
    dismissToast(id)
  }

  clear(): void {
    toastState.items.splice(0)
  }

  success(message: string): number {
    return this.add(message, 'success')
  }

  error(message: string): number {
    return this.add(message, 'error')
  }

  info(message: string): number {
    return this.add(message, 'info')
  }
}

export const notificationService = new NotificationService()
