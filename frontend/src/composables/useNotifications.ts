import { ref } from 'vue'

export type NotificationType = 'error' | 'success' | 'info'

export interface Notification {
  id: number
  message: string
  type: NotificationType
}

const notifications = ref<Notification[]>([])
let nextId = 0

export function useNotifications() {
  function addNotification(message: string, type: NotificationType = 'info') {
    const id = nextId++
    notifications.value.push({ id, message, type })
    // Auto-remove after 8 seconds (longer for complex error messages)
    setTimeout(() => {
      removeNotification(id)
    }, 8000)
  }

  function removeNotification(id: number) {
    notifications.value = notifications.value.filter(n => n.id !== id)
  }

  return {
    notifications,
    addNotification,
    removeNotification
  }
}
