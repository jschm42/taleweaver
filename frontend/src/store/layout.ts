import { ref } from 'vue'

export const isMobileSidebarOpen = ref(false)

export function openMobileSidebar() {
  isMobileSidebarOpen.value = true
}

export function closeMobileSidebar() {
  isMobileSidebarOpen.value = false
}

const GAME_HEADER_PINNED_KEY = 'tw_game_header_pinned'

function readHeaderPinned(): boolean {
  try {
    return localStorage.getItem(GAME_HEADER_PINNED_KEY) === 'true'
  } catch {
    return false
  }
}

/** In-game header: hidden and shown on hover by default; pinned keeps it (and the app header) visible. */
export const isGameHeaderPinned = ref(readHeaderPinned())

export function toggleGameHeaderPin() {
  isGameHeaderPinned.value = !isGameHeaderPinned.value
  try {
    localStorage.setItem(GAME_HEADER_PINNED_KEY, String(isGameHeaderPinned.value))
  } catch {
    /* storage unavailable (private mode) */
  }
}
