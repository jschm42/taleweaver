import { ref, computed } from 'vue'

export interface Notification {
  id: number
  message: string
  type: 'error' | 'success' | 'info'
}

/**
 * Notification service for managing toast notifications
 */
class NotificationService {
  private notifications = ref<Notification[]>([])
  private nextId = 0
  private readonly DURATION_MS = 5000

  get all() {
    return computed(() => this.notifications.value)
  }

  add(message: string, type: 'error' | 'success' | 'info' = 'info'): number {
    const id = this.nextId++
    this.notifications.value.push({ id, message, type })

    setTimeout(() => {
      this.remove(id)
    }, this.DURATION_MS)

    return id
  }

  remove(id: number): void {
    this.notifications.value = this.notifications.value.filter(n => n.id !== id)
  }

  clear(): void {
    this.notifications.value = []
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
