import { ref } from 'vue'

export const isMobileSidebarOpen = ref(false)

export function openMobileSidebar() {
  isMobileSidebarOpen.value = true
}

export function closeMobileSidebar() {
  isMobileSidebarOpen.value = false
}
